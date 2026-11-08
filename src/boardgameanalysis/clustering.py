"""Cluster top games by their categories and mechanics."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.cluster import AgglomerativeClustering
from sklearn.manifold import TSNE

from boardgameanalysis.features import CATEGORY_PREFIX, MECHANIC_PREFIX, Features


@dataclass(frozen=True)
class Clusters:
    games: pd.DataFrame
    """Top games with ``cluster``, ``cluster_name``, ``tsne_x`` and ``tsne_y`` columns."""
    traits: pd.DataFrame
    names: list[str]


def strip_prefix(trait: str) -> str:
    return trait.removeprefix(CATEGORY_PREFIX).removeprefix(MECHANIC_PREFIX)


def name_clusters(traits: pd.DataFrame, labels: np.ndarray, n_traits: int = 2) -> list[str]:
    """Label each cluster by the traits most over-represented in it versus all games."""
    overall = traits.mean()
    names = []
    for c in range(labels.max() + 1):
        lift = traits[labels == c].mean() - overall
        top = lift.nlargest(n_traits).index
        names.append("/".join(strip_prefix(t) for t in top))
    return names


def cluster_games(
    features: Features,
    *,
    top: int = 500,
    n_clusters: int = 11,
    perplexity: float = 5.0,
    random_state: int = 20,
) -> Clusters:
    data = features.data
    top_ids = data.index[data["rank"] <= top]
    traits = features.traits.loc[top_ids]
    traits = traits.loc[:, traits.sum() > 0]

    labels = AgglomerativeClustering(n_clusters=n_clusters, linkage="ward").fit_predict(traits)
    embedding = TSNE(
        init="pca",
        metric="jaccard",
        perplexity=perplexity,
        learning_rate=200,
        max_iter=1000,
        random_state=random_state,
    ).fit_transform(traits.to_numpy(dtype=bool))

    names = name_clusters(traits, labels)
    games = data.loc[top_ids, ["names", "rank"]].copy()
    games["cluster"] = labels
    games["cluster_name"] = [names[i] for i in labels]
    games["tsne_x"] = embedding[:, 0]
    games["tsne_y"] = embedding[:, 1]
    return Clusters(games=games, traits=traits, names=names)


def summarize(clusters: Clusters, n_games: int = 10, n_traits: int = 5) -> str:
    lines = []
    for c, name in enumerate(clusters.names):
        members = clusters.games[clusters.games["cluster"] == c]
        lines.append(f"Cluster {c + 1}: {name} ({len(members)} games)")
        for _, row in members.sort_values("rank").head(n_games).iterrows():
            lines.append(f"  #{int(row['rank']):>4}  {row['names']}")
        share = clusters.traits.loc[members.index].mean().nlargest(n_traits) * 100
        lines.extend(f"    {pct:5.1f}%  {strip_prefix(str(t))}" for t, pct in share.items())
        lines.append("")
    return "\n".join(lines)
