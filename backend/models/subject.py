"""Subject taxonomy model — canonical Egyptian MOE curriculum subjects.

Replaces hardcoded math-only assumptions with a 24-key taxonomy seeded from
backend/data/subjects_seed.json. Each Subject row carries enough metadata
(content traits, default topic sections, letterhead lines, MOE catalog
aliases including hamza variants) for the SubjectStrategy registry in
Phase 2 to dispatch on subject_key alone.
"""

from datetime import datetime

from sqlalchemy import JSON, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class Subject(Base):
    """A canonical curriculum subject (math, arabic_lang, physics, ...).

    Rows are not user-editable — they're seeded on app startup from
    backend/data/subjects_seed.json. `key` is the stable snake_case
    identifier used as a foreign key by Book/Workbook/Exam.
    """

    __tablename__ = "subjects"

    key: Mapped[str] = mapped_column(String(40), primary_key=True)
    label_en: Mapped[str] = mapped_column(String(100), nullable=False)
    label_ar: Mapped[str] = mapped_column(String(100), nullable=False)

    # MOE catalog 'subject' strings that map to this canonical key,
    # including hamza variants (e.g. الاسبانية vs الإسبانية).
    moe_catalog_labels: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    # Flags driving SubjectStrategy dispatch:
    # {has_math, has_code, primary_script, primary_direction,
    #  has_diagrams, has_quotations, has_formula_boxes, has_math_rendering, ...}
    content_traits: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    # Per-subject weekly-assessment topic split — replaces the hardcoded
    # Algebra/Trig/Geometry default in exam_orchestrator.py.
    default_topic_sections: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    # Per-subject MOE department names for exam letterhead.
    letterhead_lines_ar: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    letterhead_lines_en: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<Subject(key='{self.key}', label_en='{self.label_en}')>"
