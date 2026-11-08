"""Turn the games table into model features."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

CATEGORY_PREFIX = "cat:"
MECHANIC_PREFIX = "mech:"


@dataclass(frozen=True)
class Features:
    """Filtered games plus the model's design matrix.

    ``data`` keeps every original column (with raw ``year``) for plotting; ``X`` is what the
    model sees; ``traits`` is the binary category/mechanic block used for clustering.
    """

    data: pd.DataFrame
    X: pd.DataFrame
    traits: pd.DataFrame

    @property
    def y(self) -> pd.Series:
        return self.data["avg_rating"]


def one_hot_lists(column: pd.Series, prefix: str, min_count: int) -> pd.DataFrame:
    """One-hot encode a column of lists, keeping values seen in at least ``min_count`` rows."""
    exploded = column.explode().dropna()
    exploded = exploded[exploded != "none"]
    dummies = pd.crosstab(exploded.index, exploded).clip(upper=1)
    dummies = dummies.loc[:, dummies.sum() >= min_count]
    dummies = dummies.reindex(column.index, fill_value=0).astype(np.int8)
    dummies.columns = [f"{prefix}{c}" for c in dummies.columns]
    dummies.index.name = column.index.name
    return dummies


def build_features(
    games: pd.DataFrame,
    *,
    max_rank: int = 5000,
    min_votes: int = 500,
    min_trait_count: int = 20,
    base_year: int = 2000,
    max_time: int = 300,
    max_players: int = 8,
) -> Features:
    """Replicates the original notebook's preprocessing.

    Keeps ranked games in the top ``max_rank`` with more than ``min_votes`` ratings, measures
    year as years past ``base_year`` (older games are 0), clamps play time and player count,
    and one-hot encodes categories and mechanics that appear at least ``min_trait_count`` times.
    """
    data = games[games["rank"].between(1, max_rank)]
    data = data[data["num_votes"] > min_votes]
    data = data.dropna(subset=["avg_rating", "year", "avg_time"]).copy()

    data["years_since_base"] = (data["year"] - base_year).clip(lower=0)
    data["log_num_votes"] = np.log10(data["num_votes"])
    data["log_owned"] = np.log10(data["owned"].clip(lower=1))
    data["avg_time"] = data["avg_time"].clip(upper=max_time)
    data["max_players"] = data["max_players"].clip(upper=max_players)

    cat = one_hot_lists(data["category"], CATEGORY_PREFIX, min_trait_count)
    mech = one_hot_lists(data["mechanic"], MECHANIC_PREFIX, min_trait_count)
    traits = cat.join(mech)

    X = data[["years_since_base", "avg_time"]].join(traits)
    return Features(data=data, X=X, traits=traits)
