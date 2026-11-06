"""Italian formatting helpers shared by web and bot."""
from datetime import date

from app.forecasting.predictor import Prediction

MESI = ["gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic"]
GIORNI = ["lun", "mar", "mer", "gio", "ven", "sab", "dom"]

STATUS = {
    "in_arrivo": "in arrivo",
    "finestra": "nella finestra prevista",
    "in_ritardo": "in ritardo",
    "dimenticato": "nessun inizio registrato da molto tempo: hai dimenticato di registrare?",
}


def fmt(d: date, weekday: bool = False) -> str:
    s = f"{d.day} {MESI[d.month - 1]} {d.year}"
    return f"{GIORNI[d.weekday()]} {s}" if weekday else s


def method_label(p: Prediction) -> str:
    if p.method == "statistica":
        return "mediana (pochi dati)"
    if p.method == "fallback_mediana":
        return f"mediana ultimi 12 cicli (il modello {p.model_name} dava {p.model_raw:g} gg, troppo lontano)"
    return f"modello {p.model_name} (errore medio ±{p.mae:.1f} gg)"


def when_text(days_to_start: int) -> str:
    if days_to_start > 1:
        return f"tra {days_to_start} giorni"
    if days_to_start == 1:
        return "domani"
    if days_to_start == 0:
        return "oggi"
    if days_to_start == -1:
        return "ieri"
    return f"{-days_to_start} giorni fa"


def prediction_text(p: Prediction) -> str:
    """Plain-text (no markup) summary for Telegram."""
    return (
        f"🩸 Prossimo ciclo: {fmt(p.start, True)} ({when_text(p.days_to_start)})\n"
        f"Finestra: {fmt(p.window_low)} – {fmt(p.window_high)}\n"
        f"Fine prevista: {fmt(p.end)}\n"
        f"Durata stimata: {p.length} giorni\n"
        f"Stato: {STATUS[p.status]}\n"
        f"Metodo: {method_label(p)}"
    )
