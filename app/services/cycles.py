from datetime import date, timedelta

from sqlmodel import Session, select

from app.config import settings
from app.models import Cycle


class CycleError(ValueError):
    pass


def list_cycles(session: Session) -> list[Cycle]:
    return list(session.exec(select(Cycle).order_by(Cycle.start_date)))


def last_cycle(session: Session) -> Cycle | None:
    return session.exec(select(Cycle).order_by(Cycle.start_date.desc())).first()


def valid_lengths(session: Session) -> list[int]:
    """Chronological cycle lengths, excluding the first entry and flagged gaps."""
    return [c.cycle_length for c in list_cycles(session) if c.cycle_length is not None and not c.is_gap]


def recompute_lengths(session: Session) -> None:
    prev: Cycle | None = None
    for c in list_cycles(session):
        c.end_date = c.start_date + timedelta(days=settings.bleed_days - 1)
        c.cycle_length = (c.start_date - prev.start_date).days if prev else None
        c.is_gap = c.cycle_length is not None and c.cycle_length > settings.gap_days
        session.add(c)
        prev = c
    session.commit()


def add_cycle(session: Session, start: date, source: str = "web", today: date | None = None) -> Cycle:
    today = today or date.today()
    if start > today:
        raise CycleError("La data non può essere nel futuro.")
    existing = session.exec(select(Cycle).where(Cycle.start_date == start)).first()
    if existing:
        raise CycleError(f"Il ciclo del {start:%d/%m/%Y} è già registrato.")
    # Two starts closer than min_length days are almost certainly a typo.
    near = session.exec(
        select(Cycle).where(
            Cycle.start_date > start - timedelta(days=settings.min_length - 5),
            Cycle.start_date < start + timedelta(days=settings.min_length - 5),
        )
    ).first()
    if near:
        raise CycleError(
            f"C'è già un inizio il {near.start_date:%d/%m/%Y}, troppo vicino. Elimina quello prima, se è sbagliato."
        )
    cycle = Cycle(start_date=start, end_date=start, source=source)
    session.add(cycle)
    session.commit()
    recompute_lengths(session)
    session.refresh(cycle)
    return cycle


def delete_cycle(session: Session, cycle_id: int) -> None:
    cycle = session.get(Cycle, cycle_id)
    if cycle is None:
        raise CycleError("Ciclo non trovato.")
    session.delete(cycle)
    session.commit()
    recompute_lengths(session)


def days_since_last(session: Session, today: date | None = None) -> int | None:
    last = last_cycle(session)
    if last is None:
        return None
    return ((today or date.today()) - last.start_date).days
