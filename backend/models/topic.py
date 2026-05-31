"""Topic database model."""

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class Topic(Base):
    """Represents a detected topic within a chapter."""

    __tablename__ = "topics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chapter_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="concept"
    )  # concept, example, exercise, formula, definition
    difficulty: Mapped[str] = mapped_column(
        String(20), nullable=False, default="beginner"
    )  # beginner, intermediate, advanced
    page_num: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Relationships
    chapter: Mapped["Chapter"] = relationship("Chapter", back_populates="topics")  # noqa: F821

    def __repr__(self) -> str:
        return (
            f"<Topic(id={self.id}, chapter_id={self.chapter_id}, "
            f"title='{self.title}', type='{self.content_type}')>"
        )
