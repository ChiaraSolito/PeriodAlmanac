"""Web app: editing, undo, calendar and the home ring."""
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.db import get_session
from app.forecasting.predictor import predict
from app.main import app
from app.services.calendar_view import build_month, build_ring
from app.services.cycles import CycleError, add_cycle, list_cycles, update_cycle
from app.web.routes import _safe_next

TODAY = date(2026, 11, 12)
LENGTHS = [27, 28, 26, 29, 27, 28, 27, 26, 28, 30, 27, 28]


# ---------- update_cycle ----------

def test_update_cycle_recomputes_lengths(session):
    for d in [date(2026, 1, 1), date(2026, 1, 29), date(2026, 2, 26)]:
        add_cycle(session, d, today=TODAY)
    middle = list_cycles(session)[1]
    update_cycle(session, middle.id, date(2026, 1, 31), today=TODAY)
    cycles = list_cycles(session)
    assert [c.cycle_length for c in cycles] == [None, 30, 26]
    assert cycles[1].end_date == date(2026, 2, 6)


def test_update_cycle_same_date_is_noop(session):
    c = add_cycle(session, date(2026, 1, 1), today=TODAY)
    assert update_cycle(session, c.id, date(2026, 1, 1), today=TODAY).start_date == date(2026, 1, 1)


@pytest.mark.parametrize("bad", [date(2026, 11, 13), date(2026, 1, 29), date(2026, 1, 25)])
def test_update_cycle_validates(session, bad):
    first = add_cycle(session, date(2026, 1, 1), today=TODAY)
    add_cycle(session, date(2026, 1, 29), today=TODAY)
    with pytest.raises(CycleError):
        update_cycle(session, first.id, bad, today=TODAY)  # future, duplicate, too close


def test_update_cycle_allows_small_shift_of_itself(session):
    c = add_cycle(session, date(2026, 1, 10), today=TODAY)
    # Moving an entry by a few days must not collide with itself.
    assert update_cycle(session, c.id, date(2026, 1, 8), today=TODAY).start_date == date(2026, 1, 8)


# ---------- calendar ----------

class _C:  # minimal stand-in for Cycle
    def __init__(self, id, start):
        self.id, self.start_date, self.end_date = id, start, start + timedelta(days=6)


def _days(month):
    return {d.date: d for week in month.weeks for d in week}


def test_calendar_marks_logged_predicted_and_window():
    last = date(2026, 10, 27)  # the November grid starts on Monday 26 October
    p = predict(last, LENGTHS, today=TODAY)
    m = build_month(2026, 11, [_C(1, last)], p, TODAY)
    days = _days(m)

    assert days[last].start_id == 1 and days[date(2026, 11, 2)].period and not days[date(2026, 11, 3)].period
    assert days[p.start].predicted and days[p.end].predicted
    assert days[p.window_low].window or days[p.window_low].predicted
    assert days[TODAY].is_today
    assert all(len(w) == 7 for w in m.weeks)
    assert m.weeks[0][0].date.weekday() == 0  # weeks start on Monday
    assert (m.prev, m.next) == (date(2026, 10, 1), date(2026, 12, 1))
    assert ("Inizio previsto" in [what for _, what in m.events])


def test_calendar_projects_next_cycles_fainter():
    last = date(2026, 10, 20)
    p = predict(last, LENGTHS, today=TODAY)
    second = p.start + timedelta(days=p.length)
    m = build_month(second.year, second.month, [], p, TODAY)
    assert _days(m)[second].projected


def test_calendar_hides_prediction_when_data_is_missing():
    last = date(2026, 6, 13)
    p = predict(last, LENGTHS, today=TODAY)
    assert p.status == "dimenticato"
    m = build_month(2026, 7, [_C(1, last)], p, TODAY)
    assert not any(d.predicted or d.window or d.projected for w in m.weeks for d in w)


# ---------- ring ----------

def test_ring_values_are_within_the_circle():
    p = predict(date(2026, 10, 20), LENGTHS, today=TODAY)
    r = build_ring(p, TODAY)
    assert r.cycle_day == 24
    assert 0 < r.progress <= 100
    assert 0 <= r.window_from <= 100 and r.window_from + r.window_len <= 101
    assert 8 <= r.marker_x <= 112 and 8 <= r.marker_y <= 112


