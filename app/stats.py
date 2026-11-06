import io
import statistics

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from sqlmodel import Session  # noqa: E402

from app.services.cycles import list_cycles, valid_lengths  # noqa: E402


def compute_stats(session: Session) -> dict:
    lengths = valid_lengths(session)
    cycles = list_cycles(session)
    if not lengths:
        return {"count": len(cycles)}
    recent = lengths[-12:]
    older = lengths[-24:-12]
    trend = "stabile"
    if older:
        diff = statistics.mean(recent) - statistics.mean(older)
        trend = "in aumento" if diff > 1 else "in diminuzione" if diff < -1 else "stabile"
    return {
        "count": len(cycles),
        "mean": round(statistics.mean(lengths), 1),
        "median": statistics.median(lengths),
        "std": round(statistics.pstdev(lengths), 1),
        "recent_mean": round(statistics.mean(recent), 1),
        "recent_median": statistics.median(recent),
        "min": min(lengths),
        "max": max(lengths),
        "trend": trend,
        "gaps": sum(c.is_gap for c in cycles),
        "last": [
            {"start": c.start_date.isoformat(), "length": c.cycle_length, "is_gap": c.is_gap} for c in cycles[-12:]
        ],
    }


def chart_png(session: Session, n: int = 36) -> bytes:
    cycles = [c for c in list_cycles(session) if c.cycle_length is not None and not c.is_gap][-n:]
    fig, ax = plt.subplots(figsize=(7, 3.2), dpi=120)
    if cycles:
        xs = [c.start_date for c in cycles]
        ys = [c.cycle_length for c in cycles]
        med = statistics.median(ys)
        ax.axhline(med, color="#9a9a9a", lw=1, ls="--", label=f"mediana {med:g} gg")
        ax.plot(xs, ys, marker="o", ms=3.5, color="#c2185b", lw=1.6)
        ax.legend(frameon=False, fontsize=8, loc="upper left")
    ax.set_ylabel("durata (giorni)")
    ax.set_title("Durata degli ultimi cicli", fontsize=10)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.grid(axis="y", alpha=0.25)
    fig.autofmt_xdate()
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    return buf.getvalue()
