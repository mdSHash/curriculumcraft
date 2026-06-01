"""MOE eLibrary API router — browse and import official textbooks across
every subject in the catalog (math, arabic, languages, sciences, ICT, …)."""

import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import SessionLocal, get_db
from models.book import Book
from models.subject import Subject
from services.moe_library_service import MOELibraryService
from services.subjects.registry import resolve_subject_key_from_moe_label

router = APIRouter(prefix="/moe-library", tags=["moe-library"])
logger = logging.getLogger(__name__)

# Singleton service instance
_moe_service = MOELibraryService()


class ImportRequest(BaseModel):
    """Request body for importing a book from MOE eLibrary."""
    book_id: str


class ImportResponse(BaseModel):
    """Response after initiating a book import."""
    id: int
    title: str
    status: str
    subject_key: Optional[str] = None
    message: str


def _validate_subject_key(db: Session, subject_key: Optional[str]) -> Optional[str]:
    """Return subject_key if valid, raise 400 if unknown, return None for empty."""
    if not subject_key:
        return None
    exists = db.query(Subject).filter(Subject.key == subject_key).first()
    if exists is None:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unknown subject key: {subject_key!r}. "
                f"See GET /api/subjects for the valid taxonomy."
            ),
        )
    return subject_key


@router.get("/books")
async def get_moe_books(
    subject: Optional[str] = None,
    grade: Optional[str] = None,
    stage: Optional[str] = None,
    db: Session = Depends(get_db),
) -> list[dict]:
    """Browse books in the MOE eLibrary catalog.

    Args:
        subject: Optional canonical subject key (e.g. 'math', 'arabic_lang',
                 'physics'). Omit to browse all subjects across the catalog.
        grade: Optional grade key (e.g. 'primary1', 'secondary2').
        stage: Optional stage key ('primary', 'preparatory', 'secondary').
    """
    subject_key = _validate_subject_key(db, subject)
    try:
        return await _moe_service.get_books(
            db=db,
            subject_key=subject_key,
            grade_level=grade,
            stage=stage,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/assessments")
async def get_moe_assessments(
    subject: Optional[str] = None,
    grade: Optional[str] = None,
    stage: Optional[str] = None,
    week: Optional[int] = None,
    db: Session = Depends(get_db),
) -> list[dict]:
    """Browse the official weekly-assessments catalog.

    Backed by https://ellibrary.moe.gov.eg/cha/books.json — Classroom &
    Home Assessments published by curriculum-development departments
    across all subjects.

    Args:
        subject: Optional canonical subject key. Omit for all subjects.
        grade: Optional grade key.
        stage: Optional stage key.
        week: Optional 1-based week number (1..11).
    """
    subject_key = _validate_subject_key(db, subject)
    try:
        return await _moe_service.get_assessments(
            db=db,
            subject_key=subject_key,
            grade_level=grade,
            stage=stage,
            week=week,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/assessments/grades")
async def get_assessment_grades(
    subject: Optional[str] = None,
    db: Session = Depends(get_db),
) -> list[dict]:
    """Return available (grade, subject, term) tuples for assessments.

    Drives the frontend grade picker so it only shows grades that actually
    have weekly assessments published. Pass `subject` to scope to one
    subject; omit to span the whole catalog.
    """
    subject_key = _validate_subject_key(db, subject)
    try:
        all_items = await _moe_service.get_assessments(
            db=db, subject_key=subject_key
        )
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))

    seen: dict[tuple, dict] = {}
    for item in all_items:
        key = (
            item.get("grade_key", ""),
            item.get("grade", ""),
            item.get("title", ""),
            item.get("term", ""),
        )
        bucket = seen.setdefault(
            key,
            {
                "grade_key": key[0],
                "grade": key[1],
                "subject": key[2],
                "term": key[3],
                "weeks": set(),
            },
        )
        wk = item.get("week_number")
        if wk is not None:
            bucket["weeks"].add(wk)

    out = []
    for v in seen.values():
        v["weeks"] = sorted(v["weeks"])
        v["count"] = len(v["weeks"])
        out.append(v)
    out.sort(key=lambda x: (x["grade_key"], x["subject"]))
    return out


