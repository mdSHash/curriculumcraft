"""MathStrategy — preserves the existing math-specific behavior byte-for-byte.

This strategy is constructed automatically by the registry whenever
subject_key == 'math'. It overrides the system_prompt hook to return the
exact math system prompt the LLMService used before the multi-subject
refactor, so workbook output for math books is unchanged.

Other math hooks (verifier dispatch, math notation reminder, OMML rendering
gate) are picked up via the trait flags (has_math=True, has_math_rendering=
True, has_formula_boxes=True) seeded in subjects.json.
"""

from __future__ import annotations

from typing import Optional

from services.subjects.base import SubjectStrategy

# The math-flavored system prompt — kept identical to the constant that
# previously lived at the top of services/llm_service.py. Any change here
# changes Gemini output for math users; the snapshot test guard in Phase 5
# pins this string against the old build.
MATH_SYSTEM_PROMPT_EN = """You are a professional mathematics teacher creating exam-quality questions for the Egyptian secondary school curriculum (First Secondary / Thanawiya Amma — الصف الأول الثانوي).

ROLE & STANDARDS:
- You produce questions with absolute mathematical rigor — no approximation errors, no incorrect answers.
- Every correct_answer you provide MUST actually be correct. Before outputting, mentally solve the problem and verify.
- You use precise mathematical notation consistently.
- You create questions that match real Egyptian ministry exam style and difficulty.

MATH NOTATION FORMAT (use these consistently):
- Superscripts/powers: x^2, x^3, a^n
- Fractions: frac(numerator, denominator) — e.g., frac(3, 4) means ¾
- Square roots: sqrt(expression) — e.g., sqrt(3), sqrt(x^2 + 1)
- Subscripts: x_1, x_2, a_n
- Special symbols (use Unicode directly): ∈, ∴, ≈, ≠, ∠, ⊥, ∥, △, →, ∞, ±, ≤, ≥
- Absolute value: |x|
- Intervals: [a, b], (a, b), [a, b)
- Set notation: {x ∈ R : x > 0}

SELF-VERIFICATION RULE:
Before outputting ANY exercise, you MUST:
1. Solve the problem yourself step by step
2. Verify the correct_answer matches your solution
3. For MCQ: verify that exactly ONE option is correct and the other 3 are wrong but plausible
4. Check that the question is solvable with the given information

OUTPUT: Always return a valid JSON array. No markdown fences, no explanation text — pure JSON only."""


class MathStrategy(SubjectStrategy):
    """Math-specific strategy — preserves pre-refactor behavior."""

    key = "math"

    def teacher_role(self, lang: str = "en") -> str:
        if lang == "ar":
            return "معلم رياضيات محترف"
        return "professional mathematics teacher"

    def system_prompt(self, lang: str = "en") -> Optional[str]:
        """Return the math-flavored system prompt.

        Identical to the SYSTEM_PROMPT constant that previously lived at
        the top of services/llm_service.py.
        """
        return MATH_SYSTEM_PROMPT_EN

    def verifier(self):
        """Math verification is dispatched to MathVerifier.

        Returns None when the verifier module fails to import (e.g. sympy
        missing) so the orchestrator falls through to "all unverified"
        instead of crashing.
        """
        try:
            from services.math_verifier import MathVerifier
            return MathVerifier()
        except Exception:
            return None
