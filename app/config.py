from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    db_url: str = f"sqlite:///{(ROOT / 'data' / 'cycles.db').as_posix()}"
    csv_path: Path = ROOT / "data" / "cycles_with_durations.csv"
    telegram_token: str = ""
    allowed_chat_id: int = 0
    tz: str = "Europe/Rome"
    reminder_hour: int = 9
    gap_days: int = 45
    bleed_days: int = 7
    min_length: int = 20
    max_length: int = 45


settings = Settings()
