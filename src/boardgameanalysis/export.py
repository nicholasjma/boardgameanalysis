"""Export the analysis as one compact JSON document for the website."""

from __future__ import annotations

import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from boardgameanalysis import __version__
from boardgameanalysis.clustering import Clusters, strip_prefix
from boardgameanalysis.dataset import RATING_BUCKETS
from boardgameanalysis.features import CATEGORY_PREFIX, Features
from boardgameanalysis.model import ModelResult

PRETTY = {"years_since_base": "Year published", "avg_time": "Play time"}


def _r(x: Any, nd: int = 3) -> float | None:
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else round(float(x), nd)


def _feature_label(col: str) -> str:
    return PRETTY.get(col, strip_prefix(col))


def _feature_kind(col: str) -> str:
    if col in PRETTY:
        return "numeric"
    return "category" if col.startswith(CATEGORY_PREFIX) else "mechanic"


def _histogram(
    values: np.ndarray, bins: int, lo: float, hi: float
) -> list[dict[str, float | None]]:
    counts, edges = np.histogram(values, bins=bins, range=(lo, hi))
    return [
        {"x0": _r(edges[i], 3), "x1": _r(edges[i + 1], 3), "n": int(c)}
        for i, c in enumerate(counts)
    ]


def build_export(
    features: Features,
    result: ModelResult,
    rated: pd.DataFrame,
    clusters: Clusters | None,
    *,
    source: str,
    snapshot: str,
    base_year: int,
    compare: pd.DataFrame | None = None,
    compare_snapshot: str | None = None,
    beeswarm_features: int = 16,
    waterfall_parts: int = 6,
    beeswarm_points: int = 500,
    seed: int = 7,
) -> dict[str, Any]:
    X = features.X
    trait_cols = list(features.traits.columns)
    y = features.y.to_numpy()
    resid = (rated["avg_rating"] - rated["predicted_rating"]).to_numpy()
    baseline = float(np.std(y))

    # --- SHAP summaries -------------------------------------------------------------------
    shap_df = pd.DataFrame(result.shap_values, index=result.shap_X.index, columns=X.columns)
    mean_abs = shap_df.abs().mean().sort_values(ascending=False)
    rng = np.random.default_rng(seed)
    sample_idx = rng.choice(len(shap_df), size=min(beeswarm_points, len(shap_df)), replace=False)
    beeswarm = []
    for col in mean_abs.index[:beeswarm_features]:
        vals = result.shap_X[col].to_numpy(dtype=float)
        lo, hi = float(np.nanmin(vals)), float(np.nanmax(vals))
        norm = (vals - lo) / (hi - lo) if hi > lo else np.zeros_like(vals)
        beeswarm.append(
            {
                "feature": _feature_label(col),
                "kind": _feature_kind(col),
                "meanAbs": _r(mean_abs[col], 4),
                "points": [[_r(shap_df[col].iloc[i], 4), _r(norm[i], 3)] for i in sample_idx],
            }
        )

    # Dependence curves for the numeric features (raw value vs SHAP).
    dependence = {}
    for col in PRETTY:
        raw = result.shap_X[col].to_numpy(dtype=float)
        if col == "years_since_base":
            raw = raw + base_year
        dependence[col] = [[_r(raw[i], 1), _r(shap_df[col].iloc[i], 4)] for i in sample_idx]

    # --- Traits -------------------------------------------------------------------------------
    traits = []
    for col in trait_cols:
        present = features.traits[col] == 1
        ids = present[present].index
        shap_present = shap_df.loc[shap_df.index.intersection(ids), col]
        traits.append(
            {
                "key": col,
                "name": strip_prefix(col),
                "kind": _feature_kind(col),
                "count": int(present.sum()),
                "meanRating": _r(rated.loc[ids, "avg_rating"].mean()),
                "meanMagic": _r(rated.loc[ids, "magic_sauce"].mean()),
                "meanWeight": _r(rated.loc[ids, "weight"].mean()),
                "effect": _r(shap_present.mean(), 4) if len(shap_present) else None,
                "importance": _r(mean_abs[col], 4),
                "ratings": [_r(v, 2) for v in rated.loc[ids, "avg_rating"]],
            }
        )

    # --- Games --------------------------------------------------------------------------------
    cl: dict[Any, Any] = clusters.games.to_dict("index") if clusters is not None else {}
    then_map: dict[Any, Any] = (
        compare[["rank", "avg_rating"]].dropna().to_dict("index") if compare is not None else {}
    )
    contrib = result.contributions
    contrib_cols = [c for c in contrib.columns if c != "bias"]
    contrib_values = contrib[contrib_cols].to_numpy()
    contrib_row = {gid: i for i, gid in enumerate(contrib.index)}
    contrib_bias = contrib["bias"].to_numpy()
    trait_matrix = features.traits.to_numpy(dtype=bool)
    trait_row = {gid: i for i, gid in enumerate(features.traits.index)}
    games = []
    for row in rated.sort_values("rank").reset_index().to_dict("records"):
        gid = int(row["game_id"])
        g: dict[str, Any] = {
            "id": gid,
            "name": row["names"],
            "rank": int(row["rank"]),
            "year": int(row["year"]),
            "rating": _r(row["avg_rating"]),
            "geek": _r(row["geek_rating"]),
            "pred": _r(row["predicted_rating"]),
            "magic": _r(row["magic_sauce"]),
            "votes": int(row["num_votes"]),
            "weight": _r(row["weight"], 2),
            "time": int(row["avg_time"]),
            "players": [int(row["min_players"]), int(row["max_players"])],
            "traits": np.flatnonzero(trait_matrix[trait_row[gid]]).tolist(),
        }
        ci = contrib_row[gid]
        vals = contrib_values[ci]
        order = np.argsort(-np.abs(vals))[:waterfall_parts]
        g["why"] = {
            "base": _r(contrib_bias[ci], 3),
            "parts": [[_feature_label(contrib_cols[j]), _r(vals[j], 3)] for j in order],
            "other": _r(vals.sum() - vals[order].sum(), 3),
        }
        if all(c in row for c in RATING_BUCKETS) and not pd.isna(row[RATING_BUCKETS[0]]):
            g["dist"] = [int(row[c]) for c in RATING_BUCKETS]
        if "wishlisted" in row and not pd.isna(row["wishlisted"]):
            g["wish"] = int(row["wishlisted"])
        if gid in then_map:
            old = then_map[gid]
            g["then"] = {"rank": int(old["rank"]), "rating": _r(old["avg_rating"])}
        if gid in cl:
            info = cl[gid]
            g["cluster"] = int(info["cluster"])
            g["tsne"] = [_r(info["tsne_x"], 2), _r(info["tsne_y"], 2)]
        games.append(g)

    # --- Clusters ------------------------------------------------------------------------------
    cluster_out = []
    if clusters is not None:
        for c, name in enumerate(clusters.names):
            members = clusters.games[clusters.games["cluster"] == c]
            share = clusters.traits.loc[members.index].mean().nlargest(6)
            cluster_out.append(
                {
                    "id": c,
                    "name": name,
                    "size": len(members),
                    "meanRating": _r(rated.loc[members.index, "avg_rating"].mean()),
                    "meanMagic": _r(rated.loc[members.index, "magic_sauce"].mean()),
                    "topGames": [int(i) for i in members.sort_values("rank").index[:8]],
                    "traits": [
                        {"name": strip_prefix(str(t)), "share": _r(s)} for t, s in share.items()
                    ],
                }
            )

    # --- Year trend ----------------------------------------------------------------------------
    by_year = (
        rated[rated["year"] >= 1980]
        .groupby("year")
        .agg(
            n=("avg_rating", "size"),
            rating=("avg_rating", "mean"),
            pred=("predicted_rating", "mean"),
            weight=("weight", "mean"),
        )
        .reset_index()
    )
    years = [
        {
            "year": int(r["year"]),
            "n": int(r["n"]),
            "rating": _r(r["rating"]),
            "pred": _r(r["pred"]),
            "weight": _r(r["weight"]),
        }
        for r in by_year.to_dict("records")
    ]

    comparison = _compare(rated, compare, compare_snapshot) if compare is not None else None

    ss_res = float(np.sum(resid**2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    return {
        "meta": {
            "version": __version__,
            "generated": datetime.now(UTC).isoformat(timespec="seconds"),
            "source": source,
            "snapshot": snapshot,
            "games": len(rated),
            "features": int(X.shape[1]),
            "categories": sum(c.startswith(CATEGORY_PREFIX) for c in trait_cols),
            "mechanics": sum(not c.startswith(CATEGORY_PREFIX) for c in trait_cols),
            "rmse": _r(result.rmse, 4),
            "foldRmse": [_r(v, 4) for v in result.fold_rmse],
            "baselineStd": _r(baseline, 4),
            "r2": _r(1 - ss_res / ss_tot, 4),
            "meanRating": _r(float(y.mean())),
            "baseYear": base_year,
            "minVotes": int(features.data["num_votes"].min()),
        },
        "traitKeys": trait_cols,
        "traits": traits,
        "games": games,
        "importance": [
            {"feature": _feature_label(c), "kind": _feature_kind(c), "meanAbs": _r(v, 4)}
            for c, v in mean_abs.head(30).items()
            if isinstance(c, str)
        ],
        "beeswarm": beeswarm,
        "dependence": dependence,
        "residuals": _histogram(resid, 40, -2.0, 2.0),
        "ratingHistogram": _histogram(y, 40, 5.5, 9.5),
        "clusters": cluster_out,
        "years": years,
        "compare": comparison,
    }


def _shares(games: pd.DataFrame, column: str, top: int) -> pd.Series:
    subset = games[games["rank"].between(1, top)]
    return subset[column].explode().dropna().value_counts() / len(subset)


def _compare(rated: pd.DataFrame, then: pd.DataFrame, label: str | None) -> dict[str, Any]:
    """How the top of BGG changed between the comparison snapshot and this one."""
    top = int(min(rated["rank"].max(), then["rank"].max()))
    now_top = rated[rated["rank"] <= top]
    then_top = then[then["rank"].between(1, top)]
    shifts = []
    for column, kind in (("category", "category"), ("mechanic", "mechanic")):
        a, b = _shares(then, column, top), _shares(rated, column, top)
        for name in a.index.intersection(b.index):
            if max(a[name], b[name]) >= 0.03:
                shifts.append(
                    {"name": name, "kind": kind, "then": _r(a[name], 4), "now": _r(b[name], 4)}
                )
    shifts.sort(key=lambda d: abs(d["now"] - d["then"]), reverse=True)
    stats = {
        "medianYear": [int(then_top["year"].median()), int(now_top["year"].median())],
        "meanWeight": [_r(then_top["weight"].mean(), 2), _r(now_top["weight"].mean(), 2)],
        "meanTime": [_r(then_top["avg_time"].mean(), 0), _r(now_top["avg_time"].mean(), 0)],
        "meanRating": [_r(then_top["avg_rating"].mean()), _r(now_top["avg_rating"].mean())],
        "medianVotes": [int(then_top["num_votes"].median()), int(now_top["num_votes"].median())],
    }
    return {
        "snapshot": label,
        "top": top,
        "retained": int(now_top.index.isin(then_top.index).sum()),
        "newSince": int((now_top["year"] > then_top["year"].max()).sum()),
        "stats": stats,
        "shifts": shifts[:40],
    }


def write_export(doc: dict[str, Any], path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    return path
