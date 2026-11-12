from collections.abc import Iterator

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine

from app.config import settings

BUSY_TIMEOUT_MS = 5000


def configure_sqlite(eng: Engine) -> Engine:
    """WAL lets the web app and the bot read while the other writes; busy_timeout waits for locks instead of failing."""
    if eng.dialect.name != "sqlite":
        return eng

    @event.listens_for(eng, "connect")
    def _set_pragmas(dbapi_conn, _record) -> None:
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")
        cur.close()

    return eng


engine = configure_sqlite(create_engine(settings.db_url, connect_args={"check_same_thread": False}))


def init_db(eng=None) -> None:
    from app import models  # noqa: F401  (register tables)

    SQLModel.metadata.create_all(eng or engine)


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
