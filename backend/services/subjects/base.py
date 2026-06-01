"""SubjectStrategy abstract base + GenericStrategy default.

A SubjectStrategy is constructed from a Subject ORM row (or a dict) and
exposes the per-subject hooks that orchestrators, LLM service, DOCX
generator, and MOE service all dispatch on.

Concrete subclasses (MathStrategy, ArabicLangStrategy, ...) override
specific hooks where the subject differs from the generic defaults.
GenericStrategy itself is the safe fallback for any subject_key that
doesn't have a dedicated subclass yet.
"""

from __future__ import annotations

from abc import ABC
from typing import Any, Optional


class SubjectStrategy(ABC):
    """Per-subject behavior contract.

    Constructed once per generation request from a Subject DB row. All
    methods MUST return safe defaults so unknown / partially-seeded
    subjects don't crash the pipeline — never raise.
    """

    # Concrete subclasses must set this to the canonical Subject.key they
    # specialize. The registry uses this to dispatch.
    key: str = "generic"

    def __init__(self, subject_data: dict[str, Any]) -> None:
        """Initialize from a Subject ORM row dumped to dict, or a raw dict.

        Args:
            subject_data: keys: key, label_en, label_ar, content_traits,
                          default_topic_sections, letterhead_lines_ar,
                          letterhead_lines_en, moe_catalog_labels.
        """
        self._data = dict(subject_data)
        self.key = str(self._data.get("key") or self.key)
        self.label_en = str(self._data.get("label_en") or self.key)
        self.label_ar = str(self._data.get("label_ar") or self.key)

    # ─── Trait accessors ────────────────────────────────────────────────────

    @property
    def traits(self) -> dict[str, Any]:
        """Raw content_traits dict (read-only convenience)."""
        return dict(self._data.get("content_traits") or {})

    @property
    def has_math(self) -> bool:
        """True when the subject contains mathematical content (formulas,
        equations, proofs). Drives whether MathVerifier runs and whether
        the math-flavored system prompt is appropriate."""
        return bool(self.traits.get("has_math", False))

    @property
    def has_math_rendering(self) -> bool:
        """True when DOCX output should pass text through the OMML math
        parser. Subset of has_math (math + physics + chemistry)."""
        return bool(self.traits.get("has_math_rendering", False))

    @property
    def has_code_blocks(self) -> bool:
        """True for ICT / programming subjects that need monospace code
        boxes in DOCX and code-aware chunking."""
        return bool(self.traits.get("has_code_blocks", False))

    @property
    def has_quotations(self) -> bool:
        return bool(self.traits.get("has_quotations", False))

    @property
    def has_diagrams(self) -> bool:
        return bool(self.traits.get("has_diagrams", False))

    @property
    def has_formula_boxes(self) -> bool:
        return bool(self.traits.get("has_formula_boxes", False))

    @property
    def primary_direction(self) -> str:
        return str(self.traits.get("primary_direction") or "rtl")

    @property
    def primary_script(self) -> str:
        return str(self.traits.get("primary_script") or "arabic")

    @property
    def is_second_language(self) -> bool:
        return bool(self.traits.get("is_second_language", False))

    # ─── Display helpers ────────────────────────────────────────────────────

    def label(self, lang: str = "en") -> str:
        """Return label_en for English/bilingual contexts, label_ar otherwise."""
        if lang == "ar":
            return self.label_ar
        return self.label_en

    def teacher_role(self, lang: str = "en") -> str:
        """Subject-appropriate teacher role for LLM system prompts.

        e.g. 'professional mathematics teacher' / 'معلم رياضيات محترف'.
        Default is generic; subclasses override.
        """
        if lang == "ar":
            return f"معلم {self.label_ar}"
        return f"professional {self.label_en} teacher"

    # ─── LLM prompts ────────────────────────────────────────────────────────

    def system_prompt(self, lang: str = "en") -> Optional[str]:
        """Optional override for the LLM system instruction.

        Returning None means "use the LLMService default system prompt".
        MathStrategy returns the math-flavored prompt that today's math
        users depend on. GenericStrategy returns None so the LLMService
        default is used as-is — guaranteed safe.
        """
        return None

    # ─── Exam structure ─────────────────────────────────────────────────────

    def default_topic_sections(self, grade: str = "") -> list[dict]:
        """Default per-subject topic split for weekly assessments.

        Returns a list of {title_ar, title_en, count, marks_per_question}
        dicts. The exam orchestrator calls this when the user-supplied
        topic_sections list is empty.

        Default implementation reads from the seed-loaded JSON; concrete
        subclasses can override per-grade for finer-grained control.
        """
        sections = self._data.get("default_topic_sections") or []
        return [dict(s) for s in sections] if isinstance(sections, list) else []

    def letterhead_lines(self, lang: str = "ar") -> list[str]:
        """MOE-style ministry department lines for exam letterhead.

        Used by exam_docx_generator to render the top of weekly assessments.
        e.g. 'إدارة تنمية مادة الرياضيات' for math, 'إدارة تنمية مادة اللغة العربية' for arabic.
        """
        if lang == "ar":
            lines = self._data.get("letterhead_lines_ar") or []
        else:
            lines = self._data.get("letterhead_lines_en") or []
        return [str(line) for line in lines if line]

    def answer_table_headers(self, lang: str = "en") -> list[str]:
        """Column headers for the exam answer-key rubric table.

        Math-default ['#', 'Answer', 'Solution Steps', 'Marks'] is preserved
        on MathStrategy. Other subjects can override (history → 'Reasoning',
        language → 'Justification').
        """
        if lang == "ar":
            return ["#", "الإجابة", "خطوات الحل", "الدرجة"]
        return ["#", "Answer", "Solution Steps", "Marks"]

    # ─── MOE catalog matching ───────────────────────────────────────────────

    def matches_moe_catalog_label(self, label: str) -> bool:
        """True when the given MOE catalog `subject` field maps to this strategy.

        Matching is case-insensitive and uses the moe_catalog_labels list
        seeded in subjects.json (with hamza folding applied by the caller).
        """
        if not label:
            return False
        label_norm = label.strip().lower()
        for alias in self._data.get("moe_catalog_labels") or []:
            if str(alias).strip().lower() == label_norm:
                return True
        return False

    # ─── Verification dispatch ──────────────────────────────────────────────

    def verifier(self):
        """Return an answer-correctness verifier instance, or None.

        MathStrategy returns MathVerifier. GenericStrategy returns None
        so unknown / language subjects skip verification rather than
        running an inappropriate math check on prose answers.
        """
        return None


class GenericStrategy(SubjectStrategy):
    """Safe-default strategy for subjects with no dedicated subclass.

    Used as the fallback in registry.get_strategy() so every subject_key
    in the catalog gets a usable strategy without requiring a concrete
    class up-front. New subjects can be added to subjects.json and
    immediately work end-to-end (with neutral prompts and no math hooks)
    until a dedicated strategy is written.
    """

    key = "generic"