@router.get("/stages")
async def get_available_stages(
    subject: Optional[str] = None,
    db: Session = Depends(get_db),
) -> list[dict]:
    """Get available stages (educational levels) with their book counts.

    Pass `subject` to count books for a single canonical subject; omit to
    count the whole catalog.
    """
    subject_key = _validate_subject_key(db, subject)
    try:
        all_books = await _moe_service.get_books(db=db, subject_key=subject_key)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))

    stage_counts: dict[str, int] = {}
    for book in all_books:
        stage_key = book.get("stage_key", "")
        if stage_key:
            stage_counts[stage_key] = stage_counts.get(stage_key, 0) + 1

    stages = [
        {"key": "primary", "label_ar": "الإبتدائية", "label_en": "Primary", "count": stage_counts.get("primary", 0)},
        {"key": "preparatory", "label_ar": "الإعدادية", "label_en": "Preparatory", "count": stage_counts.get("preparatory", 0)},
        {"key": "secondary", "label_ar": "الثانوي العام", "label_en": "Secondary", "count": stage_counts.get("secondary", 0)},
    ]
    return stages


@router.get("/catalog-subjects")
async def get_catalog_subjects(db: Session = Depends(get_db)) -> list[dict]:
    """List the distinct subjects present in the MOE textbook catalog.

    Each entry maps a raw MOE catalog `subject` string to its canonical
    subject_key (or null if the alias doesn't match the seeded taxonomy
    yet). Useful for spotting catalog drift after MOE adds new subjects.
    """
    try:
        return await _moe_service.list_catalog_subjects(db=db)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


async def _run_moe_ingestion(book_id: int, file_path: str) -> None:
    """Background task to run the ingestion pipeline for an MOE-imported book."""
    from services.ingestion_pipeline import IngestionPipeline

    db = SessionLocal()
    try:
        pipeline = IngestionPipeline(db=db, book_id=book_id, file_path=file_path)
        await pipeline.run()
    except Exception as e:
        logger.error(f"MOE book ingestion failed for book {book_id}: {e}")
        try:
            book = db.query(Book).filter(Book.id == book_id).first()
            if book:
                book.status = "error"
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


@router.post("/import", response_model=ImportResponse)
async def import_moe_book(
    request: ImportRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> ImportResponse:
    """Download and import a book from MOE eLibrary into the system."""
    moe_book = await _moe_service.get_book_by_id(request.book_id)
    if not moe_book:
        raise HTTPException(status_code=404, detail="Book not found in MOE catalog.")

    pdf_url = moe_book.get("link", "")
    if not pdf_url:
        raise HTTPException(status_code=400, detail="Book has no PDF link.")

    # Resolve canonical subject_key from the MOE catalog's subject string
    # (handles hamza variants + the legacy '-قديم' Chinese guard).
    moe_subject = moe_book.get("subject", "")
    resolved_subject_key = (
        resolve_subject_key_from_moe_label(db, moe_subject) or "math"
    )

    # Look up display labels for the resolved subject so the Book row
    # carries human-readable strings, not just the slug.
    subject_row = (
        db.query(Subject).filter(Subject.key == resolved_subject_key).first()
    )
    subject_label = (
        subject_row.label_en if subject_row else moe_subject or "Curriculum"
    )

    # Skip re-import if we already have this exact (title, grade, term).
    existing = db.query(Book).filter(
        Book.title == moe_subject,
        Book.grade_level == moe_book.get("grade", ""),
        Book.term == ("1" if "الأول" in moe_book.get("term", "") else "2"),
    ).first()
    if existing:
        return ImportResponse(
            id=existing.id,
            title=existing.title,
            status=existing.status,
            subject_key=existing.subject_key,
            message="Book already imported.",
        )

    try:
        filename = f"moe_{request.book_id}_{pdf_url.split('/')[-1]}"
        file_path = await _moe_service.download_book_pdf(pdf_url, filename=filename)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=f"Failed to download book: {e}")

    term_number = "1" if "الأول" in moe_book.get("term", "") else "2"
    book = Book(
        title=moe_subject or "Unknown",
        grade_level=moe_book.get("grade", ""),
        academic_year="2025-2026",
        term=term_number,
        subject=subject_label,
        subject_key=resolved_subject_key,
        is_legacy_curriculum="-قديم" in moe_subject,
        primary_language="ar",
        filename=filename,
        file_path=file_path,
        total_pages=0,
        chapters_detected=0,
        status="processing",
    )
    db.add(book)
    db.commit()
    db.refresh(book)

    background_tasks.add_task(_run_moe_ingestion, book.id, file_path)

    return ImportResponse(
        id=book.id,
        title=book.title,
        status="processing",
        subject_key=book.subject_key,
        message="Book download complete. Ingestion started.",
    )
