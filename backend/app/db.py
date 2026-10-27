"""SQLAlchemy engine and session dependency."""
from __future__ import annotations

import os
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./pixi.db")
_engine_kwargs: dict[str, object] = {"pool_pre_ping": True}
if DATABASE_URL.startswith("sqlite"):
    _engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, **_engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    """Base class for persisted Pixi models."""


def get_db() -> Generator[Session, None, None]:
    """Yield a session and always close it after request handling."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
