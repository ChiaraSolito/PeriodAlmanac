from datetime import date, timedelta

import pytest

from app.services.cycles import CycleError, add_cycle, delete_cycle, list_cycles, valid_lengths

TODAY = date(2026, 11, 6)


def test_out_of_order_backfill_recomputes_lengths(session):
    for d in [date(2026, 1, 1), date(2026, 2, 28), date(2026, 1, 29)]:
        add_cycle(session, d, today=TODAY)
    cycles = list_cycles(session)
    assert [c.cycle_length for c in cycles] == [None, 28, 30]
    assert all(c.end_date == c.start_date + timedelta(days=6) for c in cycles)


def test_gap_over_45_days_is_flagged_and_excluded(session):
    add_cycle(session, date(2026, 1, 1), today=TODAY)
    add_cycle(session, date(2026, 1, 29), today=TODAY)
    add_cycle(session, date(2026, 5, 1), today=TODAY)  # 92 days: unlogged cycles
    gap = list_cycles(session)[-1]
    assert gap.is_gap and gap.cycle_length == 92
    assert valid_lengths(session) == [28]


def test_backfilling_the_gap_clears_the_flag(session):
    add_cycle(session, date(2026, 1, 1), today=TODAY)
    add_cycle(session, date(2026, 3, 1), today=TODAY)  # 59 days -> gap
    assert list_cycles(session)[-1].is_gap
    add_cycle(session, date(2026, 1, 30), today=TODAY)  # backfill the missing start
    assert valid_lengths(session) == [29, 30]
    assert not any(c.is_gap for c in list_cycles(session))


def test_delete_recomputes(session):
    for d in [date(2026, 1, 1), date(2026, 1, 29), date(2026, 2, 26)]:
        add_cycle(session, d, today=TODAY)
    middle = list_cycles(session)[1]
    delete_cycle(session, middle.id)
    assert [c.cycle_length for c in list_cycles(session)] == [None, 56]


@pytest.mark.parametrize(
    "bad",
    [date(2026, 11, 7), date(2026, 1, 1), date(2026, 1, 10)],  # future, duplicate, too close
)
def test_rejects_invalid_dates(session, bad):
    add_cycle(session, date(2026, 1, 1), today=TODAY)
    with pytest.raises(CycleError):
        add_cycle(session, bad, today=TODAY)
