"""Shared pytest fixtures."""

from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import app.models  # noqa: F401
from app.models.base import Base


@pytest.fixture
def session() -> Generator[Session, None, None]:
    """Provide a clean in-memory SQLite database session for unit and domain service tests."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    db = factory()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()
