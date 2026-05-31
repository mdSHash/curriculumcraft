"""Database setup and session management."""

from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from config import get_settings

settings = get_settings()

# Ensure the directory for the database file exists
db_path = Path(settings.DB_PATH)
db_path.parent.mkdir(parents=True, exist_ok=True)

# SQLAlchemy engine
engine = create_engine(
    f"sqlite:///{settings.DB_PATH}",
    connect_args={"check_same_thread": False},
    echo=False,
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""

    pass


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables() -> None:
    """Create all tables in the database.

    Note: All ORM models must be imported before calling this function
    so that Base.metadata knows about them. The main.py module imports
    the `models` package which registers all models including ChunkMetadata.
    """
    Base.metadata.create_all(bind=engine)
    _run_migrations()


def _run_migrations() -> None:
    """Run lightweight schema migrations for SQLite (add missing columns)."""
    import sqlite3

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    def add_column_if_missing(table: str, column: str, ddl: str) -> None:
        cursor.execute(f"PRAGMA table_info({table})")
        existing = {row[1] for row in cursor.fetchall()}
        if column not in existing:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")
            conn.commit()

    # Workbooks
    add_column_if_missing("workbooks", "error_message",    "error_message TEXT")
    add_column_if_missing("workbooks", "progress",         "progress INTEGER NOT NULL DEFAULT 0")
    add_column_if_missing("workbooks", "progress_message", "progress_message TEXT")

    # Exams
    add_column_if_missing("exams", "progress",         "progress INTEGER NOT NULL DEFAULT 0")
    add_column_if_missing("exams", "progress_message", "progress_message TEXT")

    conn.close()
