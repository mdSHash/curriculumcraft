"""Subject strategy package.

A SubjectStrategy encapsulates per-subject behavior so that LLM prompts,
exam letterhead lines, default topic sections, fallback exercise templates,
DOCX rendering pipeline choice, and answer verification can be dispatched
on `book.subject_key` instead of being hardcoded for math.

Look up a strategy with:

    from services.subjects.registry import get_strategy
    strategy = get_strategy(db, subject_key)  # never returns None

The registry falls back to GenericStrategy for unknown keys, so calling
code can rely on the return value being usable.
"""

from services.subjects.base import GenericStrategy, SubjectStrategy
from services.subjects.math import MathStrategy
from services.subjects.registry import get_strategy

__all__ = [
    "GenericStrategy",
    "MathStrategy",
    "SubjectStrategy",
    "get_strategy",
]
