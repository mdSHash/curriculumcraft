"""RAG (Retrieval-Augmented Generation) pipeline service.

Orchestrates hybrid search (semantic + keyword) with metadata filtering,
context assembly, and fallback to pure semantic search.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class RetrievedChunk:
    """A single retrieved chunk with score and metadata."""

    text: str
    score: float
    metadata: dict = field(default_factory=dict)

    @property
    def content_type(self) -> str:
        return self.metadata.get("content_type", "explanation")

    @property
    def lesson_title(self) -> Optional[str]:
        return self.metadata.get("lesson_title")

    @property
    def chapter_id(self) -> Optional[int]:
        return self.metadata.get("chapter_id")

    @property
    def page_number(self) -> Optional[int]:
        return self.metadata.get("page_number")


class RAGService:
    """Orchestrates the full RAG pipeline: retrieve relevant content for workbook generation.

    Supports hybrid search (semantic + BM25 keyword) with metadata pre-filtering.
    Falls back to pure semantic search if hybrid search is not available.
    """

    def __init__(
        self,
        embedding_service,
        hybrid_search=None,
        context_assembler=None,
    ) -> None:
        """Initialize the RAG service.

        Args:
            embedding_service: The EmbeddingService for vector search.
            hybrid_search: Optional HybridSearch instance for combined retrieval.
            context_assembler: Optional ContextAssembler for building LLM context.
        """
        self.embedding_service = embedding_service
        self.hybrid_search = hybrid_search
        self.context_assembler = context_assembler

    def query(
        self,
        query_text: str,
        book_id: int,
        filters: Optional[dict] = None,
        top_k: int = 10,
    ) -> list[RetrievedChunk]:
        """Execute a RAG query with optional metadata filtering.

        Uses hybrid search if available, otherwise falls back to pure semantic.

        Args:
            query_text: The search query string.
            book_id: The book's database ID.
            filters: Optional metadata filters:
                     {"chapter_id": int, "lesson_title": str, "content_type": str}
            top_k: Maximum number of results to return.

        Returns:
            List of RetrievedChunk objects sorted by relevance.
        """
        if self.hybrid_search is not None:
            return self._hybrid_query(query_text, book_id, filters, top_k)
        else:
            return self._semantic_query(query_text, book_id, filters, top_k)

    def query_for_context(
        self,
        query_text: str,
        book_id: int,
        filters: Optional[dict] = None,
        top_k: int = 15,
        max_tokens: int = 4000,
    ) -> str:
        """Query and assemble context for LLM consumption.

        Combines retrieval with context assembly in one call.

        Args:
            query_text: The search query string.
            book_id: The book's database ID.
            filters: Optional metadata filters.
            top_k: Maximum chunks to retrieve.
            max_tokens: Token budget for assembled context.

        Returns:
            Assembled context string ready for LLM prompt.
        """
        chunks = self.query(query_text, book_id, filters, top_k)

        if not chunks:
            return f"No relevant content found for: {query_text}"

        # Convert to dicts for context assembler
        chunk_dicts = [
            {
                "text": c.text,
                "score": c.score,
                **c.metadata,
            }
            for c in chunks
        ]

        if self.context_assembler is not None:
            result = self.context_assembler.assemble(
                chunk_dicts, query=query_text
            )
            return result.text
        else:
            # Simple concatenation fallback
            return self._simple_assemble(chunk_dicts, max_tokens)

    def retrieve_for_exercise_generation(
        self,
        book_id: int,
        topic: str,
        exercise_type: str,
        difficulty: str,
        chapter_id: Optional[int] = None,
        top_k: int = 15,
    ) -> str:
        """Retrieve and assemble context specifically for exercise generation.

        Args:
            book_id: The book's database ID.
            topic: Topic/lesson title for the exercises.
            exercise_type: Type of exercise to generate.
            difficulty: Target difficulty level.
            chapter_id: Optional chapter filter.
            top_k: Maximum chunks to retrieve.

        Returns:
            Formatted context string for exercise generation prompt.
        """
        # Build filters
        filters = {}
        if chapter_id is not None:
            filters["chapter_id"] = chapter_id

        # Query with topic as the search text
        chunks = self.query(topic, book_id, filters, top_k)

        # Convert to dicts
        chunk_dicts = [
            {
                "text": c.text,
                "score": c.score,
                **c.metadata,
            }
            for c in chunks
        ]

        if self.context_assembler is not None:
            return self.context_assembler.assemble_for_exercise_generation(
                chunk_dicts, topic, exercise_type, difficulty
            )
        else:
            return self._simple_assemble(chunk_dicts, 4000)

    async def retrieve_for_topics(
        self,
        book_id: int,
        topics: list[str],
        content_types: Optional[list[str]] = None,
        difficulty: Optional[str] = None,
        top_k: int = 20,
    ) -> list[dict]:
        """Retrieve relevant content chunks for given topics.

        Backward-compatible async method for existing code.

        Args:
            book_id: The book's database ID.
            topics: List of topic strings to search for.
            content_types: Optional filter for content types.
            difficulty: Optional filter for difficulty level.
            top_k: Maximum results per topic query.

        Returns:
            Deduplicated and ranked list of relevant chunk dicts.
        """
        all_results: list[dict] = []
        seen_texts: set[str] = set()

        for topic in topics:
            filters = {}
            if content_types and len(content_types) == 1:
                filters["content_type"] = content_types[0]

            chunks = self.query(topic, book_id, filters, top_k)

            for chunk in chunks:
                # Apply content_type filter (multi-value)
                if content_types and chunk.content_type not in content_types:
                    continue

                # Deduplicate by text prefix (first 100 chars)
                text_key = chunk.text[:100]
                if text_key in seen_texts:
                    continue
                seen_texts.add(text_key)

                result_dict = {
                    "text": chunk.text,
                    "score": chunk.score,
                    "content_type": chunk.content_type,
                    "lesson_title": chunk.lesson_title,
                    "chapter_id": chunk.chapter_id,
                    "page_number": chunk.page_number,
                    **chunk.metadata,
                }
                all_results.append(result_dict)

        # Sort by relevance score (descending)
        all_results.sort(key=lambda x: x.get("score", 0), reverse=True)

        logger.info(
            f"Retrieved {len(all_results)} unique chunks for "
            f"{len(topics)} topics (book_id={book_id})"
        )

        return all_results

    async def get_context_for_generation(
        self,
        book_id: int,
        chapter_ids: list[int],
        exercise_types: list[str],
        difficulty_distribution: dict[str, int],
    ) -> str:
        """Build a context string for LLM workbook generation.

        Backward-compatible method that now uses hybrid search.

        Args:
            book_id: The book's database ID.
            chapter_ids: List of chapter IDs to include.
            exercise_types: Types of exercises to generate.
            difficulty_distribution: Dict mapping difficulty to count.

        Returns:
            Formatted context string for LLM prompt.
        """
        context_parts: list[str] = []

        for chapter_id in chapter_ids:
            # Retrieve definitions and concepts
            def_chunks = self.query(
                query_text="تعريف مفهوم قاعدة definition concept rule",
                book_id=book_id,
                filters={"chapter_id": chapter_id, "content_type": "definition"},
                top_k=5,
            )

            # Retrieve theorems
            thm_chunks = self.query(
                query_text="نظرية قانون خاصية theorem formula law",
                book_id=book_id,
                filters={"chapter_id": chapter_id, "content_type": "theorem"},
                top_k=3,
            )

            # Retrieve examples
            ex_chunks = self.query(
                query_text="مثال حل example solution worked",
                book_id=book_id,
                filters={"chapter_id": chapter_id, "content_type": "example"},
                top_k=3,
            )

            # Retrieve exercise style references
            prob_chunks = self.query(
                query_text="تمرين تدريب exercise problem",
                book_id=book_id,
                filters={"chapter_id": chapter_id, "content_type": "exercise"},
                top_k=3,
            )

            # Assemble chapter context
            if def_chunks or thm_chunks:
                context_parts.append(
                    f"\n{'═' * 50}\n📖 Chapter {chapter_id} — Concepts & Definitions\n{'═' * 50}"
                )
                for chunk in (def_chunks + thm_chunks)[:5]:
                    context_parts.append(f"• {chunk.text}")

            if ex_chunks:
                context_parts.append(
                    f"\n--- Chapter {chapter_id} — Worked Examples ---"
                )
                for chunk in ex_chunks[:3]:
                    context_parts.append(f"Example: {chunk.text}")

            if prob_chunks:
                context_parts.append(
                    f"\n--- Chapter {chapter_id} — Exercise Style Reference ---"
                )
                for chunk in prob_chunks[:2]:
                    context_parts.append(f"Reference: {chunk.text}")

        # Build final context
        context = "\n\n".join(context_parts)

        # Add generation instructions header
        header = (
            f"CURRICULUM CONTEXT (from textbook chapters {chapter_ids}):\n"
            f"Exercise types requested: {', '.join(exercise_types)}\n"
            f"Difficulty distribution: {difficulty_distribution}\n"
            f"{'=' * 60}\n"
        )

        return header + context

    def _hybrid_query(
        self,
        query_text: str,
        book_id: int,
        filters: Optional[dict],
        top_k: int,
    ) -> list[RetrievedChunk]:
        """Execute hybrid search (semantic + keyword).

        Args:
            query_text: Search query.
            book_id: Book database ID.
            filters: Metadata filters.
            top_k: Max results.

        Returns:
            List of RetrievedChunk objects.
        """
        try:
            results = self.hybrid_search.search(
                book_id=book_id,
                query=query_text,
                top_k=top_k,
                filters=filters,
            )
        except Exception as e:
            logger.warning(
                f"Hybrid search failed, falling back to semantic: {e}"
            )
            return self._semantic_query(query_text, book_id, filters, top_k)

        return [
            RetrievedChunk(
                text=r.get("text", ""),
                score=r.get("score", 0.0),
                metadata={
                    k: v for k, v in r.items()
                    if k not in ("text", "score", "_faiss_index")
                },
            )
            for r in results
        ]

    def _semantic_query(
        self,
        query_text: str,
        book_id: int,
        filters: Optional[dict],
        top_k: int,
    ) -> list[RetrievedChunk]:
        """Execute pure semantic (FAISS) search with post-filtering.

        Args:
            query_text: Search query.
            book_id: Book database ID.
            filters: Metadata filters (applied post-retrieval).
            top_k: Max results.

        Returns:
            List of RetrievedChunk objects.
        """
        # Retrieve more than needed to account for post-filtering
        fetch_k = top_k * 3 if filters else top_k

        results = self.embedding_service.search(
            book_id=book_id, query=query_text, top_k=fetch_k
        )

        # Apply filters post-retrieval
        if filters:
            results = self._apply_post_filters(results, filters)

        # Convert to RetrievedChunk objects
        chunks = []
        for r in results[:top_k]:
            chunks.append(
                RetrievedChunk(
                    text=r.get("text", ""),
                    score=r.get("score", 0.0),
                    metadata={
                        k: v for k, v in r.items()
                        if k not in ("text", "score")
                    },
                )
            )

        return chunks

    def _apply_post_filters(
        self, results: list[dict], filters: dict
    ) -> list[dict]:
        """Apply metadata filters to search results.

        Args:
            results: Raw search results.
            filters: Filter criteria.

        Returns:
            Filtered results.
        """
        filtered = []
        for r in results:
            passes = True

            if "chapter_id" in filters and filters["chapter_id"] is not None:
                if r.get("chapter_id") != filters["chapter_id"]:
                    passes = False

            if "lesson_title" in filters and filters["lesson_title"] is not None:
                r_lesson = (r.get("lesson_title") or r.get("topic") or "").lower()
                f_lesson = filters["lesson_title"].lower()
                if f_lesson not in r_lesson and r_lesson not in f_lesson:
                    passes = False

            if "content_type" in filters and filters["content_type"] is not None:
                if r.get("content_type") != filters["content_type"]:
                    passes = False

            if passes:
                filtered.append(r)

        return filtered

    def _simple_assemble(self, chunk_dicts: list[dict], max_tokens: int) -> str:
        """Simple context assembly without ContextAssembler.

        Args:
            chunk_dicts: List of chunk dictionaries.
            max_tokens: Token budget.

        Returns:
            Concatenated context string.
        """
        parts: list[str] = []
        tokens_used = 0

        for chunk in chunk_dicts:
            text = chunk.get("text", "")
            # Rough token estimate
            chunk_tokens = len(text.split()) * 1.3
            if tokens_used + chunk_tokens > max_tokens:
                break
            parts.append(text)
            tokens_used += chunk_tokens

        return "\n\n".join(parts)
