"""Book-related Pydantic schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class BookCreate(BaseModel):
    """Schema for book upload metadata."""

    title: str
    grade_level: str
    academic_year: str = ""
    term: str = ""
    subject: str = "Mathematics"


class BookResponse(BaseModel):
    """Full book information response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    grade_level: str
    academic_year: str
    term: str
    subject: str
    filename: str
    file_path: str
    total_pages: int
    chapters_detected: int
    status: str
    created_at: datetime
    updated_at: datetime


class LessonInfo(BaseModel):
    """Information about a single lesson within a chapter (Egyptian curriculum)."""

    id: int
    lesson_num: int
    title: str
    page_start: int | None = None
    page_end: int | None = None


class TopicInfo(BaseModel):
    """Information about a single topic within a chapter."""

    id: int
    title: str
    content_type: str = "concept"
    difficulty: str = "beginner"
    page_start: int | None = None
    page_end: int | None = None


class ChapterInfo(BaseModel):
    """Information about a single chapter."""

    id: int
    title: str
    page_start: int | None = None
    page_end: int | None = None
    topics: list[TopicInfo] = []
    lessons: list[LessonInfo] = []


class BookOutline(BaseModel):
    """Chapters and topics structure for a book."""

    book_id: int
    title: str
    total_pages: int
    chapters: list[ChapterInfo] = []
