import math
import statistics
from dataclasses import asdict, dataclass
from datetime import date, timedelta

import numpy as np

from app.config import settings
from app.forecasting.backtest import cached_backtest, get_model

MIN_CYCLES_FOR_MODEL = 6


@dataclass
class Prediction:
    last_start: date
    start: date
    window_low: date
    window_high: date
    end: date
    length: int
    method: str  # statistica | modello:<name> | fallback_mediana
    model_name: str | None
    model_raw: float | None
    mae: float | None
    status: str  # in_arrivo | finestra | in_ritardo | dimenticato
    days_to_start: int

    def to_dict(self) -> dict:
        return asdict(self)


def predict_length(lengths: list[int]) -> tuple[float, str, str | None, float | None, float | None]:
    """Returns (length, method, model_name, raw_model_value, mae)."""
    if len(lengths) < MIN_CYCLES_FOR_MODEL:
        return float(statistics.median(lengths)), "statistica", None, None, None

    bt = cached_backtest(tuple(lengths))
    raw = get_model(bt.best).predict_next(lengths)
    recent = lengths[-12:]
    med = float(statistics.median(recent))
    tol = max(3.0, 1.5 * float(np.std(recent)))
    # With too few cycles the backtest has nothing to score (MAE = inf): report "unknown", not infinity.
    mae = bt.scores[bt.best] if math.isfinite(bt.scores[bt.best]) else None

    out_of_range = not (settings.min_length <= raw <= settings.max_length)
    if out_of_range or abs(raw - med) > tol:
        return med, "fallback_mediana", bt.best, raw, mae
    return raw, f"modello:{bt.best}", bt.best, raw, mae


def predict(last_start: date, lengths: list[int], today: date | None = None) -> Prediction:
    if not lengths:
        raise ValueError("Servono almeno due cicli registrati per fare una previsione.")
    today = today or date.today()

    length_f, method, model_name, raw, mae = predict_length(lengths)
    length = int(round(length_f))
    start = last_start + timedelta(days=length)

    recent = lengths[-12:]
    p25, p75 = np.percentile(recent, [25, 75])
    low = min(last_start + timedelta(days=int(np.floor(p25))), start)
    high = max(last_start + timedelta(days=int(np.ceil(p75))), start)

    since_last = (today - last_start).days
    if since_last > settings.gap_days:
        status = "dimenticato"
    elif today > high:
        status = "in_ritardo"
    elif today >= low:
        status = "finestra"
    else:
        status = "in_arrivo"

    return Prediction(
        last_start=last_start,
        start=start,
        window_low=low,
        window_high=high,
        end=start + timedelta(days=settings.bleed_days - 1),
        length=length,
        method=method,
        model_name=model_name,
        model_raw=round(raw, 2) if raw is not None else None,
        mae=mae,
        status=status,
        days_to_start=(start - today).days,
    )
