"""Service to fetch and manage books from the Egyptian MOE eLibrary.

Integrates with https://ellibrary.moe.gov.eg to:
  • browse/download official student textbooks  (`/books/books.json`)
  • browse/download official weekly assessments (`/cha/books.json`)

The "cha" endpoint exposes the *Classroom & Home Assessments* — official
weekly assessment PDFs published by the Mathematics Curriculum Development
Department for Secondary 1 & 2 (term 2 2025-2026 at time of writing).
Each assessment follows a topic-organized layout with three parallel
"groups" (First/Second/Third) of equivalent difficulty.
"""

import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Optional

import httpx

from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Cache duration: 24 hours in seconds
CACHE_TTL_SECONDS = 24 * 60 * 60

# Math subject keywords (Arabic variants found in the catalog)
MATH_SUBJECT_KEYWORDS = [
    "الرياضيات",
    "رياضيات",
    "Math",
]

# Stage mapping for filtering
STAGE_MAP = {
    "primary": "الإبتدائية",
    "preparatory": "الإعدادية",
    "secondary": "الثانوي العام",
    "kg": "رياض الاطفال",
}

# Grade mapping for the frontend
GRADE_MAP = {
    "primary1": "الصف الأول الإبتدائي",
    "primary2": "الصف الثاني الابتدائي",
    "primary3": "الصف الثالث الابتدائي",
    "primary4": "الصف الرابع الابتدائي",
    "primary5": "الصف الخامس الابتدائي",
    "primary6": "الصف السادس الابتدائي",
    "preparatory1": "الصف الأول الإعدادي",
    "preparatory2": "الصف الثاني الإعدادي",
    "preparatory3": "الصف الثالث الإعدادي",
    "secondary1": "الصف الاول الثانوي",
    "secondary2": "الصف الثاني الثانوي",
    "secondary3": "الصف الثالث الثانوي",
}


