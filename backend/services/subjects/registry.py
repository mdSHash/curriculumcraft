"""Strategy registry — looks up a SubjectStrategy by subject_key.

Loads the Subject row from the DB once per call, instantiates the
matching concrete strategy class (MathStrategy for 'math', etc.), and
falls back to GenericStrategy for keys with no dedicated class. This
means every subject in subjects.json has a usable strategy out of the
box — concrete subclasses are an opt-in optimization.
"""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from models.subject import Subject
from services.subjects.base import GenericStrategy, SubjectStrategy
from services.subjects.math import MathStrategy

logger = logging.getLogger(__name__)

# Registry of dedicated concrete strategies. Add ArabicLangStrategy here
# when Phase 5 lands its full implementation; until then arabic_lang
# automatically uses GenericStrategy + the seeded label/letterhead/topic
# section data, which is good enough for the SubjectPicker + browse
# experience that ships in Phases 3-4.
_CONCRETE: dict[str, type[SubjectStrategy]] = {
    "math": MathStrategy,
}


def get_strategy(db: Session, subject_key: Optional[str]) -> SubjectStrategy:
    """Return the SubjectStrategy for the given key.

    Never returns None: unknown keys (or None) fall back to GenericStrategy
    constructed from a minimal stub so calling code can always rely on
    strategy.label, strategy.has_math, etc.

    Args:
        db: Active SQLAlchemy session.
        subject_key: Canonical subject key (e.g. 'math', 'arabic_lang')
                     or None for an unknown book.

    Returns:
        A concrete SubjectStrategy instance.
    """
    key = (subject_key or "math").strip() or "math"

    subject = db.query(Subject).filter(Subject.key == key).first()
    if subject is None:
        logger.warning(
            "get_strategy: unknown subject_key=%r, falling back to math row",
            key,
        )
        # Try math as a last-ditch fallback so existing math users never
        # hit a code path with empty defaults.
        subject = db.query(Subject).filter(Subject.key == "math").first()

    data = (
        _row_to_dict(subject)
        if subject is not None
        else {"key": key, "label_en": key, "label_ar": key}
    )

    cls = _CONCRETE.get(data.get("key", ""), GenericStrategy)
    return cls(data)


def _row_to_dict(row: Subject) -> dict:
    """Snapshot a Subject ORM row into a plain dict for the strategy."""
    return {
        "key": row.key,
        "label_en": row.label_en,
        "label_ar": row.label_ar,
        "moe_catalog_labels": list(row.moe_catalog_labels or []),
        "content_traits": dict(row.content_traits or {}),
        "default_topic_sections": list(row.default_topic_sections or []),
        "letterhead_lines_ar": list(row.letterhead_lines_ar or []),
        "letterhead_lines_en": list(row.letterhead_lines_en or []),
    }


def resolve_subject_key_from_moe_label(
    db: Session, moe_label: str
) -> Optional[str]:
    """Map an MOE catalog `subject` string to a canonical subject_key.

    Applies hamza-fold normalization (إ/أ/آ → ا) before matching against
    each Subject's moe_catalog_labels list.

    Args:
        db: Active SQLAlchemy session.
        moe_label: The 'subject' field from a MOE catalog entry,
                   e.g. 'الرياضيات باللغة العربية'.

    Returns:
        The matching subject_key (e.g. 'math'), or None if no match.
    """
    if not moe_label:
        return None

    target = _normalize_arabic(moe_label)

    # Treat the legacy '-قديم' suffix specially — it marks the deprecated
    # Chinese curriculum which must NOT collapse into chinese_l2.
    has_legacy_suffix = "-قديم" in moe_label

    for s in db.query(Subject).all():
        for alias in s.moe_catalog_labels or []:
            if _normalize_arabic(str(alias)) == target:
                # Legacy guard: don't return a non-legacy key for a legacy label.
                if has_legacy_suffix and "-قديم" not in str(alias):
                    continue
                return s.key
    return None


_HAMZA_TRANSLATION = str.maketrans(
    {
        "إ": "ا",
        "أ": "ا",
        "آ": "ا",
        "ٱ": "ا",
    }
)


def _normalize_arabic(s: str) -> str:
    """Hamza-fold + casefold + collapse spaces.

    'اللغة الإسبانية' and 'اللغة الاسبانية' both normalize to the same form,
    fixing the MOE catalog's hamza-variant duplicates.
    """
    if not s:
        return ""
    return " ".join(s.translate(_HAMZA_TRANSLATION).split()).strip().lower()
