"""Semantic chunking service for math textbook content.

Splits text at lesson/topic boundaries, preserves math expressions intact,
and attaches rich metadata to each chunk for filtering during retrieval.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# Target chunk size in tokens (approximated as words for simplicity)
CHUNK_SIZE_TARGET = 512
CHUNK_SIZE_MAX = 1024
CHUNK_OVERLAP_TOKENS = 50


@dataclass
class ContentChunk:
    """A semantically coherent chunk of textbook content with metadata."""

    text: str
    book_id: int
    chapter_id: Optional[int] = None
    lesson_title: Optional[str] = None
    unit_title: Optional[str] = None
    page_number: Optional[int] = None
    content_type: str = "explanation"
    language: str = "ar"
    token_count: int = 0
    chunk_index: int = 0
    keywords: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.token_count == 0:
            self.token_count = estimate_tokens(self.text)


def estimate_tokens(text: str) -> int:
    """Estimate token count for a text string.

    Uses a simple heuristic: split on whitespace for Arabic/English mixed content.
    Arabic tokens are roughly 1 word = 1.5 tokens on average.
    """
    if not text:
        return 0
    words = text.split()
    arabic_count = sum(1 for w in words if any("\u0600" <= c <= "\u06FF" for c in w))
    english_count = len(words) - arabic_count
    return int(arabic_count * 1.5 + english_count * 1.3)


def detect_language(text: str) -> str:
    """Detect whether text is primarily Arabic, English, or mixed."""
    if not text:
        return "en"
    arabic_chars = sum(1 for c in text if "\u0600" <= c <= "\u06FF")
    latin_chars = sum(1 for c in text if c.isascii() and c.isalpha())
    total = arabic_chars + latin_chars
    if total == 0:
        return "ar"
    arabic_ratio = arabic_chars / total
    if arabic_ratio > 0.7:
        return "ar"
    elif arabic_ratio < 0.3:
        return "en"
    return "mixed"


def detect_content_type(text: str) -> str:
    """Classify a chunk's content type based on textual cues.

    Returns one of: definition, example, exercise, theorem, explanation.
    """
    text_lower = text.lower().strip()

    # Arabic content type markers
    arabic_definition_markers = ["تعريف", "يُعرَّف", "يعرف", "المقصود بـ"]
    arabic_example_markers = ["مثال", "حل:", "الحل:", "حل المثال"]
    arabic_exercise_markers = ["تمرين", "تدريب", "حل التمارين", "أوجد", "احسب", "أكمل"]
    arabic_theorem_markers = ["نظرية", "قاعدة", "خاصية", "قانون"]

    # English content type markers
    english_definition_markers = ["definition:", "define", "is defined as", "we define"]
    english_example_markers = ["example", "solution:", "solve:", "worked example"]
    english_exercise_markers = ["exercise", "problem", "find", "calculate", "solve", "determine"]
    english_theorem_markers = ["theorem", "rule:", "property:", "law:", "formula:"]

    # Check Arabic markers first (primary language)
    for marker in arabic_definition_markers:
        if marker in text:
            return "definition"

    for marker in arabic_theorem_markers:
        if marker in text:
            return "theorem"

    for marker in arabic_example_markers:
        if marker in text:
            return "example"

    for marker in arabic_exercise_markers:
        if marker in text:
            return "exercise"

    # Check English markers
    for marker in english_definition_markers:
        if marker in text_lower:
            return "definition"

    for marker in english_theorem_markers:
        if marker in text_lower:
            return "theorem"

    for marker in english_example_markers:
        if marker in text_lower:
            return "example"

    for marker in english_exercise_markers:
        if marker in text_lower:
            return "exercise"

    # Heuristic: if text has numbered items with math, likely exercise
    numbered_pattern = re.compile(r"^\s*[\(\[]?\d+[\)\].]", re.MULTILINE)
    if len(numbered_pattern.findall(text)) >= 3:
        return "exercise"

    # Heuristic: heavy math content (equations) suggests theorem/formula
    equation_pattern = re.compile(r"[=<>≤≥±∓]")
    if len(equation_pattern.findall(text)) >= 3:
        return "theorem"

    return "explanation"


# Regex patterns for semantic boundary detection
HEADING_PATTERNS = [
    # Arabic lesson/unit markers
    re.compile(r"^(الدرس|الوحدة|الباب|الفصل)\s*(الأول|الثاني|الثالث|الرابع|الخامس|السادس|السابع|الثامن|التاسع|العاشر|\d+)", re.MULTILINE),
    # Arabic section markers with colon
    re.compile(r"^(تعريف|مثال|تمرين|نظرية|قاعدة|ملاحظة|حل)\s*[:：]", re.MULTILINE),
    # Numbered Arabic sections
    re.compile(r"^\d+[-–]\d+\s+", re.MULTILINE),
    # English headings
    re.compile(r"^(Lesson|Unit|Chapter|Section|Example|Exercise|Theorem|Definition)\s*\d*\s*[:.]?", re.MULTILINE | re.IGNORECASE),
    # Markdown-style headings
    re.compile(r"^#{1,4}\s+", re.MULTILINE),
    # Bold text as heading (common in textbooks)
    re.compile(r"^\*\*[^*]+\*\*\s*$", re.MULTILINE),
]

# Patterns that should never be split
MATH_EXPRESSION_PATTERNS = [
    # LaTeX-style expressions
    re.compile(r"\$[^$]+\$"),
    re.compile(r"\\\([^)]+\\\)"),
    re.compile(r"\\\[[^\]]+\\\]"),
    # Multi-line equations (aligned environments)
    re.compile(r"\\begin\{[^}]+\}.*?\\end\{[^}]+\}", re.DOTALL),
    # Fraction patterns
    re.compile(r"\\frac\{[^}]+\}\{[^}]+\}"),
    # Simple inline math: numbers with operators spanning multiple tokens
    re.compile(r"\d+\s*[+\-×÷*/=<>≤≥²³√∑∏∫]\s*\d+(?:\s*[+\-×÷*/=<>≤≥²³√]\s*\d+)*"),
]

# Exercise numbering patterns
EXERCISE_NUMBER_PATTERN = re.compile(r"^\s*[\(\[]?(\d+)[\)\].]?\s+", re.MULTILINE)


class SemanticChunker:
    """Chunks textbook content by semantic boundaries, not character count.

    Respects lesson boundaries, paragraph breaks, and math expression integrity.
    Attaches rich metadata to each chunk for downstream filtering.
    """

    def __init__(
        self,
        chunk_size_target: int = CHUNK_SIZE_TARGET,
        chunk_size_max: int = CHUNK_SIZE_MAX,
        chunk_overlap_tokens: int = CHUNK_OVERLAP_TOKENS,
    ) -> None:
        self.chunk_size_target = chunk_size_target
        self.chunk_size_max = chunk_size_max
        self.chunk_overlap_tokens = chunk_overlap_tokens

    def chunk_lesson(
        self,
        lesson_text: str,
        book_id: int,
        chapter_id: Optional[int] = None,
        unit_title: Optional[str] = None,
        lesson_title: Optional[str] = None,
        start_page: Optional[int] = None,
    ) -> list[ContentChunk]:
        """Chunk a lesson's text into semantic units.

        Args:
            lesson_text: The full text of the lesson.
            book_id: Database ID of the book.
            chapter_id: Database ID of the chapter (optional).
            unit_title: Title of the unit/chapter.
            lesson_title: Title of the lesson/topic.
            start_page: Starting page number of the lesson.

        Returns:
            List of ContentChunk objects with metadata.
        """
        if not lesson_text or not lesson_text.strip():
            return []

        # Step 1: Split by semantic boundaries
        segments = self._split_by_semantic_boundaries(lesson_text)

        # Step 2: Merge small segments and split large ones to meet target size
        sized_segments = self._enforce_size_constraints(segments)

        # Step 3: Create ContentChunk objects with metadata
        chunks: list[ContentChunk] = []
        for idx, segment_text in enumerate(sized_segments):
            if not segment_text.strip():
                continue

            content_type = detect_content_type(segment_text)
            language = detect_language(segment_text)

            chunk = ContentChunk(
                text=segment_text.strip(),
                book_id=book_id,
                chapter_id=chapter_id,
                lesson_title=lesson_title,
                unit_title=unit_title,
                page_number=start_page,
                content_type=content_type,
                language=language,
                chunk_index=idx,
            )
            chunks.append(chunk)

        logger.debug(
            f"Chunked lesson '{lesson_title}' into {len(chunks)} chunks "
            f"(book_id={book_id})"
        )
        return chunks

    def chunk_full_text(
        self,
        full_text: str,
        book_id: int,
        chapter_id: Optional[int] = None,
        unit_title: Optional[str] = None,
        lesson_title: Optional[str] = None,
        start_page: Optional[int] = None,
    ) -> list[ContentChunk]:
        """Chunk arbitrary text (not necessarily a single lesson).

        Useful for processing raw extracted text that hasn't been
        split into lessons yet.

        Args:
            full_text: The text to chunk.
            book_id: Database ID of the book.
            chapter_id: Database ID of the chapter (optional).
            unit_title: Title of the unit/chapter.
            lesson_title: Title of the lesson/topic.
            start_page: Starting page number.

        Returns:
            List of ContentChunk objects with metadata.
        """
        return self.chunk_lesson(
            lesson_text=full_text,
            book_id=book_id,
            chapter_id=chapter_id,
            unit_title=unit_title,
            lesson_title=lesson_title,
            start_page=start_page,
        )

    def _split_by_semantic_boundaries(self, text: str) -> list[str]:
        """Split text at natural semantic boundaries.

        Priority order:
        1. Section headers (Arabic/English markers)
        2. Double newlines (paragraph breaks)
        3. Exercise number boundaries
        4. Never split inside math expressions
        """
        # Find all heading positions
        boundary_positions: list[int] = []

        for pattern in HEADING_PATTERNS:
            for match in pattern.finditer(text):
                boundary_positions.append(match.start())

        # Also split at double newlines (paragraph breaks)
        for match in re.finditer(r"\n\s*\n", text):
            boundary_positions.append(match.start())

        # Remove duplicates and sort
        boundary_positions = sorted(set(boundary_positions))

        # Remove boundaries that fall inside math expressions
        boundary_positions = self._filter_math_boundaries(text, boundary_positions)

        if not boundary_positions:
            return [text]

        # Split text at boundaries
        segments: list[str] = []
        prev_pos = 0
        for pos in boundary_positions:
            if pos > prev_pos:
                segment = text[prev_pos:pos]
                if segment.strip():
                    segments.append(segment)
            prev_pos = pos

        # Don't forget the last segment
        if prev_pos < len(text):
            last_segment = text[prev_pos:]
            if last_segment.strip():
                segments.append(last_segment)

        return segments if segments else [text]

    def _filter_math_boundaries(self, text: str, positions: list[int]) -> list[int]:
        """Remove boundary positions that fall inside math expressions."""
        # Find all math expression spans
        math_spans: list[tuple[int, int]] = []
        for pattern in MATH_EXPRESSION_PATTERNS:
            for match in pattern.finditer(text):
                math_spans.append((match.start(), match.end()))

        if not math_spans:
            return positions

        # Filter out positions inside math spans
        filtered: list[int] = []
        for pos in positions:
            inside_math = any(start <= pos < end for start, end in math_spans)
            if not inside_math:
                filtered.append(pos)

        return filtered

    def _enforce_size_constraints(self, segments: list[str]) -> list[str]:
        """Merge small segments and split large ones to meet target size.

        - Segments smaller than chunk_size_target/3 are merged with neighbors
        - Segments larger than chunk_size_max are split at sentence boundaries
        - Overlap is added between consecutive chunks from split segments
        """
        # Phase 1: Merge very small segments
        merged: list[str] = []
        buffer = ""

        for segment in segments:
            segment_tokens = estimate_tokens(segment)

            if segment_tokens > self.chunk_size_max:
                # Flush buffer first
                if buffer.strip():
                    merged.append(buffer.strip())
                    buffer = ""
                # Split the large segment
                sub_segments = self._split_large_segment(segment)
                merged.extend(sub_segments)
            elif estimate_tokens(buffer + "\n\n" + segment) <= self.chunk_size_target:
                # Merge with buffer
                buffer = (buffer + "\n\n" + segment).strip()
            else:
                # Flush buffer and start new one
                if buffer.strip():
                    merged.append(buffer.strip())
                buffer = segment

        # Flush remaining buffer
        if buffer.strip():
            merged.append(buffer.strip())

        # Phase 2: Add overlap between consecutive chunks
        if len(merged) <= 1:
            return merged

        result: list[str] = []
        for i, chunk_text in enumerate(merged):
            if i > 0 and self.chunk_overlap_tokens > 0:
                # Get overlap from previous chunk (last N tokens)
                prev_words = merged[i - 1].split()
                overlap_words = prev_words[-self.chunk_overlap_tokens:]
                if overlap_words:
                    overlap_text = " ".join(overlap_words)
                    # Only add overlap if it doesn't make chunk too large
                    combined = overlap_text + "\n" + chunk_text
                    if estimate_tokens(combined) <= self.chunk_size_max:
                        chunk_text = combined

            result.append(chunk_text)

        return result

    def _split_large_segment(self, text: str) -> list[str]:
        """Split a segment that exceeds chunk_size_max at sentence boundaries.

        Never splits mid-sentence or mid-formula.
        """
        # Split at sentence boundaries
        sentences = self._split_into_sentences(text)

        chunks: list[str] = []
        current_chunk: list[str] = []
        current_tokens = 0

        for sentence in sentences:
            sentence_tokens = estimate_tokens(sentence)

            if current_tokens + sentence_tokens > self.chunk_size_target and current_chunk:
                # Flush current chunk
                chunks.append(" ".join(current_chunk))
                # Keep overlap
                overlap_sentences = current_chunk[-2:] if len(current_chunk) >= 2 else current_chunk[-1:]
                current_chunk = overlap_sentences + [sentence]
                current_tokens = sum(estimate_tokens(s) for s in current_chunk)
            else:
                current_chunk.append(sentence)
                current_tokens += sentence_tokens

        # Flush remaining
        if current_chunk:
            chunks.append(" ".join(current_chunk))

        return chunks

    def _split_into_sentences(self, text: str) -> list[str]:
        """Split text into sentences, respecting Arabic and math content.

        Handles:
        - Arabic sentence endings (period, question mark)
        - English sentence endings
        - Newlines as sentence boundaries
        - Does NOT split inside math expressions
        """
        # First, protect math expressions by replacing them with placeholders
        math_placeholders: dict[str, str] = {}
        protected_text = text

        for pattern in MATH_EXPRESSION_PATTERNS:
            for match in pattern.finditer(protected_text):
                placeholder = f"__MATH_{len(math_placeholders)}__"
                math_placeholders[placeholder] = match.group()
                protected_text = protected_text.replace(match.group(), placeholder, 1)

        # Split on sentence boundaries
        # Arabic uses ، (comma) and . (period) and ؟ (question mark)
        sentence_pattern = re.compile(
            r"(?<=[.!?؟])\s+|(?<=\n)\s*(?=\S)"
        )
        raw_sentences = sentence_pattern.split(protected_text)

        # Restore math expressions
        sentences: list[str] = []
        for sent in raw_sentences:
            for placeholder, original in math_placeholders.items():
                sent = sent.replace(placeholder, original)
            sent = sent.strip()
            if sent:
                sentences.append(sent)

        return sentences if sentences else [text]
