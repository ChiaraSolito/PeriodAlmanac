from dataclasses import dataclass
from functools import lru_cache

from app.forecasting.candidates import Forecaster, default_candidates


@dataclass(frozen=True)
class BacktestResult:
    best: str
    scores: dict[str, float]  # model name -> MAE in days


def walk_forward_mae(model: Forecaster, lengths: list[int], n_test: int = 24, min_train: int = 12) -> float:
    start = max(min_train, len(lengths) - n_test)
    errors = [abs(model.predict_next(lengths[:i]) - lengths[i]) for i in range(start, len(lengths))]
    return sum(errors) / len(errors) if errors else float("inf")


def run_backtest(lengths: list[int], candidates: list[Forecaster] | None = None) -> BacktestResult:
    candidates = candidates or default_candidates()
    scores = {m.name: round(walk_forward_mae(m, lengths), 3) for m in candidates}
    best = min(scores, key=scores.get)
    return BacktestResult(best=best, scores=scores)


@lru_cache(maxsize=8)
def cached_backtest(lengths: tuple[int, ...]) -> BacktestResult:
    """Cache keyed on the data itself, so any insert/delete invalidates it automatically."""
    return run_backtest(list(lengths))


def get_model(name: str) -> Forecaster:
    return next(m for m in default_candidates() if m.name == name)
