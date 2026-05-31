"""PDF text extraction service with pdfplumber + pytesseract fallback."""

import io
import logging
import re
from pathlib import Path
from typing import Optional

import pdfplumber
import fitz  # pymupdf
from PIL import Image, ImageEnhance, ImageFilter

logger = logging.getLogger(__name__)


class PageContent:
    """Represents extracted content from a single page."""

    def __init__(self, page_num: int, text: str, is_ocr: bool = False) -> None:
        self.page_num = page_num
        self.text = text
        self.is_ocr = is_ocr

    def __repr__(self) -> str:
        return f"<PageContent(page={self.page_num}, chars={len(self.text)}, ocr={self.is_ocr})>"


class PDFExtractor:
    """Extracts text content from PDF files using pdfplumber with OCR fallback."""

    # Minimum character threshold to consider a page as having valid digital text
    MIN_TEXT_LENGTH: int = 50

    # OCR DPI — higher = better accuracy for scanned books, but slower
    OCR_DPI: int = 400

    def __init__(self, file_path: str) -> None:
        self.file_path = Path(file_path)
        self.pages: list[PageContent] = []
        self._total_pages: int = 0

    async def extract(self) -> list[PageContent]:
        """Main extraction method. Tries pdfplumber first, falls back to OCR.

        Returns:
            List of PageContent objects for each page in the PDF.
        """
        if not self.file_path.exists():
            raise FileNotFoundError(f"PDF file not found: {self.file_path}")

        self.pages = []

        # First pass: extract with pdfplumber
        pdfplumber_pages = self._extract_with_pdfplumber()

        # Second pass: OCR fallback for pages with insufficient text
        ocr_count = 0
        quality_rejected = 0
        for page in pdfplumber_pages:
            if len(page.text.strip()) < self.MIN_TEXT_LENGTH:
                ocr_text = self._extract_with_ocr(page.page_num)
                if ocr_text and self._validate_text_quality(ocr_text):
                    self.pages.append(
                        PageContent(
                            page_num=page.page_num,
                            text=ocr_text,
                            is_ocr=True,
                        )
                    )
                    ocr_count += 1
                else:
                    if ocr_text and not self._validate_text_quality(ocr_text):
                        quality_rejected += 1
                        logger.warning(
                            f"OCR text for page {page.page_num} failed quality check, "
                            f"discarding garbage text ({len(ocr_text)} chars)"
                        )
                        self.pages.append(
                            PageContent(
                                page_num=page.page_num,
                                text="[Page content could not be extracted]",
                                is_ocr=True,
                            )
                        )
                    else:
                        # Keep whatever text we got from pdfplumber, even if short
                        self.pages.append(page)
            else:
                # Validate pdfplumber text quality too
                if self._validate_text_quality(page.text):
                    self.pages.append(page)
                else:
                    quality_rejected += 1
                    logger.warning(
                        f"pdfplumber text for page {page.page_num} failed quality check, "
                        f"discarding garbage text"
                    )
                    self.pages.append(
                        PageContent(
                            page_num=page.page_num,
                            text="[Page content could not be extracted]",
                            is_ocr=False,
                        )
                    )

        if ocr_count > 0:
            logger.info(
                f"OCR was used for {ocr_count}/{len(self.pages)} pages "
                f"(scanned content detected)"
            )
        if quality_rejected > 0:
            logger.warning(
                f"Quality gate rejected {quality_rejected} pages as garbage text"
            )

        return self.pages

    def _extract_with_pdfplumber(self) -> list[PageContent]:
        """Extract text from digital PDF pages using pdfplumber.

        Returns:
            List of PageContent objects with extracted text.
        """
        pages: list[PageContent] = []

        try:
            with pdfplumber.open(str(self.file_path)) as pdf:
                self._total_pages = len(pdf.pages)
                for i, page in enumerate(pdf.pages):
                    try:
                        text = page.extract_text() or ""
                    except Exception as e:
                        logger.warning(
                            f"pdfplumber failed on page {i + 1}: {e}"
                        )
                        text = ""

                    pages.append(
                        PageContent(page_num=i + 1, text=text, is_ocr=False)
                    )
        except Exception as e:
            logger.error(f"Failed to open PDF with pdfplumber: {e}")
            # Try to at least get page count from pymupdf
            try:
                doc = fitz.open(str(self.file_path))
                self._total_pages = len(doc)
                pages = [
                    PageContent(page_num=i + 1, text="", is_ocr=False)
                    for i in range(self._total_pages)
                ]
                doc.close()
            except Exception as e2:
                logger.error(f"Failed to open PDF with pymupdf: {e2}")
                raise RuntimeError(
                    f"Cannot open PDF file: {self.file_path}"
                ) from e2

        return pages

    def _extract_with_ocr(self, page_num: int) -> str:
        """OCR fallback for scanned/image-based pages with enhanced preprocessing.

        Uses higher DPI, grayscale conversion, contrast enhancement, sharpening,
        and binarization for better OCR accuracy on scanned Egyptian textbooks.

        Args:
            page_num: 1-based page number to OCR.

        Returns:
            Extracted text from OCR, or empty string on failure.
        """
        try:
            import pytesseract
        except ImportError:
            logger.warning(
                "pytesseract is not installed. Skipping OCR for page %d. "
                "Install with: pip install pytesseract",
                page_num,
            )
            return ""

        try:
            doc = fitz.open(str(self.file_path))
            page = doc[page_num - 1]  # 0-based index

            # Render page at high DPI for better OCR accuracy
            mat = fitz.Matrix(self.OCR_DPI / 72, self.OCR_DPI / 72)
            pix = page.get_pixmap(matrix=mat)

            # Convert to PIL Image
            img_data = pix.tobytes("png")
            image = Image.open(io.BytesIO(img_data))

            # Preprocessing for better OCR accuracy on scanned books
            # 1. Convert to grayscale
            image = image.convert("L")
            # 2. Increase contrast (helps with faded scans)
            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(1.5)
            # 3. Sharpen (helps with blurry scans)
            image = image.filter(ImageFilter.SHARPEN)
            # 4. Binarize (threshold) — clean black/white for OCR
            image = image.point(lambda x: 0 if x < 128 else 255, "1")

            # Determine OCR language based on content detection
            # Try Arabic + English for Egyptian textbooks
            ocr_lang = self._detect_ocr_language(page)

            # Run OCR with optimized settings
            text = pytesseract.image_to_string(
                image,
                lang=ocr_lang,
                config="--psm 6 --oem 3",  # PSM 6: uniform block, OEM 3: LSTM
            )

            doc.close()
            return text.strip()

        except Exception as e:
            logger.warning(f"OCR failed for page {page_num}: {e}")
            return ""

    def _detect_ocr_language(self, page) -> str:
        """Detect whether to use Arabic, English, or both for OCR.

        Checks if the page has RTL text indicators or Arabic characters.
        Falls back to 'ara+eng' for bilingual Egyptian textbooks.

        Args:
            page: A pymupdf page object.

        Returns:
            Tesseract language string (e.g., 'ara+eng', 'eng').
        """
        try:
            # Try to get any text from the page to detect language
            text = page.get_text("text")
            if text:
                # Check for Arabic characters
                arabic_chars = sum(
                    1 for c in text if "\u0600" <= c <= "\u06FF"
                )
                total_alpha = sum(1 for c in text if c.isalpha())
                if total_alpha > 0 and arabic_chars / total_alpha > 0.3:
                    return "ara+eng"
        except Exception:
            pass

        # Default: Arabic + English for Egyptian math textbooks
        return "ara+eng"

    def _validate_text_quality(self, text: str) -> bool:
        """
        Validate that extracted text is readable and not OCR garbage.
        Returns True if text passes quality checks, False if it's garbage.
        """
        if not text or len(text.strip()) < 20:
            return False

        # Check 1: Ratio of alphanumeric + Arabic characters vs total
        # Good text should be mostly readable characters
        readable_chars = len(re.findall(
            r'[\w\u0600-\u06FF\u0750-\u077F\s.,;:!?(){}[\]+=\-*/^]', text
        ))
        total_chars = len(text)
        if total_chars == 0:
            return False
        readability_ratio = readable_chars / total_chars
        if readability_ratio < 0.6:  # Less than 60% readable = garbage
            return False

        # Check 2: Average word length (garbage tends to have very short or very long "words")
        words = text.split()
        if len(words) < 3:
            return False
        avg_word_len = sum(len(w) for w in words) / len(words)
        if avg_word_len < 1.5 or avg_word_len > 25:
            return False

        # Check 3: Excessive special characters (OCR garbage has lots of ~@#$%^&*)
        special_chars = len(re.findall(r'[~@#$%&*|\\<>{}]', text))
        if special_chars / total_chars > 0.1:  # More than 10% special chars = garbage
            return False

        # Check 4: Repetitive character patterns (OCR artifact)
        if re.search(r'(.)\1{5,}', text):  # Same char repeated 6+ times
            return False

        return True

    def get_total_pages(self) -> int:
        """Return total page count.

        Returns:
            Total number of pages in the PDF.
        """
        if self._total_pages == 0:
            try:
                doc = fitz.open(str(self.file_path))
                self._total_pages = len(doc)
                doc.close()
            except Exception:
                pass
        return self._total_pages
