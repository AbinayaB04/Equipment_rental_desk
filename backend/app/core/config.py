"""Application settings, read from environment variables."""

import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Self

# Unset APP_ENV means production, so a forgotten variable never enables development-only behaviour.
DEFAULT_APP_ENV = "production"


def _split_csv(value: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in value.split(",") if part.strip())


@dataclass(frozen=True)
class Settings:
    app_env: str
    database_url: str
    cors_origins: tuple[str, ...]
    log_level: str

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Self:
        source = os.environ if env is None else env
        return cls(
            app_env=source.get("APP_ENV", DEFAULT_APP_ENV),
            database_url=source.get("DATABASE_URL", ""),
            cors_origins=_split_csv(source.get("CORS_ORIGINS", "")),
            log_level=source.get("LOG_LEVEL", "INFO").upper(),
        )
