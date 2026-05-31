"""Orchestrates the full book ingestion pipeline.

Coordinates PDF extraction → LLM structure detection → semantic chunking →
embedding → FAISS index + BM25 index creation → metadata storage.
"""

import logging
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from config import get_settings
from models.book import Book
from models.chapter import Chapter
from models.topic import Topic

logger = logging.getLogger(__name__)
settings = get_settings()


class IngestionPipeline:
    """Coordinates PDF extraction → parsing → semantic chunking → embedding → storage."""

    def __init__(self, db: Session, book_id: int, file_path: str) -> None:
        """Initialize the ingestion pipeline.

        Args:
            db: SQLAlchemy database session.
            book_id: The book's database ID.
            file_path: Path to the uploaded PDF file.
        """
        self.db = db
        self.book_id = book_id
        self.file_path = file_path

    async def run(self) -> None:
        """Execute the full ingestion pipeline.

        Steps:
            1. Extract text from PDF/DOCX
            2. Initialize LLM service for structure detection
            3. Parse content into units/lessons/chunks using LLM
            4. Save chapter/topic structure to DB
            5. Semantic chunking with metadata
            6. Generate embeddings for all chunks
            7. Create and save FAISS index + BM25 index
            8. Save chunk metadata to DB
            9. Update book status to "ready"
        """
        # Lazy imports — these pull in heavy dependencies
        from services.content_parser import ContentParser
        from services.embedding_service import EmbeddingService
        from services.pdf_extractor import PDFExtractor
        from services.docx_extractor import DocxExtractor
        from services.semantic_chunker import SemanticChunker, ContentChunk
        # Note: HybridSearch is lazy-imported inside the BM25 try/except block
        # to gracefully handle missing rank-bm25 package

        try:
            logger.info(f"Starting ingestion pipeline for book {self.book_id}")

            # Step 1: Extract text from file (PDF or DOCX)
            file_ext = Path(self.file_path).suffix.lower()
            logger.info(
                f"[Book {self.book_id}] Step 1: Extracting text from "
                f"{file_ext.upper()} file..."
            )

            if file_ext == ".docx":
                extractor = DocxExtractor(self.file_path)
            else:
                extractor = PDFExtractor(self.file_path)

            pages = await extractor.extract()
            total_pages = extractor.get_total_pages()

            logger.info(
                f"[Book {self.book_id}] Extracted {len(pages)} pages "
                f"({total_pages} total)"
            )

            # Update total pages in DB
            book = self.db.query(Book).filter(Book.id == self.book_id).first()
            if book:
                book.total_pages = total_pages
                self.db.commit()

            # Step 2: Initialize LLM service for structure detection
            logger.info(
                f"[Book {self.book_id}] Step 2: Initializing LLM for structure detection..."
            )
            llm_service = None
            if settings.GEMINI_API_KEY:
                try:
                    from services.llm_service import LLMService

                    llm_service = LLMService(
                        api_key=settings.GEMINI_API_KEY,
                        model=settings.GEMINI_MODEL,
                    )
                    if llm_service.model:
                        logger.info(
                            f"[Book {self.book_id}] LLM service initialized "
                            f"(model: {settings.GEMINI_MODEL})"
                        )
                    else:
                        logger.warning(
                            f"[Book {self.book_id}] LLM model not available, "
                            f"will use fallback parsing"
                        )
                        llm_service = None
                except Exception as e:
                    logger.warning(
                        f"[Book {self.book_id}] Failed to init LLM service: {e}"
                    )
                    llm_service = None
            else:
                logger.info(
                    f"[Book {self.book_id}] No GEMINI_API_KEY configured, "
                    f"using fallback parsing"
                )

            # Step 3: Parse content with LLM-powered structure detection
            logger.info(f"[Book {self.book_id}] Step 3: Parsing content...")
            parser = ContentParser(pages, llm_service=llm_service)
            units, legacy_chunks = await parser.parse()

            logger.info(
                f"[Book {self.book_id}] Detected {len(units)} units, "
                f"{sum(len(u.lessons) for u in units)} lessons, "
                f"{len(legacy_chunks)} legacy chunks"
            )

            # Step 4: Save chapter/topic structure to DB
            logger.info(
                f"[Book {self.book_id}] Step 4: Saving structure to database..."
            )
            chapter_map = self._save_structure_to_db(units)

            # Step 5: Semantic chunking with metadata
            logger.info(
                f"[Book {self.book_id}] Step 5: Semantic chunking..."
            )
            chunker = SemanticChunker(
                chunk_size_target=settings.RAG_MAX_CONTEXT_CHARS // 32,  # ~8000 tokens / 8 chunks = 1000 tokens target
                chunk_size_max=1024,
                chunk_overlap_tokens=50,
            )

            all_chunks: list[ContentChunk] = []

            for unit in units:
                unit_title = unit.title or f"الوحدة {unit.unit_num}"
                chapter_id = chapter_map.get(unit.unit_num)

                for lesson in unit.lessons:
                    # Try to get lesson text from the lesson object itself
                    lesson_text = getattr(lesson, "text", "") or ""

                    # If lesson has no text attribute, extract from pages using
                    # the lesson's page range (start_page → end_page)
                    if not lesson_text and hasattr(lesson, "start_page") and hasattr(lesson, "end_page"):
                        lesson_page_texts = []
                        start_pg = getattr(lesson, "start_page", None)
                        end_pg = getattr(lesson, "end_page", None)
                        if start_pg and end_pg:
                            for page in pages:
                                if start_pg <= page.page_num <= end_pg:
                                    if page.text and page.text.strip():
                                        lesson_page_texts.append(page.text)
                            lesson_text = "\n\n".join(lesson_page_texts)

                    # If still no text, try to get it from legacy chunks
                    if not lesson_text:
                        lesson_chunks_text = [
                            c.text for c in legacy_chunks
                            if hasattr(c, "topic") and c.topic == lesson.title
                        ]
                        lesson_text = "\n\n".join(lesson_chunks_text)

                    if not lesson_text.strip():
                        continue

                    lesson_title = lesson.title or f"Lesson {lesson.lesson_num}"
                    start_page = lesson.start_page if hasattr(lesson, "start_page") else None

                    chunks = chunker.chunk_lesson(
                        lesson_text=lesson_text,
                        book_id=self.book_id,
                        chapter_id=chapter_id,
                        unit_title=unit_title,
                        lesson_title=lesson_title,
                        start_page=start_page,
                    )
                    all_chunks.extend(chunks)

            # If semantic chunking produced no chunks, fall back to legacy chunks
            if not all_chunks and legacy_chunks:
                logger.info(
                    f"[Book {self.book_id}] Semantic chunking produced no results, "
                    f"using legacy chunks"
                )
                for i, chunk in enumerate(legacy_chunks):
                    chapter_id = chapter_map.get(
                        getattr(chunk, "chapter_num", None)
                    )
                    all_chunks.append(
                        ContentChunk(
                            text=chunk.text,
                            book_id=self.book_id,
                            chapter_id=chapter_id,
                            lesson_title=getattr(chunk, "topic", None),
                            unit_title=None,
                            page_number=getattr(chunk, "page_num", None),
                            content_type=getattr(chunk, "content_type", "explanation"),
                            language="ar",
                            chunk_index=i,
                        )
                    )

            logger.info(
                f"[Book {self.book_id}] Created {len(all_chunks)} semantic chunks"
            )

            # Step 6: Generate embeddings for all chunks
            if all_chunks:
                logger.info(
                    f"[Book {self.book_id}] Step 6: Generating embeddings for "
                    f"{len(all_chunks)} chunks..."
                )
                embedding_service = EmbeddingService(
                    model_name=settings.EMBEDDING_MODEL,
                    faiss_dir=settings.FAISS_DIR,
                )

                chunk_texts = [chunk.text for chunk in all_chunks]
                embeddings = embedding_service.embed_batch(chunk_texts)

                # Step 7: Create FAISS index + BM25 index
                logger.info(
                    f"[Book {self.book_id}] Step 7: Creating FAISS + BM25 indices..."
                )
                embedding_service.create_index(
                    book_id=self.book_id,
                    chunks=all_chunks,
                    embeddings=embeddings,
                )

                # Build BM25 keyword index (lazy import — rank_bm25 may not be installed)
                try:
                    from services.hybrid_search import HybridSearch

                    hybrid_search = HybridSearch(
                        embedding_service=embedding_service,
                        faiss_dir=settings.FAISS_DIR,
                        semantic_weight=settings.RAG_HYBRID_ALPHA,
                        mmr_lambda=settings.RAG_MMR_LAMBDA,
                    )
                    # Get metadata for BM25 indexing
                    metadata = embedding_service.get_metadata(self.book_id)
                    hybrid_search.build_bm25_index(self.book_id, metadata)
                    logger.info(
                        f"[Book {self.book_id}] BM25 index built successfully"
                    )
                except ImportError as e:
                    logger.warning(
                        f"[Book {self.book_id}] rank-bm25 not installed, "
                        f"skipping BM25 index: {e}"
                    )
                except Exception as e:
                    logger.warning(
                        f"[Book {self.book_id}] Failed to build BM25 index "
                        f"(hybrid search will be unavailable): {e}"
                    )

                # Step 8: Save chunk metadata to DB
                try:
                    logger.info(
                        f"[Book {self.book_id}] Step 8: Saving chunk metadata to DB..."
                    )
                    self._save_chunk_metadata_to_db(all_chunks)
                except Exception as e:
                    logger.warning(
                        f"[Book {self.book_id}] Failed to save chunk metadata to DB "
                        f"(FAISS index is still valid): {e}"
                    )

            else:
                logger.warning(
                    f"[Book {self.book_id}] No chunks generated, skipping embedding"
                )

            # Step 9: Update book status to "ready"
            logger.info(f"[Book {self.book_id}] Step 9: Updating status to 'ready'")
            book = self.db.query(Book).filter(Book.id == self.book_id).first()
            if book:
                book.status = "ready"
                book.chapters_detected = len(units)
                self.db.commit()

            logger.info(
                f"[Book {self.book_id}] Ingestion pipeline completed successfully! "
                f"({len(units)} units, "
                f"{sum(len(u.lessons) for u in units)} lessons, "
                f"{len(all_chunks)} chunks)"
            )

        except Exception as e:
            logger.error(
                f"[Book {self.book_id}] Ingestion pipeline failed: {e}",
                exc_info=True,
            )
            # Update book status to "error"
            try:
                book = self.db.query(Book).filter(Book.id == self.book_id).first()
                if book:
                    book.status = "error"
                    self.db.commit()
            except Exception as db_err:
                logger.error(
                    f"[Book {self.book_id}] Failed to update error status: {db_err}"
                )

    def _save_structure_to_db(self, units: list) -> dict[int, int]:
        """Save detected unit/lesson structure to the database.

        Units are saved as Chapter records, lessons as Topic records.
        This reuses the existing DB models for backward compatibility.

        Args:
            units: List of DetectedUnit objects with their lessons.

        Returns:
            Dict mapping unit_num to chapter DB ID.
        """
        # Remove any existing chapters for this book (in case of re-processing)
        self.db.query(Chapter).filter(Chapter.book_id == self.book_id).delete()
        self.db.commit()

        chapter_map: dict[int, int] = {}

        for idx, unit in enumerate(units):
            # Ensure chapter title is never empty
            chapter_title = (unit.title or "").strip()
            if not chapter_title:
                chapter_title = (
                    f"الوحدة {unit.unit_num}"
                    if unit.unit_num
                    else f"Unit {idx + 1}"
                )

            # Create chapter record (unit → chapter)
            chapter = Chapter(
                book_id=self.book_id,
                chapter_num=unit.unit_num,
                title=chapter_title,
                start_page=unit.start_page,
                end_page=unit.end_page,
            )
            self.db.add(chapter)
            self.db.flush()  # Get the chapter ID

            chapter_map[unit.unit_num] = chapter.id

            # Create topic records (lesson → topic)
            for lesson_idx, lesson in enumerate(unit.lessons):
                # Ensure topic title is never empty
                topic_title = (lesson.title or "").strip()
                if not topic_title:
                    topic_title = f"Lesson {lesson.lesson_num or lesson_idx + 1}"

                topic = Topic(
                    chapter_id=chapter.id,
                    title=topic_title[:500],  # Truncate to fit column
                    content_type="lesson",
                    difficulty="intermediate",
                    page_num=lesson.start_page,
                )
                self.db.add(topic)

        self.db.commit()
        logger.info(
            f"[Book {self.book_id}] Saved {len(units)} units to database"
        )
        return chapter_map

    def _save_chunk_metadata_to_db(self, chunks: list) -> None:
        """Save chunk metadata to the chunk_metadata table.

        Args:
            chunks: List of ContentChunk objects.
        """
        from models.chunk_metadata import ChunkMetadata

        # Remove existing chunk metadata for this book
        self.db.query(ChunkMetadata).filter(
            ChunkMetadata.book_id == self.book_id
        ).delete()
        self.db.commit()

        for idx, chunk in enumerate(chunks):
            meta = ChunkMetadata(
                book_id=self.book_id,
                chapter_id=chunk.chapter_id,
                chunk_index=idx,
                text=chunk.text,
                lesson_title=chunk.lesson_title,
                unit_title=chunk.unit_title,
                page_number=chunk.page_number,
                content_type=chunk.content_type,
                language=chunk.language,
                token_count=chunk.token_count,
            )
            self.db.add(meta)

        self.db.commit()
        logger.info(
            f"[Book {self.book_id}] Saved {len(chunks)} chunk metadata records to DB"
        )
