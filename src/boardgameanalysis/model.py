"""Cross-validated XGBoost model of average rating from game traits."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.model_selection import KFold

from boardgameanalysis.features import Features

DEFAULT_PARAMS: dict[str, Any] = {
    "objective": "reg:squarederror",
    "colsample_bytree": 0.3,
    "learning_rate": 0.1,
    "max_depth": 6,
    "reg_lambda": 1.0,
    "reg_alpha": 10.0,
    "n_estimators": 60,
}


@dataclass(frozen=True)
class ModelResult:
    predictions: pd.Series
    """Out-of-fold predicted average rating for every game."""
    fold_rmse: list[float]
    shap_values: np.ndarray
    """SHAP values for the first fold's model on its training rows (as in the original)."""
    shap_X: pd.DataFrame
    contributions: pd.DataFrame = field(default_factory=pd.DataFrame)
    """Out-of-fold SHAP contributions per game; ``bias`` + the row sum equals the prediction."""
    params: dict[str, Any] = field(default_factory=dict)

    @property
    def rmse(self) -> float:
        return float(np.sqrt(np.mean(np.square(self.fold_rmse))))


def cross_validate(
    features: Features,
    *,
    n_splits: int = 5,
    random_state: int = 523,
    params: dict[str, Any] | None = None,
) -> ModelResult:
    params = {**DEFAULT_PARAMS, **(params or {}), "random_state": random_state}
    X, y = features.X, features.y
    preds = pd.Series(np.nan, index=X.index, name="predicted_rating")
    fold_rmse: list[float] = []
    shap_values: np.ndarray | None = None
    shap_X: pd.DataFrame | None = None
    contributions = pd.DataFrame(0.0, index=X.index, columns=[*X.columns, "bias"])

    folds = KFold(n_splits=n_splits, shuffle=True, random_state=random_state)
    for i, (train_idx, test_idx) in enumerate(folds.split(X)):
        model = xgb.XGBRegressor(**params)
        model.fit(X.iloc[train_idx], y.iloc[train_idx])
        fold_pred = model.predict(X.iloc[test_idx])
        preds.iloc[test_idx] = fold_pred
        test_contribs = model.get_booster().predict(
            xgb.DMatrix(X.iloc[test_idx]), pred_contribs=True
        )
        contributions.iloc[test_idx] = test_contribs
        fold_rmse.append(float(np.sqrt(np.mean((y.iloc[test_idx] - fold_pred) ** 2))))
        if i == 0:
            shap_X = X.iloc[train_idx]
            # XGBoost computes exact TreeSHAP natively; the last column is the bias term.
            contribs = model.get_booster().predict(xgb.DMatrix(shap_X), pred_contribs=True)
            shap_values = contribs[:, :-1]

    assert shap_values is not None and shap_X is not None
    return ModelResult(
        predictions=preds,
        fold_rmse=fold_rmse,
        shap_values=shap_values,
        shap_X=shap_X,
        contributions=contributions,
        params=params,
    )


def with_predictions(features: Features, result: ModelResult) -> pd.DataFrame:
    """Games with ``predicted_rating`` and ``magic_sauce`` (actual minus predicted)."""
    out = features.data.join(result.predictions)
    out["magic_sauce"] = out["avg_rating"] - out["predicted_rating"]
    return out.sort_values("magic_sauce", ascending=False)
