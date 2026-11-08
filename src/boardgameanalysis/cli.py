"""Command line interface: ``boardgameanalysis fetch`` and ``boardgameanalysis analyze``."""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Sequence
from pathlib import Path

log = logging.getLogger("boardgameanalysis")


def _fetch(args: argparse.Namespace) -> int:
    from boardgameanalysis.api import BGGClient
    from boardgameanalysis.dataset import fetch_games, games_to_frame, read_rank_dump, save_games

    ranks = read_rank_dump(args.ranks, top=args.top)
    log.info("Fetching %d games from the BGG XML API", len(ranks))

    def progress(done: int, total: int) -> None:
        print(f"\r  {done}/{total} games", end="", file=sys.stderr, flush=True)

    with BGGClient(args.token, delay_s=args.delay) as client:
        games = fetch_games(ranks["id"], client, cache=args.cache, progress=progress)
    print(file=sys.stderr)
    save_games(games_to_frame(games), args.out)
    log.info("Wrote %d games to %s", len(games), args.out)
    return 0


def _analyze(args: argparse.Namespace) -> int:
    from boardgameanalysis import plots
    from boardgameanalysis.clustering import cluster_games, summarize
    from boardgameanalysis.dataset import load_games
    from boardgameanalysis.features import build_features
    from boardgameanalysis.model import cross_validate, with_predictions

    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True)

    games = load_games(args.games)
    features = build_features(
        games, max_rank=args.max_rank, min_votes=args.min_votes, base_year=args.base_year
    )
    log.info("%d games, %d features", len(features.X), features.X.shape[1])

    result = cross_validate(features)
    log.info("Cross-validated RMSE: %.4f", result.rmse)
    rated = with_predictions(features, result)

    top = rated[rated["rank"] <= 500][["names", "rank", "magic_sauce", "avg_rating"]]
    top.head(50).round(2).to_csv(out / "magic.csv", index=False)
    rated[["names", "rank", "avg_rating", "predicted_rating", "magic_sauce"]].round(4).to_csv(
        out / "predictions.csv"
    )

    paths = [
        *plots.residuals(rated, out),
        plots.predicted_vs_actual(rated, out, args.base_year),
        plots.rank_vs_average(rated, out, args.base_year),
        plots.rank_vs_magic(rated, out, args.base_year, 200, 20),
        plots.rank_vs_magic(rated, out, args.base_year, 500, 50),
        plots.rank_vs_magic(rated, out, args.base_year, args.max_rank, 100),
        plots.shap_summary(result, out),
    ]

    if not args.skip_clusters:
        clusters = cluster_games(features, n_clusters=args.clusters)
        (out / "clusters.txt").write_text(summarize(clusters), encoding="utf-8")
        clusters.games.to_csv(out / "clusters.csv")
        paths.append(plots.clusters_html(clusters, out))

    print(f"RMSE: {result.rmse:.4f}")
    print("Top 10 by magic sauce (top 500 ranked):")
    print(top.head(10).round(2).to_string(index=False))
    for p in paths:
        log.info("wrote %s", p)
    return 0


def build_parser() -> argparse.ArgumentParser:
    from boardgameanalysis import __version__

    parser = argparse.ArgumentParser(prog="boardgameanalysis", description=__doc__)
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    f = sub.add_parser("fetch", help="Download live game data from BGG")
    f.add_argument(
        "--ranks",
        type=Path,
        required=True,
        help="BGG rank dump (boardgames_ranks.csv or .zip), "
        "from boardgamegeek.com/data_dumps/bg_ranks",
    )
    f.add_argument(
        "--top", type=int, default=5000, help="Number of top-ranked games (default 5000)"
    )
    f.add_argument("--out", type=Path, default=Path("data/games.csv"))
    f.add_argument("--cache", type=Path, default=Path("data/cache/games.jsonl"))
    f.add_argument("--token", help="BGG API token (default: $BGG_TOKEN)")
    f.add_argument("--delay", type=float, default=5.0, help="Seconds between requests (default 5)")
    f.set_defaults(func=_fetch)

    a = sub.add_parser("analyze", help="Model ratings and render figures")
    a.add_argument("games", type=Path, nargs="?", default=Path("data/bgg_kaggle_2509.csv"))
    a.add_argument("--out", type=Path, default=Path("output"))
    a.add_argument("--max-rank", type=int, default=5000)
    a.add_argument("--min-votes", type=int, default=500)
    a.add_argument("--base-year", type=int, default=2000)
    a.add_argument("--clusters", type=int, default=11)
    a.add_argument("--skip-clusters", action="store_true")
    a.set_defaults(func=_analyze)

    e = sub.add_parser("export", help="Export analysis JSON for the website")
    e.add_argument("games", type=Path, nargs="?", default=Path("data/bgg_kaggle_2509.csv"))
    e.add_argument(
        "--compare",
        type=Path,
        default=Path("data/bgg_db_1806.csv"),
        help="Older snapshot to compare against (use '' to skip)",
    )
    e.add_argument("--compare-snapshot", default="2018-06")
    e.add_argument("--out", type=Path, default=Path("site/src/lib/data/analysis.json"))
    e.add_argument("--snapshot", default="2025-09", help="Label for when the data was captured")
    e.add_argument("--max-rank", type=int, default=5000)
    e.add_argument("--min-votes", type=int, default=500)
    e.add_argument("--base-year", type=int, default=2000)
    e.add_argument("--clusters", type=int, default=11)
    e.add_argument("--umap-top", type=int, default=1000, help="games in the 3D UMAP (0 = skip)")
    e.add_argument("--perplexity", type=float, default=30.0, help="t-SNE perplexity for the map")
    e.set_defaults(func=_export)

    k = sub.add_parser("import-kaggle", help="Convert the Kaggle BGG dataset to our CSV schema")
    k.add_argument("source", type=Path, help="boardgame-geek-dataset_organized.csv")
    k.add_argument("--out", type=Path, default=Path("data/bgg_kaggle_2509.csv"))
    k.set_defaults(func=_import_kaggle)
    return parser


def _import_kaggle(args: argparse.Namespace) -> int:
    from boardgameanalysis.dataset import load_kaggle, save_games

    df = load_kaggle(args.source)
    save_games(df, args.out)
    log.info("Wrote %d games to %s", len(df), args.out)
    return 0


def _export(args: argparse.Namespace) -> int:
    from boardgameanalysis.clustering import cluster_games
    from boardgameanalysis.dataset import load_games
    from boardgameanalysis.embedding import umap_3d
    from boardgameanalysis.export import build_export, write_export
    from boardgameanalysis.features import build_features
    from boardgameanalysis.model import cross_validate, with_predictions

    features = build_features(
        load_games(args.games),
        max_rank=args.max_rank,
        min_votes=args.min_votes,
        base_year=args.base_year,
    )
    result = cross_validate(features)
    rated = with_predictions(features, result)
    clusters = cluster_games(features, n_clusters=args.clusters, perplexity=args.perplexity)
    doc = build_export(
        features,
        result,
        rated,
        clusters,
        source=args.games.name,
        snapshot=args.snapshot,
        base_year=args.base_year,
        compare=load_games(args.compare) if str(args.compare) not in ("", ".") else None,
        compare_snapshot=args.compare_snapshot,
        embedding=umap_3d(features, top=args.umap_top) if args.umap_top > 0 else None,
    )
    path = write_export(doc, args.out)
    log.info("Wrote %s (%.0f KB, RMSE %.4f)", path, path.stat().st_size / 1024, result.rmse)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    code: int = args.func(args)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
