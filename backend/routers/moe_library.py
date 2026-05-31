"""MOE eLibrary API router — browse and import official textbooks."""

import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import SessionLocal, get_db
from models.book import Book
from services.moe_library_service import MOELibraryService

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
    message: str


@router.get("/books")
async def get_moe_books(
    subject: str = "math",
    grade: Optional[str] = None,
    stage: Optional[str] = None,
) -> list[dict]:
    """Get available books from MOE eLibrary.

    Args:
        subject: Subject filter. Currently only 'math' is supported.
        grade: Optional grade key (e.g., 'primary1', 'secondary2').
        stage: Optional stage key (e.g., 'primary', 'preparatory', 'secondary').

    Returns:
        List of available math books with metadata.
    """
    if subject != "math":
        raise HTTPException(
            status_code=400,
            detail="Only 'math' subject is currently supported.",
        )

    try:
        books = await _moe_service.get_math_books(grade_level=grade, stage=stage)
        return books
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/assessments")
async def get_moe_assessments(
    subject: str = "math",
    grade: Optional[str] = None,
    stage: Optional[str] = None,
    week: Optional[int] = None,
) -> list[dict]:
    """Browse official weekly assessments from the MOE eLibrary.

    Backed by https://ellibrary.moe.gov.eg/cha/books.json — the
    Classroom & Home Assessments catalog (Mathematics Curriculum
    Development Department).

    Args:
        subject: Subject filter. Currently only 'math' is supported.
        grade: Optional grade key (e.g. 'secondary1', 'secondary2').
        stage: Optional stage key (e.g. 'secondary').
        week: Optional 1-based week number (1..11).

    Returns:
        List of available math weekly assessments with metadata.
    """
    if subject != "math":
        raise HTTPException(
            status_code=400,
            detail="Only 'math' subject is currently supported.",
        )
    try:
        return await _moe_service.get_math_assessments(
            grade_level=grade, stage=stage, week=week
        )
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/assessments/grades")
async def get_assessment_grades() -> list[dict]:
    """Return available (grade, subject, term) tuples for assessments.

    Useful so the frontend grade picker only shows grades that actually
    have weekly assessments published (currently Secondary 1 & 2 only).
    """
    try:
        all_math = await _moe_service.get_math_assessments()
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))

    # Distinct (grade_key, grade, subject, term) with weekly count
    seen: dict[tuple, dict] = {}
    for item in all_math:
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
async def get_available_stages() -> list[dict]:
    """Get available stages (educational levels) with their math book counts."""
    try:
        all_math = await _moe_service.get_math_books()
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))

    # Count books per stage
    stage_counts: dict[str, int] = {}
    for book in all_math:
        stage_key = book.get("stage_key", "")
        if stage_key:
            stage_counts[stage_key] = stage_counts.get(stage_key, 0) + 1

    stages = [
        {"key": "primary", "label_ar": "الإبتدائية", "label_en": "Primary", "count": stage_counts.get("primary", 0)},
        {"key": "preparatory", "label_ar": "الإعدادية", "label_en": "Preparatory", "count": stage_counts.get("preparatory", 0)},
        {"key": "secondary", "label_ar": "الثانوي العام", "label_en": "Secondary", "count": stage_counts.get("secondary", 0)},
    ]
    return stages


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
    """Download and import a book from MOE eLibrary into the system.

    Steps:
        1. Look up the book in the MOE catalog by ID
        2. Download the PDF
        3. Create a database record
        4. Run the ingestion pipeline (same as manual upload)
        5. Return the book record
    """
    # 1. Find the book in the catalog
    moe_book = await _moe_service.get_book_by_id(request.book_id)
    if not moe_book:
        raise HTTPException(status_code=404, detail="Book not found in MOE catalog.")

    pdf_url = moe_book.get("link", "")
    if not pdf_url:
        raise HTTPException(status_code=400, detail="Book has no PDF link.")

    # Check if this book was already imported
    existing = db.query(Book).filter(
        Book.title == moe_book.get("subject", ""),
        Book.grade_level == moe_book.get("grade", ""),
        Book.term == ("1" if "الأول" in moe_book.get("term", "") else "2"),
    ).first()
    if existing:
        return ImportResponse(
            id=existing.id,
            title=existing.title,
            status=existing.status,
            message="Book already imported.",
        )

    # 2. Download the PDF
    try:
        filename = f"moe_{request.book_id}_{pdf_url.split('/')[-1]}"
        file_path = await _moe_service.download_book_pdf(pdf_url, filename=filename)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=f"Failed to download book: {e}")

    # 3. Create database record
    term_number = "1" if "الأول" in moe_book.get("term", "") else "2"
    book = Book(
        title=moe_book.get("subject", "Unknown"),
        grade_level=moe_book.get("grade", ""),
        academic_year="2025-2026",
        term=term_number,
        subject="Mathematics",
        filename=filename,
        file_path=file_path,
        total_pages=0,
        chapters_detected=0,
        status="processing",
    )
    db.add(book)
    db.commit()
    db.refresh(book)

    # 4. Run ingestion pipeline in background
    background_tasks.add_task(_run_moe_ingestion, book.id, file_path)

    return ImportResponse(
        id=book.id,
        title=book.title,
        status="processing",
        message="Book download complete. Ingestion started.",
    )
