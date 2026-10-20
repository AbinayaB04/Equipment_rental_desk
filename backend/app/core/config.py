"""Application settings, read from environment variables."""

import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Self

# Unset APP_ENV means production, so a forgotten variable never enables development-only behaviour.
DEFAULT_APP_ENV = "production"


def _split_csv(value: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in value.split(",") if part.strip())


MIN_TEST_CLOCK_KEY_LENGTH = 16


@dataclass(frozen=True)
class Settings:
    app_env: str
    database_url: str
    cors_origins: tuple[str, ...]
    log_level: str
    allow_test_clock: bool = False
    test_clock_key: str = ""

    def __post_init__(self) -> None:
        if self.app_env == "production" and self.allow_test_clock:
            if not self.test_clock_key:
                raise ValueError("TEST_CLOCK_KEY is required to enable test clock in production.")
            if len(self.test_clock_key) < MIN_TEST_CLOCK_KEY_LENGTH:
                raise ValueError(
                    f"TEST_CLOCK_KEY must be at least {MIN_TEST_CLOCK_KEY_LENGTH} "
                    "characters long in production."
                )

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Self:
        source = os.environ if env is None else env
        app_env = source.get("APP_ENV", DEFAULT_APP_ENV).strip().lower()
        raw_allow = source.get("ALLOW_TEST_CLOCK", "").strip().lower() in ("true", "1", "yes")
        test_clock_key = source.get("TEST_CLOCK_KEY", "").strip()

        if app_env == "production" and raw_allow:
            if not test_clock_key:
                raise ValueError("TEST_CLOCK_KEY is required to enable test clock in production.")
            if len(test_clock_key) < MIN_TEST_CLOCK_KEY_LENGTH:
                raise ValueError(
                    f"TEST_CLOCK_KEY must be at least {MIN_TEST_CLOCK_KEY_LENGTH} "
                    "characters long in production."
                )
            allow_test_clock = True
        elif raw_allow:
            allow_test_clock = True
        else:
            allow_test_clock = False

        return cls(
            app_env=app_env,
            database_url=source.get("DATABASE_URL", ""),
            cors_origins=_split_csv(source.get("CORS_ORIGINS", "")),
            log_level=source.get("LOG_LEVEL", "INFO").upper(),
            allow_test_clock=allow_test_clock,
            test_clock_key=test_clock_key,
        )
