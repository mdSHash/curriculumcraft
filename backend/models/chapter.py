"""Chapter database model."""

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class Chapter(Base):
    """Represents a detected chapter within an uploaded book."""

    __tablename__ = "chapters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    book_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("books.id", ondelete="CASCADE"), nullable=False
    )
    chapter_num: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    start_page: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    end_page: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Relationships
    book: Mapped["Book"] = relationship("Book", back_populates="chapters")  # noqa: F821
    topics: Mapped[list["Topic"]] = relationship(  # noqa: F821
        "Topic", back_populates="chapter", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return (
            f"<Chapter(id={self.id}, book_id={self.book_id}, "
            f"num={self.chapter_num}, title='{self.title}')>"
        )
