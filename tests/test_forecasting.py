from datetime import date, timedelta

import pytest

from app.forecasting import predictor
from app.forecasting.backtest import run_backtest
from app.forecasting.candidates import EWMA, RecentMedian
from app.forecasting.predictor import predict, predict_length

REGULAR = [27, 28, 26, 29, 27, 28, 27, 26, 28, 30, 27, 28, 26, 27, 29, 28, 27, 26, 28, 27]


def test_backtest_picks_a_model_and_scores_all():
    r = run_backtest(REGULAR, [RecentMedian(), EWMA(0.3)])
    assert r.best in r.scores
    assert all(v >= 0 for v in r.scores.values())


def test_few_cycles_uses_statistics():
    length, method, *_ = predict_length([27, 29, 28])
    assert method == "statistica" and length == 28


class _Crazy:
    name = "crazy"

    def predict_next(self, lengths):
        return 40.0


def test_fallback_triggers_when_model_is_far_from_median(monkeypatch):
    from app.forecasting.backtest import BacktestResult

    monkeypatch.setattr(predictor, "cached_backtest", lambda _: BacktestResult("crazy", {"crazy": 1.0}))
    monkeypatch.setattr(predictor, "get_model", lambda _: _Crazy())
    length, method, name, raw, _ = predict_length(REGULAR)
    assert method == "fallback_mediana"
    assert name == "crazy" and raw == 40.0
    assert length == 27.5  # median of the last 12


def test_model_used_when_close_to_median(monkeypatch):
    from app.forecasting.backtest import BacktestResult

    monkeypatch.setattr(predictor, "cached_backtest", lambda _: BacktestResult("ewma_0.3", {"ewma_0.3": 1.5}))
    monkeypatch.setattr(predictor, "get_model", lambda _: EWMA(0.3))
    _, method, *_ = predict_length(REGULAR)
    assert method == "modello:ewma_0.3"


@pytest.mark.parametrize("lengths", [REGULAR, [25, 38, 26, 31, 22, 35, 27, 29, 33, 24, 30, 26, 28]])
def test_window_contains_predicted_start(lengths):
    last = date(2026, 10, 10)
    p = predict(last, lengths, today=date(2026, 10, 20))
    assert p.window_low <= p.start <= p.window_high
    assert p.end == p.start + timedelta(days=6)
    assert p.start == last + timedelta(days=p.length)


@pytest.mark.parametrize(
    "today,status",
    [
        (date(2026, 10, 20), "in_arrivo"),
        (date(2026, 11, 7), "finestra"),
        (date(2026, 11, 20), "in_ritardo"),
        (date(2026, 12, 1), "dimenticato"),
    ],
)
def test_status(today, status):
    p = predict(date(2026, 10, 10), REGULAR, today=today)
    assert p.status == status
