"""Database setup and session management."""

import json
import logging
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine, select
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from config import get_settings

logger = logging.getLogger(__name__)
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
    """Create all tables in the database, run migrations, then seed taxonomy.

    Note: All ORM models must be imported before calling this function so
    that Base.metadata knows about them. The main.py module imports the
    `models` package which registers Book, Chapter, ChunkMetadata, Exam,
    Subject, Topic, and Workbook.
    """
    Base.metadata.create_all(bind=engine)
    _run_migrations()
    _seed_subjects()


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
    add_column_if_missing("workbooks", "subject_key",      "subject_key VARCHAR(40)")

    # Exams
    add_column_if_missing("exams", "progress",         "progress INTEGER NOT NULL DEFAULT 0")
    add_column_if_missing("exams", "progress_message", "progress_message TEXT")
    add_column_if_missing("exams", "subject_key",      "subject_key VARCHAR(40)")

    # Books — multi-subject support (Phase 1).
    # Existing rows default to 'math' so the 3 already-ingested books behave
    # identically to before this migration.
    add_column_if_missing("books", "subject_key",          "subject_key VARCHAR(40)")
    add_column_if_missing("books", "is_legacy_curriculum", "is_legacy_curriculum BOOLEAN NOT NULL DEFAULT 0")
    add_column_if_missing("books", "primary_language",     "primary_language VARCHAR(10) NOT NULL DEFAULT 'ar'")

    # Backfill subject_key for any pre-migration row.
    cursor.execute("UPDATE books      SET subject_key = 'math' WHERE subject_key IS NULL")
    cursor.execute("UPDATE workbooks  SET subject_key = 'math' WHERE subject_key IS NULL")
    cursor.execute("UPDATE exams      SET subject_key = 'math' WHERE subject_key IS NULL")
    conn.commit()
    conn.close()


def _seed_subjects() -> None:
    """Seed the subjects table from backend/data/subjects_seed.json.

    Idempotent: existing rows are updated in place so edits to the seed
    JSON propagate to running deployments on next restart. Rows present
    in the DB but missing from the seed file are left untouched (forward
    compatibility for hand-added subjects).
    """
    seed_path = Path(__file__).resolve().parent / "seeds" / "subjects.json"
    if not seed_path.exists():
        logger.warning("subjects.json not found at %s; skipping seed", seed_path)
        return

    try:
        with seed_path.open("r", encoding="utf-8") as f:
            seed_data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.error("Failed to load subjects.json: %s", e)
        return

    # Import lazily to avoid a hard cycle (database.py -> models.subject ->
    # database.Base) at module-import time. By the time _seed_subjects()
    # is called from create_tables(), the model is already registered.
    from models.subject import Subject

    session = SessionLocal()
    try:
        existing = {s.key: s for s in session.execute(select(Subject)).scalars().all()}
        added = updated = 0

        for row in seed_data:
            key = row.get("key")
            if not key:
                continue

            payload = {
                "label_en": row.get("label_en", key),
                "label_ar": row.get("label_ar", key),
                "moe_catalog_labels": row.get("moe_catalog_labels", []),
                "content_traits": row.get("content_traits", {}),
                "default_topic_sections": row.get("default_topic_sections", []),
                "letterhead_lines_ar": row.get("letterhead_lines_ar", []),
                "letterhead_lines_en": row.get("letterhead_lines_en", []),
            }

            if key in existing:
                subject = existing[key]
                for field, value in payload.items():
                    setattr(subject, field, value)
                updated += 1
            else:
                session.add(Subject(key=key, **payload))
                added += 1

        session.commit()
        logger.info(
            "Subjects seeded: %d added, %d updated (total in DB: %d)",
            added, updated, len(seed_data),
        )
    except Exception as e:
        session.rollback()
        logger.error("Failed to seed subjects: %s", e, exc_info=True)
    finally:
        session.close()
