from datetime import date

from pydantic import BaseModel


class CycleIn(BaseModel):
    start_date: date


class CycleOut(BaseModel):
    id: int
    start_date: date
    end_date: date
    cycle_length: int | None
    is_gap: bool
    source: str


class PredictionOut(BaseModel):
    last_start: date
    start: date
    window_low: date
    window_high: date
    end: date
    length: int
    method: str
    model_name: str | None
    model_raw: float | None
    mae: float | None
    status: str
    days_to_start: int


class BacktestOut(BaseModel):
    best: str
    scores: dict[str, float]
