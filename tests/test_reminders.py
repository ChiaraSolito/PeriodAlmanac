from datetime import date, timedelta

import pytest

from app.forecasting.predictor import predict
from app.services.reminders import Reminder, due_reminders, parse_date

LENGTHS = [27, 28, 26, 29, 27, 28, 27, 26, 28, 30, 27, 28]
LAST = date(2026, 10, 10)


def _p(today):
    return predict(LAST, LENGTHS, today=today)


def test_pre_reminder_two_days_before_and_only_once():
    p = _p(LAST)
    pre_day = p.start - timedelta(days=2)
    p = _p(pre_day)
    assert due_reminders(p, pre_day, {}) == [Reminder("pre", p.start)]
    assert due_reminders(p, pre_day, {("pre", p.start): pre_day}) == []


def test_day_reminder_on_predicted_day():
    start = _p(LAST).start
    p = _p(start)
    assert due_reminders(p, start, {}) == [Reminder("day", start)]


def test_late_nudge_every_two_days():
    start = _p(LAST).start
    late = _p(LAST).window_high + timedelta(days=1)
    p = _p(late)
    assert p.status == "in_ritardo"
    assert due_reminders(p, late, {}) == [Reminder("late", start)]
    assert due_reminders(p, late, {("late", start): late - timedelta(days=1)}) == []
    assert due_reminders(p, late, {("late", start): late - timedelta(days=2)}) == [Reminder("late", start)]


def test_gap_reminder_after_45_days():
    t = LAST + timedelta(days=50)
    p = _p(t)
    assert due_reminders(p, t, {}) == [Reminder("gap", LAST)]


@pytest.mark.parametrize(
    "text,expected",
    [
        ("oggi", date(2026, 11, 6)),
        ("ieri", date(2026, 11, 5)),
        ("03/11/2026", date(2026, 11, 3)),
        ("3/11/26", date(2026, 11, 3)),
        ("2026-11-03", date(2026, 11, 3)),
        ("20/12", date(2025, 12, 20)),  # no year, would be future -> last year
        ("31/02/2026", None),
        ("boh", None),
    ],
)
def test_parse_date(text, expected):
    assert parse_date(text, date(2026, 11, 6)) == expected
