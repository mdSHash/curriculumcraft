"""Context assembler for building coherent LLM context from retrieved chunks.

Assembles retrieved chunks into a structured context string suitable for
LLM consumption, with token budget management, deduplication, and
content-type prioritization.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# Default token budget for assembled context
DEFAULT_CONTEXT_TOKENS = 4000

# Priority order for content types (lower = higher priority)
CONTENT_TYPE_PRIORITY = {
    "definition": 0,
    "theorem": 1,
    "example": 2,
    "explanation": 3,
    "exercise": 4,
}


@dataclass
class AssembledContext:
    """Result of context assembly."""

    text: str
    total_tokens: int
    chunk_count: int
    content_types_included: list[str] = field(default_factory=list)
    lessons_included: list[str] = field(default_factory=list)


class ContextAssembler:
    """Assembles retrieved chunks into coherent LLM context.

    Features:
    - Token budget management (respects max context size)
    - Groups chunks by lesson/topic for coherence
    - Adds structural markers between sections
    - Prioritizes: definitions first, then examples, then exercises
    - Deduplicates near-identical chunks (cosine similarity > 0.95)
    """

    def __init__(
        self,
        max_tokens: int = DEFAULT_CONTEXT_TOKENS,
        dedup_threshold: float = 0.95,
        embedding_service=None,
    ) -> None:
        """Initialize the context assembler.

        Args:
            max_tokens: Maximum token budget for assembled context.
            dedup_threshold: Cosine similarity threshold for deduplication.
            embedding_service: Optional EmbeddingService for deduplication embeddings.
        """
        self.max_tokens = max_tokens
        self.dedup_threshold = dedup_threshold
        self.embedding_service = embedding_service

    def assemble(
        self,
        chunks: list[dict],
        query: Optional[str] = None,
        include_metadata_headers: bool = True,
    ) -> AssembledContext:
        """Assemble retrieved chunks into coherent context.

        Args:
            chunks: List of chunk dicts from hybrid search (with text, score, metadata).
            query: Optional original query for context header.
            include_metadata_headers: Whether to add section headers between groups.

        Returns:
            AssembledContext with the assembled text and statistics.
        """
        if not chunks:
            return AssembledContext(text="", total_tokens=0, chunk_count=0)

        # Step 1: Deduplicate near-identical chunks
        unique_chunks = self._deduplicate(chunks)

        # Step 2: Sort by content type priority, then by score
        prioritized = self._prioritize(unique_chunks)

        # Step 3: Group by lesson/topic
        grouped = self._group_by_lesson(prioritized)

        # Step 4: Assemble within token budget
        assembled = self._assemble_with_budget(
            grouped, include_metadata_headers
        )

        return assembled

    def assemble_for_exercise_generation(
        self,
        chunks: list[dict],
        topic: str,
        exercise_type: str,
        difficulty: str,
    ) -> str:
        """Assemble context specifically for exercise generation.

        Prioritizes definitions and examples that are relevant to the topic,
        and includes exercise style references.

        Args:
            chunks: Retrieved chunks from RAG.
            topic: The topic for exercise generation.
            exercise_type: Type of exercise to generate.
            difficulty: Target difficulty level.

        Returns:
            Formatted context string for LLM prompt.
        """
        if not chunks:
            return self._minimal_context(topic, exercise_type, difficulty)

        # Deduplicate
        unique_chunks = self._deduplicate(chunks)

        # Separate by content type
        definitions = [c for c in unique_chunks if c.get("content_type") == "definition"]
        theorems = [c for c in unique_chunks if c.get("content_type") == "theorem"]
        examples = [c for c in unique_chunks if c.get("content_type") == "example"]
        exercises = [c for c in unique_chunks if c.get("content_type") == "exercise"]
        explanations = [c for c in unique_chunks if c.get("content_type") == "explanation"]

        # Build context with clear sections
        parts: list[str] = []
        token_budget = self.max_tokens
        tokens_used = 0

        # Header
        header = (
            f"=== TEXTBOOK CONTENT FOR: {topic} ===\n"
            f"Exercise type: {exercise_type} | Difficulty: {difficulty}\n"
            f"{'=' * 50}\n"
        )
        header_tokens = self._estimate_tokens(header)
        parts.append(header)
        tokens_used += header_tokens

        # Definitions and theorems (highest priority)
        if definitions or theorems:
            parts.append("\n--- KEY DEFINITIONS & RULES ---")
            tokens_used += 5
            for chunk in (definitions + theorems)[:5]:
                text = chunk.get("text", "")
                chunk_tokens = self._estimate_tokens(text)
                if tokens_used + chunk_tokens > token_budget:
                    break
                parts.append(f"• {text}")
                tokens_used += chunk_tokens

        # Examples (second priority)
        if examples:
            parts.append("\n--- WORKED EXAMPLES ---")
            tokens_used += 5
            for chunk in examples[:3]:
                text = chunk.get("text", "")
                chunk_tokens = self._estimate_tokens(text)
                if tokens_used + chunk_tokens > token_budget:
                    break
                parts.append(f"Example: {text}")
                tokens_used += chunk_tokens

        # Exercise style references (for matching style)
        if exercises:
            parts.append("\n--- EXERCISE STYLE REFERENCE ---")
            tokens_used += 5
            for chunk in exercises[:2]:
                text = chunk.get("text", "")
                chunk_tokens = self._estimate_tokens(text)
                if tokens_used + chunk_tokens > token_budget:
                    break
                parts.append(f"Reference: {text}")
                tokens_used += chunk_tokens

        # Explanations (fill remaining budget)
        if explanations and tokens_used < token_budget * 0.8:
            parts.append("\n--- ADDITIONAL CONTEXT ---")
            tokens_used += 5
            for chunk in explanations[:3]:
                text = chunk.get("text", "")
                chunk_tokens = self._estimate_tokens(text)
                if tokens_used + chunk_tokens > token_budget:
                    break
                parts.append(text)
                tokens_used += chunk_tokens

        return "\n".join(parts)

    def _deduplicate(self, chunks: list[dict]) -> list[dict]:
        """Remove near-duplicate chunks based on text similarity.

        Uses simple text overlap heuristic if embedding service is not available,
        or cosine similarity if embeddings can be computed.

        Args:
            chunks: List of chunk dicts.

        Returns:
            Deduplicated list of chunks.
        """
        if len(chunks) <= 1:
            return chunks

        # Try embedding-based deduplication
        if self.embedding_service is not None:
            return self._deduplicate_with_embeddings(chunks)

        # Fallback: text overlap deduplication
        return self._deduplicate_by_text_overlap(chunks)

    def _deduplicate_with_embeddings(self, chunks: list[dict]) -> list[dict]:
        """Deduplicate using cosine similarity of embeddings."""
        texts = [c.get("text", "") for c in chunks]
        try:
            embeddings = self.embedding_service.embed_batch(texts)
        except Exception as e:
            logger.warning(f"Embedding dedup failed, using text overlap: {e}")
            return self._deduplicate_by_text_overlap(chunks)

        # Compute pairwise similarities
        unique_indices: list[int] = [0]  # Always keep first chunk

        for i in range(1, len(chunks)):
            is_duplicate = False
            for j in unique_indices:
                sim = float(np.dot(embeddings[i], embeddings[j]))
                if sim > self.dedup_threshold:
                    is_duplicate = True
                    break
            if not is_duplicate:
                unique_indices.append(i)

        return [chunks[i] for i in unique_indices]

    def _deduplicate_by_text_overlap(self, chunks: list[dict]) -> list[dict]:
        """Deduplicate using simple text overlap ratio."""
        unique: list[dict] = []

        for chunk in chunks:
            text = chunk.get("text", "").strip()
            if not text:
                continue

            is_duplicate = False
            for existing in unique:
                existing_text = existing.get("text", "")
                overlap = self._text_overlap_ratio(text, existing_text)
                if overlap > 0.85:
                    is_duplicate = True
                    break

            if not is_duplicate:
                unique.append(chunk)

        return unique

    def _text_overlap_ratio(self, text_a: str, text_b: str) -> float:
        """Calculate word-level overlap ratio between two texts."""
        words_a = set(text_a.lower().split())
        words_b = set(text_b.lower().split())

        if not words_a or not words_b:
            return 0.0

        intersection = words_a & words_b
        smaller = min(len(words_a), len(words_b))

        return len(intersection) / smaller if smaller > 0 else 0.0

    def _prioritize(self, chunks: list[dict]) -> list[dict]:
        """Sort chunks by content type priority, then by relevance score.

        Args:
            chunks: List of chunk dicts.

        Returns:
            Sorted list with definitions first, then examples, etc.
        """
        def sort_key(chunk: dict) -> tuple:
            content_type = chunk.get("content_type", "explanation")
            priority = CONTENT_TYPE_PRIORITY.get(content_type, 99)
            score = chunk.get("score", 0)
            return (priority, -score)

        return sorted(chunks, key=sort_key)

    def _group_by_lesson(self, chunks: list[dict]) -> dict[str, list[dict]]:
        """Group chunks by lesson title for coherent assembly.

        Args:
            chunks: Prioritized list of chunk dicts.

        Returns:
            Dict mapping lesson title to list of chunks.
        """
        groups: dict[str, list[dict]] = {}

        for chunk in chunks:
            lesson = chunk.get("lesson_title") or chunk.get("topic") or "General"
            if lesson not in groups:
                groups[lesson] = []
            groups[lesson].append(chunk)

        return groups

    def _assemble_with_budget(
        self,
        grouped: dict[str, list[dict]],
        include_headers: bool,
    ) -> AssembledContext:
        """Assemble grouped chunks within token budget.

        Args:
            grouped: Dict of lesson -> chunks.
            include_headers: Whether to add section headers.

        Returns:
            AssembledContext with assembled text.
        """
        parts: list[str] = []
        tokens_used = 0
        chunk_count = 0
        content_types: set[str] = set()
        lessons: list[str] = []

        for lesson_title, chunks in grouped.items():
            # Add lesson header
            if include_headers:
                header = f"\n{'─' * 40}\n📖 {lesson_title}\n{'─' * 40}"
                header_tokens = self._estimate_tokens(header)
                if tokens_used + header_tokens > self.max_tokens:
                    break
                parts.append(header)
                tokens_used += header_tokens
                lessons.append(lesson_title)

            # Add chunks for this lesson
            for chunk in chunks:
                text = chunk.get("text", "").strip()
                if not text:
                    continue

                chunk_tokens = self._estimate_tokens(text)
                if tokens_used + chunk_tokens > self.max_tokens:
                    break

                # Add content type marker
                content_type = chunk.get("content_type", "explanation")
                type_marker = self._get_type_marker(content_type)

                formatted = f"{type_marker} {text}"
                parts.append(formatted)
                tokens_used += chunk_tokens + 2  # +2 for marker
                chunk_count += 1
                content_types.add(content_type)

        assembled_text = "\n\n".join(parts)

        return AssembledContext(
            text=assembled_text,
            total_tokens=tokens_used,
            chunk_count=chunk_count,
            content_types_included=list(content_types),
            lessons_included=lessons,
        )

    def _get_type_marker(self, content_type: str) -> str:
        """Get a visual marker for content type."""
        markers = {
            "definition": "[تعريف/DEF]",
            "theorem": "[قاعدة/THM]",
            "example": "[مثال/EX]",
            "exercise": "[تمرين/PROB]",
            "explanation": "[شرح/INFO]",
        }
        return markers.get(content_type, "[INFO]")

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count for budget management."""
        if not text:
            return 0
        words = text.split()
        arabic_count = sum(1 for w in words if any("\u0600" <= c <= "\u06FF" for c in w))
        english_count = len(words) - arabic_count
        return int(arabic_count * 1.5 + english_count * 1.3)

    def _minimal_context(self, topic: str, exercise_type: str, difficulty: str) -> str:
        """Generate minimal context when no chunks are available."""
        return (
            f"Topic: {topic}\n"
            f"Exercise type: {exercise_type}\n"
            f"Difficulty: {difficulty}\n"
            f"Note: No textbook content available for this topic. "
            f"Generate exercises based on standard curriculum for this topic."
        )
