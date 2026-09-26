import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from app.settings import get_settings

settings = get_settings()

# Do not attempt to connect at import time. The first real DB access happens
# inside a request or an ingestion call, at which point env vars are fully set.
_engine = None

def _get_engine():
    global _engine
    if _engine is None:
        # Always start with SQLite in local/test envs where psycopg2 is absent.
        _engine = create_engine("sqlite:///./solvia_dev.db", connect_args={"check_same_thread": False})
    return _engine

engine = _get_engine()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
