from __future__ import annotations

import zipfile
from pathlib import Path

import httpx
import pandas as pd

from boardgameanalysis.api import BGGClient
from boardgameanalysis.dataset import (
    fetch_games,
    games_to_frame,
    load_games,
    read_rank_dump,
    save_games,
)

FIXTURES = Path(__file__).parent / "fixtures"
LEGACY = Path(__file__).parents[1] / "data" / "bgg_db_1806.csv"
THING = (FIXTURES / "thing.xml").read_text(encoding="utf-8")

RANKS_CSV = """id,name,yearpublished,rank,bayesaverage,average,usersrated,is_expansion
3,C,2020,2,8,8,100,0
1,A,2020,1,8,8,100,0
2,Exp,2020,0,0,0,10,1
4,Unranked,2020,0,0,0,5,0
"""


def test_read_rank_dump_csv_and_zip(tmp_path: Path) -> None:
    csv = tmp_path / "boardgames_ranks.csv"
    csv.write_text(RANKS_CSV)
    assert read_rank_dump(csv)["id"].tolist() == [1, 3]
    assert read_rank_dump(csv, top=1)["id"].tolist() == [1]

    zipped = tmp_path / "ranks.zip"
    with zipfile.ZipFile(zipped, "w") as zf:
        zf.write(csv, "boardgames_ranks.csv")
    assert read_rank_dump(zipped)["id"].tolist() == [1, 3]


def test_fetch_resumes_from_cache(tmp_path: Path) -> None:
    calls = 0

    def handle(_r: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, text=THING)

    cache = tmp_path / "cache.jsonl"
    client = BGGClient("t", delay_s=0, transport=httpx.MockTransport(handle))
    first = fetch_games([174430, 999], client, cache)
    second = fetch_games([999, 174430], client, cache)
    assert calls == 1
    assert [g.game_id for g in first] == [174430, 999]
    assert [g.game_id for g in second] == [999, 174430]
    assert second[1].mechanics == ("Cooperative Game", "I Cut, You Choose")


def test_save_load_roundtrip_keeps_commas_in_names(tmp_path: Path) -> None:
    from boardgameanalysis.api import parse_things

    df = games_to_frame(parse_things(THING))
    path = tmp_path / "games.csv"
    save_games(df, path)
    loaded = load_games(path)
    assert loaded.loc[174430, "mechanic"] == ["Cooperative Game", "I Cut, You Choose"]
    assert loaded.loc[999, "mechanic"] == []
    assert loaded.loc[174430, "names"] == "Gloomhaven"


def test_load_legacy_snapshot() -> None:
    df = load_games(LEGACY)
    assert len(df) == 4999
    row = df.loc[174430]
    assert row["names"] == "Gloomhaven"
    assert "Co-operative Play" in row["mechanic"]
    assert isinstance(df["category"].iloc[0], list)
    assert pd.api.types.is_numeric_dtype(df["avg_rating"])
