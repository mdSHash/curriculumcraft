"""Workbook-related Pydantic schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class ScopeConfig(BaseModel):
    """Step 1: Content scope selection."""

    book_id: int
    chapter_ids: list[int] = []
    topic_ids: list[int] = []
    page_range_start: int | None = None
    page_range_end: int | None = None


class StructureConfig(BaseModel):
    """Step 2: Workbook structure configuration."""

    output_mode: str = "workbook_only"  # workbook_only, illustration_and_workbook
    total_pages: int = 20
    layout_style: str = "standard"  # spacious, standard, dense
    include_cover: bool = True
    include_objectives: bool = True
    include_worked_examples: bool = True
    include_formula_box: bool = True
    include_answer_lines: bool = True
    include_answer_box: bool = True
    include_difficulty_labels: bool = True
    include_page_numbers: bool = True
    include_section_headers: bool = True
    include_teacher_notes: bool = False


class ExerciseConfig(BaseModel):
    """Step 3: Exercise type and difficulty configuration."""

    difficulty_easy: int = 40
    difficulty_medium: int = 40
    difficulty_hard: int = 20
    types: list[str] = ["multiple_choice", "fill_blank", "show_work", "word_problems"]
    exercises_per_type: dict[str, int] | None = None  # None = auto-distribute
    source: str = "both"  # original, ai_generated, both


class FormattingConfig(BaseModel):
    """Step 4: Formatting and metadata configuration."""

    title: str = "Math Workbook"
    school_name: str = ""
    teacher_name: str = ""
    grade: str = ""
    term: str = ""
    academic_year: str = ""
    font_size: str = "medium"  # small, medium, large
    answer_style: str = "ruled_lines"  # dotted_lines, ruled_lines, grid, plain_box
    margins: str = "normal"  # normal, wide
    language: str = "english"  # arabic, english, bilingual


class WorkbookConfig(BaseModel):
    """Complete workbook generation configuration (4-step wizard)."""

    scope: ScopeConfig
    structure: StructureConfig = StructureConfig()
    exercises: ExerciseConfig = ExerciseConfig()
    formatting: FormattingConfig = FormattingConfig()


class WorkbookResponse(BaseModel):
    """Full workbook information response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    book_id: int
    title: str
    config_json: str
    filename: str
    file_path: str
    total_pages: int
    status: str
    progress: int = 0
    progress_message: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime


class WorkbookListItem(BaseModel):
    """Workbook summary for list views."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    book_id: int
    title: str
    total_pages: int
    status: str
    progress: int = 0
    progress_message: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
