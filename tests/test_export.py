from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from boardgameanalysis.clustering import cluster_games
from boardgameanalysis.dataset import RATING_BUCKETS, load_games
from boardgameanalysis.export import build_export, write_export
from boardgameanalysis.features import build_features
from boardgameanalysis.model import cross_validate, with_predictions

DATA = Path(__file__).parents[1] / "data"


@pytest.fixture(scope="module")
def doc() -> dict:  # type: ignore[type-arg]
    games = load_games(DATA / "bgg_kaggle_2509.csv")
    features = build_features(games)
    result = cross_validate(features)
    rated = with_predictions(features, result)
    clusters = cluster_games(features, n_clusters=6, perplexity=30)
    return build_export(
        features,
        result,
        rated,
        clusters,
        source="test",
        snapshot="2025-09",
        base_year=2000,
        compare=load_games(DATA / "bgg_db_1806.csv"),
        compare_snapshot="2018-06",
    )


def test_kaggle_snapshot_loads() -> None:
    games = load_games(DATA / "bgg_kaggle_2509.csv")
    assert len(games) > 1900
    assert games["rank"].min() == 1
    assert set(RATING_BUCKETS) <= set(games.columns)
    # Mechanic names containing commas survive the round trip.
    assert games["mechanic"].map(lambda ms: any("," in m for m in ms)).any()


def test_export_is_consistent(doc: dict, tmp_path: Path) -> None:  # type: ignore[type-arg]
    meta = doc["meta"]
    assert meta["games"] == len(doc["games"])
    assert 0 < meta["r2"] < 1
    assert len(doc["traits"]) == len(doc["traitKeys"])
    assert len(doc["clusters"]) == 6

    for g in doc["games"][:50]:
        why = g["why"]
        total = why["base"] + sum(v for _, v in why["parts"]) + why["other"]
        assert total == pytest.approx(g["pred"], abs=0.01)
        assert g["magic"] == pytest.approx(g["rating"] - g["pred"], abs=0.002)
        assert len(g["dist"]) == 10
        assert all(0 <= t < len(doc["traitKeys"]) for t in g["traits"])

    for c in doc["clusters"]:
        keys = [t["key"] for t in c["traits"]]
        assert len(keys) == len(set(keys)), c["name"]

    cmp = doc["compare"]
    assert cmp["retained"] <= cmp["top"]
    assert all(0 <= s["then"] <= 1 and 0 <= s["now"] <= 1 for s in cmp["shifts"])
    assert sum(b["n"] for b in doc["ratingHistogram"]) == meta["games"]

    path = write_export(doc, tmp_path / "a.json")
    assert json.loads(path.read_text(encoding="utf-8"))["meta"]["games"] == meta["games"]
    assert not np.isnan([g["rating"] for g in doc["games"]]).any()
