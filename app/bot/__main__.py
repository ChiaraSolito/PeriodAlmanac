"""Telegram bot. Run with:  python -m app.bot"""
import asyncio
import functools
import logging
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from sqlmodel import Session
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from app import i18n
from app.config import settings
from app.db import engine, init_db
from app.services.cycles import CycleError, add_cycle, delete_cycle, list_cycles
from app.services.forecast import current_prediction
from app.services.reminders import due_reminders, load_last_sent, mark_sent, parse_date
from app.stats import chart_png, compute_stats

logging.basicConfig(format="%(asctime)s %(levelname)s %(name)s: %(message)s", level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("bot")

TZ = ZoneInfo(settings.tz)

HELP = (
    "Ciao! Comandi disponibili:\n"
    "/prossimo – previsione del prossimo ciclo\n"
    "/log – registra un inizio (es. /log oggi, /log 03/11/2026)\n"
    "/storico – ultimi cicli, con possibilità di eliminarli\n"
    "/stats – statistiche e grafico\n"
    "/id – mostra il tuo chat id"
)

LOG_KEYBOARD = InlineKeyboardMarkup(
    [[
        InlineKeyboardButton("Oggi", callback_data="log:oggi"),
        InlineKeyboardButton("Ieri", callback_data="log:ieri"),
        InlineKeyboardButton("Altra data", callback_data="log:altra"),
    ]]
)
CONFIRM_KEYBOARD = InlineKeyboardMarkup(
    [
        [InlineKeyboardButton("Sì, oggi", callback_data="log:oggi")],
        [
            InlineKeyboardButton("Non ancora", callback_data="noop:nonancora"),
            InlineKeyboardButton("Altra data", callback_data="log:altra"),
        ],
    ]
)


def today() -> date:
    return datetime.now(TZ).date()


def allowed(handler):
    """Only the configured chat may use the bot."""

    @functools.wraps(handler)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat = update.effective_chat
        if chat is None or chat.id != settings.allowed_chat_id:
            log.warning("Rifiutato chat id %s", chat.id if chat else None)
            if update.effective_message:
                await update.effective_message.reply_text("Non autorizzato. Usa /id e configura ALLOWED_CHAT_ID.")
            return
        return await handler(update, context)

    return wrapper


# ---- sync helpers (run in a thread so the model backtest never blocks the event loop) ----

def _prediction_text() -> str:
    with Session(engine) as s:
        p = current_prediction(s, today=today())
    return i18n.prediction_text(p) if p else "Registra almeno due inizi per avere una previsione."


def _log(d: date) -> str:
    with Session(engine) as s:
        try:
            c = add_cycle(s, d, source="bot", today=today())
        except CycleError as exc:
            return f"⚠️ {exc}"
        p = current_prediction(s, today=today())
    msg = f"✅ Registrato inizio del {i18n.fmt(c.start_date)} (fine prevista {i18n.fmt(c.end_date)})."
    if c.cycle_length:
        msg += f"\nDurata del ciclo precedente: {c.cycle_length} giorni."
    if p:
        msg += f"\n\nProssimo previsto: {i18n.fmt(p.start, True)} ({i18n.fmt(p.window_low)} – {i18n.fmt(p.window_high)})."
    return msg


def _stats() -> tuple[str, bytes | None]:
    with Session(engine) as s:
        st = compute_stats(s)
        if "mean" not in st:
            return "Dati insufficienti.", None
        png = chart_png(s)
    text = (
        f"📊 {st['count']} cicli registrati\n"
        f"Mediana ultimi 12: {st['recent_median']} gg (media {st['recent_mean']})\n"
        f"Media storica: {st['mean']} ± {st['std']} gg\n"
        f"Min–max: {st['min']}–{st['max']} gg\n"
        f"Tendenza: {st['trend']}"
    )
    if st["gaps"]:
        text += f"\nIntervalli esclusi (>{settings.gap_days} gg): {st['gaps']}"
    return text, png


def _history() -> tuple[str, InlineKeyboardMarkup | None]:
    with Session(engine) as s:
        cycles = list_cycles(s)[-10:][::-1]
    if not cycles:
        return "Nessun ciclo registrato.", None
    lines, buttons = [], []
    for c in cycles:
        length = "primo" if c.cycle_length is None else f"{c.cycle_length} gg" + (" (escluso)" if c.is_gap else "")
        lines.append(f"• {i18n.fmt(c.start_date)} – {length}")
        buttons.append([InlineKeyboardButton(f"🗑 {i18n.fmt(c.start_date)}", callback_data=f"del:{c.id}")])
    return "Ultimi cicli:\n" + "\n".join(lines), InlineKeyboardMarkup(buttons)


def _delete(cycle_id: int) -> str:
    with Session(engine) as s:
        try:
            delete_cycle(s, cycle_id)
        except CycleError as exc:
            return f"⚠️ {exc}"
    return "🗑 Eliminato."


def _reminders(force: bool = False) -> list[tuple[str, bool]]:
    """Returns messages to send as (text, with_confirm_keyboard)."""
    t = today()
    with Session(engine) as s:
        p = current_prediction(s, today=t)
        if p is None:
            return []
        due = due_reminders(p, t, {} if force else load_last_sent(s))
        out = []
        for r in due:
            if r.kind == "pre":
                out.append((f"🔔 Tra {p.days_to_start} giorni è previsto il ciclo ({i18n.fmt(p.start, True)}).\n"
                            f"Finestra: {i18n.fmt(p.window_low)} – {i18n.fmt(p.window_high)}.", False))
            elif r.kind == "day":
                out.append((f"🩸 Oggi è il giorno previsto ({i18n.fmt(p.start)}). È iniziato?", True))
            elif r.kind == "late":
                out.append((f"⏰ Il ciclo previsto per il {i18n.fmt(p.start)} non è ancora stato registrato "
                            f"({-p.days_to_start} giorni di ritardo rispetto alla previsione). È iniziato?", True))
            elif r.kind == "gap":
                days = (t - p.last_start).days
                out.append((f"🤔 L'ultimo inizio registrato è del {i18n.fmt(p.last_start)} ({days} giorni fa).\n"
                            "Hai dimenticato di registrare? Usa /log con la data, ad es. /log 03/11/2026.", True))
            if not force:
                mark_sent(s, r, t)
        return out


# ---- handlers ----

async def cmd_id(update: Update, _: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(f"Il tuo chat id è: {update.effective_chat.id}")


@allowed
async def cmd_help(update: Update, _: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(HELP)


@allowed
async def cmd_predict(update: Update, _: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(await asyncio.to_thread(_prediction_text))


@allowed
async def cmd_log(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        d = parse_date(" ".join(context.args), today())
        if d is None:
            await update.effective_message.reply_text("Data non valida. Usa gg/mm/aaaa, es. /log 03/11/2026.")
            return
        await update.effective_message.reply_text(await asyncio.to_thread(_log, d))
        return
    await update.effective_message.reply_text("Quando è iniziato?", reply_markup=LOG_KEYBOARD)


@allowed
async def cmd_stats(update: Update, _: ContextTypes.DEFAULT_TYPE):
    text, png = await asyncio.to_thread(_stats)
    if png:
        await update.effective_message.reply_photo(png, caption=text)
    else:
        await update.effective_message.reply_text(text)


@allowed
async def cmd_history(update: Update, _: ContextTypes.DEFAULT_TYPE):
    text, kb = await asyncio.to_thread(_history)
    await update.effective_message.reply_text(text, reply_markup=kb)


@allowed
async def cmd_test_reminders(update: Update, _: ContextTypes.DEFAULT_TYPE):
    msgs = await asyncio.to_thread(_reminders, True)
    if not msgs:
        await update.effective_message.reply_text("Nessun promemoria dovuto oggi.")
    for text, confirm in msgs:
        await update.effective_message.reply_text(text, reply_markup=CONFIRM_KEYBOARD if confirm else None)


@allowed
async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    action, _, arg = q.data.partition(":")
    if action == "log" and arg == "altra":
        context.user_data["awaiting_date"] = True
        await q.message.reply_text("Scrivi la data di inizio (gg/mm/aaaa):")
    elif action == "log":
        d = parse_date(arg, today())
        await q.edit_message_reply_markup(None)
        await q.message.reply_text(await asyncio.to_thread(_log, d))
    elif action == "del":
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("Sì, elimina", callback_data=f"delok:{arg}"),
            InlineKeyboardButton("Annulla", callback_data="noop:annulla"),
        ]])
        await q.message.reply_text("Confermi l'eliminazione?", reply_markup=kb)
    elif action == "delok":
        await q.edit_message_reply_markup(None)
        await q.message.reply_text(await asyncio.to_thread(_delete, int(arg)))
    elif action == "noop":
        await q.edit_message_reply_markup(None)
        if arg == "nonancora":
            await q.message.reply_text("Ok, te lo richiederò nei prossimi giorni.")


@allowed
async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("awaiting_date"):
        await update.effective_message.reply_text(HELP)
        return
    d = parse_date(update.effective_message.text, today())
    if d is None:
        await update.effective_message.reply_text("Non ho capito la data. Usa gg/mm/aaaa, es. 03/11/2026.")
        return
    context.user_data["awaiting_date"] = False
    await update.effective_message.reply_text(await asyncio.to_thread(_log, d))


async def daily_job(context: ContextTypes.DEFAULT_TYPE):
    for text, confirm in await asyncio.to_thread(_reminders):
        await context.bot.send_message(
            settings.allowed_chat_id, text, reply_markup=CONFIRM_KEYBOARD if confirm else None
        )


def main() -> None:
    if not settings.telegram_token:
        raise SystemExit("TELEGRAM_TOKEN mancante: copia .env.example in .env e compilalo.")
    init_db()
    app = Application.builder().token(settings.telegram_token).build()
    app.add_handler(CommandHandler("id", cmd_id))
    app.add_handler(CommandHandler(["start", "aiuto", "help"], cmd_help))
    app.add_handler(CommandHandler(["prossimo", "predict"], cmd_predict))
    app.add_handler(CommandHandler("log", cmd_log))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("storico", cmd_history))
    app.add_handler(CommandHandler("test_promemoria", cmd_test_reminders))
    app.add_handler(CallbackQueryHandler(on_button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    if settings.allowed_chat_id:
        app.job_queue.run_daily(daily_job, time(hour=settings.reminder_hour, tzinfo=TZ), name="promemoria")
        # Also check once shortly after start-up, in case the PC was off at the scheduled hour.
        app.job_queue.run_once(daily_job, 10)
    else:
        log.warning("ALLOWED_CHAT_ID non impostato: promemoria disattivati. Scrivi /id al bot.")

    log.info("Bot avviato (polling).")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
