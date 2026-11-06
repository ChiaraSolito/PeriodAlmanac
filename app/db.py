from collections.abc import Iterator

from sqlmodel import Session, SQLModel, create_engine

from app.config import settings

engine = create_engine(settings.db_url, connect_args={"check_same_thread": False})


def init_db(eng=None) -> None:
    from app import models  # noqa: F401  (register tables)

    SQLModel.metadata.create_all(eng or engine)


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
