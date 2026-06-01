"""Exam generation orchestrator — coordinates RAG retrieval + LLM generation +
DOCX assembly for exams, quizzes, and weekly MOE-style assessments.
"""

import asyncio
import copy
import json
import logging
import random
import traceback
import uuid
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from config import get_settings
from models.exam import Exam

logger = logging.getLogger(__name__)
settings = get_settings()


# ─── MOE Exam Structure Templates ────────────────────────────────────────────
# Based on official Egyptian Ministry of Education assessment formats observed
# at https://ellibrary.moe.gov.eg/cha/books.json (Classroom & Home Assessments
# published by the Mathematics Curriculum Development Department).
#
#   • monthly_exam     — multi-section, MCQ + complete + answer + solve + essay
#   • quiz             — short version of monthly_exam (3 sections)
#   • weekly_assessment — TOPIC-organized, no MCQ, three parallel groups —
#                         matches the cha/ Sec 1/2 format exactly.

MOE_EXAM_SECTIONS = {
    "monthly_exam": [
        {
            "key": "choose_correct",
            "title_ar": "السؤال الأول: اختر الإجابة الصحيحة مما بين القوسين",
            "title_en": "Question 1: Choose the correct answer from the brackets",
            "question_type": "multiple_choice",
            "bloom_level": "remember_understand",
        },
        {
            "key": "complete_following",
            "title_ar": "السؤال الثاني: أكمل ما يأتي",
            "title_en": "Question 2: Complete the following",
            "question_type": "fill_in_blank",
            "bloom_level": "remember_understand",
        },
        {
            "key": "answer_short",
            "title_ar": "السؤال الثالث: أجب عما يأتي",
            "title_en": "Question 3: Answer the following",
            "question_type": "short_answer",
            "bloom_level": "apply_analyze",
        },
        {
            "key": "solve_prove",
            "title_ar": "السؤال الرابع: حل المسائل الآتية",
            "title_en": "Question 4: Solve the following problems",
            "question_type": "show_work",
            "bloom_level": "apply_analyze",
        },
        {
            "key": "essay_extended",
            "title_ar": "السؤال الخامس: أجب بالتفصيل",
            "title_en": "Question 5: Answer in detail",
            "question_type": "long_answer",
            "bloom_level": "evaluate_create",
        },
    ],
    "quiz": [
        {
            "key": "choose_correct",
            "title_ar": "السؤال الأول: اختر الإجابة الصحيحة",
            "title_en": "Question 1: Choose the correct answer",
            "question_type": "multiple_choice",
            "bloom_level": "remember_understand",
        },
        {
            "key": "complete_following",
            "title_ar": "السؤال الثاني: أكمل ما يأتي",
            "title_en": "Question 2: Complete the following",
            "question_type": "fill_in_blank",
            "bloom_level": "apply_analyze",
        },
        {
            "key": "solve_prove",
            "title_ar": "السؤال الثالث: حل",
            "title_en": "Question 3: Solve",
            "question_type": "show_work",
            "bloom_level": "apply_analyze",
        },
    ],
}

# Default mark distributions per exam type
DEFAULT_MARKS = {
    "monthly_exam": {
        "choose_correct": 16,       # 8 questions × 2 marks
        "complete_following": 10,   # 5 questions × 2 marks
        "answer_short": 8,          # 4 questions × 2 marks
        "solve_prove": 6,           # 3 questions × 2 marks
        "essay_extended": 0,
    },
    "quiz": {
        "choose_correct": 10,       # 5 questions × 2 marks
        "complete_following": 6,    # 3 questions × 2 marks
        "solve_prove": 4,           # 2 questions × 2 marks
    },
}

# Default topical sections used when the user picks `weekly_assessment`
# without supplying their own `topic_sections`. Mirrors the Sec 1 Math
# weekly assessment we sampled (Algebra / Trigonometry / Geometry).
DEFAULT_TOPIC_SECTIONS = [
    {
        "title_ar": "أولاً: الجبر",
        "title_en": "First: Algebra",
        "count": 4,
        "marks_per_question": 2,
    },
    {
        "title_ar": "ثانيًا: حساب المثلثات",
        "title_en": "Second: Trigonometry",
        "count": 4,
        "marks_per_question": 2,
    },
    {
        "title_ar": "ثالثًا: الهندسة",
        "title_en": "Third: Geometry",
        "count": 2,
        "marks_per_question": 2,
    },
]


