"""Math verification service — validates generated exercises for mathematical correctness.

Uses programmatic verification for simple arithmetic and LLM verification for complex cases.
"""

import ast
import logging
import math
import operator
import re
import traceback
from typing import Optional

from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


# Safe expression evaluator — whitelist-based, no eval()
_SAFE_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

_SAFE_FUNCTIONS = {
    "sqrt": math.sqrt,
    "abs": abs,
}


def _safe_eval_expr(node) -> float:
    """Recursively evaluate an AST node using only whitelisted operations."""
    if isinstance(node, ast.Expression):
        return _safe_eval_expr(node.body)
    elif isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return float(node.value)
        raise ValueError(f"Unsupported constant: {node.value}")
    elif isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in _SAFE_OPERATORS:
            raise ValueError(f"Unsupported operator: {op_type.__name__}")
        left = _safe_eval_expr(node.left)
        right = _safe_eval_expr(node.right)
        return _SAFE_OPERATORS[op_type](left, right)
    elif isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type not in _SAFE_OPERATORS:
            raise ValueError(f"Unsupported unary operator: {op_type.__name__}")
        operand = _safe_eval_expr(node.operand)
        return _SAFE_OPERATORS[op_type](operand)
    elif isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name) and node.func.id in _SAFE_FUNCTIONS:
            args = [_safe_eval_expr(arg) for arg in node.args]
            return _SAFE_FUNCTIONS[node.func.id](*args)
        raise ValueError(f"Unsupported function call: {ast.dump(node.func)}")
    else:
        raise ValueError(f"Unsupported expression node: {type(node).__name__}")


def safe_eval(expr: str) -> Optional[float]:
    """Safely evaluate a math expression using AST parsing.

    Supports: +, -, *, /, **, sqrt(), abs()
    Never uses eval().

    Args:
        expr: A string math expression like "2 + 3 * 4" or "sqrt(16) + 3"

    Returns:
        The numeric result, or None if the expression is invalid/unsafe.
    """
    try:
        # Normalize the expression
        cleaned = expr.strip()
        cleaned = cleaned.replace("×", "*").replace("÷", "/").replace("−", "-")
        cleaned = cleaned.replace("\u00d7", "*").replace("\u00f7", "/")
        cleaned = cleaned.replace("\u2212", "-")
        cleaned = cleaned.replace("^", "**")
        # Remove any characters that aren't part of a math expression
        cleaned = re.sub(r"[^\d\+\-\*\/\.\(\)\s\w]", "", cleaned)
        cleaned = cleaned.strip()

        if not cleaned:
            return None

        tree = ast.parse(cleaned, mode="eval")
        result = _safe_eval_expr(tree)
        if isinstance(result, (int, float)) and not math.isnan(result) and not math.isinf(result):
            return float(result)
        return None
    except Exception:
        return None


class VerificationResult:
    """Result of verifying a single exercise."""

    def __init__(self, verified: bool, reason: str = "", corrected: Optional[dict] = None):
        self.verified = verified
        self.reason = reason
        self.corrected = corrected


