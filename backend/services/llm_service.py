"""LLM interaction service using Google Gemini for exercise generation."""

import json
import logging
import re
from typing import Optional

from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# ─── System Prompt ────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a professional mathematics teacher creating exam-quality questions for the Egyptian secondary school curriculum (First Secondary / Thanawiya Amma — الصف الأول الثانوي).

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


class LLMService:
    """Handles all LLM interactions using Google Gemini for generating workbook content."""

    def __init__(self, api_key: str, model: str = "gemini-2.5-pro"):
        self.model_name = model
        self.api_key = api_key
        self.model = None
        self._genai = None
        self._configure()
        self._probe_model()

    def _configure(self) -> None:
        """Configure the Gemini API (lazy import)."""
        try:
            import google.generativeai as genai

            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel(
                self.model_name,
                system_instruction=SYSTEM_PROMPT,
            )
            self._genai = genai
            logger.info(f"Gemini API configured with model: {self.model_name}")
        except ImportError:
            logger.warning(
                "google-generativeai not installed. LLM features disabled. "
                "Run: pip install google-generativeai"
            )
            self.model = None
            self._genai = None
        except Exception as e:
            logger.error(f"Failed to configure Gemini API: {e}")
            self.model = None
            self._genai = None

    def _probe_model(self) -> None:
        """Verify the configured Gemini model is reachable.

        Sends a tiny request to fail fast on invalid model IDs (e.g. typos
        like 'gemini-3.1-pro-preview') instead of silently falling back to
        template exercises on every generation. Logs ERROR with a clear
        remediation hint when the probe fails.
        """
        if self.model is None or self._genai is None:
            return
        try:
            response = self.model.generate_content(
                "ping",
                generation_config=self._genai.GenerationConfig(
                    temperature=0.0,
                    max_output_tokens=1,
                ),
            )
            _ = getattr(response, "text", None)
            logger.info(
                f"Gemini model probe OK: '{self.model_name}' is reachable"
            )
        except Exception as e:
            logger.error(
                "Gemini model probe FAILED for '%s': %s. "
                "All generation will silently fall back to templates. "
                "Fix: set GEMINI_MODEL in backend/.env to a valid model "
                "(e.g. 'gemini-2.5-pro' or 'gemini-2.0-flash') and restart.",
                self.model_name,
                e,
            )
            self.model = None
            self._genai = None

    # ─── Public API ─────────────────────────────────────────────────────────────

    async def generate_exercises(
        self,
        context: str,
        exercise_type: str,
        count: int,
        difficulty: str,
        language: str = "english",
        grade_level: str = "",
        lesson_title: str = "",
    ) -> list[dict]:
        """Generate exercises based on retrieved context using Gemini.

        Args:
            context: RAG-retrieved textbook content for the LLM.
            exercise_type: Type of exercise (multiple_choice, fill_in_blank, long_answer, etc.).
            count: Number of exercises to generate.
            difficulty: Difficulty level (easy, medium, hard).
            language: Output language (english, arabic, bilingual).
            grade_level: Grade level string (e.g., "الصف الأول الثانوي").
            lesson_title: Specific lesson/topic title for context.

        Returns:
            List of exercise dicts.
        """
        if self.model is None:
            logger.warning("LLM model not available, returning empty exercises")
            return []

        prompt = self._build_exercise_prompt(
            context, exercise_type, count, difficulty, language, grade_level, lesson_title
        )

        # Attempt generation with retry logic for malformed JSON
        max_retries = 2
        last_raw_response = ""

        for attempt in range(1, max_retries + 2):  # 1 initial + 2 retries
            try:
                logger.info(
                    f"Calling Gemini API (attempt {attempt}): type={exercise_type}, "
                    f"count={count}, difficulty={difficulty}, lang={language}"
                )

                current_prompt = prompt
                if attempt > 1:
                    # On retry, add explicit correction instruction
                    current_prompt = (
                        f"{prompt}\n\n"
                        f"IMPORTANT: Your previous response was not valid JSON. "
                        f"Return ONLY a raw JSON array starting with [ and ending with ]. "
                        f"No markdown code fences, no explanation text."
                    )

                response = self.model.generate_content(
                    current_prompt,
                    generation_config=self._genai.GenerationConfig(
                        temperature=settings.LLM_TEMPERATURE,
                        top_p=0.85,
                        response_mime_type="application/json",
                    ),
                )

                # Check if response was blocked or empty
                if not response.candidates:
                    logger.warning("Gemini API returned no candidates (possibly blocked by safety filters)")
                    return []

                # Extract response text
                try:
                    response_text = response.text
                except (ValueError, AttributeError) as e:
                    logger.warning(f"Gemini response has no text content: {e}")
                    return []

                if not response_text:
                    logger.warning("Gemini API returned empty response text")
                    return []

                last_raw_response = response_text

                # Parse JSON with fallback extraction
                exercises = self._parse_json_response(response_text)

                if exercises is None:
                    if attempt <= max_retries:
                        logger.warning(
                            f"Attempt {attempt}: Failed to parse JSON, retrying... "
                            f"Raw response (first 500 chars): {response_text[:500]}"
                        )
                        continue
                    else:
                        logger.error(
                            f"All {max_retries + 1} attempts failed to produce valid JSON. "
                            f"Last raw response: {last_raw_response[:1000]}"
                        )
                        return []

                # Validate exercises
                validated = self._validate_exercises(exercises, exercise_type, count)
                logger.info(
                    f"Gemini returned {len(exercises)} exercises, "
                    f"{len(validated)} passed validation"
                )
                return validated

            except Exception as e:
                if attempt <= max_retries:
                    logger.warning(f"Attempt {attempt} error ({type(e).__name__}): {e}, retrying...")
                    continue
                logger.error(f"Gemini API error after {attempt} attempts ({type(e).__name__}): {e}")
                return []

        return []

    async def generate_worked_example(
        self,
        context: str,
        topic: str,
        language: str = "english"
    ) -> dict:
        """Generate a worked example for a topic using Gemini."""
        if self.model is None:
            logger.warning("LLM model not available, returning fallback worked example")
            return self._fallback_worked_example(topic, language)

        if language in ("arabic", "bilingual"):
            lang_instruction = (
                "اكتب المثال بالعربية الفصحى. استخدم المصطلحات الرياضية العربية.\n"
                "Write the example in Arabic using proper mathematical terminology."
            )
        else:
            lang_instruction = "Write in clear English."

        prompt = f"""You are an expert Egyptian mathematics teacher creating a worked example.

Topic: {topic}
Language: {lang_instruction}

Based on this curriculum content:
{context[:settings.LLM_MAX_CONTEXT_CHARS]}

Create ONE detailed worked example with:
1. A clear problem statement appropriate for this topic
2. Step-by-step solution (numbered steps, showing all work)
3. Final answer clearly marked
4. A brief tip or note for students

Return as JSON:
{{
    "problem": "The problem statement",
    "steps": ["Step 1: ...", "Step 2: ...", "Step 3: ..."],
    "answer": "The final answer",
    "tip": "A helpful tip"
}}

CRITICAL: The example must be mathematically correct. Double-check all calculations."""

        try:
            logger.info(f"Calling Gemini API for worked example: topic={topic}")
            response = self.model.generate_content(
                prompt,
                generation_config=self._genai.GenerationConfig(
                    temperature=settings.LLM_TEMPERATURE,
                    response_mime_type="application/json",
                )
            )

            if not response.candidates:
                logger.warning("Gemini returned no candidates for worked example")
                raise ValueError("No candidates returned")

            try:
                response_text = response.text
            except (ValueError, AttributeError) as e:
                logger.warning(f"Gemini worked example response has no text: {e}")
                raise ValueError(f"No text in response: {e}")

            result = json.loads(response_text)
            logger.info(f"Gemini returned worked example for topic: {topic}")
            return result
        except Exception as e:
            logger.error(f"Gemini API error generating worked example: {e}")
            return self._fallback_worked_example(topic, language)

    # ─── JSON Parsing with Fallback ─────────────────────────────────────────────

    def _parse_json_response(self, response_text: str) -> Optional[list]:
        """Parse JSON response with multiple fallback strategies.

        Args:
            response_text: Raw text from the LLM response.

        Returns:
            Parsed list of exercises, or None if all parsing fails.
        """
        # Strategy 1: Direct parse
        try:
            result = json.loads(response_text)
            return self._normalize_parsed_result(result)
        except json.JSONDecodeError:
            pass

        # Strategy 2: Strip markdown code fences
        cleaned = response_text.strip()
        if cleaned.startswith("```"):
            # Remove opening fence (```json or ```)
            cleaned = re.sub(r"^```(?:json)?\s*\n?", "", cleaned)
            # Remove closing fence
            cleaned = re.sub(r"\n?```\s*$", "", cleaned)
            try:
                result = json.loads(cleaned)
                return self._normalize_parsed_result(result)
            except json.JSONDecodeError:
                pass

        # Strategy 3: Find JSON array pattern [...] in the text
        match = re.search(r"\[[\s\S]*\]", response_text)
        if match:
            try:
                result = json.loads(match.group(0))
                return self._normalize_parsed_result(result)
            except json.JSONDecodeError:
                pass

        # Strategy 4: Find JSON object pattern {...} and wrap in array
        match = re.search(r"\{[\s\S]*\}", response_text)
        if match:
            try:
                result = json.loads(match.group(0))
                if isinstance(result, dict):
                    return self._normalize_parsed_result(result)
            except json.JSONDecodeError:
                pass

        logger.error(f"All JSON parsing strategies failed for response: {response_text[:300]}")
        return None

    def _normalize_parsed_result(self, result) -> Optional[list]:
        """Normalize parsed JSON into a list of exercise dicts."""
        if isinstance(result, list):
            return result
        elif isinstance(result, dict) and "exercises" in result:
            return result["exercises"]
        elif isinstance(result, dict):
            return [result]
        return None

    # ─── Prompt Builder ────────────────────────────────────────────────────────

    def _build_exercise_prompt(
        self,
        context: str,
        exercise_type: str,
        count: int,
        difficulty: str,
        language: str,
        grade_level: str,
        lesson_title: str = "",
    ) -> str:
        """Build a detailed, curriculum-aligned prompt for exercise generation.

        This prompt is specifically designed for Egyptian math curriculum workbooks
        with full Arabic support and detailed quality instructions.
        """
        # ── Language-specific instructions ──
        lang_config = {
            "arabic": {
                "instruction": (
                    "اكتب جميع التمارين بالعربية الفصحى.\n"
                    "استخدم المصطلحات الرياضية العربية المعتمدة في المنهج المصري.\n"
                    "Write ALL exercise text in Modern Standard Arabic.\n"
                    "Use Arabic mathematical terminology as used in Egyptian curriculum."
                ),
                "notation": (
                    "Use Arabic mathematical notation:\n"
                    "- Use × for multiplication (not *)\n"
                    "- Use ÷ for division (not /)\n"
                    "- Numbers can be in Hindu-Arabic numerals (1,2,3)\n"
                    "- Use Arabic terms: جمع (addition), طرح (subtraction), "
                    "ضرب (multiplication), قسمة (division)\n"
                    "- Fractions: frac(numerator, denominator)\n"
                    "- Geometry terms in Arabic: مثلث, مربع, مستطيل, دائرة\n"
                    "- Use Egyptian context: جنيه (pounds), Egyptian names, local scenarios"
                ),
            },
            "english": {
                "instruction": "Write all exercises in clear, simple English.",
                "notation": (
                    "Use the math notation format defined in the system prompt:\n"
                    "- Powers: x^2, x^3\n"
                    "- Fractions: frac(a, b)\n"
                    "- Roots: sqrt(x)\n"
                    "- Subscripts: x_1, x_2\n"
                    "- Symbols: ∈, ∴, ≈, ≠, ∠, ⊥, ∥, △"
                ),
            },
            "bilingual": {
                "instruction": (
                    "Write each exercise in BOTH Arabic and English.\n"
                    "Arabic first, then English translation below.\n"
                    "اكتب كل تمرين بالعربية أولاً ثم بالإنجليزية."
                ),
                "notation": "Use standard mathematical notation understood in both languages.",
            },
        }

        lang = lang_config.get(language, lang_config["english"])

        # ── Difficulty calibration ──
        difficulty_specs = {
            "easy": {
                "description": "Direct application of a single formula or concept",
                "cognitive": "Remember & Apply (Bloom's levels 1-2)",
                "steps": "Single step — direct substitution or recall",
                "design": (
                    "The student should be able to solve this by directly applying ONE formula "
                    "or definition. No multi-step reasoning required."
                ),
                "example_note": "e.g., 'Find the value of sin(30°)' or 'Solve: 2x + 4 = 10'",
            },
            "medium": {
                "description": "2-3 steps requiring understanding of the concept",
                "cognitive": "Apply & Analyze (Bloom's levels 3-4)",
                "steps": "2-3 steps — requires understanding, not just memorization",
                "design": (
                    "The student must understand the concept well enough to apply it in a "
                    "slightly non-trivial way. May require rearranging an equation, combining "
                    "two simple ideas, or interpreting a word problem."
                ),
                "example_note": "e.g., 'Solve 4x^2 + 40x + 100 = 0 by factoring'",
            },
            "hard": {
                "description": "Multi-step problem requiring combining concepts or creative thinking",
                "cognitive": "Analyze & Create (Bloom's levels 4-5)",
                "steps": "3-6 steps, may require combining multiple concepts",
                "design": (
                    "The student must combine multiple concepts, apply theorems in non-obvious ways, "
                    "or solve multi-step problems that require planning. These are exam-level questions "
                    "that differentiate top students."
                ),
                "example_note": (
                    "e.g., 'In △ABC, D ∈ AB and E ∈ AC such that DE ∥ BC. "
                    "If AD = 4 cm, DB = 2 cm, and area of △ADE = 32 cm^2, find area of trapezium DBCE.'"
                ),
            },
        }

        diff = difficulty_specs.get(difficulty, difficulty_specs["medium"])

        # ── Exercise type format specifications with JSON schema ──
        type_specs = self._get_type_specs(exercise_type)

        # ── Trim context to configured max ──
        max_context = settings.LLM_MAX_CONTEXT_CHARS
        trimmed_context = context[:max_context] if len(context) > max_context else context

        # ── Build the full prompt (NO trailing [ character) ──
        prompt = f"""Generate {count} math exercises based on the following textbook content.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TEXTBOOK CONTENT (from the student's actual textbook):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{trimmed_context}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
GENERATION REQUIREMENTS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

QUANTITY: Generate exactly {count} exercises.

EXERCISE TYPE: {exercise_type.replace('_', ' ').title()}

LESSON/TOPIC: {lesson_title if lesson_title else 'Determine from the textbook content above'}

DIFFICULTY LEVEL: {difficulty.upper()}
- Definition: {diff['description']}
- Cognitive level: {diff['cognitive']}
- Expected solution: {diff['steps']}
- Design principle: {diff['design']}
- Example: {diff['example_note']}

GRADE LEVEL: {grade_level if grade_level else 'Egyptian First Secondary (الصف الأول الثانوي)'}

LANGUAGE:
{lang['instruction']}

MATHEMATICAL NOTATION:
{lang['notation']}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OUTPUT JSON SCHEMA:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{type_specs['schema']}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
QUALITY RULES (CRITICAL — violations make the output useless):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. VERIFY YOUR ANSWER: Solve each problem yourself before outputting. The correct_answer MUST actually be correct.
2. For MCQ: ALL 4 distractors must be plausible (based on common student errors like sign mistakes, order-of-operations errors, forgetting to square, etc.). No obviously wrong options like "0" or "undefined" unless mathematically justified.
3. For MCQ: correct_answer must EXACTLY match one of the 4 options strings.
4. Each exercise must be UNIQUE — no repeated problems with just different numbers.
5. Exercises MUST be directly related to the textbook content provided above.
6. Use the SAME terminology, notation, and style as the textbook.
7. Difficulty must match the specified level precisely — see the design principle above.
8. All exercises must be solvable with the knowledge from this lesson only.
9. Question text must be clear, unambiguous, and at least 10 characters long.
10. For Arabic: use proper Arabic mathematical terms, not transliterated English.

Return ONLY a valid JSON array of {count} objects matching the schema above. No markdown, no explanation, no code fences — just the JSON array."""

        return prompt

    def _get_type_specs(self, exercise_type: str) -> dict:
        """Get the JSON schema specification for a given exercise type."""

        # Normalize type aliases
        normalized = exercise_type
        if exercise_type in ("fill_blank", "fill_in_blank"):
            normalized = "fill_in_blank"
        elif exercise_type in ("word_problems", "word_problem", "show_work", "long_answer"):
            normalized = "long_answer"

        specs = {
            "multiple_choice": {
                "schema": """Return a JSON array where each object has this EXACT structure:
[
  {
    "question": "The question text using proper math notation (e.g., 'Solve: 4x^2 + 40x + 100 = 0')",
    "type": "multiple_choice",
    "options": ["option A text", "option B text", "option C text", "option D text"],
    "correct_answer": "the exact text of the correct option (must match one of the 4 options exactly)",
    "difficulty": "easy|medium|hard",
    "hint": "A brief hint that guides without giving away the answer",
    "topic": "The specific topic name"
  }
]

RULES FOR OPTIONS:
- Exactly 4 options (no more, no less)
- correct_answer must be the EXACT string of one of the 4 options
- All 4 options must be plausible — distractors should be based on common student errors:
  * Sign errors (forgetting negative)
  * Arithmetic mistakes (e.g., 3×4=14 instead of 12)
  * Forgetting a step (e.g., not dividing by coefficient)
  * Confusing similar formulas
- Options should be in logical order (ascending numbers, alphabetical, etc.)
- No "all of the above" or "none of the above"
""",
            },
            "fill_in_blank": {
                "schema": """Return a JSON array where each object has this EXACT structure:
[
  {
    "question": "Question text with _____ marking the blank (e.g., 'In △ABC right-angled at A, if AD ⊥ BC, then (AB)^2 = BC × _____.')",
    "type": "fill_in_blank",
    "correct_answer": "The exact value/expression that fills the blank (e.g., 'BD')",
    "difficulty": "easy|medium|hard",
    "hint": "A brief hint that guides without giving away the answer",
    "topic": "The specific topic name"
  }
]

RULES:
- The blank (shown as _____) must have exactly ONE correct answer
- Provide enough context to determine the answer uniquely
- correct_answer should be concise (a number, variable, or short expression)
""",
            },
            "true_false": {
                "schema": """Return a JSON array where each object has this EXACT structure:
[
  {
    "question": "A clear mathematical statement that is definitively true or false",
    "type": "true_false",
    "correct_answer": "true" or "false",
    "difficulty": "easy|medium|hard",
    "hint": "A brief explanation of why it's true/false",
    "topic": "The specific topic name"
  }
]

RULES:
- Statement must be unambiguous — clearly true or clearly false
- Avoid double negatives
- Mix true and false answers (not all one type)
- Statements should test understanding, not trick students
""",
            },
            "long_answer": {
                "schema": """Return a JSON array where each object has this EXACT structure:
[
  {
    "question": "A problem requiring full solution with steps (e.g., 'In △ABC, D ∈ AB and E ∈ AC such that DE ∥ BC. If AD = 4 cm, DB = 2 cm, and area of △ADE = 32 cm^2, find the area of trapezium DBCE.')",
    "type": "long_answer",
    "correct_answer": "The complete solution with key steps (e.g., 'Area of ABC = 72 cm^2, so trapezium DBCE = 72 - 32 = 40 cm^2')",
    "difficulty": "easy|medium|hard",
    "hint": "A hint that guides the student toward the approach without solving it",
    "topic": "The specific topic name"
  }
]

RULES:
- Problem must require multiple steps to solve
- correct_answer should show the key reasoning steps and final answer
- Wording must be precise and unambiguous
- Include units where applicable
""",
            },
            "matching": {
                "schema": """Return a JSON array where each object has this EXACT structure:
[
  {
    "question": "Match each item in Column A with its corresponding item in Column B",
    "type": "matching",
    "left_items": ["item 1", "item 2", "item 3", "item 4"],
    "right_items": ["match for item 2", "match for item 4", "match for item 1", "match for item 3"],
    "correct_answer": "1-C, 2-A, 3-D, 4-B",
    "difficulty": "easy|medium|hard",
    "hint": "A brief hint",
    "topic": "The specific topic name"
  }
]

RULES:
- 4-6 items in each column
- Right column must be SHUFFLED (not in matching order)
- Each item has exactly one correct match
- correct_answer shows the mapping
""",
            },
        }

        return specs.get(normalized, specs["long_answer"])

    # ─── Validation ────────────────────────────────────────────────────────────

    def _validate_exercises(
        self, exercises: list, exercise_type: str, count: int
    ) -> list[dict]:
        """Validate and clean LLM-generated exercises.

        Checks that each exercise has the required fields for its type,
        field values are reasonable, MCQ options are correct, and no duplicates exist.

        Args:
            exercises: Raw list of exercise dicts from LLM.
            exercise_type: Expected exercise type.
            count: Requested count (for logging).

        Returns:
            List of validated exercise dicts.
        """
        # Normalize exercise type for validation
        normalized_type = exercise_type
        if exercise_type in ("fill_blank", "fill_in_blank"):
            normalized_type = "fill_in_blank"
        elif exercise_type in ("word_problems", "word_problem", "show_work"):
            normalized_type = "long_answer"

        required_fields = {
            "multiple_choice": ["question", "options", "correct_answer"],
            "fill_in_blank": ["question", "correct_answer"],
            "true_false": ["question", "correct_answer"],
            "matching": ["left_items", "right_items"],
            "long_answer": ["question", "correct_answer"],
        }

        fields = required_fields.get(normalized_type, ["question"])
        valid: list[dict] = []
        seen_questions: set = set()

        for ex in exercises:
            if not isinstance(ex, dict):
                logger.debug(f"Skipping non-dict exercise: {type(ex)}")
                continue

            # Check required fields exist and are non-empty
            missing = [f for f in fields if not ex.get(f)]
            if missing:
                logger.debug(f"Exercise missing fields {missing}: {str(ex)[:100]}")
                continue

            # Question length check (at least 10 characters)
            question_text = ex.get("question", "") or ex.get("statement", "")
            if len(str(question_text)) < 10:
                logger.debug(f"Exercise question too short: '{question_text}'")
                continue

            # Duplicate check
            q_normalized = str(question_text).strip().lower()
            if q_normalized in seen_questions:
                logger.debug(f"Duplicate question skipped: '{question_text[:50]}'")
                continue
            seen_questions.add(q_normalized)

            # Type-specific validation
            if normalized_type == "multiple_choice":
                if not self._validate_mcq(ex):
                    continue

            elif normalized_type == "true_false":
                answer = str(ex.get("correct_answer", "")).lower().strip()
                if answer not in ("true", "false"):
                    # Try boolean conversion
                    if isinstance(ex.get("correct_answer"), bool):
                        ex["correct_answer"] = "true" if ex["correct_answer"] else "false"
                    else:
                        logger.debug(f"True/false exercise has invalid answer: {ex.get('correct_answer')}")
                        continue
                else:
                    ex["correct_answer"] = answer

            elif normalized_type == "matching":
                left = ex.get("left_items", [])
                right = ex.get("right_items", [])
                if not isinstance(left, list) or not isinstance(right, list):
                    continue
                if len(left) < 2 or len(right) < 2:
                    continue

            # Ensure type and difficulty fields are present
            if "type" not in ex:
                ex["type"] = exercise_type
            if "difficulty" not in ex:
                ex["difficulty"] = difficulty if 'difficulty' in dir() else "medium"

            valid.append(ex)

        if len(valid) < count:
            logger.warning(
                f"Validation reduced exercises from {len(exercises)} to {len(valid)} "
                f"(requested {count})"
            )

        return valid

    def _validate_mcq(self, ex: dict) -> bool:
        """Validate a multiple choice exercise.

        Checks:
        - Exactly 4 options
        - correct_answer matches one of the options exactly
        - Options are all strings and non-empty

        Returns:
            True if valid, False otherwise.
        """
        opts = ex.get("options", [])

        # Must be a list
        if not isinstance(opts, list):
            logger.debug(f"MCQ options is not a list: {type(opts)}")
            return False

        # Must have exactly 4 options
        if len(opts) != 4:
            logger.debug(f"MCQ has {len(opts)} options instead of 4: {opts}")
            # Try to salvage: if 3 options, still reject; if 5+, trim to 4
            if len(opts) > 4:
                ex["options"] = opts[:4]
                opts = ex["options"]
            else:
                return False

        # All options must be non-empty strings
        for i, opt in enumerate(opts):
            if not isinstance(opt, str) or not opt.strip():
                logger.debug(f"MCQ option {i} is empty or not a string: {opt}")
                return False

        # correct_answer must match one of the options exactly
        correct = ex.get("correct_answer", "")

        # Direct match
        if correct in opts:
            return True

        # Try case-insensitive match
        correct_lower = str(correct).strip().lower()
        for opt in opts:
            if opt.strip().lower() == correct_lower:
                ex["correct_answer"] = opt  # Fix to exact match
                return True

        # Legacy format: correct might be "A", "B", "C", "D" letter
        if correct.upper() in ("A", "B", "C", "D"):
            idx = ord(correct.upper()) - ord("A")
            if 0 <= idx < len(opts):
                ex["correct_answer"] = opts[idx]
                return True

        # Legacy format: correct might be an integer index
        if isinstance(correct, int) and 0 <= correct < len(opts):
            ex["correct_answer"] = opts[correct]
            return True

        logger.debug(
            f"MCQ correct_answer '{correct}' does not match any option: {opts}"
        )
        return False

    # ─── Fallbacks ──────────────────────────────────────────────────────────────

    def _fallback_worked_example(self, topic: str, language: str) -> dict:
        """Return a language-appropriate fallback worked example."""
        if language in ("arabic", "bilingual"):
            return {
                "problem": f"مثال تطبيقي على: {topic}",
                "steps": [
                    "الخطوة 1: حدد المعطيات",
                    "الخطوة 2: طبق القاعدة المناسبة",
                    "الخطوة 3: احسب النتيجة",
                ],
                "answer": "راجع خطوات الحل أعلاه",
                "tip": "تأكد دائماً من إظهار خطوات الحل كاملة",
            }
        return {
            "problem": f"Example problem for {topic}",
            "steps": [
                "Step 1: Identify the given information",
                "Step 2: Apply the formula",
                "Step 3: Calculate the result",
            ],
            "answer": "See solution steps above",
            "tip": "Always show your working",
        }

    # ─── Solved Examples for Study Book Mode ─────────────────────────────────────

    async def generate_solved_examples(
        self,
        context: str,
        topic: str,
        count: int = 2,
        difficulty: str = "medium",
        language: str = "english",
        grade_level: str = "",
    ) -> list[dict]:
        """Generate solved examples with full step-by-step solutions for study book mode.

        Produces textbook-style worked examples with:
        - Clear problem statement
        - Step-by-step solution using ∵ (since) and ∴ (therefore)
        - Key formula identification
        - Coefficient/parameter callouts

        Args:
            context: RAG-retrieved textbook content.
            topic: The mathematical topic.
            count: Number of solved examples to generate.
            difficulty: Difficulty level (easy, medium, hard).
            language: Output language (english, arabic, bilingual).
            grade_level: Grade level string.

        Returns:
            List of solved example dicts with structure:
            {
                "title": str,
                "topic": str,
                "difficulty": str,
                "solution_steps": list[str],
                "key_formula": str | None,
                "coefficients": dict | None,
            }
        """
        if self.model is None:
            logger.warning("LLM model not available, returning fallback solved examples")
            return self._fallback_solved_examples(topic, count, difficulty, language)

        # Language instructions
        if language in ("arabic", "bilingual"):
            lang_instruction = (
                "اكتب الأمثلة بالعربية الفصحى. استخدم المصطلحات الرياضية العربية.\n"
                "Write the examples in Arabic using proper mathematical terminology.\n"
                "Use ∵ for 'بما أن' (since/because) and ∴ for 'إذن' (therefore)."
            )
        else:
            lang_instruction = (
                "Write in clear English.\n"
                "Use ∵ for 'since/because' and ∴ for 'therefore'."
            )

        # Trim context
        max_context = settings.LLM_MAX_CONTEXT_CHARS
        trimmed_context = context[:max_context] if len(context) > max_context else context

        prompt = f"""You are an expert Egyptian mathematics teacher creating SOLVED EXAMPLES for a study book.
These are textbook-style worked examples that show students HOW to solve problems step by step.

Topic: {topic}
Language: {lang_instruction}
Grade Level: {grade_level if grade_level else 'Egyptian First Secondary (الصف الأول الثانوي)'}
Difficulty: {difficulty}
Number of examples: {count}

Based on this curriculum content:
{trimmed_context}

Create {count} detailed SOLVED EXAMPLES with full step-by-step solutions.

MATH NOTATION FORMAT (use these consistently):
- Superscripts/powers: x^2, x^3, a^n
- Fractions: frac(numerator, denominator) — e.g., frac(3, 4) means 3/4
- Square roots: sqrt(expression) — e.g., sqrt(3), sqrt(x^2 + 1)
- Subscripts: x_1, x_2, a_n
- Special symbols (use Unicode directly): ∈, ∴, ∵, ≈, ≠, ∠, ⊥, ∥, △, →, ∞, ±, ≤, ≥

SOLUTION STEP FORMAT:
- Start reasoning steps with "∵" (since/because)
- Start conclusion steps with "∴" (therefore)
- Show every algebraic manipulation clearly
- Use "or" between multiple solutions (e.g., x_1 and x_2)
- End with the final answer clearly marked: "∴ The S.S. = {{...}}" or "∴ The answer is ..."

Return as a JSON array of {count} objects with this EXACT structure:
[
  {{
    "title": "The problem statement (e.g., 'Find in ℝ the solution set of: x^2 - 6x - 7 = 0')",
    "topic": "{topic}",
    "difficulty": "{difficulty}",
    "solution_steps": [
      "∵ x^2 - 6x - 7 = 0",
      "∵ Using the quadratic formula: x = frac(-b ± sqrt(b^2 - 4ac), 2a)",
      "∵ a = 1, b = -6, c = -7",
      "∵ x = frac(6 ± sqrt(36 + 28), 2) = frac(6 ± sqrt(64), 2) = frac(6 ± 8, 2)",
      "∴ x_1 = frac(6 + 8, 2) = 7",
      "or x_2 = frac(6 - 8, 2) = -1",
      "∴ The S.S. = {{7, -1}}"
    ],
    "key_formula": "x = frac(-b ± sqrt(b^2 - 4ac), 2a)",
    "coefficients": {{"a": "1", "b": "-6", "c": "-7"}}
  }}
]

CRITICAL RULES:
1. Each example must be mathematically CORRECT. Verify all calculations.
2. Show EVERY step — don't skip algebraic manipulations.
3. The solution_steps array must have at least 4 steps.
4. key_formula should be the main formula used (null if no single formula applies).
5. coefficients should list the key parameters used (null if not applicable).
6. Examples must be appropriate for the topic and difficulty level.
7. Use the same math notation format as specified above.

Return ONLY a valid JSON array. No markdown, no explanation — just the JSON array."""

        # Attempt generation with retry
        max_retries = 2
        for attempt in range(1, max_retries + 2):
            try:
                logger.info(
                    f"Calling Gemini API for solved examples (attempt {attempt}): "
                    f"topic={topic}, count={count}, difficulty={difficulty}"
                )

                current_prompt = prompt
                if attempt > 1:
                    current_prompt = (
                        f"{prompt}\n\n"
                        f"IMPORTANT: Your previous response was not valid JSON. "
                        f"Return ONLY a raw JSON array starting with [ and ending with ]. "
                        f"No markdown code fences, no explanation text."
                    )

                response = self.model.generate_content(
                    current_prompt,
                    generation_config=self._genai.GenerationConfig(
                        temperature=settings.LLM_TEMPERATURE,
                        top_p=0.85,
                        response_mime_type="application/json",
                    ),
                )

                if not response.candidates:
                    logger.warning("Gemini returned no candidates for solved examples")
                    if attempt <= max_retries:
                        continue
                    return self._fallback_solved_examples(topic, count, difficulty, language)

                try:
                    response_text = response.text
                except (ValueError, AttributeError) as e:
                    logger.warning(f"Gemini solved examples response has no text: {e}")
                    if attempt <= max_retries:
                        continue
                    return self._fallback_solved_examples(topic, count, difficulty, language)

                if not response_text:
                    if attempt <= max_retries:
                        continue
                    return self._fallback_solved_examples(topic, count, difficulty, language)

                # Parse JSON
                parsed = self._parse_json_response(response_text)
                if parsed is None:
                    if attempt <= max_retries:
                        logger.warning(
                            f"Attempt {attempt}: Failed to parse solved examples JSON, retrying..."
                        )
                        continue
                    return self._fallback_solved_examples(topic, count, difficulty, language)

                # Validate solved examples
                validated = self._validate_solved_examples(parsed, topic, difficulty)
                if validated:
                    logger.info(
                        f"Gemini returned {len(validated)} solved examples for topic: {topic}"
                    )
                    return validated
                else:
                    if attempt <= max_retries:
                        continue
                    return self._fallback_solved_examples(topic, count, difficulty, language)

            except Exception as e:
                if attempt <= max_retries:
                    logger.warning(f"Attempt {attempt} error for solved examples: {e}, retrying...")
                    continue
                logger.error(f"Gemini API error generating solved examples: {e}")
                return self._fallback_solved_examples(topic, count, difficulty, language)

        return self._fallback_solved_examples(topic, count, difficulty, language)

    # ─── Lesson Illustration for Study Book Mode ──────────────────────────────────

    async def generate_lesson_illustration(
        self,
        context: str,
        topic: str,
        language: str = "english",
        grade_level: str = "first_secondary",
    ) -> dict:
        """Generate a structured lesson illustration (textbook-style summary) for a topic.

        Produces a comprehensive lesson summary with key concepts, theorems,
        formulas, and important notes — suitable for rendering as a textbook page
        before solved examples.

        Args:
            context: RAG-retrieved textbook content for accuracy.
            topic: The mathematical topic title.
            language: Output language (english, arabic, bilingual).
            grade_level: Grade level string.

        Returns:
            Dict with structure:
            {
                "topic": str,
                "introduction": str,
                "key_concepts": list[str],
                "theorems": list[{"name": str, "statement": str, "notation": str}],
                "key_formulas": list[{"name": str, "formula": str, "description": str}],
                "important_notes": list[str],
            }
        """
        if self.model is None:
            logger.warning("LLM model not available, returning fallback lesson illustration")
            return self._fallback_lesson_illustration(topic, language)

        # Language instructions
        if language in ("arabic", "bilingual"):
            lang_instruction = (
                "اكتب ملخص الدرس بالعربية الفصحى. استخدم المصطلحات الرياضية العربية المعتمدة.\n"
                "Write the lesson summary in Arabic using proper mathematical terminology.\n"
                "Use Arabic terms for all concepts and theorems."
            )
        else:
            lang_instruction = "Write in clear, precise English suitable for a textbook."

        # Trim context
        max_context = settings.LLM_MAX_CONTEXT_CHARS
        trimmed_context = context[:max_context] if len(context) > max_context else context

        prompt = f"""You are an expert mathematics textbook author creating a LESSON ILLUSTRATION — a structured summary page that introduces a topic before worked examples.

Topic: {topic}
Language: {lang_instruction}
Grade Level: {grade_level if grade_level else 'Egyptian First Secondary (الصف الأول الثانوي)'}

Based on this curriculum content:
{trimmed_context}

Create a comprehensive, structured lesson summary for this topic. This should read like a textbook page that a student would study BEFORE attempting exercises.

MATH NOTATION FORMAT (use these consistently):
- Superscripts/powers: x^2, x^3, a^n
- Fractions: frac(numerator, denominator) — e.g., frac(3, 4) means 3/4
- Square roots: sqrt(expression) — e.g., sqrt(3), sqrt(x^2 + 1)
- Subscripts: x_1, x_2, a_n
- Special symbols (use Unicode directly): ∈, ∴, ∵, ≈, ≠, ∠, ⊥, ∥, △, →, ∞, ±, ≤, ≥

Return as a JSON object with this EXACT structure:
{{
    "topic": "{topic}",
    "introduction": "A clear 1-3 sentence introduction explaining what this topic is about and why it matters.",
    "key_concepts": [
        "Concept 1: Clear definition or explanation",
        "Concept 2: Clear definition or explanation",
        "Concept 3: Clear definition or explanation"
    ],
    "theorems": [
        {{
            "name": "Theorem Name",
            "statement": "The full theorem statement in clear language",
            "notation": "Mathematical notation using the format above (e.g., If ∠A = ∠D and ∠B = ∠E, then △ABC ~ △DEF)"
        }}
    ],
    "key_formulas": [
        {{
            "name": "Formula Name",
            "formula": "The formula using notation format (e.g., x = frac(-b ± sqrt(b^2 - 4ac), 2a))",
            "description": "Brief description of when/how to use this formula"
        }}
    ],
    "important_notes": [
        "Important note or common mistake to avoid",
        "Another key point students should remember"
    ]
}}

REQUIREMENTS:
1. Include 3-5 key concepts that define the topic clearly
2. Include 2-4 theorems relevant to this topic (with proper names and statements)
3. Include 2-4 key formulas that students need to memorize
4. Include 2-3 important notes (common mistakes, tips, or connections)
5. The introduction should be engaging and set context for the topic
6. All content must be mathematically accurate and curriculum-aligned
7. Use the same notation format as specified above
8. Theorems should have both a statement (in words) and notation (in math symbols)

Return ONLY a valid JSON object. No markdown, no explanation — just the JSON object."""

        # Attempt generation with retry
        max_retries = 2
        for attempt in range(1, max_retries + 2):
            try:
                logger.info(
                    f"Calling Gemini API for lesson illustration (attempt {attempt}): topic={topic}"
                )

                current_prompt = prompt
                if attempt > 1:
                    current_prompt = (
                        f"{prompt}\n\n"
                        f"IMPORTANT: Your previous response was not valid JSON. "
                        f"Return ONLY a raw JSON object starting with {{ and ending with }}. "
                        f"No markdown code fences, no explanation text."
                    )

                response = self.model.generate_content(
                    current_prompt,
                    generation_config=self._genai.GenerationConfig(
                        temperature=settings.LLM_TEMPERATURE,
                        top_p=0.85,
                        response_mime_type="application/json",
                    ),
                )

                if not response.candidates:
                    logger.warning("Gemini returned no candidates for lesson illustration")
                    if attempt <= max_retries:
                        continue
                    return self._fallback_lesson_illustration(topic, language)

                try:
                    response_text = response.text
                except (ValueError, AttributeError) as e:
                    logger.warning(f"Gemini lesson illustration response has no text: {e}")
                    if attempt <= max_retries:
                        continue
                    return self._fallback_lesson_illustration(topic, language)

                if not response_text:
                    if attempt <= max_retries:
                        continue
                    return self._fallback_lesson_illustration(topic, language)

                # Parse JSON
                parsed = self._parse_json_response(response_text)
                if parsed is None:
                    if attempt <= max_retries:
                        logger.warning(
                            f"Attempt {attempt}: Failed to parse lesson illustration JSON, retrying..."
                        )
                        continue
                    return self._fallback_lesson_illustration(topic, language)

                # _parse_json_response returns a list; we need a dict
                if isinstance(parsed, list) and len(parsed) > 0:
                    result = parsed[0]
                elif isinstance(parsed, dict):
                    result = parsed
                else:
                    if attempt <= max_retries:
                        continue
                    return self._fallback_lesson_illustration(topic, language)

                # Validate the structure
                validated = self._validate_lesson_illustration(result, topic)
                if validated:
                    logger.info(f"Gemini returned lesson illustration for topic: {topic}")
                    return validated
                else:
                    if attempt <= max_retries:
                        continue
                    return self._fallback_lesson_illustration(topic, language)

            except Exception as e:
                if attempt <= max_retries:
                    logger.warning(f"Attempt {attempt} error for lesson illustration: {e}, retrying...")
                    continue
                logger.error(f"Gemini API error generating lesson illustration: {e}")
                return self._fallback_lesson_illustration(topic, language)

        return self._fallback_lesson_illustration(topic, language)

    def _validate_lesson_illustration(self, data: dict, topic: str) -> dict | None:
        """Validate and normalize a lesson illustration dict from LLM output.

        Args:
            data: Raw dict from LLM.
            topic: Expected topic name.

        Returns:
            Validated dict or None if invalid.
        """
        if not isinstance(data, dict):
            return None

        # Must have at least introduction and key_concepts
        introduction = data.get("introduction", "")
        key_concepts = data.get("key_concepts", [])

        if not introduction or len(str(introduction)) < 20:
            logger.debug(f"Lesson illustration introduction too short: '{introduction}'")
            return None

        if not isinstance(key_concepts, list) or len(key_concepts) < 2:
            logger.debug(f"Lesson illustration has too few key concepts: {len(key_concepts) if isinstance(key_concepts, list) else 0}")
            return None

        # Validate theorems
        theorems = data.get("theorems", [])
        validated_theorems = []
        if isinstance(theorems, list):
            for thm in theorems:
                if isinstance(thm, dict) and thm.get("name") and thm.get("statement"):
                    validated_theorems.append({
                        "name": str(thm["name"]),
                        "statement": str(thm["statement"]),
                        "notation": str(thm.get("notation", "")) if thm.get("notation") else "",
                    })

        # Validate formulas
        key_formulas = data.get("key_formulas", [])
        validated_formulas = []
        if isinstance(key_formulas, list):
            for formula in key_formulas:
                if isinstance(formula, dict) and formula.get("name") and formula.get("formula"):
                    validated_formulas.append({
                        "name": str(formula["name"]),
                        "formula": str(formula["formula"]),
                        "description": str(formula.get("description", "")) if formula.get("description") else "",
                    })

        # Validate important notes
        important_notes = data.get("important_notes", [])
        if not isinstance(important_notes, list):
            important_notes = []
        important_notes = [str(n) for n in important_notes if n]

        return {
            "topic": data.get("topic", topic),
            "introduction": str(introduction),
            "key_concepts": [str(c) for c in key_concepts if c],
            "theorems": validated_theorems,
            "key_formulas": validated_formulas,
            "important_notes": important_notes,
        }

    def _fallback_lesson_illustration(self, topic: str, language: str) -> dict:
        """Generate a fallback lesson illustration when LLM is unavailable.

        Args:
            topic: The mathematical topic.
            language: Output language.

        Returns:
            Fallback lesson illustration dict.
        """
        if language in ("arabic", "bilingual"):
            return {
                "topic": topic,
                "introduction": f"في هذا الدرس سنتعرف على {topic} وأهم المفاهيم والنظريات المرتبطة به.",
                "key_concepts": [
                    "المفهوم الأول: راجع الكتاب المدرسي للتعريف الدقيق",
                    "المفهوم الثاني: راجع الكتاب المدرسي للتعريف الدقيق",
                    "المفهوم الثالث: راجع الكتاب المدرسي للتعريف الدقيق",
                ],
                "theorems": [
                    {
                        "name": "النظرية الأساسية",
                        "statement": "راجع الكتاب المدرسي لنص النظرية",
                        "notation": "",
                    }
                ],
                "key_formulas": [
                    {
                        "name": "القانون الأساسي",
                        "formula": "راجع الكتاب المدرسي",
                        "description": "يُستخدم هذا القانون في حل المسائل المتعلقة بهذا الدرس",
                    }
                ],
                "important_notes": [
                    "تأكد من فهم التعريفات الأساسية قبل حل التمارين",
                    "راجع الأمثلة المحلولة بعناية",
                ],
            }
        return {
            "topic": topic,
            "introduction": f"In this lesson, we will explore {topic} and its key concepts, theorems, and formulas.",
            "key_concepts": [
                "Concept 1: Refer to the textbook for the precise definition",
                "Concept 2: Refer to the textbook for the precise definition",
                "Concept 3: Refer to the textbook for the precise definition",
            ],
            "theorems": [
                {
                    "name": "Fundamental Theorem",
                    "statement": "Refer to the textbook for the theorem statement",
                    "notation": "",
                }
            ],
            "key_formulas": [
                {
                    "name": "Key Formula",
                    "formula": "Refer to the textbook",
                    "description": "This formula is used to solve problems related to this topic",
                }
            ],
            "important_notes": [
                "Make sure to understand the basic definitions before attempting exercises",
                "Review the solved examples carefully",
            ],
        }

    def _validate_solved_examples(self, examples: list, topic: str, difficulty: str) -> list[dict]:
        """Validate solved examples from LLM output.

        Args:
            examples: Raw list of example dicts from LLM.
            topic: Expected topic.
            difficulty: Expected difficulty.

        Returns:
            List of validated solved example dicts.
        """
        valid = []
        for ex in examples:
            if not isinstance(ex, dict):
                continue

            # Must have title and solution_steps
            title = ex.get("title", "")
            steps = ex.get("solution_steps", [])

            if not title or len(str(title)) < 10:
                logger.debug(f"Solved example title too short: '{title}'")
                continue

            if not isinstance(steps, list) or len(steps) < 3:
                logger.debug(f"Solved example has too few steps: {len(steps) if isinstance(steps, list) else 0}")
                continue

            # Ensure all steps are strings
            steps = [str(s) for s in steps if s]
            if len(steps) < 3:
                continue

            # Build validated example
            validated_ex = {
                "title": str(title),
                "topic": ex.get("topic", topic),
                "difficulty": ex.get("difficulty", difficulty),
                "solution_steps": steps,
                "key_formula": ex.get("key_formula") if ex.get("key_formula") else None,
                "coefficients": ex.get("coefficients") if isinstance(ex.get("coefficients"), dict) else None,
            }
            valid.append(validated_ex)

        return valid

    def _fallback_solved_examples(
        self, topic: str, count: int, difficulty: str, language: str
    ) -> list[dict]:
        """Generate fallback solved examples when LLM is unavailable.

        Args:
            topic: The mathematical topic.
            count: Number of examples to generate.
            difficulty: Difficulty level.
            language: Output language.

        Returns:
            List of fallback solved example dicts.
        """
        examples = []
        if language in ("arabic", "bilingual"):
            templates = [
                {
                    "title": f"أوجد في ℝ مجموعة حل المعادلة: x^2 - 5x + 6 = 0",
                    "topic": topic,
                    "difficulty": difficulty,
                    "solution_steps": [
                        "∵ x^2 - 5x + 6 = 0",
                        "∵ بالتحليل: (x - 2)(x - 3) = 0",
                        "∴ x - 2 = 0  أو  x - 3 = 0",
                        "∴ x = 2  أو  x = 3",
                        "∴ م.ح = {2, 3}",
                    ],
                    "key_formula": "(x - r_1)(x - r_2) = 0",
                    "coefficients": {"a": "1", "b": "-5", "c": "6"},
                },
                {
                    "title": f"أوجد في ℝ مجموعة حل المعادلة: 2x^2 + 4x - 6 = 0",
                    "topic": topic,
                    "difficulty": difficulty,
                    "solution_steps": [
                        "∵ 2x^2 + 4x - 6 = 0",
                        "∵ بالقسمة على 2: x^2 + 2x - 3 = 0",
                        "∵ بالتحليل: (x + 3)(x - 1) = 0",
                        "∴ x + 3 = 0  أو  x - 1 = 0",
                        "∴ x = -3  أو  x = 1",
                        "∴ م.ح = {-3, 1}",
                    ],
                    "key_formula": "x = frac(-b ± sqrt(b^2 - 4ac), 2a)",
                    "coefficients": {"a": "2", "b": "4", "c": "-6"},
                },
            ]
        else:
            templates = [
                {
                    "title": f"Find in ℝ the solution set of: x^2 - 5x + 6 = 0",
                    "topic": topic,
                    "difficulty": difficulty,
                    "solution_steps": [
                        "∵ x^2 - 5x + 6 = 0",
                        "∵ By factoring: (x - 2)(x - 3) = 0",
                        "∴ x - 2 = 0  or  x - 3 = 0",
                        "∴ x = 2  or  x = 3",
                        "∴ The S.S. = {2, 3}",
                    ],
                    "key_formula": "(x - r_1)(x - r_2) = 0",
                    "coefficients": {"a": "1", "b": "-5", "c": "6"},
                },
                {
                    "title": f"Find in ℝ the solution set of: 2x^2 + 4x - 6 = 0",
                    "topic": topic,
                    "difficulty": difficulty,
                    "solution_steps": [
                        "∵ 2x^2 + 4x - 6 = 0",
                        "∵ Dividing by 2: x^2 + 2x - 3 = 0",
                        "∵ By factoring: (x + 3)(x - 1) = 0",
                        "∴ x + 3 = 0  or  x - 1 = 0",
                        "∴ x = -3  or  x = 1",
                        "∴ The S.S. = {-3, 1}",
                    ],
                    "key_formula": "x = frac(-b ± sqrt(b^2 - 4ac), 2a)",
                    "coefficients": {"a": "2", "b": "4", "c": "-6"},
                },
            ]

        for i in range(min(count, len(templates))):
            examples.append(templates[i])

        return examples
