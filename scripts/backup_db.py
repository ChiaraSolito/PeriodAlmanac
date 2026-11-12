"""Consistent backup of the SQLite database, keeping the last N days.

On the server (from cron):
    docker compose exec -T web python scripts/backup_db.py
Writes data/backups/cycles-YYYYMMDD.db and deletes backups older than --keep-days.
"""
import argparse
import re
import sqlite3
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAME = re.compile(r"^cycles-(\d{8})\.db$")


def backup(db_path: Path, backup_dir: Path, keep_days: int = 14, today: date | None = None) -> Path:
    today = today or date.today()
    if not db_path.exists():
        raise FileNotFoundError(f"Database non trovato: {db_path}")
    backup_dir.mkdir(parents=True, exist_ok=True)

    target = backup_dir / f"cycles-{today:%Y%m%d}.db"
    tmp = target.with_suffix(".db.tmp")
    # SQLite's online backup API: safe while the web app and the bot are writing.
    # (sqlite3's context manager doesn't close connections, so close them explicitly.)
    src, dst = sqlite3.connect(db_path), sqlite3.connect(tmp)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    tmp.replace(target)

    cutoff = today - timedelta(days=keep_days)
    for f in backup_dir.iterdir():
        m = NAME.match(f.name)
        if m and date(int(m[1][:4]), int(m[1][4:6]), int(m[1][6:])) < cutoff:
            f.unlink()
    return target


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--db", type=Path, default=ROOT / "data" / "cycles.db")
    p.add_argument("--dir", type=Path, default=ROOT / "data" / "backups")
    p.add_argument("--keep-days", type=int, default=14)
    args = p.parse_args()
    target = backup(args.db, args.dir, args.keep_days)
    print(f"Backup creato: {target} ({target.stat().st_size} byte)")


if __name__ == "__main__":
    main()
