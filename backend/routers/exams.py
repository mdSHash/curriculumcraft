"""Exams API router — generate, list, download, status, delete exams and quizzes."""

import asyncio
import json
import logging
import traceback
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from database import get_db, SessionLocal
from models.book import Book
from models.exam import Exam
from schemas.exam import (
    ExamConfig,
    ExamListItem,
    ExamResponse,
    ExamStatusResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/exams", tags=["exams"])


async def _run_exam_generation(exam_id: int, config_dict: dict) -> None:
    """Background task that runs the exam generation pipeline."""
    from services.exam_orchestrator import ExamOrchestrator

    logger.info(f"[BG] Starting exam generation for exam {exam_id}")
    db = SessionLocal()
    try:
        orchestrator = ExamOrchestrator(
            db=db, config=config_dict, exam_id=exam_id
        )
        await orchestrator.generate()
        logger.info(f"[BG] Exam generation completed successfully for exam {exam_id}")
    except Exception as e:
        logger.error(
            f"[BG] Exam generation FAILED for exam {exam_id}: {e}\n"
            f"{traceback.format_exc()}"
        )
        try:
            exam = db.query(Exam).filter(Exam.id == exam_id).first()
            if exam and exam.status != "error":
                exam.status = "error"
                exam.error_message = str(e)[:500]
                db.commit()
        except Exception as db_err:
            logger.error(f"[BG] Failed to update exam status to error: {db_err}")
    finally:
        db.close()


def _background_exam_generate(exam_id: int, config_dict: dict) -> None:
    """Synchronous wrapper to run async exam generation in a background task."""
    logger.info(f"[BG] Background task started for exam {exam_id}")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_run_exam_generation(exam_id, config_dict))
    except Exception as e:
        logger.error(
            f"[BG] Event loop crashed for exam {exam_id}: {e}\n"
            f"{traceback.format_exc()}"
        )
        try:
            db = SessionLocal()
            exam = db.query(Exam).filter(Exam.id == exam_id).first()
            if exam and exam.status != "error":
                exam.status = "error"
                exam.error_message = str(e)[:500]
                db.commit()
            db.close()
        except Exception:
            pass
    finally:
        loop.close()


@router.post("/generate", response_model=ExamResponse, status_code=201)
def generate_exam(
    config: ExamConfig,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> ExamResponse:
    """Generate an exam or quiz from the given configuration.

    Creates a database record immediately and starts generation in background.
    Poll the /exams/{id}/status endpoint to check progress.
    """
    # Validate book exists
    book = db.query(Book).filter(Book.id == config.scope.book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found.")

    if book.status != "ready":
        raise HTTPException(
            status_code=400,
            detail=f"Book is not ready (status: {book.status}). Please wait for processing to complete.",
        )

    # Create exam record. subject_key is denormalized from the parent
    # Book at creation time so deletion / subject rename of the book
    # doesn't break in-flight generation.
    exam = Exam(
        book_id=config.scope.book_id,
        subject_key=book.subject_key or "math",
        title=config.formatting.title,
        exam_type=config.structure.exam_type,
        config_json=json.dumps(config.model_dump(), ensure_ascii=False),
        total_marks=config.structure.total_marks,
        duration_minutes=config.structure.duration_minutes,
        num_variants=config.structure.num_variants,
        status="generating",
    )
    db.add(exam)
    db.commit()
    db.refresh(exam)

    # Start background generation
    config_dict = config.model_dump()
    background_tasks.add_task(_background_exam_generate, exam.id, config_dict)

    logger.info(f"Exam generation initiated: id={exam.id}, type={exam.exam_type}")

    return ExamResponse.model_validate(exam)


@router.get("", response_model=list[ExamListItem])
def list_exams(db: Session = Depends(get_db)) -> list[ExamListItem]:
    """List all generated exams."""
    exams = db.query(Exam).order_by(Exam.created_at.desc()).all()
    return [ExamListItem.model_validate(e) for e in exams]


@router.get("/{exam_id}", response_model=ExamResponse)
def get_exam(exam_id: int, db: Session = Depends(get_db)) -> ExamResponse:
    """Get full exam details."""
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found.")
    return ExamResponse.model_validate(exam)


@router.get("/{exam_id}/status", response_model=ExamStatusResponse)
def get_exam_status(exam_id: int, db: Session = Depends(get_db)) -> ExamStatusResponse:
    """Get exam generation status (for polling)."""
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found.")
    return ExamStatusResponse(
        id=exam.id,
        status=exam.status,
        progress=exam.progress or 0,
        progress_message=exam.progress_message,
        error=exam.error_message,
    )


@router.get("/{exam_id}/download")
def download_exam(exam_id: int, db: Session = Depends(get_db)):
    """Download the generated exam DOCX file."""
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found.")
    if exam.status != "ready":
        raise HTTPException(status_code=400, detail="Exam is not ready for download.")

    file_path = Path(exam.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Exam file not found on disk.")

    return FileResponse(
        path=str(file_path),
        filename=exam.filename,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


@router.get("/{exam_id}/download-answer-key")
def download_answer_key(exam_id: int, db: Session = Depends(get_db)):
    """Download the answer key DOCX file."""
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found.")
    if exam.status != "ready":
        raise HTTPException(status_code=400, detail="Exam is not ready for download.")
    if not exam.answer_key_path:
        raise HTTPException(status_code=404, detail="Answer key not available.")

    file_path = Path(exam.answer_key_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Answer key file not found on disk.")

    return FileResponse(
        path=str(file_path),
        filename=exam.answer_key_filename or "answer_key.docx",
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


@router.delete("/{exam_id}", status_code=204)
def delete_exam(exam_id: int, db: Session = Depends(get_db)):
    """Delete an exam and its files."""
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found.")

    # Delete files
    if exam.file_path:
        file_path = Path(exam.file_path)
        if file_path.exists():
            file_path.unlink()

    if exam.answer_key_path:
        ak_path = Path(exam.answer_key_path)
        if ak_path.exists():
            ak_path.unlink()

    # Delete DB record
    db.delete(exam)
    db.commit()
    return None
