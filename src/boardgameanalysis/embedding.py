"""3D UMAP embedding of the top games by their categories and mechanics."""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd

from boardgameanalysis.features import Features


def umap_3d(
    features: Features,
    *,
    top: int = 1000,
    n_neighbors: int = 15,
    min_dist: float = 0.1,
    random_state: int = 42,
) -> pd.DataFrame:
    """Embed the ``top`` ranked games in 3D using Jaccard distance on their trait vectors.

    Returns a frame indexed by game_id with ``umap_x``, ``umap_y`` and ``umap_z`` columns,
    centred on the origin and scaled so the farthest game sits at radius 1.
    """
    from umap import UMAP  # slow import (numba); keep it out of module import time

    ids = features.data.sort_values("rank").index[:top]
    traits = features.traits.loc[ids]
    traits = traits.loc[:, traits.sum() > 0]

    reducer = UMAP(
        n_components=3,
        n_neighbors=n_neighbors,
        min_dist=min_dist,
        metric="jaccard",
        random_state=random_state,
    )
    with warnings.catch_warnings():
        # Fixing random_state disables parallelism; UMAP warns about it every time.
        warnings.filterwarnings("ignore", message=".*n_jobs.*", category=UserWarning)
        # Jaccard has no gradient, so inverse_transform is unavailable; we never use it.
        warnings.filterwarnings("ignore", message=".*inverse_transform.*", category=UserWarning)
        coords = np.asarray(reducer.fit_transform(traits.to_numpy(dtype=bool)), dtype=float)

    coords -= coords.mean(axis=0)
    coords /= float(np.max(np.linalg.norm(coords, axis=1)))
    return pd.DataFrame(coords, index=ids, columns=["umap_x", "umap_y", "umap_z"])
