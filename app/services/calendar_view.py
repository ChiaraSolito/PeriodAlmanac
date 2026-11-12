"""View models for the web app: month calendar and the cycle ring on the home page."""
import calendar
import math
from dataclasses import dataclass, field
from datetime import date, timedelta

from app.config import settings
from app.forecasting.predictor import Prediction
from app.models import Cycle

PROJECTIONS = 2  # extra cycles after the next one, shown fainter as a rough estimate


@dataclass
class Day:
    date: date
    in_month: bool
    is_today: bool = False
    is_future: bool = False
    period: bool = False  # logged bleeding day
    start_id: int | None = None  # set on the first day of a logged period
    predicted: bool = False  # next predicted period
    projected: bool = False  # later estimated periods
    window: bool = False  # prediction window for the next start

    @property
    def classes(self) -> str:
        names = ["day"]
        for flag in ("period", "predicted", "projected", "window"):
            if getattr(self, flag):
                names.append(flag)
        if self.start_id:
            names.append("start")
        if not self.in_month:
            names.append("out")
        if self.is_today:
            names.append("today")
        return " ".join(names)


@dataclass
class Month:
    year: int
    month: int
    weeks: list[list[Day]]
    prev: date
    next: date
    events: list[tuple[date, str]] = field(default_factory=list)  # summary lines for this month


def build_month(
    year: int, month: int, cycles: list[Cycle], prediction: Prediction | None, today: date
) -> Month:
    bleed = timedelta(days=settings.bleed_days - 1)

    period_days: dict[date, int | None] = {}
    for c in cycles:
        d = c.start_date
        while d <= c.end_date:
            period_days.setdefault(d, None)
            d += timedelta(days=1)
        period_days[c.start_date] = c.id

    predicted: set[date] = set()
    projected: set[date] = set()
    window: set[date] = set()
    upcoming: list[tuple[date, bool]] = []  # (start, is_first)
    # When nothing was logged for > GAP_DAYS the prediction is meaningless: show only the history.
    if prediction and prediction.status != "dimenticato":
        for k in range(PROJECTIONS + 1):
            start = prediction.start + timedelta(days=k * prediction.length)
            target = predicted if k == 0 else projected
            target.update(_span(start, start + bleed))
            upcoming.append((start, k == 0))
        window.update(_span(prediction.window_low, prediction.window_high))

    weeks = []
    for week in calendar.Calendar(firstweekday=0).monthdatescalendar(year, month):
        row = []
        for d in week:
            row.append(
                Day(
                    date=d,
                    in_month=d.month == month,
                    is_today=d == today,
                    is_future=d > today,
                    period=d in period_days,
                    start_id=period_days.get(d),
                    predicted=d in predicted and d not in period_days,
                    projected=d in projected and d not in period_days,
                    window=d in window and d not in period_days,
                )
            )
        weeks.append(row)

    first = date(year, month, 1)
    events = [(c.start_date, "Inizio registrato") for c in cycles if (c.start_date.year, c.start_date.month) == (year, month)]
    for start, is_first in upcoming:
        if (start.year, start.month) == (year, month):
            events.append((start, "Inizio previsto" if is_first else "Inizio stimato"))
    events.sort()
    return Month(
        year=year,
        month=month,
        weeks=weeks,
        prev=(first - timedelta(days=1)).replace(day=1),
        next=(first + timedelta(days=32)).replace(day=1),
        events=events,
    )


def _span(a: date, b: date) -> set[date]:
    return {a + timedelta(days=i) for i in range((b - a).days + 1)}


@dataclass
class Ring:
    """SVG data for the home ring. Values are percentages of the circle (pathLength=100)."""

    cycle_day: int
    progress: float
    window_from: float
    window_len: float
    marker_x: float
    marker_y: float


RING_R = 52
RING_C = 60  # centre of the 120x120 viewBox


def build_ring(p: Prediction, today: date) -> Ring:
    cycle_day = (today - p.last_start).days + 1
    # The full circle is the longest of: predicted length, window end, today (when late).
    span = max(p.length, (p.window_high - p.last_start).days, cycle_day)
    pct = lambda days: max(0.0, min(100.0, days / span * 100))  # noqa: E731
    w_from = pct((p.window_low - p.last_start).days)
    w_to = pct((p.window_high - p.last_start).days + 1)
    # The SVG is rotated -90deg in CSS (so arcs start at 12 o'clock); the marker lives in the same rotated space.
    angle = pct(p.length) / 100 * 2 * math.pi
    return Ring(
        cycle_day=cycle_day,
        progress=round(pct(cycle_day), 2),
        window_from=round(w_from, 2),
        window_len=round(max(w_to - w_from, 1.5), 2),
        marker_x=round(RING_C + RING_R * math.cos(angle), 2),
        marker_y=round(RING_C + RING_R * math.sin(angle), 2),
    )
