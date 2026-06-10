from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings

_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    redis_url: str = "redis://localhost:6379/0"
    data_provider: str = "espn"  # espn | footballdata
    football_data_token: str | None = None
    allowed_origins: str = "*"  # comma-separated, or * for any
    poll_enabled: bool = True
    debug_dir: str = "debug"
    db_path: str = str(_ROOT / "db" / "players.sqlite")

    model_config = {"env_file": ".env", "extra": "ignore"}

    @property
    def origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


@lru_cache
def settings() -> Settings:
    return Settings()
