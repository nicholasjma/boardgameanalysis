"""Building and loading the games table.

Two sources produce the same normalized frame (indexed by ``game_id``):

* live data: IDs from BGG's daily rank dump + details from the XML API (:func:`fetch_games`)
* the 2018 snapshot in ``data/bgg_db_1806.csv`` (:func:`load_games`)

List-valued columns (``mechanic``, ``category``, ``designer``) are stored on disk joined with
``|`` because BGG mechanic names can themselves contain commas (e.g. "I Cut, You Choose").
"""

from __future__ import annotations

import io
import json
import logging
import zipfile
from collections.abc import Callable, Iterable
from pathlib import Path

import pandas as pd

from boardgameanalysis.api import BGGClient, Game

log = logging.getLogger(__name__)

LIST_COLUMNS = ("mechanic", "category", "designer")
LIST_SEP = "|"
LEGACY_LIST_SEP = ", "

COLUMNS = [
    "rank",
    "bgg_url",
    "names",
    "min_players",
    "max_players",
    "avg_time",
    "min_time",
    "max_time",
    "year",
    "avg_rating",
    "geek_rating",
    "num_votes",
    "image_url",
    "age",
    "mechanic",
    "owned",
    "category",
    "designer",
    "weight",
]


def read_rank_dump(path: str | Path, top: int | None = None) -> pd.DataFrame:
    """Read BGG's ``boardgames_ranks.csv`` data dump (plain or zipped).

    Download it while logged in from https://boardgamegeek.com/data_dumps/bg_ranks.
    Returns ranked, non-expansion games sorted by rank, optionally truncated to ``top``.
    """
    path = Path(path)
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as zf:
            name = next(n for n in zf.namelist() if n.lower().endswith(".csv"))
            df = pd.read_csv(io.BytesIO(zf.read(name)))
    else:
        df = pd.read_csv(path)
    missing = {"id", "rank"} - set(df.columns)
    if missing:
        raise ValueError(f"{path} does not look like a BGG rank dump (missing {missing})")
    if "is_expansion" in df.columns:
        df = df[df["is_expansion"] == 0]
    df = df[pd.to_numeric(df["rank"], errors="coerce").fillna(0) > 0]
    df = df.sort_values("rank")
    return df.head(top) if top else df


def _read_cache(cache: Path) -> dict[int, Game]:
    games: dict[int, Game] = {}
    if not cache.exists():
        return games
    with cache.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            rec = json.loads(line)
            for key in ("mechanics", "categories", "designers"):
                rec[key] = tuple(rec[key])
            games[rec["game_id"]] = Game(**rec)
    return games


def fetch_games(
    ids: Iterable[int],
    client: BGGClient,
    cache: str | Path,
    progress: Callable[[int, int], None] | None = None,
) -> list[Game]:
    """Fetch details for ``ids``, appending to a JSONL ``cache`` so runs can resume."""
    cache = Path(cache)
    cache.parent.mkdir(parents=True, exist_ok=True)
    wanted = list(dict.fromkeys(int(i) for i in ids))
    have = _read_cache(cache)
    todo = [i for i in wanted if i not in have]
    log.info("%d games requested, %d cached, %d to fetch", len(wanted), len(have), len(todo))
    done = len(wanted) - len(todo)
    with cache.open("a", encoding="utf-8") as f:
        for batch in client.iter_games(todo):
            for game in batch:
                f.write(json.dumps(game.to_dict()) + "\n")
                have[game.game_id] = game
            f.flush()
            done += len(batch)
            if progress:
                progress(done, len(wanted))
    return [have[i] for i in wanted if i in have]


def games_to_frame(games: Iterable[Game]) -> pd.DataFrame:
    rows = [
        {
            "game_id": g.game_id,
            "rank": g.rank,
            "bgg_url": g.bgg_url,
            "names": g.name,
            "min_players": g.min_players,
            "max_players": g.max_players,
            "avg_time": g.avg_time,
            "min_time": g.min_time,
            "max_time": g.max_time,
            "year": g.year,
            "avg_rating": g.avg_rating,
            "geek_rating": g.geek_rating,
            "num_votes": g.num_votes,
            "image_url": g.image_url,
            "age": g.age,
            "mechanic": list(g.mechanics),
            "owned": g.owned,
            "category": list(g.categories),
            "designer": list(g.designers),
            "weight": g.weight,
        }
        for g in games
    ]
    return pd.DataFrame(rows, columns=["game_id", *COLUMNS]).set_index("game_id")


def save_games(df: pd.DataFrame, path: str | Path) -> None:
    out = df.copy()
    for col in LIST_COLUMNS:
        out[col] = out[col].map(LIST_SEP.join)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(path)


def _split(sep: str) -> Callable[[object], list[str]]:
    def split(value: object) -> list[str]:
        if not isinstance(value, str) or not value or value == "none":
            return []
        return [v.strip() for v in value.split(sep) if v.strip()]

    return split


def load_games(path: str | Path) -> pd.DataFrame:
    """Load a games CSV written by :func:`save_games` or the legacy 2018 snapshot."""
    df = pd.read_csv(path, index_col="game_id")
    # Legacy file joined lists with ", "; ours uses "|". Single-item rows are the same either way.
    joined = df["mechanic"].dropna().astype(str)
    sep = LIST_SEP if joined.str.contains(LIST_SEP, regex=False).any() else LEGACY_LIST_SEP
    for col in LIST_COLUMNS:
        df[col] = df[col].map(_split(sep))
    extra = [c for c in OPTIONAL_COLUMNS if c in df.columns]
    return df[COLUMNS + extra]


# Columns some sources provide beyond the core schema.
RATING_BUCKETS = [f"rating_{i}" for i in range(1, 11)]
OPTIONAL_COLUMNS = ["wishlisted", "std_dev", *RATING_BUCKETS]


def load_kaggle(path: str | Path) -> pd.DataFrame:
    """Convert the Kaggle "Board Games Dataset Complete Features" CSV to our schema.

    Source: https://www.kaggle.com/datasets/chik0di/board-games-dataset-complete-features
    (``boardgame-geek-dataset_organized.csv``; ODbL). Lists in that file are joined with "; ".
    """
    raw = pd.read_csv(path)
    ids = raw["url"].str.extract(r"/boardgame(?:expansion)?/(\d+)", expand=False)
    if ids.isna().any():
        raise ValueError(f"{int(ids.isna().sum())} rows in {path} have no BGG id in their url")
    split = _split(";")
    df = pd.DataFrame(
        {
            "game_id": ids.astype(int),
            "rank": raw["rank_overall"],
            "bgg_url": raw["url"],
            "names": raw["boardgame"],
            "min_players": raw["min_players"],
            "max_players": raw["max_players"],
            # BGG's "playing time" is the box's upper figure, matching the 2018 snapshot.
            "avg_time": raw["max_playtime"],
            "min_time": raw["min_playtime"],
            "max_time": raw["max_playtime"],
            "year": raw["release_year"],
            "avg_rating": raw["avg_rating"],
            "geek_rating": float("nan"),
            "num_votes": raw["num_ratings"],
            "image_url": None,
            "age": raw["minimum_age"],
            "mechanic": raw["mechanics"].map(split),
            "owned": raw["owned"],
            "category": raw["categories"].map(split),
            "designer": raw["designers"].map(split),
            "weight": raw["complexity"].where(raw["complexity"] > 0),
            "wishlisted": raw["wishlisted"],
            "std_dev": raw["std_deviation"],
            **{c: raw[c] for c in RATING_BUCKETS},
        }
    )
    return df.drop_duplicates("game_id").set_index("game_id")
