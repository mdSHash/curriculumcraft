"""Exam database model."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class Exam(Base):
    """Represents a generated exam or quiz."""

    __tablename__ = "exams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    book_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("books.id"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    exam_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="quiz"
    )  # quiz, monthly_exam
    config_json: Mapped[str] = mapped_column(Text, nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    file_path: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    answer_key_filename: Mapped[str | None] = mapped_column(
        String(255), nullable=True, default=None
    )
    answer_key_path: Mapped[str | None] = mapped_column(
        String(500), nullable=True, default=None
    )
    total_marks: Mapped[int] = mapped_column(Integer, nullable=False, default=40)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    num_variants: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="generating"
    )  # generating, ready, error
    error_message: Mapped[str | None] = mapped_column(
        Text, nullable=True, default=None
    )
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    progress_message: Mapped[str | None] = mapped_column(
        Text, nullable=True, default=None
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    # Relationships
    book: Mapped["Book"] = relationship("Book", back_populates="exams")  # noqa: F821

    def __repr__(self) -> str:
        return f"<Exam(id={self.id}, title='{self.title}', type='{self.exam_type}', status='{self.status}')>"
