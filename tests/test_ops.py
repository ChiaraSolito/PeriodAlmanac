"""SQLite concurrency settings and backups (deployment, issue #9)."""
import sqlite3
import sys
import threading
import time
from datetime import date
from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine, text

from app.db import BUSY_TIMEOUT_MS, configure_sqlite
from app.services.cycles import add_cycle, list_cycles

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from backup_db import backup  # noqa: E402


def _file_engine(path: Path):
    eng = configure_sqlite(create_engine(f"sqlite:///{path.as_posix()}", connect_args={"check_same_thread": False}))
    SQLModel.metadata.create_all(eng)
    return eng


def test_wal_and_busy_timeout_are_set(tmp_path):
    eng = _file_engine(tmp_path / "c.db")
    with eng.connect() as conn:
        assert conn.execute(text("PRAGMA journal_mode")).scalar() == "wal"
        assert conn.execute(text("PRAGMA busy_timeout")).scalar() == BUSY_TIMEOUT_MS


def test_write_waits_for_other_writer_instead_of_failing(tmp_path):
    db = tmp_path / "c.db"
    eng = _file_engine(db)

    # Another process (e.g. the bot) holds the write lock for a moment.
    holder = sqlite3.connect(db, isolation_level=None, check_same_thread=False)
    holder.execute("BEGIN IMMEDIATE")
    threading.Timer(0.5, holder.commit).start()

    start = time.monotonic()
    with Session(eng) as s:
        add_cycle(s, date(2026, 1, 1), today=date(2026, 11, 6))
        assert len(list_cycles(s)) == 1
    assert time.monotonic() - start >= 0.4  # it waited for the lock
    holder.close()


def test_backup_creates_copy_and_prunes_old(tmp_path):
    db = tmp_path / "c.db"
    eng = _file_engine(db)
    with Session(eng) as s:
        add_cycle(s, date(2026, 1, 1), today=date(2026, 11, 6))

    out = tmp_path / "backups"
    out.mkdir()
    (out / "cycles-20261020.db").write_bytes(b"old")  # 17 days before: pruned
    (out / "cycles-20261101.db").write_bytes(b"recent")  # kept
    (out / "notes.txt").write_text("not a backup")  # untouched

    target = backup(db, out, keep_days=14, today=date(2026, 11, 6))

    assert target.name == "cycles-20261106.db"
    conn = sqlite3.connect(target)
    assert conn.execute("SELECT COUNT(*) FROM cycle").fetchone()[0] == 1
    conn.close()
    assert sorted(f.name for f in out.iterdir()) == ["cycles-20261101.db", "cycles-20261106.db", "notes.txt"]
