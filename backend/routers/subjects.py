"""Subjects router — serves the canonical taxonomy to the frontend."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import get_db
from models.book import Book
from models.subject import Subject
from schemas.subject import SubjectConfig, SubjectListItem, SubjectResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/subjects", tags=["subjects"])


@router.get("", response_model=list[SubjectListItem])
def list_subjects(db: Session = Depends(get_db)) -> list[SubjectListItem]:
    """Return all 24 canonical subjects with book counts.

    Drives the frontend SubjectPicker. Empty subjects are still returned
    so users see the full taxonomy, not just what's been ingested.
    """
    counts = dict(
        db.query(Book.subject_key, func.count(Book.id))
        .group_by(Book.subject_key)
        .all()
    )

    items: list[SubjectListItem] = []
    for s in db.query(Subject).order_by(Subject.label_en).all():
        items.append(
            SubjectListItem(
                key=s.key,
                label_en=s.label_en,
                label_ar=s.label_ar,
                book_count=int(counts.get(s.key, 0) or 0),
            )
        )
    return items


@router.get("/{key}", response_model=SubjectResponse)
def get_subject(key: str, db: Session = Depends(get_db)) -> SubjectResponse:
    """Return the full record for a single subject."""
    subject = db.query(Subject).filter(Subject.key == key).first()
    if subject is None:
        raise HTTPException(status_code=404, detail=f"Unknown subject key: {key}")
    return subject  # type: ignore[return-value]


@router.get("/{key}/config", response_model=SubjectConfig)
def get_subject_config(key: str, db: Session = Depends(get_db)) -> SubjectConfig:
    """Return the wizard-facing subject config.

    Used by the React wizard to decide which content-box options to render,
    text direction, default topic sections, etc. Trait keys default safely
    when the seed JSON omits them.
    """
    subject = db.query(Subject).filter(Subject.key == key).first()
    if subject is None:
        raise HTTPException(status_code=404, detail=f"Unknown subject key: {key}")

    traits = subject.content_traits or {}
    return SubjectConfig(
        key=subject.key,
        label_en=subject.label_en,
        label_ar=subject.label_ar,
        has_math_rendering=bool(traits.get("has_math_rendering", False)),
        has_formula_boxes=bool(traits.get("has_formula_boxes", False)),
        has_code_blocks=bool(traits.get("has_code_blocks", False)),
        has_quotations=bool(traits.get("has_quotations", False)),
        has_diagrams=bool(traits.get("has_diagrams", False)),
        primary_direction=str(traits.get("primary_direction", "rtl")),
        primary_script=str(traits.get("primary_script", "arabic")),
        is_second_language=bool(traits.get("is_second_language", False)),
        default_topic_sections=subject.default_topic_sections or [],
    )
