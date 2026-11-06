"""Decides which reminders are due. Pure logic + small DB helpers, so it is unit-testable without Telegram."""
import re
from dataclasses import dataclass
from datetime import date, timedelta

from sqlmodel import Session, select

from app.forecasting.predictor import Prediction
from app.models import ReminderLog

LATE_EVERY_DAYS = 2
GAP_EVERY_DAYS = 7


@dataclass(frozen=True)
class Reminder:
    kind: str  # pre | day | late | gap
    target: date


def due_reminders(p: Prediction, today: date, last_sent: dict[tuple[str, date], date]) -> list[Reminder]:
    """`last_sent` maps (kind, target) -> last date it was sent. Tolerates missed runs (bot offline)."""

    def never(kind: str, target: date) -> bool:
        return (kind, target) not in last_sent

    def older_than(kind: str, target: date, days: int) -> bool:
        sent = last_sent.get((kind, target))
        return sent is None or (today - sent).days >= days

    if p.status == "dimenticato":
        return [Reminder("gap", p.last_start)] if older_than("gap", p.last_start, GAP_EVERY_DAYS) else []
    if p.status == "in_ritardo":
        return [Reminder("late", p.start)] if older_than("late", p.start, LATE_EVERY_DAYS) else []
    if p.days_to_start <= 0 and never("day", p.start):
        return [Reminder("day", p.start)]
    if 0 < p.days_to_start <= 2 and never("pre", p.start):
        return [Reminder("pre", p.start)]
    return []


def load_last_sent(session: Session) -> dict[tuple[str, date], date]:
    out: dict[tuple[str, date], date] = {}
    for r in session.exec(select(ReminderLog).order_by(ReminderLog.sent_on)):
        out[(r.kind, r.target_date)] = r.sent_on
    return out


def mark_sent(session: Session, r: Reminder, today: date) -> None:
    session.add(ReminderLog(kind=r.kind, target_date=r.target, sent_on=today))
    session.commit()


def parse_date(text: str, today: date) -> date | None:
    """Accepts 'oggi', 'ieri', dd/mm/yyyy, dd/mm (current year), dd-mm-yyyy, yyyy-mm-dd."""
    t = text.strip().lower()
    if t == "oggi":
        return today
    if t == "ieri":
        return today - timedelta(days=1)
    try:
        if m := re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", t):
            return date(int(m[1]), int(m[2]), int(m[3]))
        if m := re.fullmatch(r"(\d{1,2})[/.\-](\d{1,2})(?:[/.\-](\d{2,4}))?", t):
            year = int(m[3]) if m[3] else today.year
            year = year + 2000 if year < 100 else year
            d = date(year, int(m[2]), int(m[1]))
            # "dd/mm" without year that lands in the future means last year.
            if not m[3] and d > today:
                d = d.replace(year=d.year - 1)
            return d
    except ValueError:
        return None
    return None
