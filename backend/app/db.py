from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def _normalize_db_url(url: str) -> str:
    if url.startswith("postgresql+asyncpg"):
        return url.replace("postgresql+asyncpg", "postgresql+psycopg2")
    if url.startswith("postgresql://"):
        return url  # psycopg2-binary
    # Fallback to sqlite for local dev if nothing provided
    return url


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./local.db")
DATABASE_URL = _normalize_db_url(DATABASE_URL)

engine = create_engine(DATABASE_URL, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


@contextmanager
def get_session() -> Iterator:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

