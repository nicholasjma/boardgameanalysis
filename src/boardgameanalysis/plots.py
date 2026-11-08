"""Figures from the original analysis, rendered to files."""

from __future__ import annotations

from pathlib import Path

import matplotlib as mpl

mpl.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import scipy.stats as stats
import shap
import statsmodels.api as sm
from matplotlib.axes import Axes
from matplotlib.figure import Figure

from boardgameanalysis.clustering import Clusters
from boardgameanalysis.model import ModelResult

VOTE_LEGEND = (100, 500, 1000, 5000)


def _save(fig: Figure, path: Path) -> Path:
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def _year_scatter(
    ax: Axes, x: pd.Series, y: pd.Series, games: pd.DataFrame, base_year: int, size: float
) -> None:
    years = games["year"].clip(lower=base_year)
    sc = ax.scatter(
        x,
        y,
        s=size * np.sqrt(games["num_votes"]),
        c=years,
        cmap="plasma",
        alpha=0.15,
        marker=".",
    )
    cbar = ax.figure.colorbar(sc, ax=ax, label="Year")
    ticks = np.linspace(base_year, int(years.max()), 4).round().astype(int)
    cbar.set_ticks(list(ticks))
    cbar.set_ticklabels([f"≤{ticks[0]}", *map(str, ticks[1:])])
    for v in VOTE_LEGEND:
        ax.scatter([], [], c="k", alpha=0.3, s=size * v**0.5, label=str(v))
    ax.legend(scatterpoints=1, frameon=False, labelspacing=1, title="Number of votes")


def residuals(games: pd.DataFrame, out: Path) -> list[Path]:
    res = (games["avg_rating"] - games["predicted_rating"]).to_numpy()
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.hist(res, bins=30)
    ax.set(title="Residuals", xlabel="Actual - predicted rating", ylabel="Frequency")
    paths = [_save(fig, out / "residuals.png")]

    fig = sm.qqplot(res, stats.t, fit=True, line="45")
    fig.axes[0].set_title("QQ plot for residuals")
    paths.append(_save(fig, out / "qqplot.png"))
    return paths


def predicted_vs_actual(games: pd.DataFrame, out: Path, base_year: int) -> Path:
    fig, ax = plt.subplots(figsize=(8, 7))
    _year_scatter(ax, games["predicted_rating"], games["avg_rating"], games, base_year, 1.0)
    lo = float(min(games["predicted_rating"].quantile(0.005), games["avg_rating"].quantile(0.005)))
    hi = float(max(games["predicted_rating"].max(), games["avg_rating"].quantile(0.995)))
    ax.plot([lo, hi], [lo, hi], color="0.5", linestyle="--", linewidth=1)
    ax.set(
        title="Predicted vs actual rating",
        xlabel="Predicted rating",
        ylabel="Actual rating",
        xlim=(lo, hi),
        ylim=(lo, hi),
    )
    return _save(fig, out / "predvsactual.png")


def rank_vs_average(games: pd.DataFrame, out: Path, base_year: int) -> Path:
    fig, ax = plt.subplots(figsize=(10, 6))
    _year_scatter(ax, games["rank"], games["avg_rating"], games, base_year, 1.0)
    ax.set(title="Rank vs average rating", xlabel="Rank", ylabel="Average rating")
    ax.invert_xaxis()
    return _save(fig, out / "rankvsavg.png")


def rank_vs_magic(
    games: pd.DataFrame, out: Path, base_year: int, max_rank: int, bin_size: int
) -> Path:
    subset = games[games["rank"] <= max_rank]
    fig, ax = plt.subplots(figsize=(10, 6))
    _year_scatter(ax, subset["rank"], subset["magic_sauce"], subset, base_year, 0.3)
    bins = (subset["rank"] - 1) // bin_size
    means = subset.groupby(bins)["magic_sauce"].mean()
    ax.plot(
        means.index * bin_size + bin_size / 2,
        means.to_numpy(),
        c="red",
        marker=".",
        linestyle=":",
        label=f"Mean per {bin_size} ranks",
    )
    ax.set(
        title=f"Rank vs magic sauce (top {max_rank})",
        xlabel="Rank",
        ylabel="Magic sauce (actual - predicted)",
        xlim=(max_rank, 1),
    )
    return _save(fig, out / f"magic{max_rank}.png")


def shap_summary(result: ModelResult, out: Path, max_display: int = 20) -> Path:
    shap.summary_plot(result.shap_values, result.shap_X, max_display=max_display, show=False)
    fig = plt.gcf()
    fig.suptitle("SHAP values")
    return _save(fig, out / "shap_summary.png")


def clusters_html(clusters: Clusters, out: Path, top: int = 200) -> Path:
    games = clusters.games[clusters.games["rank"] <= top]
    fig = go.Figure()
    for c, name in enumerate(clusters.names):
        members = games[games["cluster"] == c]
        fig.add_trace(
            go.Scatter(
                x=members["tsne_x"],
                y=members["tsne_y"],
                mode="markers",
                marker={"size": 14, "opacity": 0.5},
                name=name,
                text=members["names"] + " (#" + members["rank"].astype(int).astype(str) + ")",
                hoverinfo="text",
            )
        )
    fig.update_layout(
        title=f"BGG top {top} clustered by category and mechanic (t-SNE)",
        xaxis={"visible": False},
        yaxis={"visible": False},
        hovermode="closest",
        template="plotly_white",
    )
    path = out / "clusters.html"
    fig.write_html(path, include_plotlyjs="cdn")
    return path
