from datetime import date, datetime, timezone

from sqlmodel import Field, SQLModel


class Cycle(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    start_date: date = Field(unique=True, index=True)
    end_date: date
    # Days since the previous start (same convention as the original CSV).
    cycle_length: int | None = None
    # True when cycle_length > GAP_DAYS: probably unlogged cycles, excluded from stats/training.
    is_gap: bool = False
    source: str = "web"  # import | web | bot
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ReminderLog(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    kind: str = Field(index=True)  # pre | day | late | gap
    target_date: date  # predicted start (or last start for 'gap') the reminder refers to
    sent_on: date