class MOELibraryService:
    """Service to fetch and manage books from the Egyptian MOE eLibrary."""

    BASE_URL = "https://ellibrary.moe.gov.eg"
    BOOKS_API = f"{BASE_URL}/books/books.json"
    ASSESSMENTS_API = f"{BASE_URL}/cha/books.json"

    CACHE_FILE = Path(__file__).parent.parent / "data" / "moe_catalog_cache.json"
    ASSESSMENTS_CACHE_FILE = (
        Path(__file__).parent.parent / "data" / "moe_assessments_cache.json"
    )
    REFERENCE_TEXT_CACHE = (
        Path(__file__).parent.parent / "data" / "moe_assessment_text_cache"
    )
    DOWNLOAD_DIR = Path(__file__).parent.parent / "data" / "uploads"
    REFERENCES_DIR = (
        Path(__file__).parent.parent / "data" / "moe_assessment_pdfs"
    )

    # Cookie values supplied by the user; observed to be required for the cha/
    # endpoint by some Azure-fronted edge nodes (ARRAffinity sticky-session
    # cookies). They are harmless when not strictly required.
    DEFAULT_ASSESSMENT_COOKIES = {
        "ARRAffinity": (
            "64adb35001c568b258ff44fc1c3af6bf72cb47eb6848a69162d3eb10492d715c"
        ),
        "ARRAffinitySameSite": (
            "64adb35001c568b258ff44fc1c3af6bf72cb47eb6848a69162d3eb10492d715c"
        ),
    }

    def __init__(self) -> None:
        self._client_headers = {
            "Accept": "*/*",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/148.0.0.0 Safari/537.36"
            ),
            "Referer": f"{self.BASE_URL}/books/",
        }
        # Headers used specifically when calling the cha/ endpoint. Mirror the
        # real browser request the user provided so the edge accepts us.
        self._assessment_headers = {
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.8",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Pragma": "no-cache",
            "Referer": f"{self.BASE_URL}/cha/",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "Sec-GPC": "1",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/148.0.0.0 Safari/537.36"
            ),
        }

    # ─── Catalog ID generation ──────────────────────────────────────────────

    def _generate_book_id(self, book: dict) -> str:
        """Generate a stable unique ID for a book entry based on its properties."""
        key = (
            f"{book.get('stage', '')}-{book.get('grade', '')}-"
            f"{book.get('term', '')}-{book.get('subject', '')}-"
            f"{book.get('type', '')}"
        )
        return hashlib.md5(key.encode("utf-8")).hexdigest()[:12]

    def _generate_assessment_id(self, item: dict) -> str:
        """Generate a stable unique ID for an assessment entry.

        Uses the link as part of the key because two entries can share the
        same (stage, grade, term, subject, type) tuple if the catalog is ever
        revised — the link is the unique pointer.
        """
        key = (
            f"{item.get('stage', '')}-{item.get('grade', '')}-"
            f"{item.get('term', '')}-{item.get('subject', '')}-"
            f"{item.get('type', '')}-{item.get('link', '')}"
        )
        return hashlib.md5(key.encode("utf-8")).hexdigest()[:12]

    # ─── Cache helpers ──────────────────────────────────────────────────────

    def get_cached_catalog(self) -> Optional[list[dict]]:
        """Return cached textbook catalog if available and fresh (within 24h)."""
        return self._read_catalog_cache(self.CACHE_FILE)

    def get_cached_assessments(self) -> Optional[list[dict]]:
        """Return cached weekly-assessments catalog if available and fresh."""
        return self._read_catalog_cache(self.ASSESSMENTS_CACHE_FILE)

    def _read_catalog_cache(self, path: Path) -> Optional[list[dict]]:
        if not path.exists():
            return None
        try:
            cache_data = json.loads(path.read_text(encoding="utf-8"))
            cached_at = cache_data.get("cached_at", 0)
            if time.time() - cached_at > CACHE_TTL_SECONDS:
                logger.info(f"Cache expired: {path.name}")
                return None
            return cache_data.get("books", [])
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to read catalog cache {path.name}: {e}")
            return None

    def _save_catalog_cache(self, path: Path, books: list[dict]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        cache_data = {"cached_at": time.time(), "books": books}
        path.write_text(
            json.dumps(cache_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info(f"Cached {len(books)} entries → {path.name}")

    # ─── Textbook catalog ───────────────────────────────────────────────────

    async def fetch_catalog(self) -> list[dict]:
        """Fetch the full book catalog from MOE eLibrary."""
        cached = self.get_cached_catalog()
        if cached is not None:
            logger.info(f"Using cached MOE catalog: {len(cached)} books.")
            return cached

        logger.info("Fetching MOE eLibrary catalog from API...")
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(self.BOOKS_API, headers=self._client_headers)
                response.raise_for_status()
                books_raw = response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"MOE API returned error status: {e.response.status_code}")
            raise RuntimeError(f"MOE eLibrary API error: {e.response.status_code}")
        except httpx.RequestError as e:
            logger.error(f"MOE API request failed: {e}")
            raise RuntimeError(f"Failed to connect to MOE eLibrary: {e}")
        except json.JSONDecodeError:
            logger.error("MOE API returned invalid JSON.")
            raise RuntimeError("MOE eLibrary returned invalid data.")

        books = []
        for book in books_raw:
            if not isinstance(book, dict):
                continue
            book["id"] = self._generate_book_id(book)
            books.append(book)

        self._save_catalog_cache(self.CACHE_FILE, books)
        logger.info(f"Fetched {len(books)} books from MOE eLibrary.")
        return books

    async def get_math_books(
        self, grade_level: Optional[str] = None, stage: Optional[str] = None
    ) -> list[dict]:
        """Filter catalog to only math books, optionally by grade level or stage."""
        catalog = await self.fetch_catalog()

        math_books = [
            b for b in catalog
            if any(kw in b.get("subject", "") for kw in MATH_SUBJECT_KEYWORDS)
        ]

        if stage and stage in STAGE_MAP:
            stage_arabic = STAGE_MAP[stage]
            math_books = [b for b in math_books if b.get("stage") == stage_arabic]

        if grade_level and grade_level in GRADE_MAP:
            grade_arabic = GRADE_MAP[grade_level]
            math_books = [b for b in math_books if b.get("grade") == grade_arabic]

        enriched = []
        for book in math_books:
            enriched.append({
                "id": book.get("id"),
                "title": book.get("subject", ""),
                "stage": book.get("stage", ""),
                "stage_key": self._reverse_stage_lookup(book.get("stage", "")),
                "grade": book.get("grade", ""),
                "grade_key": self._reverse_grade_lookup(book.get("grade", "")),
                "term": book.get("term", ""),
                "term_number": "1" if "الأول" in book.get("term", "") else "2",
                "type": book.get("type", ""),
                "pdf_url": book.get("link", ""),
            })

        return enriched

    # ─── Weekly assessments catalog (cha/) ──────────────────────────────────

    async def fetch_assessments_catalog(self) -> list[dict]:
        """Fetch the official weekly-assessments catalog from /cha/books.json.

        Uses the user-supplied browser headers and ARRAffinity cookies so the
        Azure edge accepts the request. Cached to disk for 24h.
        """
        cached = self.get_cached_assessments()
        if cached is not None:
            logger.info(f"Using cached MOE assessments: {len(cached)} entries.")
            return cached

        logger.info("Fetching MOE weekly-assessments catalog from /cha/books.json")
        try:
            async with httpx.AsyncClient(
                timeout=30.0,
                cookies=self.DEFAULT_ASSESSMENT_COOKIES,
            ) as client:
                response = await client.get(
                    self.ASSESSMENTS_API,
                    headers=self._assessment_headers,
                )
                response.raise_for_status()
                items_raw = response.json()
        except httpx.HTTPStatusError as e:
            logger.error(
                f"MOE assessments API returned error status: {e.response.status_code}"
            )
            raise RuntimeError(
                f"MOE eLibrary assessments API error: {e.response.status_code}"
            )
        except httpx.RequestError as e:
            logger.error(f"MOE assessments API request failed: {e}")
            raise RuntimeError(f"Failed to connect to MOE assessments: {e}")
        except json.JSONDecodeError:
            logger.error("MOE assessments API returned invalid JSON.")
            raise RuntimeError("MOE assessments returned invalid data.")

        items = []
        for item in items_raw:
            if not isinstance(item, dict):
                continue
            item["id"] = self._generate_assessment_id(item)
            # Extract a 1-based week number from the type string when possible.
            item["week_number"] = self._extract_week_number(item.get("type", ""))
            items.append(item)

        self._save_catalog_cache(self.ASSESSMENTS_CACHE_FILE, items)
        logger.info(f"Fetched {len(items)} weekly assessments from MOE.")
        return items

    @staticmethod
    def _extract_week_number(type_str) -> Optional[int]:
        """Pull '11' out of '(11) تقييمات الاسبوع الحادي عشر' if present."""
        import re
        if not isinstance(type_str, str):
            return None
        m = re.match(r"^\s*\((\d+)\)", type_str)
        if m:
            try:
                return int(m.group(1))
            except ValueError:
                return None
        return None

    async def get_math_assessments(
        self,
        grade_level: Optional[str] = None,
        stage: Optional[str] = None,
        week: Optional[int] = None,
    ) -> list[dict]:
        """Filter assessments catalog to math entries.

        Args:
            grade_level: Optional grade key like 'secondary1', 'secondary2'.
            stage: Optional stage key like 'secondary'.
            week: Optional 1-based week number filter (1..11).

        Returns:
            List of math assessment entries with normalized metadata.
        """
        catalog = await self.fetch_assessments_catalog()

        math_items = [
            it for it in catalog
            if any(kw in it.get("subject", "") for kw in MATH_SUBJECT_KEYWORDS)
        ]

        if stage and stage in STAGE_MAP:
            stage_arabic = STAGE_MAP[stage]
            math_items = [it for it in math_items if it.get("stage") == stage_arabic]

        if grade_level and grade_level in GRADE_MAP:
            grade_arabic = GRADE_MAP[grade_level]
            math_items = [it for it in math_items if it.get("grade") == grade_arabic]

        if week is not None:
            math_items = [it for it in math_items if it.get("week_number") == week]

        enriched = []
        for item in math_items:
            enriched.append({
                "id": item.get("id"),
                "title": item.get("subject", ""),
                "stage": item.get("stage", ""),
                "stage_key": self._reverse_stage_lookup(item.get("stage", "")),
                "grade": item.get("grade", ""),
                "grade_key": self._reverse_grade_lookup(item.get("grade", "")),
                "term": item.get("term", ""),
                "term_number": "1" if "الأول" in item.get("term", "") else "2",
                "type": item.get("type", ""),
                "week_number": item.get("week_number"),
                "pdf_url": item.get("link", ""),
            })

        # Sort by grade → subject → week so the UI list reads naturally.
        enriched.sort(
            key=lambda x: (
                x.get("grade_key") or "",
                x.get("title") or "",
                x.get("week_number") or 99,
            )
        )
        return enriched

    async def get_assessment_by_id(self, assessment_id: str) -> Optional[dict]:
        """Find a specific weekly assessment by its generated ID."""
        catalog = await self.fetch_assessments_catalog()
        for item in catalog:
            if item.get("id") == assessment_id:
                return item
        return None

    async def get_assessment_reference_text(
        self, assessment_id: str, max_chars: int = 12000
    ) -> Optional[str]:
        """Download an official assessment PDF and extract its text.

        The result is cached on disk so subsequent generations re-use the
        extracted text without re-downloading or re-parsing.

        Args:
            assessment_id: The catalog ID returned by `get_math_assessments`.
            max_chars: Truncate the returned text to this many chars to fit
                the LLM context window.

        Returns:
            Plain text of the official assessment, or None on failure.
        """
        item = await self.get_assessment_by_id(assessment_id)
        if not item:
            logger.warning(f"Assessment {assessment_id} not found in catalog.")
            return None

        # Cached extracted text?
        self.REFERENCE_TEXT_CACHE.mkdir(parents=True, exist_ok=True)
        cache_path = self.REFERENCE_TEXT_CACHE / f"{assessment_id}.txt"
        if cache_path.exists():
            try:
                cached_text = cache_path.read_text(encoding="utf-8")
                if cached_text.strip():
                    logger.info(
                        f"Using cached reference text for assessment {assessment_id} "
                        f"({len(cached_text)} chars)"
                    )
                    return cached_text[:max_chars]
                # Empty cache → drop it so we don't keep falling through.
                cache_path.unlink(missing_ok=True)
            except OSError as e:
                logger.warning(f"Failed to read cached reference text: {e}")

        # Download the PDF
        pdf_url = item.get("link")
        if not pdf_url:
            return None
        self.REFERENCES_DIR.mkdir(parents=True, exist_ok=True)
        pdf_path = self.REFERENCES_DIR / f"{assessment_id}.pdf"
        if not pdf_path.exists():
            try:
                await self.download_book_pdf(pdf_url, filename=str(pdf_path))
            except RuntimeError as e:
                logger.warning(f"Could not download reference PDF: {e}")
                return None

        # Extract text
        try:
            text = self._extract_pdf_text(pdf_path)
        except Exception as e:
            logger.warning(f"Failed to extract reference PDF text: {e}")
            return None

        if text:
            try:
                cache_path.write_text(text, encoding="utf-8")
            except OSError as e:
                logger.warning(f"Failed to cache reference text: {e}")

        return text[:max_chars] if text else None

    @staticmethod
    def _extract_pdf_text(pdf_path: Path) -> str:
        """Extract plain text from a PDF using pdfplumber (already a dep)."""
        import pdfplumber

        out: list[str] = []
        with pdfplumber.open(str(pdf_path)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                if page_text.strip():
                    out.append(page_text)
        return "\n\n".join(out)

    # ─── Reverse lookups ────────────────────────────────────────────────────

    def _reverse_stage_lookup(self, arabic_stage: str) -> str:
        """Get English stage key from Arabic stage name."""
        for key, val in STAGE_MAP.items():
            if val == arabic_stage:
                return key
        return ""

    def _reverse_grade_lookup(self, arabic_grade: str) -> str:
        """Get English grade key from Arabic grade name."""
        for key, val in GRADE_MAP.items():
            if val == arabic_grade:
                return key
        return ""

    # ─── PDF download ───────────────────────────────────────────────────────

    async def download_book_pdf(
        self, pdf_url: str, filename: Optional[str] = None
    ) -> str:
        """Download a book or assessment PDF from the eLibrary.

        Args:
            pdf_url: Direct URL to the PDF file.
            filename: Custom save path (absolute) OR filename within DOWNLOAD_DIR.

        Returns:
            Local file path where the PDF was saved.
        """
        if filename and Path(filename).is_absolute():
            save_path = Path(filename)
        else:
            if not filename:
                filename = pdf_url.split("/")[-1]
                if not filename.endswith(".pdf"):
                    filename += ".pdf"
            save_path = self.DOWNLOAD_DIR / filename

        save_path.parent.mkdir(parents=True, exist_ok=True)
        logger.info(f"Downloading MOE PDF: {pdf_url} -> {save_path}")

        # The blob storage CDN typically doesn't need ARRAffinity cookies, but
        # it does respect a proper UA. Use the assessment headers to be safe.
        headers = dict(self._assessment_headers)
        headers["Referer"] = f"{self.BASE_URL}/cha/"

        # Stream to a .tmp sibling and atomically rename on success so a
        # mid-stream failure can never leave a partial PDF that
        # `pdf_path.exists()` callers would mistake for a complete cache hit.
        tmp_path = save_path.with_suffix(save_path.suffix + ".tmp")
        try:
            async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
                async with client.stream("GET", pdf_url, headers=headers) as response:
                    response.raise_for_status()
                    with open(tmp_path, "wb") as f:
                        async for chunk in response.aiter_bytes(chunk_size=8192):
                            f.write(chunk)
            tmp_path.replace(save_path)
        except httpx.HTTPStatusError as e:
            tmp_path.unlink(missing_ok=True)
            logger.error(
                f"Failed to download PDF (HTTP {e.response.status_code}): {pdf_url}"
            )
            raise RuntimeError(f"Download failed: HTTP {e.response.status_code}")
        except httpx.RequestError as e:
            tmp_path.unlink(missing_ok=True)
            logger.error(f"Download request failed: {e}")
            raise RuntimeError(f"Download failed: {e}")
        except Exception:
            tmp_path.unlink(missing_ok=True)
            raise

        logger.info(f"Downloaded MOE PDF successfully: {save_path}")
        return str(save_path)

    async def get_book_by_id(self, book_id: str) -> Optional[dict]:
        """Find a specific book by its generated ID."""
        catalog = await self.fetch_catalog()
        for book in catalog:
            if book.get("id") == book_id:
                return book
        return None
