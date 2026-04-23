"""Database engine and session factory.

Single source of truth for DB access. Works with SQLite (local) or Postgres (Railway)
based on DATABASE_URL env var.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from contextlib import contextmanager

from app.core.config import settings


class Base(DeclarativeBase):
    """Base for all ORM models."""
    pass


def _engine_kwargs(url: str) -> dict:
    if url.startswith("sqlite"):
        return {"connect_args": {"check_same_thread": False}}
    return {"pool_pre_ping": True, "pool_size": 5, "max_overflow": 10}


engine = create_engine(settings.database_url, **_engine_kwargs(settings.database_url))
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db():
    """FastAPI dependency — yields a DB session, guarantees close."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope():
    """Context manager for scripts / background jobs."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db():
    """Create tables if they don't exist. Idempotent."""
    from app.models import (  # noqa: F401 — import side effects register models
        campaign, journey, event, trend, competitive,
        opportunity, action, scenario, override, global_signal,
    )
    Base.metadata.create_all(bind=engine)
