import statistics
from pathlib import Path
from typing import List, Tuple
import pandas as pd
import numpy as np
import pandas as pd
from joblib import dump, load
from sklearn.linear_model import LinearRegression
from sklearn.metrics import root_mean_squared_error

MODEL_PATH = Path(__file__).resolve().parents[1] / "trained_model.joblib"
DATA_PATH = Path(__file__).resolve().parents[1] / "data/cycles_with_durations.csv"

class TimeSeriesModel:
    def __init__(self):
        self.model: LinearRegression | None = None
        self.window = 0
        self.data: pd.DataFrame = self._load_data()


    def _load_data(self) -> pd.DataFrame:
        if DATA_PATH.exists():
            data: pd.DataFrame = pd.read_csv(DATA_PATH)
            return data
        return pd.DataFrame(columns=["cycle_id","year","month","day","cycle_duration"])

    def _append_lag_features(self, data: pd.DataFrame, window: int) -> pd.DataFrame:
        if "cycle_duration" not in data.columns:
            raise ValueError("Data must contain a cycle_duration column")
        if len(data) <= window:
            raise ValueError("Not enough points to create lag features")

        lagged = data.copy()
        for lag in range(1, window + 1):
            lagged[f"lag_{lag}"] = lagged["cycle_duration"].shift(lag)
        return lagged

    def _build_features(self, data: pd.DataFrame, window: int) -> Tuple[pd.DataFrame, np.ndarray]:
        if len(data) <= window:
            raise ValueError("Not enough points to create lag features")

        lagged = self._append_lag_features(data, window)
        feature_cols = ["cycle_id", "year", "month", "day"] + [f"lag_{i}" for i in range(1, window + 1)]
        x = lagged.loc[window:, feature_cols].to_numpy(dtype=float)
        y = lagged.loc[window:, "cycle_duration"].fillna(0).to_numpy(dtype=float)
        return x, y

    def train(self, window: int = 5) -> float:
        if len(self.data) <= window:
            raise ValueError("Training data length must be greater than window size")

        X, y = self._build_features(self.data, window)
        model = LinearRegression()
        model.fit(X, y)

        y_pred = model.predict(X)
        rmse = float(root_mean_squared_error(y, y_pred))

        self.model = model
        self.window = window
        self._save()
        return rmse

    def _recursive_forecast(self, recent_data: List[float], horizon: int) -> List[float]:
        if self.model is None:
            raise ValueError("Model is not trained")
        if len(recent_data) < self.window:
            raise ValueError(f"Recent data must contain at least {self.window} values")

        history = recent_data[-self.window :]
        predictions = []
        for _ in range(horizon):
            pred = float(self.model.predict([history])[0])
            predictions.append(pred)
            history = history[1:] + [pred]
        return predictions

    def predict(self, recent_data: List[float], horizon: int) -> List[float]:
        return self._recursive_forecast(recent_data, horizon)

    def analyze(self, data: List[float]) -> dict:
        if len(data) < 3:
            raise ValueError("At least 3 values are required for analysis")

        series = pd.Series(data)
        mean = float(series.mean())
        std = float(series.std(ddof=0))

        trend = self._estimate_trend(series)
        seasonality = self._estimate_seasonality(series)

        return {
            "mean": mean,
            "std": std,
            "trend": trend,
            "seasonality": seasonality,
        }

    def _estimate_trend(self, series: pd.Series) -> str:
        diffs = series.diff().dropna()
        slope = diffs.mean()
        return "increasing" if slope > 0 else "decreasing" if slope < 0 else "flat"

    def _estimate_seasonality(self, series: pd.Series) -> str:
        autocorr = series.autocorr(lag=1)
        if autocorr > 0.5:
            return "strong"
        if autocorr > 0.2:
            return "moderate"
        return "weak"

    def _save(self) -> None:
        if self.model is None:
            return
        dump({"model": self.model, "window": self.window}, MODEL_PATH)

    def load(self) -> bool:
        if not MODEL_PATH.exists():
            return False
        payload = load(MODEL_PATH)
        self.model = payload["model"]
        self.window = payload["window"]
        return True


ts_model = TimeSeriesModel()
