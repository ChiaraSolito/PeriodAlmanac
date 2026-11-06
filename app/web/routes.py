from datetime import date
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session

from app import i18n
from app.db import get_session
from app.services.cycles import CycleError, add_cycle, delete_cycle, list_cycles
from app.services.forecast import current_prediction
from app.stats import compute_stats

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
templates.env.globals.update(fmt=i18n.fmt, when=i18n.when_text, method_label=i18n.method_label, STATUS=i18n.STATUS)

router = APIRouter(include_in_schema=False)


def _redirect(path: str, msg: str | None = None, ok: bool = True) -> RedirectResponse:
    url = path if not msg else f"{path}?{'ok' if ok else 'err'}={quote(msg)}"
    return RedirectResponse(url, status_code=303)


@router.get("/")
def home(request: Request, session: Session = Depends(get_session)):
    return templates.TemplateResponse(
        request,
        "home.html",
        {"p": current_prediction(session), "today": date.today().isoformat(), "page": "home"},
    )


@router.post("/log")
def log(start_date: date = Form(...), session: Session = Depends(get_session)):
    try:
        c = add_cycle(session, start_date, source="web")
    except CycleError as exc:
        return _redirect("/", str(exc), ok=False)
    return _redirect("/", f"Registrato inizio del {i18n.fmt(c.start_date)}.")


@router.get("/storico")
def history(request: Request, session: Session = Depends(get_session)):
    cycles = list(reversed(list_cycles(session)))
    return templates.TemplateResponse(request, "history.html", {"cycles": cycles, "page": "storico"})


@router.post("/storico/{cycle_id}/elimina")
def delete(cycle_id: int, session: Session = Depends(get_session)):
    try:
        delete_cycle(session, cycle_id)
    except CycleError as exc:
        return _redirect("/storico", str(exc), ok=False)
    return _redirect("/storico", "Eliminato.")


@router.get("/statistiche")
def stats(request: Request, session: Session = Depends(get_session)):
    return templates.TemplateResponse(request, "stats.html", {"s": compute_stats(session), "page": "statistiche"})
