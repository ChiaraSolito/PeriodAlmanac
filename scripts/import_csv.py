"""One-time import of data/cycles_with_durations.csv into SQLite. Safe to re-run (skips existing dates)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402
from sqlmodel import Session, select  # noqa: E402

from app.config import settings  # noqa: E402
from app.db import engine, init_db  # noqa: E402
from app.models import Cycle  # noqa: E402
from app.services.cycles import recompute_lengths  # noqa: E402


def main(csv_path: Path = settings.csv_path) -> None:
    init_db()
    df = pd.read_csv(csv_path, parse_dates=["date"])
    added = 0
    with Session(engine) as s:
        existing = set(s.exec(select(Cycle.start_date)))
        for d in sorted(df["date"].dt.date.unique()):
            if d not in existing:
                s.add(Cycle(start_date=d, end_date=d, source="import"))
                added += 1
        s.commit()
        recompute_lengths(s)
        total = len(list(s.exec(select(Cycle))))
    print(f"Importati {added} cicli nuovi ({total} totali) in {settings.db_url}")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else settings.csv_path)
