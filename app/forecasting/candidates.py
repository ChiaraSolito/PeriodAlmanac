"""Lightweight next-cycle-length forecasters. Each takes the chronological history and returns one value."""
import statistics
import warnings
from typing import Protocol

import numpy as np


class Forecaster(Protocol):
    name: str

    def predict_next(self, lengths: list[int]) -> float: ...


class RecentMedian:
    name = "mediana_12"

    def predict_next(self, lengths: list[int]) -> float:
        return float(statistics.median(lengths[-12:]))


class EWMA:
    def __init__(self, alpha: float = 0.3):
        self.alpha = alpha
        self.name = f"ewma_{alpha}"

    def predict_next(self, lengths: list[int]) -> float:
        level = float(lengths[0])
        for x in lengths[1:]:
            level = self.alpha * x + (1 - self.alpha) * level
        return level


class LagLinear:
    """Linear regression on the previous `window` lengths."""

    def __init__(self, window: int = 3):
        self.window = window
        self.name = f"lag_linear_{window}"

    def predict_next(self, lengths: list[int]) -> float:
        from sklearn.linear_model import LinearRegression

        w = self.window
        if len(lengths) <= w + 2:
            return float(np.mean(lengths))
        x = np.array([lengths[i - w : i] for i in range(w, len(lengths))])
        y = np.array(lengths[w:])
        model = LinearRegression().fit(x, y)
        return float(model.predict([lengths[-w:]])[0])


class Arima:
    name = "arima_1_0_1"

    def predict_next(self, lengths: list[int]) -> float:
        from statsmodels.tsa.arima.model import ARIMA

        if len(lengths) < 10:
            return float(np.mean(lengths))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            fit = ARIMA(np.asarray(lengths, dtype=float), order=(1, 0, 1)).fit()
            return float(fit.forecast(1)[0])


def default_candidates() -> list[Forecaster]:
    return [RecentMedian(), EWMA(0.2), EWMA(0.4), LagLinear(3), Arima()]
