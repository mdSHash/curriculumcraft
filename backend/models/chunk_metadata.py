"""Chunk metadata database model for the RAG pipeline."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class ChunkMetadata(Base):
    """Stores metadata for each text chunk indexed in FAISS.

    Each row corresponds to a single vector in the FAISS index for a book.
    The chunk_index field maps directly to the FAISS vector position.
    """

    __tablename__ = "chunk_metadata"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    book_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chapter_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("chapters.id", ondelete="SET NULL"), nullable=True
    )
    chunk_index: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Position in the FAISS index"
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    lesson_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    unit_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="explanation",
        comment="definition/example/exercise/theorem/explanation"
    )
    language: Mapped[str] = mapped_column(
        String(10), nullable=False, default="ar",
        comment="ar/en/mixed"
    )
    token_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    def __repr__(self) -> str:
        return (
            f"<ChunkMetadata(id={self.id}, book_id={self.book_id}, "
            f"chunk_index={self.chunk_index}, content_type='{self.content_type}')>"
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "book_id": self.book_id,
            "chapter_id": self.chapter_id,
            "chunk_index": self.chunk_index,
            "text": self.text,
            "lesson_title": self.lesson_title,
            "unit_title": self.unit_title,
            "page_number": self.page_number,
            "content_type": self.content_type,
            "language": self.language,
            "token_count": self.token_count,
        }
