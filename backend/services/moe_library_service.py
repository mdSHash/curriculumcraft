"""Service to fetch and manage books from the Egyptian MOE eLibrary.

Integrates with https://ellibrary.moe.gov.eg to:
  • browse/download official student textbooks  (`/books/books.json`)
  • browse/download official weekly assessments (`/cha/books.json`)

The "cha" endpoint exposes the *Classroom & Home Assessments* — official
weekly assessment PDFs published by the Curriculum Development departments
across all subjects (Math, Arabic, Physics, Chemistry, Languages, …).
Each assessment follows a topic-organized weekly layout (W1–W11).

Subject filtering is driven by the canonical Subject taxonomy in the DB
(see backend/seeds/subjects.json + services/subjects/registry.py). The
matcher applies hamza folding so MOE catalog variants like 'اللغة الاسبانية'
and 'اللغة الإسبانية' both resolve to the same canonical subject_key.
"""

import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Optional

import httpx

from config import get_settings
from services.subjects.registry import (
    _normalize_arabic,
    resolve_subject_key_from_moe_label,
)

logger = logging.getLogger(__name__)
settings = get_settings()

# Cache duration: 24 hours in seconds
CACHE_TTL_SECONDS = 24 * 60 * 60

# Stage mapping for filtering (English UI key → Arabic catalog value)
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

    # ARRAffinity sticky-session cookies. The MOE eLibrary's Azure-fronted
    # edge enforces these for BOTH /books/books.json AND /cha/books.json
    # when called from server IPs (Hugging Face Spaces, datacenters, etc.).
    # A browser session sets them transparently, but our backend has to
    # send them explicitly or the upstream returns 4xx / empty responses.
    # Pre-Phase-5 the cookies were only applied to /cha/, which is why the
    # HF-Space-deployed `/api/moe-library/books` reliably failed while the
    # user's browser-direct curl succeeded.
    DEFAULT_MOE_COOKIES = {
        "ARRAffinity": (
            "64adb35001c568b258ff44fc1c3af6bf72cb47eb6848a69162d3eb10492d715c"
        ),
        "ARRAffinitySameSite": (
            "64adb35001c568b258ff44fc1c3af6bf72cb47eb6848a69162d3eb10492d715c"
        ),
    }
    # Backwards-compat alias for any external caller still referencing the
    # old (assessments-only) name.
    DEFAULT_ASSESSMENT_COOKIES = DEFAULT_MOE_COOKIES

    @staticmethod
    def _browser_headers(referer: str) -> dict[str, str]:
        """Build the browser-mimicking header set MOE's edge expects.

        Identical between /books/ and /cha/ except for Referer — the edge
        validates Referer matches the called path's parent dir. Mirroring
        a real Brave/Chrome request was the only way to consistently get
        200s from the HF Space's IP range.
        """
        return {
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.8",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Pragma": "no-cache",
            "Referer": referer,
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

    def __init__(self) -> None:
        # Per-endpoint header sets. Same browser shape, different Referer.
        self._client_headers = self._browser_headers(f"{self.BASE_URL}/books/")
        self._assessment_headers = self._browser_headers(f"{self.BASE_URL}/cha/")

    # ─── Session warmup ────────────────────────────────────────────────────
    #
    # MOE's Azure-fronted edge issues `ARRAffinity` sticky-session cookies
    # bound to the originating client IP. A real browser visiting the
    # parent HTML directory sets these transparently before requesting
    # books.json; from a Hugging Face Space's IP, an un-warmed-up request
    # to books.json reliably returns 403.
    #
    # The pre-Phase-5 hardcoded cookies were captured from a developer's
    # browser session and stop working as soon as their IP rotates. Better
    # approach: GET the parent directory first inside an httpx.AsyncClient
    # (which auto-collects Set-Cookie headers into its jar), THEN call the
    # JSON endpoint reusing the same client. Cookies become per-deploy
    # automatic instead of stale-secret-managed.

    async def _fetch_json_with_session(
        self,
        json_url: str,
        warmup_url: str,
        json_headers: dict[str, str],
    ) -> list[dict]:
        """Two-step fetch: warm up session at warmup_url, then GET json_url.

        Args:
            json_url: The JSON endpoint to fetch.
            warmup_url: HTML parent directory whose Set-Cookie response
                        seeds the ARRAffinity sticky-session cookies.
            json_headers: Browser-mimicking headers for the JSON request.

        Returns:
            Parsed JSON body (list of dicts).

        Raises:
            httpx.HTTPStatusError, httpx.RequestError, json.JSONDecodeError.
        """
        # Warmup uses an HTML-friendly Accept; JSON request keeps its own headers.
        warmup_headers = dict(json_headers)
        warmup_headers["Accept"] = (
            "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        )
        warmup_headers["Sec-Fetch-Dest"] = "document"
        warmup_headers["Sec-Fetch-Mode"] = "navigate"
        warmup_headers["Sec-Fetch-Site"] = "none"
        # The warmup is a top-level navigation — drop the Referer that's
        # only valid for the JSON CORS request.
        warmup_headers.pop("Referer", None)

        async with httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            cookies=self.DEFAULT_MOE_COOKIES,  # initial seed; refreshed by warmup
        ) as client:
            try:
                wu = await client.get(warmup_url, headers=warmup_headers)
                logger.info(
                    "MOE warmup %s -> %d (cookies: %s)",
                    warmup_url,
                    wu.status_code,
                    list(client.cookies.keys()),
                )
            except httpx.RequestError as e:
                logger.warning(
                    "MOE warmup at %s failed (non-fatal): %s", warmup_url, e
                )
                # Continue anyway — the seeded DEFAULT_MOE_COOKIES might
                # still work, and we'd rather see the real failure on the
                # JSON request than abort here.

            response = await client.get(json_url, headers=json_headers)
            if response.status_code >= 400:
                logger.error(
                    "MOE %s -> %d. Body (first 500): %s. Cookies sent: %s",
                    json_url,
                    response.status_code,
                    response.text[:500],
                    list(client.cookies.keys()),
                )
            response.raise_for_status()
            return response.json()

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
        """Generate a stable unique ID for an assessment entry."""
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

    # ─── Subject matching ───────────────────────────────────────────────────

    def _entry_matches_subject(
        self, entry: dict, subject_aliases_normalized: set[str]
    ) -> bool:
        """True when entry['subject'] matches any normalized alias.

        Hamza-folded both sides so 'اللغة الاسبانية' and 'اللغة الإسبانية'
        match the same alias set.
        """
        catalog_subject = _normalize_arabic(str(entry.get("subject", "")))
        if not catalog_subject:
            return False
        return catalog_subject in subject_aliases_normalized

    def _aliases_for_subject_key(self, db, subject_key: str) -> set[str]:
        """Return the normalized MOE catalog alias set for a subject_key.

        Reads from the Subject row's moe_catalog_labels list (seeded from
        subjects.json). Returns an empty set if the key is unknown — caller
        treats empty set as "match nothing".
        """
        from models.subject import Subject

        row = db.query(Subject).filter(Subject.key == subject_key).first()
        if row is None:
            return set()
        aliases = {_normalize_arabic(str(a)) for a in (row.moe_catalog_labels or [])}
        aliases.discard("")
        return aliases

    # ─── Textbook catalog ───────────────────────────────────────────────────

    async def fetch_catalog(self) -> list[dict]:
        """Fetch the full book catalog from MOE eLibrary."""
        cached = self.get_cached_catalog()
        if cached is not None:
            logger.info(f"Using cached MOE catalog: {len(cached)} books.")
            return cached

        logger.info("Fetching MOE eLibrary catalog from /books/books.json")
        try:
            books_raw = await self._fetch_json_with_session(
                json_url=self.BOOKS_API,
                warmup_url=f"{self.BASE_URL}/books/",
                json_headers=self._client_headers,
            )
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"MOE eLibrary API error: {e.response.status_code}")
        except httpx.RequestError as e:
            raise RuntimeError(f"Failed to connect to MOE eLibrary: {e}")
        except json.JSONDecodeError:
            logger.error("MOE /books/books.json returned invalid JSON.")
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

    async def get_books(
        self,
        db=None,
        subject_key: Optional[str] = None,
        grade_level: Optional[str] = None,
        stage: Optional[str] = None,
    ) -> list[dict]:
        """Filter the textbook catalog, optionally by canonical subject_key.

        Args:
            db: SQLAlchemy session (required when subject_key is given so we
                can resolve aliases). Pass None to skip subject filtering.
            subject_key: Canonical key like 'math', 'arabic_lang', 'physics'.
                         None or empty = return all subjects.
            grade_level: Optional grade key like 'primary1', 'secondary2'.
            stage: Optional stage key like 'primary', 'preparatory', 'secondary'.
        """
        catalog = await self.fetch_catalog()

        if subject_key and db is not None:
            aliases = self._aliases_for_subject_key(db, subject_key)
            if not aliases:
                logger.warning(
                    "get_books: subject_key=%r has no aliases in DB",
                    subject_key,
                )
                return []
            catalog = [
                b for b in catalog if self._entry_matches_subject(b, aliases)
            ]

        if stage and stage in STAGE_MAP:
            stage_arabic = STAGE_MAP[stage]
            catalog = [b for b in catalog if b.get("stage") == stage_arabic]

        if grade_level and grade_level in GRADE_MAP:
            grade_arabic = GRADE_MAP[grade_level]
            catalog = [b for b in catalog if b.get("grade") == grade_arabic]

        enriched = []
        for book in catalog:
            enriched.append({
                "id": book.get("id"),
                "title": book.get("subject", ""),
                "moe_subject_label": book.get("subject", ""),
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

    async def get_math_books(
        self,
        grade_level: Optional[str] = None,
        stage: Optional[str] = None,
        db=None,
    ) -> list[dict]:
        """Deprecated: use get_books(subject_key='math', ...).

        Kept for one release as a thin wrapper for any caller that still
        imports the old name.
        """
        return await self.get_books(
            db=db,
            subject_key="math",
            grade_level=grade_level,
            stage=stage,
        )

    async def list_catalog_subjects(self, db=None) -> list[dict]:
        """List the distinct subjects present in the MOE textbook catalog,
        resolved to canonical keys.

        Returns:
            List of {key, moe_label, count} dicts. `key` is None for any
            MOE catalog subject that didn't match any seeded alias —
            useful for spotting catalog drift.
        """
        catalog = await self.fetch_catalog()
        counts: dict[tuple[Optional[str], str], int] = {}
        for book in catalog:
            label = book.get("subject", "")
            if not label:
                continue
            key = (
                resolve_subject_key_from_moe_label(db, label) if db else None
            )
            counts[(key, label)] = counts.get((key, label), 0) + 1

        out = [
            {"key": key, "moe_label": label, "count": n}
            for (key, label), n in counts.items()
        ]
        out.sort(key=lambda x: (-x["count"], x["moe_label"]))
        return out

    # ─── Weekly assessments catalog (cha/) ──────────────────────────────────

    async def fetch_assessments_catalog(self) -> list[dict]:
        """Fetch the official weekly-assessments catalog from /cha/books.json."""
        cached = self.get_cached_assessments()
        if cached is not None:
            logger.info(f"Using cached MOE assessments: {len(cached)} entries.")
            return cached

        logger.info("Fetching MOE weekly-assessments catalog from /cha/books.json")
        try:
            items_raw = await self._fetch_json_with_session(
                json_url=self.ASSESSMENTS_API,
                warmup_url=f"{self.BASE_URL}/cha/",
                json_headers=self._assessment_headers,
            )
        except httpx.HTTPStatusError as e:
            raise RuntimeError(
                f"MOE eLibrary assessments API error: {e.response.status_code}"
            )
        except httpx.RequestError as e:
            raise RuntimeError(f"Failed to connect to MOE assessments: {e}")
        except json.JSONDecodeError:
            logger.error("MOE assessments API returned invalid JSON.")
            raise RuntimeError("MOE assessments returned invalid data.")

        items = []
        for item in items_raw:
            if not isinstance(item, dict):
                continue
            item["id"] = self._generate_assessment_id(item)
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

    async def get_assessments(
        self,
        db=None,
        subject_key: Optional[str] = None,
        grade_level: Optional[str] = None,
        stage: Optional[str] = None,
        week: Optional[int] = None,
    ) -> list[dict]:
        """Filter the weekly-assessments catalog, optionally by subject_key.

        Args:
            db: SQLAlchemy session, required when subject_key is given.
            subject_key: Canonical subject key. None = all subjects.
            grade_level: Optional grade key.
            stage: Optional stage key.
            week: Optional 1-based week number filter (1..11).
        """
        catalog = await self.fetch_assessments_catalog()

        if subject_key and db is not None:
            aliases = self._aliases_for_subject_key(db, subject_key)
            if not aliases:
                logger.warning(
                    "get_assessments: subject_key=%r has no aliases in DB",
                    subject_key,
                )
                return []
            catalog = [
                it for it in catalog if self._entry_matches_subject(it, aliases)
            ]

        if stage and stage in STAGE_MAP:
            stage_arabic = STAGE_MAP[stage]
            catalog = [it for it in catalog if it.get("stage") == stage_arabic]

        if grade_level and grade_level in GRADE_MAP:
            grade_arabic = GRADE_MAP[grade_level]
            catalog = [it for it in catalog if it.get("grade") == grade_arabic]

        if week is not None:
            catalog = [it for it in catalog if it.get("week_number") == week]

        enriched = []
        for item in catalog:
            enriched.append({
                "id": item.get("id"),
                "title": item.get("subject", ""),
                "moe_subject_label": item.get("subject", ""),
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

        enriched.sort(
            key=lambda x: (
                x.get("grade_key") or "",
                x.get("title") or "",
                x.get("week_number") or 99,
            )
        )
        return enriched

    async def get_math_assessments(
        self,
        grade_level: Optional[str] = None,
        stage: Optional[str] = None,
        week: Optional[int] = None,
        db=None,
    ) -> list[dict]:
        """Deprecated: use get_assessments(subject_key='math', ...)."""
        return await self.get_assessments(
            db=db,
            subject_key="math",
            grade_level=grade_level,
            stage=stage,
            week=week,
        )

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
        """Download an official assessment PDF and extract its text."""
        item = await self.get_assessment_by_id(assessment_id)
        if not item:
            logger.warning(f"Assessment {assessment_id} not found in catalog.")
            return None

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
                cache_path.unlink(missing_ok=True)
            except OSError as e:
                logger.warning(f"Failed to read cached reference text: {e}")

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
        """Extract plain text from a PDF using pdfplumber."""
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
        """Download a book or assessment PDF from the eLibrary."""
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

        headers = dict(self._assessment_headers)
        headers["Referer"] = f"{self.BASE_URL}/cha/"

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
