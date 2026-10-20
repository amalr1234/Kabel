from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, declarative_base

engine = create_engine(
    "sqlite:///./solvia_dev.db",
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

_SQLITE_COLUMNS = {
    "tickets": {
        "sap_notes": "TEXT",
        "transactions": "TEXT",
        "error_codes": "TEXT",
        "support_level": "TEXT",
        "support_level_reason": "TEXT",
    },
    "feedback": {
        "committed_ticket_id": "TEXT",
    },
    "solution_usage": {
        "evidence_json": "TEXT",
        "solution_title": "TEXT",
        "blueprint_json": "TEXT",
        "query_system": "TEXT",
        "query_category": "TEXT",
        "query_support_level": "TEXT",
        "suggested_support_level": "TEXT",
    },
}


def ensure_schema() -> None:
    """Create missing tables and add new SQLite columns for existing DBs."""
    from app import models  # noqa: F401 — register metadata

    Base.metadata.create_all(bind=engine)
    inspector = inspect(engine)
    with engine.begin() as conn:
        for table, columns in _SQLITE_COLUMNS.items():
            if table not in inspector.get_table_names():
                continue
            existing = {col["name"] for col in inspector.get_columns(table)}
            for name, ddl in columns.items():
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
