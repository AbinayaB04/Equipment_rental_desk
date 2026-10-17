"""Database connection and session factory."""

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings

_settings = Settings.from_env()

# Connect args or pool config can be customized if needed
engine = (
    create_engine(
        _settings.database_url,
        pool_pre_ping=True,
    )
    if _settings.database_url
    else None
)

SessionLocal = (
    sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )
    if engine
    else None
)


def get_session_factory(database_url: str | None = None) -> sessionmaker[Session]:
    """Get or create a sessionmaker for a specific database URL."""
    url = database_url or Settings.from_env().database_url
    if not url:
        raise ValueError("DATABASE_URL is not configured.")
    eng = create_engine(url, pool_pre_ping=True)
    return sessionmaker(autocommit=False, autoflush=False, bind=eng)


@contextmanager
def session_scope(database_url: str | None = None) -> Generator[Session, None, None]:
    """Provide a transactional scope around a series of operations."""
    factory = (
        get_session_factory(database_url)
        if database_url
        else (SessionLocal or get_session_factory())
    )
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency for yielding database sessions."""
    with session_scope() as session:
        yield session
