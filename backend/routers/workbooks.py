"""Workbooks API router — generate, list, download, status, delete."""

import asyncio
import json
import logging
import traceback
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db, SessionLocal
from models.book import Book
from models.workbook import Workbook
from schemas.workbook import WorkbookConfig, WorkbookListItem, WorkbookResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/workbooks", tags=["workbooks"])


class WorkbookStatusResponse(BaseModel):
    """Minimal status response for polling."""

    id: int
    status: str
    progress: int = 0
    progress_message: str | None = None
    error: str | None = None


async def _run_generation(workbook_id: int, config_dict: dict) -> None:
    """Background task that runs the workbook generation pipeline.

    Creates its own DB session since background tasks run outside
    the request lifecycle.
    """
    from services.workbook_orchestrator import WorkbookOrchestrator

    logger.info(f"[BG] Starting generation for workbook {workbook_id}")
    db = SessionLocal()
    try:
        orchestrator = WorkbookOrchestrator(
            db=db, config=config_dict, workbook_id=workbook_id
        )
        await orchestrator.generate()
        logger.info(f"[BG] Generation completed successfully for workbook {workbook_id}")
    except Exception as e:
        logger.error(
            f"[BG] Background generation FAILED for workbook {workbook_id}: {e}\n"
            f"{traceback.format_exc()}"
        )
        # Ensure status is set to error with message
        try:
            workbook = db.query(Workbook).filter(Workbook.id == workbook_id).first()
            if workbook and workbook.status != "error":
                workbook.status = "error"
                workbook.error_message = str(e)[:500]  # Truncate long error messages
                db.commit()
        except Exception as db_err:
            logger.error(f"[BG] Failed to update workbook status to error: {db_err}")
    finally:
        db.close()


def _background_generate(workbook_id: int, config_dict: dict) -> None:
    """Synchronous wrapper to run async generation in a background task."""
    logger.info(f"[BG] Background task started for workbook {workbook_id}")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_run_generation(workbook_id, config_dict))
    except Exception as e:
        logger.error(
            f"[BG] Event loop crashed for workbook {workbook_id}: {e}\n"
            f"{traceback.format_exc()}"
        )
        # Last-resort: try to mark workbook as error
        try:
            db = SessionLocal()
            workbook = db.query(Workbook).filter(Workbook.id == workbook_id).first()
            if workbook and workbook.status != "error":
                workbook.status = "error"
                workbook.error_message = str(e)[:500]
                db.commit()
            db.close()
        except Exception:
            pass
    finally:
        loop.close()


@router.post("/generate", response_model=WorkbookResponse, status_code=201)
def generate_workbook(
    config: WorkbookConfig,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> WorkbookResponse:
    """Generate a workbook from the given configuration.

    Creates a DB record immediately with status='generating', then
    kicks off the actual generation in a background task.
    Returns the workbook info immediately for the client to poll status.
    """
    # Verify the book exists and is ready for generation. Without the
    # status gate, generation kicks off against an empty FAISS index and
    # silently produces template-only workbooks.
    book = db.query(Book).filter(Book.id == config.scope.book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Source book not found.")
    if book.status != "ready":
        raise HTTPException(
            status_code=400,
            detail=(
                f"Book is not ready (status: {book.status}). "
                f"Please wait for ingestion to complete."
            ),
        )

    # Create workbook record with generating status. subject_key is
    # denormalized from the parent Book at creation time so deletion or
    # subject rename of the book doesn't break in-flight generation.
    workbook = Workbook(
        book_id=config.scope.book_id,
        subject_key=book.subject_key or "math",
        title=config.formatting.title,
        config_json=json.dumps(config.model_dump(), ensure_ascii=False),
        filename="",
        file_path="",
        total_pages=config.structure.total_pages,
        status="generating",
    )
    db.add(workbook)
    db.commit()
    db.refresh(workbook)

    # Kick off background generation
    config_dict = config.model_dump()
    background_tasks.add_task(_background_generate, workbook.id, config_dict)

    logger.info(f"Workbook generation started: id={workbook.id}, title='{workbook.title}'")

    return WorkbookResponse.model_validate(workbook)


@router.get("/{workbook_id}/status", response_model=WorkbookStatusResponse)
def get_workbook_status(
    workbook_id: int, db: Session = Depends(get_db)
) -> WorkbookStatusResponse:
    """Check the generation status of a workbook (useful for polling)."""
    workbook = db.query(Workbook).filter(Workbook.id == workbook_id).first()
    if not workbook:
        raise HTTPException(status_code=404, detail="Workbook not found.")

    return WorkbookStatusResponse(
        id=workbook.id,
        status=workbook.status,
        progress=workbook.progress or 0,
        progress_message=workbook.progress_message,
        error=workbook.error_message if workbook.status == "error" else None,
    )


@router.get("", response_model=list[WorkbookListItem])
def list_workbooks(db: Session = Depends(get_db)) -> list[WorkbookListItem]:
    """List all generated workbooks."""
    workbooks = db.query(Workbook).order_by(Workbook.created_at.desc()).all()
    return [WorkbookListItem.model_validate(w) for w in workbooks]


@router.get("/{workbook_id}", response_model=WorkbookResponse)
def get_workbook(workbook_id: int, db: Session = Depends(get_db)) -> WorkbookResponse:
    """Get full details of a specific workbook."""
    workbook = db.query(Workbook).filter(Workbook.id == workbook_id).first()
    if not workbook:
        raise HTTPException(status_code=404, detail="Workbook not found.")

    return WorkbookResponse.model_validate(workbook)


@router.get("/{workbook_id}/download")
def download_workbook(workbook_id: int, db: Session = Depends(get_db)) -> FileResponse:
    """Download the generated .docx workbook file."""
    workbook = db.query(Workbook).filter(Workbook.id == workbook_id).first()
    if not workbook:
        raise HTTPException(status_code=404, detail="Workbook not found.")

    if workbook.status != "ready":
        raise HTTPException(
            status_code=400,
            detail=f"Workbook is not ready for download (status: {workbook.status}).",
        )

    file_path = Path(workbook.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Workbook file not found on disk.")

    return FileResponse(
        path=str(file_path),
        filename=workbook.filename,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


@router.delete("/{workbook_id}", status_code=204)
def delete_workbook(workbook_id: int, db: Session = Depends(get_db)) -> None:
    """Delete a workbook and its associated file."""
    workbook = db.query(Workbook).filter(Workbook.id == workbook_id).first()
    if not workbook:
        raise HTTPException(status_code=404, detail="Workbook not found.")

    # Remove file from disk if it exists
    if workbook.file_path:
        file_path = Path(workbook.file_path)
        if file_path.exists():
            file_path.unlink()

    db.delete(workbook)
    db.commit()