class ExamOrchestrator:
    """Orchestrates the complete exam generation pipeline.

    Uses the RAG service to retrieve relevant textbook content for each topic
    before generating exam questions. When the formatting config supplies
    `moe_reference_id`, the orchestrator additionally pulls the official MOE
    weekly assessment PDF and feeds its extracted text to the LLM so generated
    questions match real ministry style.
    """

    def __init__(self, db: Session, config: dict, exam_id: int) -> None:
        self.db = db
        self.config = config
        self.exam_id = exam_id

        # Config shortcuts
        self.scope = config.get("scope", {})
        self.structure = config.get("structure", {})
        self.formatting = config.get("formatting", {})

    def _set_progress(self, percent: int, message: str) -> None:
        """Persist a progress update to the exam row (best-effort)."""
        try:
            exam = self.db.query(Exam).filter(Exam.id == self.exam_id).first()
            if exam:
                exam.progress = max(0, min(100, int(percent)))
                exam.progress_message = message[:255] if message else None
                self.db.commit()
        except Exception as e:  # pragma: no cover — defensive
            logger.warning(f"[ExamOrchestrator] Failed to update progress: {e}")

    # ─── Service initialization ──────────────────────────────────────────────

    def _init_rag_services(self):
        """Lazily initialize RAG services."""
        try:
            from services.embedding_service import EmbeddingService
            from services.hybrid_search import HybridSearch
            from services.context_assembler import ContextAssembler
            from services.rag_service import RAGService

            embedding_service = EmbeddingService(
                model_name=settings.EMBEDDING_MODEL,
                faiss_dir=settings.FAISS_DIR,
            )

            hybrid_search = None
            try:
                hybrid_search = HybridSearch(
                    embedding_service=embedding_service,
                    faiss_dir=settings.FAISS_DIR,
                    semantic_weight=settings.RAG_HYBRID_ALPHA,
                    mmr_lambda=settings.RAG_MMR_LAMBDA,
                )
            except Exception as e:
                logger.warning(f"[ExamOrchestrator] Hybrid search unavailable: {e}")

            context_assembler = ContextAssembler(
                max_tokens=settings.RAG_MAX_CONTEXT_CHARS // 4,
                embedding_service=embedding_service,
            )

            rag_service = RAGService(
                embedding_service=embedding_service,
                hybrid_search=hybrid_search,
                context_assembler=context_assembler,
            )

            return rag_service, context_assembler

        except Exception as e:
            logger.warning(f"[ExamOrchestrator] Failed to initialize RAG: {e}")
            return None, None

    def _init_llm_service(self):
        """Initialize the LLM service."""
        from services.llm_service import LLMService

        if not settings.GEMINI_API_KEY:
            logger.warning("[ExamOrchestrator] No GEMINI_API_KEY configured")
            return None

        return LLMService(
            api_key=settings.GEMINI_API_KEY,
            model=settings.GEMINI_MODEL,
        )

    # ─── Top-level pipeline ──────────────────────────────────────────────────

    async def generate(self) -> dict:
        """Full exam generation pipeline."""
        from services.exam_docx_generator import ExamDocxGenerator

        try:
            exam_type = self.structure.get("exam_type", "monthly_exam")
            num_variants = max(1, int(self.structure.get("num_variants", 1) or 1))
            groups_per_variant = max(
                1, int(self.structure.get("groups_per_variant", 1) or 1)
            )
            language = self.formatting.get("language", "arabic")

            # Step 1: Plan section distribution (topic-organized OR question-type)
            self._set_progress(5, "Planning exam sections…")
            logger.info(
                f"[ExamOrchestrator] Step 1: Planning sections "
                f"for exam {self.exam_id} (type={exam_type}, "
                f"groups={groups_per_variant}, variants={num_variants})"
            )
            sections = self._plan_sections()
            logger.info(f"[ExamOrchestrator] Sections planned: {len(sections)}")

            # Step 2: Retrieve RAG context (textbook chunks + optional MOE reference)
            self._set_progress(15, "Retrieving curriculum content…")
            logger.info("[ExamOrchestrator] Step 2: Retrieving RAG context")
            context = await self._retrieve_context()

            # Step 3: Generate questions for each section × each group
            self._set_progress(25, "Generating exam questions…")
            logger.info("[ExamOrchestrator] Step 3: Generating questions via LLM")
            exam_content = await self._generate_exam_questions(
                sections, context, language, groups_per_variant
            )
            total_q = sum(
                len(g.get("questions", []))
                for s in exam_content
                for g in s.get("groups", [])
            )
            logger.info(f"[ExamOrchestrator] Generated {total_q} total questions")

            # Step 4: Build answer key
            self._set_progress(75, "Building answer key…")
            logger.info("[ExamOrchestrator] Step 4: Building answer key")
            answer_key = self._extract_answer_key(exam_content)

            # Step 5: Assemble DOCX
            self._set_progress(85, "Assembling exam document…")
            logger.info("[ExamOrchestrator] Step 5: Assembling DOCX files")
            output_dir = Path(settings.OUTPUT_DIR)
            output_dir.mkdir(parents=True, exist_ok=True)

            generator = ExamDocxGenerator(
                formatting=self.formatting,
                structure=self.structure,
            )

            # Main exam paper (variant 1)
            exam_filename = f"exam_{uuid.uuid4().hex[:8]}.docx"
            exam_path = output_dir / exam_filename
            generator.generate_exam(exam_content, str(exam_path), variant_num=1)

            # Answer key
            answer_key_filename = f"answer_key_{uuid.uuid4().hex[:8]}.docx"
            answer_key_path = output_dir / answer_key_filename
            generator.generate_answer_key(answer_key, str(answer_key_path))

            # Step 6: Generate additional variants (entirely separate papers)
            variant_files: list[str] = []
            if num_variants > 1:
                self._set_progress(90, f"Generating {num_variants - 1} extra variant(s)…")
                logger.info(
                    f"[ExamOrchestrator] Step 6: Generating "
                    f"{num_variants - 1} additional variants"
                )
                for variant_num in range(2, num_variants + 1):
                    variant_content = self._create_variant(exam_content, variant_num)
                    variant_filename = (
                        f"exam_variant{variant_num}_{uuid.uuid4().hex[:8]}.docx"
                    )
                    variant_path = output_dir / variant_filename
                    generator.generate_exam(
                        variant_content, str(variant_path), variant_num=variant_num
                    )
                    variant_files.append(variant_filename)

            # Step 7: Persist DB record
            self._set_progress(98, "Finalizing…")
            logger.info("[ExamOrchestrator] Step 7: Updating database record")
            exam = self.db.query(Exam).filter(Exam.id == self.exam_id).first()
            if exam:
                exam.filename = exam_filename
                exam.file_path = str(exam_path)
                exam.answer_key_filename = answer_key_filename
                exam.answer_key_path = str(answer_key_path)
                exam.status = "ready"
                exam.progress = 100
                exam.progress_message = "Done"
                self.db.commit()

            logger.info(
                f"[ExamOrchestrator] Exam generation complete: {exam_filename}"
            )
            return {
                "id": self.exam_id,
                "filename": exam_filename,
                "answer_key_filename": answer_key_filename,
                "variants": variant_files,
                "status": "ready",
            }

        except Exception as e:
            logger.error(
                f"[ExamOrchestrator] Generation failed for exam {self.exam_id}: {e}\n"
                f"{traceback.format_exc()}"
            )
            exam = self.db.query(Exam).filter(Exam.id == self.exam_id).first()
            if exam:
                exam.status = "error"
                exam.error_message = str(e)[:500]
                self.db.commit()
            raise

    # ─── Section planning ────────────────────────────────────────────────────

    def _plan_sections(self) -> list[dict]:
        """Decide section structure based on exam type.

        For `weekly_assessment`, returns topic-organized sections from
        `topic_sections` (or DEFAULT_TOPIC_SECTIONS).
        For other types, returns question-type-organized sections with marks
        scaled to total_marks.
        """
        exam_type = self.structure.get("exam_type", "monthly_exam")

        if exam_type == "weekly_assessment":
            return self._plan_topic_sections()
        return self._calculate_section_distribution()

    def _plan_topic_sections(self) -> list[dict]:
        """Build topic-organized sections (MOE weekly assessment style)."""
        topic_sections = self.structure.get("topic_sections") or []
        if not topic_sections:
            topic_sections = [dict(s) for s in DEFAULT_TOPIC_SECTIONS]

        total_marks = int(self.structure.get("total_marks", 20) or 20)
        sections: list[dict] = []
        for spec in topic_sections:
            count = int(spec.get("count", 4) or 0)
            if count <= 0:
                continue
            marks_per_q = int(spec.get("marks_per_question", 1) or 1)
            sections.append({
                "key": (spec.get("title_en") or spec.get("title_ar") or "section")
                       .split(":")[-1].strip().lower().replace(" ", "_") or "section",
                "title_ar": spec.get("title_ar", ""),
                "title_en": spec.get("title_en", ""),
                "question_type": "show_work",   # MOE weekly is open-ended
                "bloom_level": "apply_analyze",
                "count": count,
                "marks_per_question": marks_per_q,
                "total_marks": marks_per_q * count,
            })

        # Reconcile sum to total_marks if it drifted (clamp ≥ count)
        current = sum(s["total_marks"] for s in sections)
        if sections and current != total_marks:
            diff = total_marks - current
            largest = max(sections, key=lambda s: s["total_marks"])
            largest["total_marks"] = max(largest["count"], largest["total_marks"] + diff)
            largest["marks_per_question"] = max(
                1, largest["total_marks"] // max(largest["count"], 1)
            )
        return sections

    def _calculate_section_distribution(self) -> list[dict]:
        """Question-type-organized sections (used for quiz / monthly_exam)."""
        exam_type = self.structure.get("exam_type", "monthly_exam")
        total_marks = int(self.structure.get("total_marks", 40) or 40)

        sections_template = MOE_EXAM_SECTIONS.get(
            exam_type, MOE_EXAM_SECTIONS["monthly_exam"]
        )
        default_marks = DEFAULT_MARKS.get(exam_type, DEFAULT_MARKS["monthly_exam"])

        question_counts = {
            "choose_correct": int(self.structure.get("choose_correct", 8) or 0),
            "complete_following": int(
                self.structure.get("complete_following", 5) or 0
            ),
            "answer_short": int(self.structure.get("answer_short", 4) or 0),
            "solve_prove": int(self.structure.get("solve_prove", 3) or 0),
            "essay_extended": int(self.structure.get("essay_extended", 0) or 0),
        }

        sections: list[dict] = []
        total_questions = sum(
            question_counts.get(s["key"], 0) for s in sections_template
        )

        for section_template in sections_template:
            key = section_template["key"]
            count = question_counts.get(key, 0)
            if count == 0:
                continue

            section_marks = default_marks.get(key, 0)
            if section_marks == 0:
                section_marks = int(
                    total_marks * count / max(total_questions, 1)
                )

            marks_per_question = max(1, section_marks // max(count, 1))

            sections.append({
                **section_template,
                "count": count,
                "total_marks": marks_per_question * count,
                "marks_per_question": marks_per_question,
            })

        # Reconcile sum to total_marks (clamp to keep section total ≥ count
        # so rendered headers never show 0 / negative mark allocations).
        current_total = sum(s["total_marks"] for s in sections)
        if current_total != total_marks and sections:
            diff = total_marks - current_total
            largest = max(sections, key=lambda s: s["total_marks"])
            largest["total_marks"] = max(largest["count"], largest["total_marks"] + diff)
            largest["marks_per_question"] = max(
                1, largest["total_marks"] // max(largest["count"], 1)
            )

        return sections

    # ─── Context retrieval (RAG + optional MOE reference) ────────────────────

    async def _retrieve_context(self) -> str:
        """Retrieve textbook RAG context, optionally appended with MOE reference."""
        rag_service, _ = self._init_rag_services()
        rag_text = ""
        if rag_service:
            book_id = self.scope.get("book_id")
            chapter_ids = self.scope.get("chapter_ids", []) or []
            topic_ids = self.scope.get("topic_ids", []) or []

            from models.chapter import Chapter
            from models.topic import Topic

            query_parts: list[str] = []
            if chapter_ids:
                chapters = (
                    self.db.query(Chapter).filter(Chapter.id.in_(chapter_ids)).all()
                )
                query_parts.extend([ch.title for ch in chapters])
            if topic_ids:
                topics = self.db.query(Topic).filter(Topic.id.in_(topic_ids)).all()
                query_parts.extend([t.title for t in topics])

            if not query_parts:
                query_parts = ["exam questions"]

            try:
                results = await rag_service.retrieve_for_topics(
                    book_id=book_id,
                    topics=query_parts,
                    top_k=settings.RAG_TOP_K,
                )
                rag_text = "\n\n".join(
                    [r.get("text", "") for r in results]
                ) if results else ""
                logger.info(
                    f"[ExamOrchestrator] Retrieved {len(results or [])} RAG chunks"
                )
            except Exception as e:
                logger.error(
                    f"[ExamOrchestrator] RAG retrieval failed: {e}",
                    exc_info=True,
                )
        else:
            logger.warning("[ExamOrchestrator] RAG unavailable, using empty context")

        # Optionally pull official MOE reference for grounded generation
        reference_text = await self._get_moe_reference_text()
        if reference_text:
            return (
                "=== OFFICIAL MOE WEEKLY ASSESSMENT (REFERENCE FOR STYLE & DIFFICULTY) ===\n"
                f"{reference_text}\n\n"
                "=== TEXTBOOK CONTENT (RAG) ===\n"
                f"{rag_text}"
            )
        return rag_text

    async def _get_moe_reference_text(self) -> Optional[str]:
        """Fetch and cache the text of an official MOE assessment, if requested."""
        moe_ref_id = (
            self.formatting.get("moe_reference_id")
            or self.structure.get("moe_reference_id")
        )
        if not moe_ref_id:
            return None
        try:
            from services.moe_library_service import MOELibraryService
            svc = MOELibraryService()
            text = await svc.get_assessment_reference_text(moe_ref_id)
            if text:
                logger.info(
                    f"[ExamOrchestrator] Loaded MOE reference {moe_ref_id} "
                    f"({len(text)} chars)"
                )
            return text
        except Exception as e:
            logger.warning(f"[ExamOrchestrator] MOE reference fetch failed: {e}")
            return None

    # ─── Question generation per section × per group ─────────────────────────

    async def _generate_exam_questions(
        self,
        sections: list[dict],
        context: str,
        language: str,
        groups_per_variant: int,
    ) -> list[dict]:
        """Generate questions for each section × each parallel group.

        Returns a list of section dicts, each with a `groups` list. Group 0
        is rendered as the canonical exam paper; groups 1..N appear as
        "First/Second/Third group" panels (MOE weekly assessment style).
        """
        llm_service = self._init_llm_service()
        if not llm_service:
            logger.warning(
                "[ExamOrchestrator] LLM unavailable, generating placeholder questions"
            )
            return self._generate_placeholder_exam(sections, groups_per_variant)

        grade = self.formatting.get("grade", "")
        exam_content: list[dict] = []
        for section in sections:
            section_groups: list[dict] = []
            for group_idx in range(groups_per_variant):
                try:
                    questions = await llm_service.generate_exercises(
                        context=context,
                        exercise_type=section["question_type"],
                        count=section["count"],
                        difficulty=self._bloom_to_difficulty(
                            section.get("bloom_level", "apply_analyze")
                        ),
                        language=language,
                        grade_level=grade,
                        lesson_title=(
                            f"{section.get('title_en') or section.get('title_ar', '')} "
                            f"(group {group_idx + 1})"
                        ),
                    )
                    section_groups.append({
                        "group_index": group_idx,
                        "questions": questions[: section["count"]],
                    })
                except Exception as e:
                    logger.error(
                        f"[ExamOrchestrator] Failed to generate "
                        f"section '{section['key']}' group {group_idx + 1}: {e}"
                    )
                    section_groups.append({
                        "group_index": group_idx,
                        "questions": self._placeholder_questions(section),
                    })

            exam_content.append({
                **section,
                # Top-level questions list = group 0 (used by simple consumers)
                "questions": section_groups[0]["questions"] if section_groups else [],
                "groups": section_groups,
            })
        return exam_content

    def _build_section_prompt(
        self, section: dict, context: str, language: str, grade: str
    ) -> str:
        """Build a detailed prompt for generating a specific exam section."""
        bloom_level = section["bloom_level"]
        bloom_desc = {
            "remember_understand": (
                "Remember and Understand (recall facts, explain concepts)"
            ),
            "apply_analyze": (
                "Apply and Analyze (use knowledge in new situations, "
                "break down problems)"
            ),
            "evaluate_create": (
                "Evaluate and Create (judge, design, construct new solutions)"
            ),
        }
        return (
            f"Generate {section['count']} exam questions for the following section:\n"
            f"Section: {section.get('title_en', '')}\n"
            f"Question Type: {section['question_type']}\n"
            f"Bloom's Level: {bloom_desc.get(bloom_level, bloom_level)}\n"
            f"Marks per question: {section['marks_per_question']}\n"
            f"Grade: {grade}\n"
            f"Language: {language}\n\n"
            "The questions should follow the Egyptian Ministry of Education exam format.\n"
            "Each question must be mathematically rigorous and appropriate "
            "for the grade level.\n"
        )

    def _bloom_to_difficulty(self, bloom_level: str) -> str:
        """Map Bloom's taxonomy level to difficulty."""
        return {
            "remember_understand": "easy",
            "apply_analyze": "medium",
            "evaluate_create": "hard",
        }.get(bloom_level, "medium")

    # ─── Answer key & variants ───────────────────────────────────────────────

    def _extract_answer_key(self, exam_content: list[dict]) -> list[dict]:
        """Extract answer key entries — one row per (section, group, question)."""
        answer_key: list[dict] = []
        for section in exam_content:
            section_answers = {
                "key": section["key"],
                "title_ar": section.get("title_ar", ""),
                "title_en": section.get("title_en", ""),
                "marks_per_question": section.get("marks_per_question", 2),
                "answers": [],   # Backwards-compatible: group-0 only
                "groups": [],    # New: full per-group breakdown
            }
            qtype = section.get("question_type", "")
            for group in section.get("groups", [{
                "group_index": 0,
                "questions": section.get("questions", []),
            }]):
                group_answers: list[dict] = []
                for i, q in enumerate(group.get("questions", []), 1):
                    correct = q.get("correct_answer", "")
                    steps = q.get("solution_steps") or q.get("explanation") or ""
                    # show_work / long_answer LLM responses bundle the whole
                    # solution in correct_answer — copy it into solution_steps
                    # so the rubric column renders something useful.
                    if not steps and qtype in ("show_work", "long_answer", "short_answer"):
                        steps = correct
                    group_answers.append({
                        "number": i,
                        "correct_answer": correct,
                        "solution_steps": steps,
                        "marks": section.get("marks_per_question", 2),
                    })
                section_answers["groups"].append({
                    "group_index": group.get("group_index", 0),
                    "answers": group_answers,
                })
                if group.get("group_index", 0) == 0:
                    section_answers["answers"] = group_answers
            answer_key.append(section_answers)
        return answer_key

    def _create_variant(
        self, exam_content: list[dict], variant_num: int
    ) -> list[dict]:
        """Create a separate variant by deterministic shuffle (per variant seed).

        Deep-copies questions before mutation so each variant shuffles from the
        original ordering, not from the previous variant's already-shuffled
        state.
        """
        variant: list[dict] = []
        for section in exam_content:
            new_groups: list[dict] = []
            for group in section.get("groups", []):
                questions = copy.deepcopy(group.get("questions", []))
                random.seed(
                    variant_num * 42 + hash(section["key"]) + group.get("group_index", 0)
                )
                random.shuffle(questions)

                if section["question_type"] == "multiple_choice":
                    for q in questions:
                        options = q.get("options", [])
                        if options:
                            random.shuffle(options)
                            q["options"] = options
                new_groups.append({
                    "group_index": group.get("group_index", 0),
                    "questions": questions,
                })
            new_section = {
                **section,
                "groups": new_groups,
                "questions": new_groups[0]["questions"] if new_groups else [],
            }
            variant.append(new_section)
        return variant

    # ─── Placeholder generation (when no LLM key) ────────────────────────────

    def _generate_placeholder_exam(
        self, sections: list[dict], groups_per_variant: int
    ) -> list[dict]:
        out: list[dict] = []
        for section in sections:
            groups = []
            for g in range(groups_per_variant):
                groups.append({
                    "group_index": g,
                    "questions": self._placeholder_questions(section),
                })
            out.append({
                **section,
                "questions": groups[0]["questions"] if groups else [],
                "groups": groups,
            })
        return out

    def _placeholder_questions(self, section: dict) -> list[dict]:
        """Generate placeholder questions for a section."""
        questions = []
        for i in range(section["count"]):
            q = {
                "question": f"[Question {i + 1} - {section['question_type']}]",
                "correct_answer": "[Answer]",
                "explanation": "[Solution steps]",
            }
            if section["question_type"] == "multiple_choice":
                q["options"] = ["[Option A]", "[Option B]", "[Option C]", "[Option D]"]
            questions.append(q)
        return questions
