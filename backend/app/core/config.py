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
    allow_test_clock: bool = False
    test_clock_key: str = ""

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Self:
        source = os.environ if env is None else env
        app_env = source.get("APP_ENV", DEFAULT_APP_ENV).strip().lower()
        raw_allow = source.get("ALLOW_TEST_CLOCK", "").strip().lower() in ("true", "1", "yes")

        # Hard guard: In production, test clock is ALWAYS False, even if ALLOW_TEST_CLOCK=true
        allow_test_clock = raw_allow and app_env != "production"

        return cls(
            app_env=app_env,
            database_url=source.get("DATABASE_URL", ""),
            cors_origins=_split_csv(source.get("CORS_ORIGINS", "")),
            log_level=source.get("LOG_LEVEL", "INFO").upper(),
            allow_test_clock=allow_test_clock,
            test_clock_key=source.get("TEST_CLOCK_KEY", ""),
        )