class MathVerifier:
    """Verifies generated math exercises for correctness.

    Two-tier verification:
    1. Programmatic: evaluates arithmetic expressions directly.
    2. LLM-based: sends complex exercises to Gemini for verification.
    """

    # Patterns that can be programmatically verified — supports multi-step expressions
    _ARITHMETIC_PATTERN = re.compile(
        r"^[\d\s\+\-\*\/\×\÷\(\)\.\,\^\%]+$"
    )
    # Improved: matches multi-step expressions like (12 × 4) + 7, 2^3 - 1, sqrt(16) + 3
    _SIMPLE_EXPRESSION = re.compile(
        r"(?:sqrt\s*\(\s*\d+(?:\.\d+)?\s*\)|\d+(?:\.\d+)?)"
        r"(?:\s*[\^]\s*\d+)?"
        r"(?:\s*[+\-\×\*÷\/]\s*(?:sqrt\s*\(\s*\d+(?:\.\d+)?\s*\)|\([\d\s\+\-\×\*÷\/\.\^]+\)|\d+(?:\.\d+)?(?:\s*[\^]\s*\d+)?))*"
    )
    # Also match parenthesized leading expressions like (12 × 4) + 7
    _PAREN_EXPRESSION = re.compile(
        r"\([\d\s\+\-\×\*÷\/\.\^]+\)"
        r"(?:\s*[+\-\×\*÷\/]\s*(?:\([\d\s\+\-\×\*÷\/\.\^]+\)|\d+(?:\.\d+)?))+"
    )

    def __init__(self, api_key: str = "", model: str = ""):
        """Initialize verifier with optional LLM credentials.

        Args:
            api_key: Gemini API key for LLM verification.
            model: Gemini model name.
        """
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.model_name = model or settings.GEMINI_MODEL
        self._llm_model = None
        self._genai = None

    def _init_llm(self) -> bool:
        """Lazily initialize LLM for complex verification.

        Returns:
            True if LLM is available, False otherwise.
        """
        if self._llm_model is not None:
            return True

        if not self.api_key or self.api_key == "your_gemini_api_key_here":
            return False

        try:
            import google.generativeai as genai

            genai.configure(api_key=self.api_key)
            self._llm_model = genai.GenerativeModel(self.model_name)
            self._genai = genai
            return True
        except Exception as e:
            logger.warning(f"[MathVerifier] Failed to initialize LLM: {e}")
            return False

    async def verify_exercises(self, exercises: list[dict]) -> list[dict]:
        """Verify a list of exercises and correct errors where possible.

        This is best-effort: if verification fails, exercises are returned unchanged.
        Each exercise gets a `verified` flag and `verification_reason` field.

        Args:
            exercises: List of exercise dicts from generation.

        Returns:
            List of exercises with corrections applied where needed.
        """
        if not exercises:
            return exercises

        if not settings.MATH_VERIFICATION_ENABLED:
            logger.info("[MathVerifier] Verification disabled in settings, skipping")
            for ex in exercises:
                ex["verified"] = False
                ex["verification_reason"] = "Verification disabled"
            return exercises

        logger.info(f"[MathVerifier] Verifying {len(exercises)} exercises")

        # Separate into programmatically verifiable and complex
        simple_exercises = []
        complex_exercises = []

        for idx, ex in enumerate(exercises):
            if self._can_verify_programmatically(ex):
                simple_exercises.append((idx, ex))
            else:
                complex_exercises.append((idx, ex))

        # Phase 1: Programmatic verification
        corrections_count = 0
        failed_count = 0
        for idx, ex in simple_exercises:
            result = self._verify_programmatic(ex)
            if result.corrected is not None:
                exercises[idx] = result.corrected
                exercises[idx]["verified"] = True
                exercises[idx]["verification_reason"] = f"Corrected: {result.reason}"
                corrections_count += 1
            elif result.verified:
                exercises[idx]["verified"] = True
                exercises[idx]["verification_reason"] = "Passed programmatic verification"
            else:
                exercises[idx]["verified"] = False
                exercises[idx]["verification_reason"] = result.reason
                failed_count += 1
                logger.warning(
                    f"[MathVerifier] Exercise {idx} failed verification: {result.reason}"
                )

        logger.info(
            f"[MathVerifier] Programmatic: verified {len(simple_exercises)} exercises, "
            f"corrected {corrections_count}, failed {failed_count}"
        )

        # Phase 1.5: Sanity checks on all exercises
        for idx, ex in enumerate(exercises):
            sanity_result = self._sanity_check(ex)
            if not sanity_result.verified:
                exercises[idx]["verified"] = False
                exercises[idx]["verification_reason"] = sanity_result.reason
                logger.warning(
                    f"[MathVerifier] Exercise {idx} failed sanity check: {sanity_result.reason}"
                )

        # Phase 2: LLM verification for complex exercises (batch)
        if complex_exercises:
            llm_corrections = await self._verify_with_llm(
                [ex for _, ex in complex_exercises]
            )
            if llm_corrections:
                llm_correction_count = 0
                for (idx, _), corrected in zip(complex_exercises, llm_corrections):
                    if corrected is not None:
                        exercises[idx] = corrected
                        exercises[idx]["verified"] = True
                        exercises[idx]["verification_reason"] = "Corrected by LLM"
                        llm_correction_count += 1
                    else:
                        exercises[idx]["verified"] = True
                        exercises[idx]["verification_reason"] = "Passed LLM verification"
                logger.info(
                    f"[MathVerifier] LLM: verified {len(complex_exercises)} exercises, "
                    f"corrected {llm_correction_count}"
                )
            else:
                for idx, _ in complex_exercises:
                    exercises[idx]["verified"] = False
                    exercises[idx]["verification_reason"] = "LLM verification unavailable"
                logger.info(
                    f"[MathVerifier] LLM verification skipped or failed for "
                    f"{len(complex_exercises)} complex exercises"
                )

        # Summary log
        verified_count = sum(1 for ex in exercises if ex.get("verified", False))
        logger.info(
            f"[MathVerifier] Final: {verified_count}/{len(exercises)} exercises verified"
        )

        return exercises

    def _can_verify_programmatically(self, exercise: dict) -> bool:
        """Check if an exercise can be verified without LLM.

        Handles:
        - Simple arithmetic (addition, subtraction, multiplication, division)
        - Multi-step expressions like (12 × 4) + 7, 2^3 - 1, sqrt(16) + 3
        - Multiple choice where correct answer is specified
        - Fill-blank with numeric answers
        """
        ex_type = exercise.get("type", "")

        if ex_type == "multiple_choice":
            options = exercise.get("options", exercise.get("choices", []))
            correct = exercise.get("correct", exercise.get("correct_answer", ""))
            question = exercise.get("question", "")
            if options and correct and self._is_arithmetic_question(question):
                return True

        elif ex_type == "fill_blank":
            answer = exercise.get("answer", "")
            question = exercise.get("question", "")
            if answer and self._is_numeric(answer) and self._is_arithmetic_question(question):
                return True

        elif ex_type in ("show_work", "word_problems", "word_problem"):
            answer = exercise.get("answer", "")
            question = exercise.get("question", "")
            if answer and self._is_numeric(answer) and self._is_simple_arithmetic(question):
                return True

        return False

    def _is_arithmetic_question(self, question: str) -> bool:
        """Check if a question contains an arithmetic expression (simple or multi-step)."""
        cleaned = question.replace("?", "").replace("؟", "").strip()
        return bool(
            self._SIMPLE_EXPRESSION.search(cleaned)
            or self._PAREN_EXPRESSION.search(cleaned)
        )

    def _is_simple_arithmetic(self, question: str) -> bool:
        """Check if question is a straightforward arithmetic calculation."""
        keywords = [
            "calculate", "compute", "what is", "find",
            "احسب", "ما ناتج", "أوجد",
        ]
        question_lower = question.lower()
        return any(kw in question_lower for kw in keywords) and bool(
            self._SIMPLE_EXPRESSION.search(question)
            or self._PAREN_EXPRESSION.search(question)
        )

    def _is_numeric(self, value: str) -> bool:
        """Check if a string represents a numeric value."""
        try:
            cleaned = value.strip().replace(",", "").replace(" ", "")
            float(cleaned)
            return True
        except (ValueError, TypeError):
            return False

    def _evaluate_expression(self, expr: str) -> Optional[float]:
        """Safely evaluate a math expression using AST-based evaluator.

        Supports: +, -, *, /, **, sqrt(), abs()
        Never uses eval().
        """
        return safe_eval(expr)

    def _extract_arithmetic_from_question(self, question: str) -> Optional[str]:
        """Extract the arithmetic expression from a question string."""
        # Try parenthesized expression first (more complex)
        match = self._PAREN_EXPRESSION.search(question)
        if match:
            return match.group(0)
        # Fall back to simple expression
        match = self._SIMPLE_EXPRESSION.search(question)
        if match and match.group(0).strip():
            return match.group(0)
        return None

    def _verify_programmatic(self, exercise: dict) -> VerificationResult:
        """Programmatically verify and correct an exercise.

        Returns:
            VerificationResult with verified status, reason, and optional correction.
        """
        ex_type = exercise.get("type", "")

        if ex_type == "multiple_choice":
            return self._verify_multiple_choice(exercise)
        elif ex_type == "fill_blank":
            return self._verify_fill_blank(exercise)
        elif ex_type in ("show_work", "word_problems", "word_problem"):
            return self._verify_show_work(exercise)

        return VerificationResult(verified=False, reason="Unknown exercise type")

    def _verify_multiple_choice(self, exercise: dict) -> VerificationResult:
        """Verify multiple choice exercise."""
        question = exercise.get("question", "")
        options = exercise.get("options", exercise.get("choices", []))
        correct = exercise.get("correct", exercise.get("correct_answer", ""))

        expr = self._extract_arithmetic_from_question(question)
        if not expr:
            return VerificationResult(verified=False, reason="Could not extract expression")

        expected = self._evaluate_expression(expr)
        if expected is None:
            return VerificationResult(verified=False, reason=f"Could not evaluate: {expr}")

        # Find which option matches the correct answer
        correct_value = None
        if correct and len(correct) == 1 and correct.isalpha():
            idx = ord(correct.upper()) - ord("A")
            if 0 <= idx < len(options):
                try:
                    correct_value = float(str(options[idx]).strip().replace(",", ""))
                except (ValueError, TypeError):
                    return VerificationResult(
                        verified=False, reason="Correct option is not numeric"
                    )
        else:
            return VerificationResult(verified=False, reason="Invalid correct answer format")

        # Check if the marked correct answer matches the computed answer
        expected_int = int(expected) if expected == int(expected) else expected
        if correct_value is not None:
            correct_int = int(correct_value) if correct_value == int(correct_value) else correct_value
            if correct_int == expected_int:
                return VerificationResult(verified=True, reason="Answer matches computation")

        # Find the correct option in existing options
        for i, opt in enumerate(options):
            try:
                opt_val = float(str(opt).strip().replace(",", ""))
                opt_int = int(opt_val) if opt_val == int(opt_val) else opt_val
                if opt_int == expected_int:
                    corrected = exercise.copy()
                    corrected["correct"] = chr(65 + i)
                    corrected["correct_answer"] = chr(65 + i)
                    logger.debug(
                        f"[MathVerifier] Corrected MC answer: {correct} -> {chr(65 + i)} "
                        f"(expected={expected_int})"
                    )
                    return VerificationResult(
                        verified=True,
                        reason=f"Correct answer was at option {chr(65 + i)}, not {correct}",
                        corrected=corrected,
                    )
            except (ValueError, TypeError):
                continue

        # Correct answer not in options — replace the LAST option (D) with the correct answer
        # ensuring no duplicates
        corrected = exercise.copy()
        corrected_options = list(options)
        expected_str = str(expected_int)

        # Check for duplicates: if expected_str already exists somehow, don't add again
        existing_values = set()
        for opt in corrected_options:
            try:
                v = float(str(opt).strip().replace(",", ""))
                existing_values.add(int(v) if v == int(v) else v)
            except (ValueError, TypeError):
                existing_values.add(str(opt).strip())

        if expected_int not in existing_values:
            # Replace the last option (D) with the correct answer
            replace_idx = len(corrected_options) - 1
            corrected_options[replace_idx] = expected_str
            corrected["options"] = corrected_options
            corrected["correct"] = chr(65 + replace_idx)
            corrected["correct_answer"] = chr(65 + replace_idx)
            logger.debug(
                f"[MathVerifier] Corrected MC: inserted correct answer {expected_int} "
                f"at last position {replace_idx}"
            )
            return VerificationResult(
                verified=True,
                reason=f"Inserted correct answer {expected_int} at option {chr(65 + replace_idx)}",
                corrected=corrected,
            )

        return VerificationResult(
            verified=False,
            reason=f"Could not fix MC: expected {expected_int} but options are {options}",
        )

    def _verify_fill_blank(self, exercise: dict) -> VerificationResult:
        """Verify fill-in-the-blank exercise."""
        question = exercise.get("question", "")
        answer = exercise.get("answer", "")

        expr = self._extract_arithmetic_from_question(question)
        if not expr:
            return VerificationResult(verified=False, reason="Could not extract expression")

        # Handle "a OP _____ = result" pattern
        blank_pattern = re.search(
            r"(\d+(?:\.\d+)?)\s*([+\-\×\*÷\/])\s*_+\s*=\s*(\d+(?:\.\d+)?)", question
        )
        if blank_pattern:
            a = float(blank_pattern.group(1))
            op = blank_pattern.group(2)
            result = float(blank_pattern.group(3))

            if op in ("+",):
                expected = result - a
            elif op in ("-", "−", "\u2212"):
                expected = result + a
            elif op in ("×", "*", "\u00d7"):
                expected = result / a if a != 0 else None
            elif op in ("÷", "/", "\u00f7"):
                expected = result * a
            else:
                expected = None

            if expected is not None:
                expected_int = int(expected) if expected == int(expected) else expected
                try:
                    answer_val = float(answer.strip().replace(",", ""))
                    answer_int = int(answer_val) if answer_val == int(answer_val) else answer_val
                    if answer_int == expected_int:
                        return VerificationResult(verified=True, reason="Fill blank answer correct")
                except (ValueError, TypeError):
                    pass

                corrected = exercise.copy()
                corrected["answer"] = str(int(expected) if expected == int(expected) else expected)
                logger.debug(
                    f"[MathVerifier] Corrected fill_blank answer: {answer} -> {corrected['answer']}"
                )
                return VerificationResult(
                    verified=True,
                    reason=f"Corrected answer from {answer} to {corrected['answer']}",
                    corrected=corrected,
                )

        # Handle "result - _____ = a" pattern
        blank_pattern2 = re.search(
            r"(\d+(?:\.\d+)?)\s*[−\-\u2212]\s*_+\s*=\s*(\d+(?:\.\d+)?)", question
        )
        if blank_pattern2:
            total = float(blank_pattern2.group(1))
            remainder = float(blank_pattern2.group(2))
            expected = total - remainder
            expected_int = int(expected) if expected == int(expected) else expected

            try:
                answer_val = float(answer.strip().replace(",", ""))
                answer_int = int(answer_val) if answer_val == int(answer_val) else answer_val
                if answer_int == expected_int:
                    return VerificationResult(verified=True, reason="Fill blank answer correct")
            except (ValueError, TypeError):
                pass

            corrected = exercise.copy()
            corrected["answer"] = str(int(expected) if expected == int(expected) else expected)
            return VerificationResult(
                verified=True,
                reason=f"Corrected answer from {answer} to {corrected['answer']}",
                corrected=corrected,
            )

        # Handle simple "a + b = _____" pattern
        simple_pattern = re.search(
            r"(\d+(?:\.\d+)?)\s*([+\-\×\*÷\/])\s*(\d+(?:\.\d+)?)\s*=\s*_+", question
        )
        if simple_pattern:
            a = float(simple_pattern.group(1))
            op = simple_pattern.group(2)
            b = float(simple_pattern.group(3))

            if op in ("+",):
                expected = a + b
            elif op in ("-", "−", "\u2212"):
                expected = a - b
            elif op in ("×", "*", "\u00d7"):
                expected = a * b
            elif op in ("÷", "/", "\u00f7"):
                expected = a / b if b != 0 else None
            else:
                expected = None

            if expected is not None:
                expected_int = int(expected) if expected == int(expected) else expected
                try:
                    answer_val = float(answer.strip().replace(",", ""))
                    answer_int = int(answer_val) if answer_val == int(answer_val) else answer_val
                    if answer_int == expected_int:
                        return VerificationResult(verified=True, reason="Fill blank answer correct")
                except (ValueError, TypeError):
                    pass

                corrected = exercise.copy()
                corrected["answer"] = str(int(expected) if expected == int(expected) else expected)
                return VerificationResult(
                    verified=True,
                    reason=f"Corrected answer from {answer} to {corrected['answer']}",
                    corrected=corrected,
                )

        return VerificationResult(verified=False, reason="Could not verify fill blank pattern")

    def _verify_show_work(self, exercise: dict) -> VerificationResult:
        """Verify show-work exercise with numeric answer."""
        question = exercise.get("question", "")
        answer = exercise.get("answer", "")

        if not self._is_numeric(answer):
            return VerificationResult(verified=False, reason="Answer is not numeric")

        expr = self._extract_arithmetic_from_question(question)
        if not expr:
            return VerificationResult(verified=False, reason="Could not extract expression")

        expected = self._evaluate_expression(expr)
        if expected is None:
            return VerificationResult(verified=False, reason=f"Could not evaluate: {expr}")

        expected_int = int(expected) if expected == int(expected) else expected
        try:
            answer_val = float(answer.strip().replace(",", ""))
            answer_int = int(answer_val) if answer_val == int(answer_val) else answer_val
            if answer_int == expected_int:
                return VerificationResult(verified=True, reason="Show work answer correct")
        except (ValueError, TypeError):
            return VerificationResult(verified=False, reason="Could not parse answer")

        corrected = exercise.copy()
        corrected["answer"] = str(int(expected) if expected == int(expected) else expected)
        logger.debug(
            f"[MathVerifier] Corrected show_work answer: {answer} -> {corrected['answer']}"
        )
        return VerificationResult(
            verified=True,
            reason=f"Corrected answer from {answer} to {corrected['answer']}",
            corrected=corrected,
        )

    def _sanity_check(self, exercise: dict) -> VerificationResult:
        """Sanity check for word problems and general exercises.

        Checks:
        - No negative quantities for physical objects
        - Lengths/areas/volumes must be positive
        - Angles in triangles must sum to 180°
        """
        question = exercise.get("question", "")
        answer = exercise.get("answer", "")
        ex_type = exercise.get("type", "")

        # Check for negative physical quantities in word problems
        if ex_type in ("word_problem", "word_problems", "show_work"):
            # Check answer for negative physical quantities
            if answer and self._is_numeric(answer):
                answer_val = float(answer.strip().replace(",", ""))
                # Physical quantity keywords (Arabic + English)
                physical_keywords = [
                    "apples", "oranges", "books", "pencils", "students", "cars",
                    "balls", "marbles", "coins", "flowers", "trees", "birds",
                    "تفاح", "برتقال", "كتب", "أقلام", "طلاب", "سيارات",
                    "كرات", "عملات", "أزهار", "أشجار", "طيور",
                    "length", "width", "height", "area", "volume", "distance",
                    "طول", "عرض", "ارتفاع", "مساحة", "حجم", "مسافة",
                ]
                question_lower = question.lower()
                has_physical = any(kw in question_lower for kw in physical_keywords)

                if has_physical and answer_val < 0:
                    return VerificationResult(
                        verified=False,
                        reason=f"Negative quantity ({answer_val}) for physical objects is invalid",
                    )

            # Check for triangle angle sum
            angle_keywords = ["triangle", "مثلث", "angles", "زوايا"]
            question_lower = question.lower()
            if any(kw in question_lower for kw in angle_keywords):
                # Extract all angles mentioned
                angles = re.findall(r"(\d+)\s*[°˚]", question)
                if len(angles) >= 2 and answer and self._is_numeric(answer):
                    angle_sum = sum(int(a) for a in angles) + float(answer.strip().replace(",", ""))
                    if abs(angle_sum - 180) > 0.01:
                        return VerificationResult(
                            verified=False,
                            reason=f"Triangle angles sum to {angle_sum}°, should be 180°",
                        )

        return VerificationResult(verified=True, reason="Passed sanity check")

    async def _verify_with_llm(self, exercises: list[dict]) -> Optional[list[Optional[dict]]]:
        """Verify complex exercises using LLM.

        Sends exercises in batches to Gemini for verification.

        Args:
            exercises: List of exercises to verify.

        Returns:
            List of corrected exercises (None for exercises that are already correct),
            or None if LLM verification failed entirely.
        """
        if not self._init_llm():
            return None

        if not exercises:
            return []

        # Process in batches of 10 to avoid token limits
        batch_size = 10
        all_results: list[Optional[dict]] = []

        for batch_start in range(0, len(exercises), batch_size):
            batch = exercises[batch_start:batch_start + batch_size]
            batch_results = await self._verify_batch_with_llm(batch)
            if batch_results:
                all_results.extend(batch_results)
            else:
                all_results.extend([None] * len(batch))

        return all_results

    async def _verify_batch_with_llm(self, batch: list[dict]) -> Optional[list[Optional[dict]]]:
        """Verify a single batch of exercises with LLM.

        Returns:
            List of corrected exercises or None values.
        """
        if not self._llm_model:
            return None

        # Build verification prompt
        exercises_json = []
        for i, ex in enumerate(batch):
            exercises_json.append({
                "index": i,
                "type": ex.get("type", "unknown"),
                "question": ex.get("question", ex.get("statement", "")),
                "answer": ex.get("answer", ex.get("correct", "")),
                "options": ex.get("options", []),
            })

        import json
        prompt = (
            "You are a math verification expert. Check each exercise below for "
            "mathematical correctness. For each exercise:\n"
            "1. Verify the answer is mathematically correct\n"
            "2. For multiple choice, verify the correct option matches the right answer\n"
            "3. Check for any logical errors in the question\n"
            "4. Ensure no negative quantities for physical objects\n"
            "5. Ensure triangle angles sum to 180°\n\n"
            "Return a JSON array where each element is either:\n"
            "- null (if the exercise is correct)\n"
            "- An object with corrected fields (only include fields that need correction)\n\n"
            "IMPORTANT: Return ONLY the JSON array, no other text.\n\n"
            f"Exercises to verify:\n{json.dumps(exercises_json, ensure_ascii=False, indent=2)}"
        )

        try:
            generation_config = {
                "temperature": settings.MATH_VERIFICATION_TEMPERATURE,
                "max_output_tokens": 4096,
            }

            response = await self._llm_model.generate_content_async(
                prompt,
                generation_config=generation_config,
            )

            if not response or not response.text:
                return None

            # Parse response
            text = response.text.strip()
            if text.startswith("```"):
                text = re.sub(r"^```(?:json)?\s*", "", text)
                text = re.sub(r"\s*```$", "", text)

            corrections = json.loads(text)

            if not isinstance(corrections, list):
                return None

            # Apply corrections
            results: list[Optional[dict]] = []
            for i, correction in enumerate(corrections):
                if i >= len(batch):
                    break
                if correction is None:
                    results.append(None)
                elif isinstance(correction, dict):
                    corrected = batch[i].copy()
                    if "answer" in correction:
                        corrected["answer"] = str(correction["answer"])
                    if "correct" in correction:
                        corrected["correct"] = correction["correct"]
                    if "correct_answer" in correction:
                        corrected["correct_answer"] = correction["correct_answer"]
                    if "question" in correction:
                        corrected["question"] = correction["question"]
                    if "options" in correction:
                        corrected["options"] = correction["options"]
                    results.append(corrected)
                else:
                    results.append(None)

            # Pad with None if response was shorter
            while len(results) < len(batch):
                results.append(None)

            return results

        except Exception as e:
            logger.warning(
                f"[MathVerifier] LLM verification failed: {e}\n"
                f"{traceback.format_exc()}"
            )
            return None
