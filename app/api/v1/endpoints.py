from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlmodel import Session

from app.db import get_session
from app.forecasting.backtest import cached_backtest
from app.schemas import BacktestOut, CycleIn, CycleOut, PredictionOut
from app.services.cycles import CycleError, add_cycle, delete_cycle, list_cycles, valid_lengths
from app.services.forecast import current_prediction
from app.stats import chart_png, compute_stats

router = APIRouter(prefix="/api/v1", tags=["api"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/predict", response_model=PredictionOut)
def predict(session: Session = Depends(get_session)):
    p = current_prediction(session)
    if p is None:
        raise HTTPException(400, "Servono almeno due cicli registrati.")
    return p.to_dict()


@router.get("/cycles", response_model=list[CycleOut])
def get_cycles(session: Session = Depends(get_session)):
    return list_cycles(session)


@router.post("/cycles", response_model=CycleOut, status_code=201)
def post_cycle(body: CycleIn, session: Session = Depends(get_session)):
    try:
        return add_cycle(session, body.start_date, source="api")
    except CycleError as exc:
        raise HTTPException(400, str(exc))


@router.delete("/cycles/{cycle_id}", status_code=204)
def remove_cycle(cycle_id: int, session: Session = Depends(get_session)):
    try:
        delete_cycle(session, cycle_id)
    except CycleError as exc:
        raise HTTPException(404, str(exc))


@router.get("/stats")
def stats(session: Session = Depends(get_session)) -> dict:
    return compute_stats(session)


@router.get("/stats/chart.png")
def chart(session: Session = Depends(get_session)) -> Response:
    return Response(chart_png(session), media_type="image/png")


@router.get("/backtest", response_model=BacktestOut)
def backtest(session: Session = Depends(get_session)):
    lengths = valid_lengths(session)
    if len(lengths) < 13:
        raise HTTPException(400, "Dati insufficienti per il backtest.")
    r = cached_backtest(tuple(lengths))
    return {"best": r.best, "scores": r.scores}
