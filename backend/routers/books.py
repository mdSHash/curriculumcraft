"""Books API router — upload, list, outline, delete."""

import logging
import shutil
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from config import get_settings
from database import SessionLocal, get_db
from models.book import Book
from models.chapter import Chapter
from models.subject import Subject
from models.topic import Topic
from schemas.book import BookOutline, BookResponse, ChapterInfo, LessonInfo, TopicInfo
from utils.file_utils import get_upload_path

router = APIRouter(prefix="/books", tags=["books"])
settings = get_settings()
logger = logging.getLogger(__name__)


async def _run_ingestion(book_id: int, file_path: str) -> None:
    """Background task to run the ingestion pipeline.

    Args:
        book_id: The book's database ID.
        file_path: Path to the uploaded PDF file.
    """
    from services.ingestion_pipeline import IngestionPipeline

    # Create a new session for the background task
    db = SessionLocal()
    try:
        pipeline = IngestionPipeline(db=db, book_id=book_id, file_path=file_path)
        await pipeline.run()
    except Exception as e:
        logger.error(f"Background ingestion failed for book {book_id}: {e}")
        # Try to mark book as error
        try:
            book = db.query(Book).filter(Book.id == book_id).first()
            if book:
                book.status = "error"
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


@router.post("/upload", response_model=BookResponse, status_code=201)
async def upload_book(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: str = Form(...),
    grade_level: str = Form(""),
    academic_year: str = Form(""),
    term: str = Form(""),
    subject: str = Form("Mathematics"),
    subject_key: str = Form("math"),
    primary_language: str = Form("ar"),
    db: Session = Depends(get_db),
) -> BookResponse:
    """Upload a curriculum textbook (PDF or DOCX) and trigger ingestion pipeline.

    Args:
        subject_key: Canonical subject key (one of the 24 keys in /api/subjects).
                     Defaults to 'math' for backwards compat with existing
                     uploaders. Validated against the Subject taxonomy.
        primary_language: ISO code for the textbook's primary language
                          ('ar' | 'en' | 'fr' | 'de' | 'es' | 'it' | 'zh').
                          Drives prompt language and font selection.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided.")

    allowed_extensions = (".pdf", ".docx")
    file_lower = file.filename.lower()
    if not any(file_lower.endswith(ext) for ext in allowed_extensions):
        raise HTTPException(
            status_code=400,
            detail="Only PDF and DOCX files are accepted.",
        )

    # Validate subject_key against the canonical taxonomy.
    if not db.query(Subject).filter(Subject.key == subject_key).first():
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unknown subject_key: {subject_key!r}. "
                f"See GET /api/subjects for the valid taxonomy."
            ),
        )

    # Save the uploaded file
    upload_path = get_upload_path(file.filename)
    path_obj = Path(upload_path)
    path_obj.parent.mkdir(parents=True, exist_ok=True)

    with open(upload_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Create database record
    book = Book(
        title=title,
        grade_level=grade_level,
        academic_year=academic_year,
        term=term,
        subject=subject,
        subject_key=subject_key,
        primary_language=primary_language or "ar",
        filename=file.filename,
        file_path=upload_path,
        total_pages=0,
        chapters_detected=0,
        status="processing",
    )
    db.add(book)
    db.commit()
    db.refresh(book)

    # Trigger ingestion pipeline in the background
    background_tasks.add_task(_run_ingestion, book.id, upload_path)

    logger.info(
        f"Book uploaded: id={book.id}, title='{book.title}', "
        f"file='{book.filename}'. Ingestion started."
    )

    return BookResponse.model_validate(book)


@router.get("", response_model=list[BookResponse])
def list_books(db: Session = Depends(get_db)) -> list[BookResponse]:
    """List all uploaded books."""
    books = db.query(Book).order_by(Book.created_at.desc()).all()
    return [BookResponse.model_validate(b) for b in books]


@router.get("/{book_id}", response_model=BookResponse)
def get_book(book_id: int, db: Session = Depends(get_db)) -> BookResponse:
    """Get a single book by ID."""
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found.")
    return BookResponse.model_validate(book)


@router.get("/{book_id}/outline", response_model=BookOutline)
def get_book_outline(book_id: int, db: Session = Depends(get_db)) -> BookOutline:
    """Get the chapter/topic outline for a book from the database."""
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found.")

    # Fetch chapters with their topics
    chapters = (
        db.query(Chapter)
        .filter(Chapter.book_id == book_id)
        .order_by(Chapter.chapter_num)
        .all()
    )

    chapter_infos: list[ChapterInfo] = []
    for index, chapter in enumerate(chapters):
        # Fetch topics for this chapter
        topics = (
            db.query(Topic)
            .filter(Topic.chapter_id == chapter.id)
            .order_by(Topic.page_num)
            .all()
        )

        topic_infos = [
            TopicInfo(
                id=topic.id,
                title=topic.title or f"Topic {idx + 1}",
                content_type=topic.content_type or "concept",
                difficulty=topic.difficulty or "beginner",
                page_start=topic.page_num,
                page_end=None,
            )
            for idx, topic in enumerate(topics)
        ]

        # Build lessons list from topics with content_type="lesson"
        # This enables the frontend to display them with lesson-specific UI
        lesson_topics = [t for t in topics if t.content_type == "lesson"]
        lesson_infos = [
            LessonInfo(
                id=topic.id,
                lesson_num=idx + 1,
                title=topic.title or f"Lesson {idx + 1}",
                page_start=topic.page_num,
                page_end=None,
            )
            for idx, topic in enumerate(lesson_topics)
        ]

        chapter_infos.append(
            ChapterInfo(
                id=chapter.id,
                title=chapter.title or f"Chapter {chapter.chapter_num or index + 1}",
                page_start=chapter.start_page,
                page_end=chapter.end_page,
                topics=topic_infos,
                lessons=lesson_infos,
            )
        )

    return BookOutline(
        book_id=book.id,
        title=book.title,
        total_pages=book.total_pages,
        chapters=chapter_infos,
    )


@router.delete("/{book_id}", status_code=204)
def delete_book(book_id: int, db: Session = Depends(get_db)) -> None:
    """Delete a book, its associated file, and FAISS index."""
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found.")

    # Remove file from disk
    file_path = Path(book.file_path)
    if file_path.exists():
        file_path.unlink()

    # Remove FAISS index
    try:
        from services.embedding_service import EmbeddingService

        embedding_service = EmbeddingService(
            model_name=settings.EMBEDDING_MODEL,
            faiss_dir=settings.FAISS_DIR,
        )
        embedding_service.delete_index(book_id)
    except Exception as e:
        logger.warning(f"Failed to delete FAISS index for book {book_id}: {e}")

    db.delete(book)
    db.commit()

    logger.info(f"Book deleted: id={book_id}")