def test_ring_marker_sits_on_the_predicted_day():
    import math

    p = predict(date(2026, 10, 20), LENGTHS, today=TODAY)
    r = build_ring(p, TODAY)
    span = max(p.length, (p.window_high - p.last_start).days, r.cycle_day)
    # Unrotated SVG space: 0% is 3 o'clock, angles grow clockwise (y points down).
    turn = math.atan2(r.marker_y - 60, r.marker_x - 60) % (2 * math.pi) / (2 * math.pi)
    expected = p.length / span
    assert min(abs(turn - expected), 1 - abs(turn - expected)) < 0.01  # 100% wraps to 0%


def test_ring_when_late_is_full():
    p = predict(date(2026, 10, 1), LENGTHS, today=TODAY)
    assert p.status == "in_ritardo"
    assert build_ring(p, TODAY).progress == 100


# ---------- routes ----------

@pytest.mark.parametrize(
    "path,expected",
    [("/calendario?m=2026-11", "/calendario?m=2026-11"), ("//evil.com", "/"), ("https://evil.com", "/"),
     ("/\\evil.com", "/"), (None, "/")],
)
def test_safe_next(path, expected):
    assert _safe_next(path, "/") == expected


@pytest.fixture
def client(engine):
    def _session():
        with Session(engine) as s:
            yield s

    app.dependency_overrides[get_session] = _session
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_log_offers_undo_and_undo_deletes(client, engine):
    r = client.post("/log", data={"start_date": "2026-01-01"}, follow_redirects=False)
    assert r.status_code == 303 and "undo=" in r.headers["location"]
    undo_id = int(r.headers["location"].split("undo=")[1].split("&")[0])

    page = client.get(r.headers["location"])
    assert "Annulla" in page.text

    r = client.post(f"/storico/{undo_id}/elimina", data={"next": "/"}, follow_redirects=False)
    assert r.headers["location"].startswith("/?ok=")
    with Session(engine) as s:
        assert list_cycles(s) == []


def test_log_from_calendar_returns_to_calendar(client):
    r = client.post("/log", data={"start_date": "2026-01-01", "next": "/calendario?m=2026-01"}, follow_redirects=False)
    assert r.headers["location"].startswith("/calendario?m=2026-01&ok=")


def test_edit_flow(client, engine):
    client.post("/log", data={"start_date": "2026-01-01"})
    client.post("/log", data={"start_date": "2026-01-29"})
    with Session(engine) as s:
        second = list_cycles(s)[1]

    page = client.get(f"/storico?edit={second.id}")
    assert 'name="start_date" value="2026-01-29"' in page.text

    r = client.post(f"/storico/{second.id}/modifica", data={"start_date": "2026-01-30"}, follow_redirects=False)
    assert r.headers["location"].endswith(f"#c{second.id}") and "ok=" in r.headers["location"]

    r = client.post(f"/storico/{second.id}/modifica", data={"start_date": "2026-01-02"}, follow_redirects=False)
    assert "err=" in r.headers["location"] and f"edit={second.id}" in r.headers["location"]


@pytest.mark.parametrize("url", ["/", "/calendario", "/calendario?m=2016-05", "/calendario?m=bad", "/storico", "/statistiche"])
def test_pages_render(client, url):
    client.post("/log", data={"start_date": "2026-01-01"})
    client.post("/log", data={"start_date": "2026-01-29"})
    assert client.get(url).status_code == 200


def test_predict_with_few_cycles_has_no_infinite_error(client):
    # 8 regular cycles: enough for the model path, too few for the backtest to score anything.
    start = date.today() - timedelta(days=28 * 8)
    for i in range(9):
        client.post("/api/v1/cycles", json={"start_date": (start + timedelta(days=28 * i)).isoformat()})
    r = client.get("/api/v1/predict")
    assert r.status_code == 200 and r.json()["mae"] is None
    assert "inf" not in client.get("/").text


def test_api_patch(client):
    c = client.post("/api/v1/cycles", json={"start_date": "2026-01-01"}).json()
    r = client.patch(f"/api/v1/cycles/{c['id']}", json={"start_date": "2026-01-03"})
    assert r.status_code == 200 and r.json()["start_date"] == "2026-01-03"
    assert client.patch("/api/v1/cycles/999", json={"start_date": "2026-01-03"}).status_code == 404
