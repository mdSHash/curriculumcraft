"""Arabic RTL text utilities for bilingual workbook support."""


def reshape_arabic(text: str) -> str:
    """Reshape Arabic text for proper display in python-docx.

    Arabic characters need reshaping (joining forms) and bidi reordering
    for correct rendering in contexts that don't handle RTL natively.

    Args:
        text: Raw Arabic text string.

    Returns:
        Reshaped and bidi-reordered text ready for insertion into DOCX.
    """
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display

        reshaped = arabic_reshaper.reshape(text)
        return get_display(reshaped)
    except ImportError:
        # If libraries not available, return text as-is
        return text


def is_arabic(text: str) -> bool:
    """Check if text contains Arabic characters.

    Checks for characters in the Arabic Unicode blocks:
    - Arabic (U+0600–U+06FF)
    - Arabic Supplement (U+0750–U+077F)
    - Arabic Extended-A (U+08A0–U+08FF)

    Args:
        text: Text string to check.

    Returns:
        True if any Arabic characters are found.
    """
    for char in text:
        if "\u0600" <= char <= "\u06FF":
            return True
        if "\u0750" <= char <= "\u077F":
            return True
        if "\u08A0" <= char <= "\u08FF":
            return True
    return False


def format_bilingual(arabic: str, english: str) -> tuple[str, str]:
    """Format a bilingual text pair (Arabic + English).

    Reshapes the Arabic text for proper display while leaving
    the English text unchanged.

    Args:
        arabic: Arabic text string.
        english: English text string.

    Returns:
        Tuple of (reshaped_arabic, english).
    """
    return reshape_arabic(arabic), english


def get_text_direction(text: str) -> str:
    """Determine the primary text direction.

    Args:
        text: Text to analyze.

    Returns:
        'rtl' if primarily Arabic, 'ltr' otherwise.
    """
    if not text:
        return "ltr"

    arabic_count = sum(1 for c in text if is_arabic(c))
    total_alpha = sum(1 for c in text if c.isalpha())

    if total_alpha == 0:
        return "ltr"

    return "rtl" if arabic_count / total_alpha > 0.5 else "ltr"
