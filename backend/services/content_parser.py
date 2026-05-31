"""Content parsing service — uses LLM for intelligent structure detection."""

import re
import json
import logging
from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from services.pdf_extractor import PageContent

logger = logging.getLogger(__name__)


@dataclass
class DetectedUnit:
    """A unit/chapter in the textbook."""

    unit_num: int
    title: str
    start_page: int
    end_page: int
    lessons: list["DetectedLesson"] = field(default_factory=list)


@dataclass
class DetectedLesson:
    """A lesson within a unit."""

    lesson_num: int
    title: str
    start_page: int
    end_page: int
    content_summary: str = ""


@dataclass
class ContentChunk:
    """A chunk of content for embedding."""

    text: str
    chapter_num: int
    topic: str
    content_type: str  # concept, example, exercise, formula, definition
    difficulty: str  # beginner, intermediate, advanced
    page_num: int
    chunk_id: str


# Legacy aliases for backward compatibility with ingestion pipeline
DetectedChapter = DetectedUnit
DetectedTopic = DetectedLesson


class ContentParser:
    """Parses extracted text into structured units and lessons using LLM."""

    # Target chunk sizes
    CHUNK_SIZE_MAX: int = 800
    CHUNK_OVERLAP_WORDS: int = 15

    def __init__(self, pages: list, llm_service=None) -> None:
        """Initialize parser with extracted page content.

        Args:
            pages: List of PageContent objects from PDFExtractor.
            llm_service: Optional LLMService for intelligent parsing.
        """
        self.pages = pages
        self.llm_service = llm_service
        self.units: list[DetectedUnit] = []
        self.chunks: list[ContentChunk] = []

    async def parse(self) -> tuple[list[DetectedUnit], list[ContentChunk]]:
        """Main parsing method. Returns detected structure and content chunks.

        Returns:
            Tuple of (detected units, content chunks for embedding).
        """
        # Step 1: Try LLM-powered structure detection
        if self.llm_service and self.llm_service.model:
            try:
                self.units = await self._detect_structure_with_llm()
            except Exception as e:
                logger.warning(f"LLM structure detection failed: {e}", exc_info=True)
                self.units = self._detect_structure_fallback()
        else:
            logger.info("No LLM service available, using fallback structure detection")
            self.units = self._detect_structure_fallback()

        # Step 2: Create content chunks for embedding
        self.chunks = self._create_chunks()

        total_lessons = sum(len(u.lessons) for u in self.units)
        logger.info(
            f"Parsed {len(self.units)} units, "
            f"{total_lessons} lessons, "
            f"{len(self.chunks)} chunks"
        )

        return self.units, self.chunks

    # ------------------------------------------------------------------
    # Synchronous wrapper for backward compatibility
    # ------------------------------------------------------------------

    def parse_sync(self) -> tuple[list[DetectedUnit], list[ContentChunk]]:
        """Synchronous fallback parse (no LLM). Used when async is not available."""
        self.units = self._detect_structure_fallback()
        self.chunks = self._create_chunks()
        return self.units, self.chunks

    # ------------------------------------------------------------------
    # LLM-powered structure detection
    # ------------------------------------------------------------------

    async def _detect_structure_with_llm(self) -> list[DetectedUnit]:
        """Use Gemini to analyze text and detect book structure."""
        # Combine first 15-20 pages (likely contains TOC or intro)
        toc_text = self._get_text_for_pages(1, min(20, len(self.pages)))

        # First, try to find Table of Contents
        structure = await self._ask_llm_for_toc(toc_text)

        if not structure or len(structure) == 0:
            # No TOC found — analyze the full text in batches
            logger.info("No TOC found in first 20 pages, analyzing full text for structure")
            full_text = self._get_text_for_pages(1, len(self.pages))
            structure = await self._ask_llm_for_structure(full_text)

        if not structure or len(structure) == 0:
            logger.warning("LLM could not detect structure, falling back to page-range method")
            return self._detect_structure_fallback()

        return structure

    async def _ask_llm_for_toc(self, text: str) -> list[DetectedUnit]:
        """Ask LLM to extract Table of Contents from the beginning of the book."""
        prompt = f"""You are analyzing an Egyptian math textbook. The text below was extracted from the first pages of the book (possibly via OCR, so there may be errors).

Your task: Identify the TABLE OF CONTENTS or BOOK STRUCTURE.

Egyptian math textbooks are typically structured as:
- Units (وحدات) or Chapters (فصول) — usually 3-6 per term
- Lessons (دروس) within each unit — usually 3-8 per unit

Look for patterns like:
- "الوحدة الأولى: ..." (Unit 1: ...)
- "الوحدة الثانية: ..." (Unit 2: ...)
- "الدرس الأول: ..." (Lesson 1: ...)
- "الدرس الثاني: ..." (Lesson 2: ...)
- Or English equivalents: "Unit 1:", "Lesson 1:", "Chapter 1:"
- Page numbers next to titles

IMPORTANT:
- Do NOT include exercise problems, theorems, or random sentences as units/lessons
- A unit title is a BROAD topic (e.g., "Algebra", "Geometry", "Trigonometry", "الجبر", "الهندسة")
- A lesson title is a SPECIFIC concept (e.g., "Solving Quadratic Equations", "حل المعادلات التربيعية")
- If you can't find a clear structure, return an empty array

TEXT FROM BOOK:
{text[:8000]}

Return ONLY a JSON array in this exact format:
[
  {{
    "unit_num": 1,
    "title": "Unit title here",
    "start_page": 1,
    "lessons": [
      {{"lesson_num": 1, "title": "Lesson title here", "start_page": 5}},
      {{"lesson_num": 2, "title": "Lesson title here", "start_page": 12}}
    ]
  }},
  {{
    "unit_num": 2,
    "title": "Unit title here",
    "start_page": 30,
    "lessons": [...]
  }}
]

If you cannot identify a clear structure, return: []"""

        try:
            import google.generativeai as genai

            response = self.llm_service.model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.1,
                    response_mime_type="application/json",
                ),
            )
            result = json.loads(response.text)
            if isinstance(result, list):
                return self._parse_llm_structure(result)
            return []
        except Exception as e:
            logger.error(f"LLM TOC detection failed: {e}")
            return []

    async def _ask_llm_for_structure(self, text: str) -> list[DetectedUnit]:
        """Ask LLM to identify structure from the full text when no TOC is found."""
        prompt = f"""You are analyzing an Egyptian math textbook. The text was extracted via OCR and may contain errors.

Your task: Identify the UNITS and LESSONS in this textbook.

Rules:
1. A UNIT is a major section (like "Algebra", "Geometry", "Trigonometry", "Statistics")
2. A LESSON is a specific topic within a unit (like "Solving Linear Equations", "Properties of Triangles")
3. Do NOT include:
   - Exercise problems or questions as lessons
   - Random sentences or OCR garbage
   - Section headers like "You will learn", "Remember", "Think about"
   - Individual theorem names (unless they ARE the lesson topic)

Look for these indicators of lesson boundaries:
- New topic introduction with a title
- "الدرس" (lesson) keyword
- "وحدة" (unit) keyword
- Numbered sections (1-1, 1-2, 2-1, etc.)
- Clear topic shifts (from algebra to geometry, etc.)

TEXT (first 10000 chars):
{text[:10000]}

Return ONLY a JSON array:
[
  {{
    "unit_num": 1,
    "title": "Unit title (broad topic)",
    "start_page": 1,
    "lessons": [
      {{"lesson_num": 1, "title": "Specific lesson topic", "start_page": 1}},
      {{"lesson_num": 2, "title": "Specific lesson topic", "start_page": 8}}
    ]
  }}
]

If you truly cannot identify structure, create units based on major topic shifts you can detect. Every math textbook has at least 2-4 major units."""

        try:
            import google.generativeai as genai

            response = self.llm_service.model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.1,
                    response_mime_type="application/json",
                ),
            )
            result = json.loads(response.text)
            if isinstance(result, list):
                return self._parse_llm_structure(result)
            return []
        except Exception as e:
            logger.error(f"LLM structure detection failed: {e}")
            return []

    def _parse_llm_structure(self, data: list) -> list[DetectedUnit]:
        """Parse LLM JSON response into DetectedUnit objects."""
        units = []
        total_pages = len(self.pages)

        for i, unit_data in enumerate(data):
            if not isinstance(unit_data, dict):
                continue

            lessons = []
            unit_lessons = unit_data.get("lessons", [])

            for j, lesson_data in enumerate(unit_lessons):
                if not isinstance(lesson_data, dict):
                    continue

                start_page = lesson_data.get("start_page", 1)
                # Calculate end page (next lesson's start - 1, or unit end)
                if j + 1 < len(unit_lessons):
                    end_page = unit_lessons[j + 1].get("start_page", start_page + 5) - 1
                elif i + 1 < len(data):
                    end_page = data[i + 1].get("start_page", start_page + 10) - 1
                else:
                    end_page = total_pages

                lessons.append(
                    DetectedLesson(
                        lesson_num=lesson_data.get("lesson_num", j + 1),
                        title=lesson_data.get("title", f"Lesson {j + 1}"),
                        start_page=max(1, start_page),
                        end_page=min(end_page, total_pages),
                    )
                )

            unit_start = unit_data.get("start_page", 1)
            if i + 1 < len(data):
                unit_end = data[i + 1].get("start_page", unit_start + 20) - 1
            else:
                unit_end = total_pages

            units.append(
                DetectedUnit(
                    unit_num=unit_data.get("unit_num", i + 1),
                    title=unit_data.get("title", f"Unit {i + 1}"),
                    start_page=max(1, unit_start),
                    end_page=min(unit_end, total_pages),
                    lessons=lessons,
                )
            )

        return units

    # ------------------------------------------------------------------
    # Fallback structure detection (no LLM)
    # ------------------------------------------------------------------

    def _detect_structure_fallback(self) -> list[DetectedUnit]:
        """Fallback: create basic structure from page ranges when LLM is unavailable."""
        total_pages = len(self.pages)
        if total_pages == 0:
            return []

        pages_per_unit = max(15, total_pages // 4)  # ~4 units

        units = []
        for i in range(0, total_pages, pages_per_unit):
            unit_num = len(units) + 1
            start = i + 1
            end = min(i + pages_per_unit, total_pages)

            # Create 3-4 lessons per unit
            pages_per_lesson = max(4, (end - start + 1) // 4)
            lessons = []
            for j in range(start, end, pages_per_lesson):
                lesson_num = len(lessons) + 1
                lesson_end = min(j + pages_per_lesson - 1, end)

                # Try to extract a title from the first page of the lesson
                title = self._extract_title_from_page(j - 1) or f"Lesson {lesson_num}"

                lessons.append(
                    DetectedLesson(
                        lesson_num=lesson_num,
                        title=title,
                        start_page=j,
                        end_page=lesson_end,
                    )
                )

            unit_title = self._extract_title_from_page(i) or f"Unit {unit_num}"
            units.append(
                DetectedUnit(
                    unit_num=unit_num,
                    title=unit_title,
                    start_page=start,
                    end_page=end,
                    lessons=lessons,
                )
            )

        return units

    def _extract_title_from_page(self, page_idx: int) -> str:
        """Extract a meaningful title from a page (best effort)."""
        if page_idx < 0 or page_idx >= len(self.pages):
            return ""

        text = self.pages[page_idx].text
        lines = [line.strip() for line in text.split("\n") if line.strip()]

        for line in lines[:10]:  # Check first 10 lines
            # Skip lines that are clearly not titles
            if len(line) < 3 or len(line) > 100:
                continue
            if line.startswith(("(", ")", "[", "]", "{", "}")):
                continue
            if re.match(r"^\d+[\.\)]\s", line):  # Numbered exercise
                continue
            if any(
                skip in line.lower()
                for skip in [
                    "you will learn",
                    "remember",
                    "think about",
                    "from the previous",
                    "critical thinking",
                    "ae)",
                ]
            ):
                continue
            if re.match(r"^[\d\s\.\,]+$", line):  # Only numbers
                continue
            if re.match(r"^[a-z]\)", line):  # Option like "a)", "b)"
                continue
            return line[:80]

        return ""

    # ------------------------------------------------------------------
    # Text helpers
    # ------------------------------------------------------------------

    def _get_text_for_pages(self, start: int, end: int) -> str:
        """Get combined text for a page range (1-indexed)."""
        texts = []
        for i in range(start - 1, min(end, len(self.pages))):
            texts.append(f"--- Page {i + 1} ---\n{self.pages[i].text}")
        return "\n\n".join(texts)

    # ------------------------------------------------------------------
    # Chunking
    # ------------------------------------------------------------------

    def _create_chunks(self) -> list[ContentChunk]:
        """Create content chunks for embedding from the detected structure."""
        chunks = []

        for unit in self.units:
            for lesson in unit.lessons:
                # Get text for this lesson's page range
                lesson_text = self._get_text_for_pages(
                    lesson.start_page, lesson.end_page
                )

                if not lesson_text.strip():
                    continue

                # Split into chunks
                words = lesson_text.split()
                current_chunk = ""
                chunk_idx = 0

                for word in words:
                    if len(current_chunk) + len(word) + 1 > self.CHUNK_SIZE_MAX:
                        if current_chunk.strip():
                            chunks.append(
                                ContentChunk(
                                    text=current_chunk.strip(),
                                    chapter_num=unit.unit_num,
                                    topic=lesson.title,
                                    content_type=self._classify_content(current_chunk),
                                    difficulty="intermediate",
                                    page_num=lesson.start_page,
                                    chunk_id=f"u{unit.unit_num}_l{lesson.lesson_num}_{chunk_idx}",
                                )
                            )
                            chunk_idx += 1
                        # Keep overlap
                        overlap_words = current_chunk.split()[-self.CHUNK_OVERLAP_WORDS :]
                        current_chunk = " ".join(overlap_words) + " " + word
                    else:
                        current_chunk += " " + word if current_chunk else word

                # Last chunk
                if current_chunk.strip():
                    chunks.append(
                        ContentChunk(
                            text=current_chunk.strip(),
                            chapter_num=unit.unit_num,
                            topic=lesson.title,
                            content_type=self._classify_content(current_chunk),
                            difficulty="intermediate",
                            page_num=lesson.start_page,
                            chunk_id=f"u{unit.unit_num}_l{lesson.lesson_num}_{chunk_idx}",
                        )
                    )

        # If no chunks were created from lessons (e.g., units with no lessons),
        # chunk the entire content by unit
        if not chunks and self.units:
            for unit in self.units:
                unit_text = self._get_text_for_pages(unit.start_page, unit.end_page)
                if not unit_text.strip():
                    continue

                words = unit_text.split()
                current_chunk = ""
                chunk_idx = 0

                for word in words:
                    if len(current_chunk) + len(word) + 1 > self.CHUNK_SIZE_MAX:
                        if current_chunk.strip():
                            chunks.append(
                                ContentChunk(
                                    text=current_chunk.strip(),
                                    chapter_num=unit.unit_num,
                                    topic=unit.title,
                                    content_type=self._classify_content(current_chunk),
                                    difficulty="intermediate",
                                    page_num=unit.start_page,
                                    chunk_id=f"u{unit.unit_num}_{chunk_idx}",
                                )
                            )
                            chunk_idx += 1
                        overlap_words = current_chunk.split()[-self.CHUNK_OVERLAP_WORDS :]
                        current_chunk = " ".join(overlap_words) + " " + word
                    else:
                        current_chunk += " " + word if current_chunk else word

                if current_chunk.strip():
                    chunks.append(
                        ContentChunk(
                            text=current_chunk.strip(),
                            chapter_num=unit.unit_num,
                            topic=unit.title,
                            content_type=self._classify_content(current_chunk),
                            difficulty="intermediate",
                            page_num=unit.start_page,
                            chunk_id=f"u{unit.unit_num}_{chunk_idx}",
                        )
                    )

        return chunks

    def _classify_content(self, text: str) -> str:
        """Simple content type classification."""
        text_lower = text.lower()
        if any(w in text_lower for w in ["example", "مثال", "solution", "الحل"]):
            return "example"
        if any(
            w in text_lower
            for w in ["exercise", "تمرين", "find", "solve", "calculate", "أوجد"]
        ):
            return "exercise"
        if any(w in text_lower for w in ["definition", "تعريف", "means", "يعني"]):
            return "definition"
        if any(w in text_lower for w in ["formula", "قانون", "="]):
            return "formula"
        return "concept"
