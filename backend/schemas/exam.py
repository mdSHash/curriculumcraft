"""Exam/Quiz generation Pydantic schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ExamScopeConfig(BaseModel):
    """Content scope for the exam."""

    book_id: int
    chapter_ids: list[int] = []
    topic_ids: list[int] = []


class TopicSectionSpec(BaseModel):
    """A topic-organized section header (e.g. 'First: Algebra' / 'Second: Trigonometry').

    Used for `weekly_assessment` exam type, where sections are organized by
    mathematical topic instead of by question type.
    """

    title_ar: str = ""
    title_en: str = ""
    count: int = 4
    marks_per_question: int = 1


class ExamStructureConfig(BaseModel):
    """Exam structure and question distribution."""

    # quiz | monthly_exam | weekly_assessment
    exam_type: str = "monthly_exam"
    total_marks: int = 40
    duration_minutes: int = 60

    # Variants: separate exam papers (different students get different papers).
    num_variants: int = 1

    # Groups: parallel question sets WITHIN a single paper. The MOE weekly
    # assessments use 3 groups (First group / Second group / Third group) of
    # equivalent difficulty so a teacher can hand a different group to each row.
    groups_per_variant: int = 1

    # ─── Question type distribution (used for quiz / monthly_exam) ───────────
    choose_correct: int = 8        # اختر الإجابة الصحيحة
    complete_following: int = 5    # أكمل ما يأتي
    answer_short: int = 4          # أجب عما يأتي
    solve_prove: int = 3           # حل / برهن
    essay_extended: int = 0        # مقالي / إجابة مطولة

    # ─── Topic sections (used for weekly_assessment) ─────────────────────────
    # Empty list → orchestrator falls back to a default Algebra/Trig/Geometry
    # split appropriate to the grade level.
    topic_sections: list[TopicSectionSpec] = []

    # ─── Bloom's taxonomy distribution (percentages, sum should be ≤ 100) ────
    bloom_remember_understand: int = 30
    bloom_apply_analyze: int = 40
    bloom_evaluate_create: int = 30


class ExamFormattingConfig(BaseModel):
    """Exam formatting and metadata."""

    title: str = "امتحان شهري"
    school_name: str = ".................."
    subject: str = "الرياضيات"
    grade: str = ""
    term: str = ""
    academic_year: str = "2025-2026"
    exam_date: str = "    /    /      "
    language: str = "arabic"  # arabic | english | bilingual
    include_answer_key: bool = True
    include_marking_rubric: bool = True

    # Optional: ID of an official MOE weekly assessment to use as a reference
    # when generating questions. The text is extracted server-side and fed to
    # the LLM as additional grounding context so the output mirrors official
    # ministry style and difficulty.
    moe_reference_id: Optional[str] = None


class ExamConfig(BaseModel):
    """Complete exam generation configuration."""

    scope: ExamScopeConfig
    structure: ExamStructureConfig = ExamStructureConfig()
    formatting: ExamFormattingConfig = ExamFormattingConfig()


class ExamResponse(BaseModel):
    """Full exam information response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    book_id: int
    title: str
    exam_type: str
    total_marks: int
    duration_minutes: int
    num_variants: int
    filename: str
    file_path: str
    answer_key_filename: Optional[str] = None
    answer_key_path: Optional[str] = None
    status: str
    error_message: Optional[str] = None
    created_at: datetime


class ExamListItem(BaseModel):
    """Exam summary for list views."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    book_id: int
    title: str
    exam_type: str
    total_marks: int
    duration_minutes: int
    num_variants: int
    status: str
    progress: int = 0
    progress_message: Optional[str] = None
    created_at: datetime


class ExamStatusResponse(BaseModel):
    """Minimal status response for polling."""

    id: int
    status: str
    progress: int = 0
    progress_message: Optional[str] = None
    error: Optional[str] = None
