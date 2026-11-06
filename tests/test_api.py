from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.db import get_session
from app.main import app


@pytest.fixture
def client(engine):
    def _session():
        with Session(engine) as s:
            yield s

    app.dependency_overrides[get_session] = _session
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_log_then_predict(client):
    assert client.get("/api/v1/predict").status_code == 400
    start = date.today() - timedelta(days=200)
    for i in range(8):
        r = client.post("/api/v1/cycles", json={"start_date": (start + timedelta(days=28 * i)).isoformat()})
        assert r.status_code == 201
    p = client.get("/api/v1/predict").json()
    assert p["length"] == 28
    assert client.post("/api/v1/cycles", json={"start_date": start.isoformat()}).status_code == 400


def test_web_pages_render(client):
    for path in ["/", "/storico", "/statistiche"]:
        assert client.get(path).status_code == 200


def test_web_log_form(client):
    r = client.post("/log", data={"start_date": date.today().isoformat()}, follow_redirects=False)
    assert r.status_code == 303 and "ok=" in r.headers["location"]
