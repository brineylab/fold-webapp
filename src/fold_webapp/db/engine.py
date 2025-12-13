from __future__ import annotations

from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from fold_webapp.config import get_settings


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """
    Return a process-wide SQLAlchemy Engine.

    Notes:
    - We use a safe fallback for `database_url` until `Settings` grows this field
      (added in a later step of the plan). This keeps imports working while the
      migration is in progress.
    """
    settings = get_settings()
    database_url = getattr(settings, "database_url", "sqlite:///fold_webapp.db")
    return create_engine(database_url, future=True)


def get_session() -> Session:
    """Create a new Session. Callers are responsible for closing it."""
    engine = get_engine()
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    return SessionLocal()


