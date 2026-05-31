"""Book database model."""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class Book(Base):
    """Represents an uploaded math textbook PDF."""

    __tablename__ = "books"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    grade_level: Mapped[str] = mapped_column(String(50), nullable=False)
    academic_year: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    term: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    subject: Mapped[str] = mapped_column(String(100), nullable=False, default="Mathematics")
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    total_pages: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    chapters_detected: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="processing"
    )  # processing, ready, error
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    workbooks: Mapped[list["Workbook"]] = relationship(  # noqa: F821
        "Workbook", back_populates="book", cascade="all, delete-orphan"
    )
    exams: Mapped[list["Exam"]] = relationship(  # noqa: F821
        "Exam", back_populates="book", cascade="all, delete-orphan"
    )
    chapters: Mapped[list["Chapter"]] = relationship(  # noqa: F821
        "Chapter", back_populates="book", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Book(id={self.id}, title='{self.title}', status='{self.status}')>"
