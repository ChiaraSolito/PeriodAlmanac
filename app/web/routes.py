import re
from datetime import date
from itertools import groupby
from pathlib import Path
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session

from app import i18n
from app.db import get_session
from app.services.calendar_view import build_month, build_ring
from app.services.cycles import CycleError, add_cycle, delete_cycle, list_cycles, update_cycle, valid_lengths
from app.services.forecast import current_prediction
from app.stats import compute_stats

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
templates.env.globals.update(
    fmt=i18n.fmt,
    fmt_long=i18n.fmt_long,
    when=i18n.when_text,
    method_label=i18n.method_label,
    month_title=i18n.month_title,
    STATUS=i18n.STATUS,
    WEEKDAYS=["L", "M", "M", "G", "V", "S", "D"],
)

router = APIRouter(include_in_schema=False)
MONTH_PARAM = re.compile(r"^(\d{4})-(\d{2})$")


def _safe_next(path: str | None, default: str) -> str:
    """Only allow local paths as redirect targets (no '//host' or absolute URLs)."""
    if path and path.startswith("/") and not path.startswith("//") and "\\" not in path:
        return path
    return default


def _redirect(path: str, anchor: str = "", **params) -> RedirectResponse:
    query = urlencode({k: v for k, v in params.items() if v is not None})
    sep = "&" if "?" in path else "?"
    return RedirectResponse(f"{path}{sep + query if query else ''}{anchor}", status_code=303)


@router.get("/")
def home(request: Request, session: Session = Depends(get_session)):
    today = date.today()
    p = current_prediction(session, today=today)
    return templates.TemplateResponse(
        request,
        "home.html",
        {
            "p": p,
            "ring": build_ring(p, today) if p and p.status != "dimenticato" else None,
            "today": today,
            "page": "home",
        },
    )


@router.post("/log")
def log(start_date: date = Form(...), next: str | None = Form(None), session: Session = Depends(get_session)):
    target = _safe_next(next, "/")
    try:
        c = add_cycle(session, start_date, source="web")
    except CycleError as exc:
        return _redirect(target, err=str(exc))
    return _redirect(target, ok=f"Registrato l'inizio del {i18n.fmt(c.start_date)}.", undo=c.id)


@router.get("/calendario")
def calendar_page(request: Request, m: str | None = Query(None), session: Session = Depends(get_session)):
    today = date.today()
    match = MONTH_PARAM.match(m or "")
    year, month = (int(match[1]), int(match[2])) if match and 1 <= int(match[2]) <= 12 else (today.year, today.month)
    cal = build_month(year, month, list_cycles(session), current_prediction(session, today=today), today)
    return templates.TemplateResponse(
        request, "calendar.html", {"cal": cal, "today": today, "page": "calendario", "this_url": f"/calendario?m={year}-{month:02d}"}
    )


@router.get("/storico")
def history(request: Request, edit: int | None = Query(None), session: Session = Depends(get_session)):
    cycles = list(reversed(list_cycles(session)))
    lengths = valid_lengths(session)
    typical = sorted(lengths[-12:])[len(lengths[-12:]) // 2] if lengths else None
    years = [(y, list(items)) for y, items in groupby(cycles, key=lambda c: c.start_date.year)]
    return templates.TemplateResponse(
        request,
        "history.html",
        {"years": years, "edit": edit, "typical": typical, "today": date.today(), "page": "storico", "count": len(cycles)},
    )


@router.post("/storico/{cycle_id}/modifica")
def edit(cycle_id: int, start_date: date = Form(...), session: Session = Depends(get_session)):
    try:
        c = update_cycle(session, cycle_id, start_date)
    except CycleError as exc:
        return _redirect("/storico", anchor=f"#c{cycle_id}", edit=cycle_id, err=str(exc))
    return _redirect("/storico", anchor=f"#c{c.id}", ok=f"Data aggiornata: {i18n.fmt(c.start_date)}.")


@router.post("/storico/{cycle_id}/elimina")
def delete(cycle_id: int, next: str | None = Form(None), session: Session = Depends(get_session)):
    target = _safe_next(next, "/storico")
    try:
        delete_cycle(session, cycle_id)
    except CycleError as exc:
        return _redirect(target, err=str(exc))
    return _redirect(target, ok="Eliminato.")


@router.get("/statistiche")
def stats(request: Request, session: Session = Depends(get_session)):
    return templates.TemplateResponse(request, "stats.html", {"s": compute_stats(session), "page": "statistiche"})
