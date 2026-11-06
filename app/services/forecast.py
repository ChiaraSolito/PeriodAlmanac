from datetime import date

from sqlmodel import Session

from app.forecasting.predictor import Prediction, predict
from app.services.cycles import last_cycle, valid_lengths


def current_prediction(session: Session, today: date | None = None) -> Prediction | None:
    last = last_cycle(session)
    lengths = valid_lengths(session)
    if last is None or not lengths:
        return None
    return predict(last.start_date, lengths, today=today)
