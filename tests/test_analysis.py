from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from boardgameanalysis.clustering import cluster_games
from boardgameanalysis.dataset import load_games
from boardgameanalysis.features import build_features, one_hot_lists
from boardgameanalysis.model import cross_validate, with_predictions

LEGACY = Path(__file__).parents[1] / "data" / "bgg_db_1806.csv"


@pytest.fixture(scope="module")
def games() -> pd.DataFrame:
    return load_games(LEGACY)


def test_one_hot_lists_threshold() -> None:
    col = pd.Series([["a", "b"], ["a"], [], ["none"]], index=pd.Index([1, 2, 3, 4], name="game_id"))
    out = one_hot_lists(col, "x:", min_count=2)
    assert list(out.columns) == ["x:a"]
    assert out["x:a"].tolist() == [1, 1, 0, 0]


def test_build_features(games: pd.DataFrame) -> None:
    f = build_features(games)
    assert (f.data["num_votes"] > 500).all()
    assert f.data["rank"].max() <= 5000
    assert f.X.index.equals(f.data.index)
    assert {"years_since_base", "avg_time"} <= set(f.X.columns)
    # Memory is both a category and a mechanic; prefixes keep them apart.
    assert {"cat:Memory", "mech:Memory"} <= set(f.X.columns)
    assert f.data["avg_time"].max() <= 300
    assert f.data["years_since_base"].min() == 0


def test_model_beats_baseline(games: pd.DataFrame) -> None:
    f = build_features(games)
    result = cross_validate(f)
    baseline = float(np.std(f.y))
    assert result.predictions.notna().all()
    assert len(result.fold_rmse) == 5
    assert result.rmse < baseline
    assert result.shap_values.shape == result.shap_X.shape

    # SHAP contributions decompose each out-of-fold prediction exactly.
    recon = result.contributions.sum(axis=1)
    assert np.allclose(recon, result.predictions, atol=1e-3)

    rated = with_predictions(f, result)
    assert rated["magic_sauce"].is_monotonic_decreasing


def test_clustering(games: pd.DataFrame) -> None:
    f = build_features(games)
    clusters = cluster_games(f, n_clusters=5)
    assert len(clusters.names) == 5
    assert clusters.games["rank"].max() <= 500
    assert set(clusters.games["cluster"]) == set(range(5))


def test_umap_3d(games: pd.DataFrame) -> None:
    from boardgameanalysis.embedding import umap_3d

    f = build_features(games)
    emb = umap_3d(f, top=300)
    assert list(emb.columns) == ["umap_x", "umap_y", "umap_z"]
    assert emb.index.equals(f.data.sort_values("rank").index[:300])
    radius = np.linalg.norm(emb.to_numpy(), axis=1)
    assert radius.max() == pytest.approx(1.0)
    assert np.allclose(emb.mean().to_numpy(), 0, atol=1e-9)
