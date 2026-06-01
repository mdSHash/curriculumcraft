"""Workbook generation orchestrator — coordinates RAG retrieval + LLM generation + DOCX assembly."""

import logging
import traceback
import uuid
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from config import get_settings
from models.workbook import Workbook
from services.subjects.registry import get_strategy

logger = logging.getLogger(__name__)
settings = get_settings()


# ─── Page Budget Constants (matching frontend LAYOUT_STYLES) ─────────────────
# These define how many MCQ-equivalent exercises fit per page at each density.
EXERCISES_PER_PAGE_BY_DENSITY = {
    "spacious": 2,   # 2-3 exercises per page, large answer boxes
    "standard": 3,   # 4-5 exercises per page, medium answer spaces
    "dense": 5,      # 6-8 exercises per page, compact answer lines
}

# Exercise type weight relative to MCQ (1.0 = one MCQ slot)
EXERCISE_TYPE_WEIGHT = {
    "multiple_choice": 1.0,
    "fill_blank": 0.7,
    "fill_in_blank": 0.7,
    "true_false": 0.6,
    "matching": 1.5,
    "show_work": 1.5,
    "long_answer": 1.5,
    "word_problems": 1.5,
    "word_problem": 1.5,
}


class WorkbookOrchestrator:
    """Orchestrates the complete workbook generation pipeline.

    Uses the RAG service to retrieve relevant textbook content
    for each topic/lesson before generating exercises.
    """

    def __init__(self, db: Session, config: dict, workbook_id: int) -> None:
        """
        Args:
            db: SQLAlchemy database session.
            config: The full WorkbookConfig as a dict.
            workbook_id: The pre-created Workbook record ID.
        """
        self.db = db
        self.config = config
        self.workbook_id = workbook_id

        # Config shortcuts
        self.scope = config.get("scope", {})
        self.structure = config.get("structure", {})
        self.exercise_config = config.get("exercises", {})
        self.formatting = config.get("formatting", {})

        # Resolve the per-subject strategy from the Workbook row's
        # subject_key (denormalized from the parent Book). Used to
        # dispatch math verification, rendering pipeline, and (in
        # future commits) per-subject prompts and fallbacks.
        wb_row = self.db.query(Workbook).filter(Workbook.id == self.workbook_id).first()
        subject_key = wb_row.subject_key if wb_row else None
        self.strategy = get_strategy(self.db, subject_key)

    def _set_progress(self, percent: int, message: str) -> None:
        """Persist a progress update to the workbook row.

        Best-effort: a failure here is logged and swallowed so a progress-write
        glitch can never derail generation itself.
        """
        try:
            workbook = self.db.query(Workbook).filter(Workbook.id == self.workbook_id).first()
            if workbook:
                workbook.progress = max(0, min(100, int(percent)))
                workbook.progress_message = message[:255] if message else None
                self.db.commit()
        except Exception as e:  # pragma: no cover — defensive
            logger.warning(f"[Orchestrator] Failed to update progress: {e}")

    def _init_rag_services(self):
        """Lazily initialize RAG services (embedding, hybrid search, context assembler).

        Returns:
            Tuple of (rag_service, context_assembler) or (None, None) on failure.
        """
        try:
            from services.embedding_service import EmbeddingService
            from services.hybrid_search import HybridSearch
            from services.context_assembler import ContextAssembler
            from services.rag_service import RAGService

            logger.info(
                f"[Orchestrator] Initializing RAG services: "
                f"model={settings.EMBEDDING_MODEL}, faiss_dir={settings.FAISS_DIR}"
            )

            embedding_service = EmbeddingService(
                model_name=settings.EMBEDDING_MODEL,
                faiss_dir=settings.FAISS_DIR,
            )

            # Try to initialize hybrid search
            hybrid_search = None
            try:
                hybrid_search = HybridSearch(
                    embedding_service=embedding_service,
                    faiss_dir=settings.FAISS_DIR,
                    semantic_weight=settings.RAG_HYBRID_ALPHA,
                    mmr_lambda=settings.RAG_MMR_LAMBDA,
                )
                logger.info("[Orchestrator] Hybrid search initialized successfully")
            except Exception as e:
                logger.warning(f"[Orchestrator] Hybrid search unavailable: {e}")

            context_assembler = ContextAssembler(
                max_tokens=settings.RAG_MAX_CONTEXT_CHARS // 4,  # Convert chars to approx tokens
                embedding_service=embedding_service,
            )

            rag_service = RAGService(
                embedding_service=embedding_service,
                hybrid_search=hybrid_search,
                context_assembler=context_assembler,
            )

            logger.info("[Orchestrator] RAG services initialized successfully")
            return rag_service, context_assembler

        except Exception as e:
            logger.warning(
                f"[Orchestrator] Failed to initialize RAG services: {e}\n"
                f"{traceback.format_exc()}"
            )
            return None, None

    async def generate(self) -> dict:
        """
        Full generation pipeline:
        1. Calculate exercise distribution (capped by page budget)
        1.5. Generate lesson illustrations (if study book mode)
        1.6. Generate solved examples (if study book mode)
        2. Attempt LLM generation with RAG context (fallback if unavailable)
        3. Deduplicate exercises
        4. Verify math correctness
        5. Assemble DOCX
        6. Update DB record
        7. Return workbook info
        """
        # Lazy import — pulls in heavy docx dependency
        from services.docx_generator import DocxGenerator

        try:
            # Determine output mode
            output_mode = self.structure.get("output_mode", "workbook_only")
            num_pages = self.structure.get("total_pages", 20)
            is_study_book = output_mode == "illustration_and_workbook"

            self._set_progress(3, "Planning exercise distribution…")

            # Step 1: Calculate exercise distribution (page-budget-aware)
            logger.info(f"[Orchestrator] Step 1: Calculating exercise distribution for workbook {self.workbook_id}")
            distribution = self._calculate_exercise_distribution()
            total_planned = sum(d['count'] for d in distribution)
            logger.info(
                f"[Orchestrator] Exercise distribution calculated: {len(distribution)} batches, "
                f"total={total_planned} exercises"
            )

            # Step 1.5: Generate lesson illustrations (study book mode only)
            lesson_illustrations = []
            if is_study_book:
                self._set_progress(8, "Generating lesson illustrations…")
                logger.info(f"[Orchestrator] Step 1.5: Generating lesson illustrations for study book mode")
                lesson_illustrations = await self._generate_lesson_illustrations()
                logger.info(f"[Orchestrator] Generated {len(lesson_illustrations)} lesson illustrations")

            # Step 1.6: Generate solved examples (study book mode only)
            solved_examples = []
            if is_study_book:
                self._set_progress(20, "Generating solved examples…")
                logger.info(f"[Orchestrator] Step 1.6: Generating solved examples for study book mode")
                solved_examples = await self._generate_solved_examples()
                logger.info(f"[Orchestrator] Generated {len(solved_examples)} solved examples")

            # Step 2: Generate exercises
            self._set_progress(30 if is_study_book else 10, "Retrieving curriculum content…")
            logger.info(f"[Orchestrator] Step 2: Generating exercises for workbook {self.workbook_id}")
            exercises = await self._generate_exercises(distribution)
            logger.info(f"[Orchestrator] Generated {len(exercises)} exercises total")

            # Step 2.5: Deduplicate exercises
            self._set_progress(80, "Deduplicating exercises…")
            exercises = self._deduplicate_exercises(exercises)

            # Step 2.6: Enforce page budget cap — trim excess exercises
            # In study book mode, reduce exercise budget to account for illustrations + solved examples
            if is_study_book and (solved_examples or lesson_illustrations):
                # Each solved example takes ~1 page; each lesson illustration takes ~1.5 pages
                example_pages = len(solved_examples)
                illustration_pages = int(len(lesson_illustrations) * 1.5)
                exercise_pages = max(1, num_pages - 1 - example_pages - illustration_pages)  # -1 for cover
                max_exercises = self._get_max_exercises_for_pages(exercise_pages + 1)  # +1 because method subtracts cover
            else:
                max_exercises = self._get_max_exercises_for_pages(num_pages)

            if len(exercises) > max_exercises:
                logger.info(
                    f"[Orchestrator] Trimming exercises from {len(exercises)} to {max_exercises} "
                    f"to fit page budget (study_book={is_study_book})"
                )
                exercises = exercises[:max_exercises]

            # Step 2.7: Math verification (best-effort)
            self._set_progress(85, "Verifying math correctness…")
            exercises = await self._verify_exercises(exercises)

            # Step 2.8: Order exercises pedagogically (grouped by topic, then difficulty)
            exercises = self._order_exercises_pedagogically(exercises)

            # Step 3: Assemble DOCX
            self._set_progress(92, "Assembling document…")
            logger.info(f"[Orchestrator] Step 3: Assembling DOCX for workbook {self.workbook_id}")
            filename = f"workbook_{uuid.uuid4().hex[:8]}.docx"
            output_dir = Path(settings.OUTPUT_DIR)
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = str(output_dir / filename)

            generator = DocxGenerator(
                config=self.config,
                exercises=exercises,
                output_path=output_path,
                illustration_content=solved_examples if solved_examples else None,
                lesson_illustrations=lesson_illustrations if lesson_illustrations else None,
                num_pages=num_pages,
            )
            saved_path = generator.generate()
            logger.info(f"[Orchestrator] DOCX saved to: {saved_path}")

            # Step 4: Update DB record
            logger.info(f"[Orchestrator] Step 4: Updating DB record for workbook {self.workbook_id}")
            workbook = self.db.query(Workbook).filter(Workbook.id == self.workbook_id).first()
            if workbook:
                workbook.filename = filename
                workbook.file_path = saved_path
                workbook.status = "ready"
                workbook.progress = 100
                workbook.progress_message = "Done"
                self.db.commit()
                self.db.refresh(workbook)

            logger.info(f"[Orchestrator] Workbook {self.workbook_id} generated successfully: {filename}")

            return {
                "id": self.workbook_id,
                "filename": filename,
                "file_path": saved_path,
                "status": "ready",
                "total_exercises": len(exercises),
                "total_solved_examples": len(solved_examples),
                "total_lesson_illustrations": len(lesson_illustrations),
            }

        except Exception as e:
            logger.error(
                f"[Orchestrator] Workbook generation FAILED for ID {self.workbook_id}: {e}\n"
                f"{traceback.format_exc()}"
            )
            # Update status to error
            try:
                workbook = self.db.query(Workbook).filter(Workbook.id == self.workbook_id).first()
                if workbook:
                    workbook.status = "error"
                    self.db.commit()
            except Exception as db_err:
                logger.error(f"[Orchestrator] Failed to update error status in DB: {db_err}")

            raise

    # ─── Page Budget Helpers ───────────────────────────────────────────────────

    def _get_max_exercises_for_pages(self, num_pages: int) -> int:
        """Calculate the maximum number of exercises that fit within the page budget.

        Uses density-based constants that match the frontend LAYOUT_STYLES:
        - spacious: 2 exercises/page
        - standard: 3 exercises/page
        - dense: 5 exercises/page

        Always subtracts 1 page for the cover.

        Args:
            num_pages: Target total page count.

        Returns:
            Maximum number of exercises to generate.
        """
        # Subtract cover page
        available_content_pages = max(1, num_pages - 1)

        # Get density from layout_style
        layout_style = self.structure.get("layout_style", "standard")
        exercises_per_page = EXERCISES_PER_PAGE_BY_DENSITY.get(layout_style, 3)

        max_exercises = available_content_pages * exercises_per_page

        logger.info(
            f"[Orchestrator] Page budget: {num_pages} total pages, "
            f"content_pages={available_content_pages}, density={layout_style}, "
            f"exercises_per_page={exercises_per_page}, max_exercises={max_exercises}"
        )

        return max(4, max_exercises)

    async def _verify_exercises(self, exercises: list[dict]) -> list[dict]:
        """Run math verification on exercises (best-effort).

        If verification fails for individual exercises, they are kept but
        marked as unverified in logs. If the entire verification system fails,
        returns exercises unchanged.

        Args:
            exercises: List of exercise dicts.

        Returns:
            Verified/corrected exercises.
        """
        if not settings.verification_enabled:
            return exercises

        # Dispatch on subject: only run answer verification when the
        # strategy provides one. Math returns MathVerifier; non-math
        # subjects (arabic, language, religion, history…) return None
        # so we don't run a math-equation check on prose answers.
        verifier = self.strategy.verifier()
        if verifier is None:
            logger.info(
                "[Orchestrator] Subject %r has no answer verifier — skipping",
                self.strategy.key,
            )
            for ex in exercises:
                ex.setdefault("_verified", False)
            return exercises

        try:
            verified = await verifier.verify_exercises(exercises)
            logger.info(
                "[Orchestrator] Answer verification complete for %d exercises (subject=%s)",
                len(exercises), self.strategy.key,
            )
            return verified
        except Exception as e:
            logger.warning(
                f"[Orchestrator] Answer verification system failed (non-blocking): {e}. "
                f"All {len(exercises)} exercises included as unverified."
            )
            for ex in exercises:
                ex.setdefault("_verified", False)
            return exercises

    # ─── Pedagogical Ordering ──────────────────────────────────────────────────

    def _order_exercises_pedagogically(self, exercises: list[dict]) -> list[dict]:
        """Order exercises by topic (curriculum order) then by difficulty within each topic.

        Groups exercises by their topic, maintains the original topic order
        (which reflects curriculum sequence), and within each topic group
        orders by difficulty: easy → medium → hard.

        Args:
            exercises: List of exercise dicts with 'topic' and 'difficulty' keys.

        Returns:
            Reordered list of exercises.
        """
        if not exercises:
            return exercises

        # Get the curriculum-ordered topic list
        topic_order = self._get_topic_names_from_scope()

        # Build a topic → index map for sorting
        topic_index = {name: idx for idx, name in enumerate(topic_order)}

        # Difficulty ordering
        difficulty_order = {"easy": 0, "medium": 1, "hard": 2}

        def sort_key(ex):
            topic = ex.get("topic", "")
            # If topic not in our ordered list, put it at the end
            t_idx = topic_index.get(topic, len(topic_order))
            d_idx = difficulty_order.get(ex.get("difficulty", "medium"), 1)
            return (t_idx, d_idx)

        return sorted(exercises, key=sort_key)

    # ─── Exercise Generation ───────────────────────────────────────────────────

    async def _generate_exercises(self, distribution: list[dict]) -> list[dict]:
        """Generate exercises via LLM with RAG context, or fallback.

        Error handling:
        - If LLM is not configured: logs clearly and uses fallback
        - If LLM generation fails entirely: logs the error with traceback and uses fallback
        - If individual batches fail: logs each failure, continues with remaining batches
        - If LLM returns 0 exercises: logs warning and uses fallback
        """
        exercises: list[dict] = []

        # Try LLM generation with RAG
        api_key = settings.GEMINI_API_KEY
        if api_key and api_key != "your_gemini_api_key_here":
            logger.info(f"[Orchestrator] Attempting LLM generation with model={settings.GEMINI_MODEL}")
            try:
                from services.llm_service import LLMService

                llm = LLMService(api_key=api_key, model=settings.GEMINI_MODEL)
                logger.info(f"[Orchestrator] LLM service initialized, model available: {llm.model is not None}")

                # Initialize RAG services for context retrieval
                rag_service, context_assembler = self._init_rag_services()
                logger.info(f"[Orchestrator] RAG services initialized: rag={rag_service is not None}")

                # Get grade level from config
                grade_level = self.formatting.get("grade", "")

                batch_failures = 0
                # Reserve [progress_start, progress_end] for the batch loop so
                # the bar moves smoothly through each generated batch.
                progress_start = 30 if self.structure.get("output_mode") == "illustration_and_workbook" else 10
                progress_end = 78
                progress_span = progress_end - progress_start
                total_batches = max(1, len(distribution))

                for batch_idx, batch in enumerate(distribution):
                    pct = progress_start + int(progress_span * batch_idx / total_batches)
                    self._set_progress(
                        pct,
                        f"Generating exercises ({batch_idx + 1}/{total_batches})…",
                    )
                    try:
                        # Build context using RAG if available
                        context = await self._build_rag_context_for_batch(
                            batch, rag_service
                        )

                        # Get lesson title for this batch
                        lesson_title = batch.get("topic", "")

                        logger.debug(
                            f"[Orchestrator] Batch {batch_idx+1}/{len(distribution)}: "
                            f"type={batch['type']}, count={batch['count']}, "
                            f"topic={lesson_title}, context_len={len(context)}"
                        )

                        batch_exercises = await llm.generate_exercises(
                            context=context,
                            exercise_type=batch["type"],
                            count=batch["count"],
                            difficulty=batch["difficulty"],
                            language=self.formatting.get("language", "english"),
                            grade_level=grade_level,
                            lesson_title=lesson_title,
                        )
                        logger.info(
                            f"[Orchestrator] Batch {batch_idx+1}: got {len(batch_exercises)} exercises"
                        )
                        # Tag each exercise with metadata
                        for ex in batch_exercises:
                            ex["type"] = batch["type"]
                            ex["difficulty"] = batch["difficulty"]
                            ex["topic"] = batch.get("topic", "General")
                        exercises.extend(batch_exercises)
                    except Exception as batch_err:
                        batch_failures += 1
                        logger.error(
                            f"[Orchestrator] Batch {batch_idx+1}/{len(distribution)} FAILED: "
                            f"type={batch.get('type')}, topic={batch.get('topic')}, "
                            f"error={batch_err}"
                        )
                        continue

                if batch_failures > 0:
                    logger.warning(
                        f"[Orchestrator] {batch_failures}/{len(distribution)} batches failed during LLM generation"
                    )

                if exercises:
                    logger.info(f"[Orchestrator] LLM generation succeeded: {len(exercises)} exercises")
                    return exercises
                else:
                    logger.error(
                        "[Orchestrator] LLM returned 0 exercises across all batches. "
                        "Falling back to template exercises. Check API key and model configuration."
                    )

            except Exception as e:
                logger.error(
                    f"[Orchestrator] LLM generation system failed: {e}\n"
                    f"{traceback.format_exc()}\n"
                    f"Falling back to template exercises."
                )
        else:
            logger.warning(
                "[Orchestrator] No valid Gemini API key configured. "
                "Set GEMINI_API_KEY in .env to enable AI-generated exercises. "
                "Using template fallback."
            )

        # Fallback: generate placeholder exercises
        logger.info("[Orchestrator] Using fallback exercise generation")
        exercises = self._generate_fallback_exercises(distribution)
        logger.info(f"[Orchestrator] Fallback generated {len(exercises)} exercises")
        return exercises

    async def _build_rag_context_for_batch(self, batch: dict, rag_service) -> str:
        """Build context for a generation batch using RAG retrieval.

        Retrieves relevant textbook content for the batch's topic and
        assembles it into a coherent context string for the LLM.

        Args:
            batch: Exercise batch dict with type, difficulty, topic, etc.
            rag_service: Initialized RAGService instance (or None).

        Returns:
            Context string for LLM exercise generation.
        """
        topic = batch.get("topic", "Mathematics")
        grade = self.formatting.get("grade", "")
        book_id = self.scope.get("book_id")
        chapter_id = batch.get("chapter_id")

        # If RAG service is available and we have a book_id, use it
        if rag_service is not None and book_id:
            try:
                context = rag_service.retrieve_for_exercise_generation(
                    book_id=book_id,
                    topic=topic,
                    exercise_type=batch["type"],
                    difficulty=batch["difficulty"],
                    chapter_id=chapter_id,
                    top_k=settings.RAG_TOP_K,
                )

                if context and len(context) > 50:
                    # Append generation instructions with full metadata
                    instructions = (
                        f"\n\n{'=' * 50}\n"
                        f"GENERATION INSTRUCTIONS:\n"
                        f"Generate {batch['type']} exercises based on the above textbook content.\n"
                        f"Topic/Lesson: {topic}\n"
                        f"Grade level: {grade}\n"
                        f"Difficulty: {batch['difficulty']}\n"
                        f"The exercises MUST be aligned with the curriculum content shown above.\n"
                        f"Use similar notation, terminology, and difficulty level as the textbook.\n"
                    )
                    return context + instructions

            except Exception as e:
                logger.warning(
                    f"RAG context retrieval failed for topic '{topic}': {e}"
                )

        # Fallback: generic context without RAG (language-aware)
        language = self.formatting.get("language", "english")
        if language in ("arabic", "bilingual"):
            return (
                f"\u0623\u0646\u0634\u0626 \u062a\u0645\u0627\u0631\u064a\u0646 "
                f"\u0645\u0646 \u0646\u0648\u0639 {batch['type']} "
                f"\u0644\u0644\u0645\u0648\u0636\u0648\u0639: {topic}.\n"
                f"\u0627\u0644\u0635\u0641: {grade}.\n"
                f"\u0645\u0633\u062a\u0648\u0649 \u0627\u0644\u0635\u0639\u0648\u0628\u0629: {batch['difficulty']}.\n"
                f"\u0627\u0644\u062a\u0645\u0627\u0631\u064a\u0646 \u064a\u062c\u0628 \u0623\u0646 "
                f"\u062a\u0643\u0648\u0646 \u0645\u0646\u0627\u0633\u0628\u0629 "
                f"\u0644\u0643\u0631\u0627\u0633\u0629 \u0639\u0645\u0644 \u0631\u064a\u0627\u0636\u064a\u0627\u062a "
                f"\u0645\u0637\u0628\u0648\u0639\u0629.\n"
                f"Generate {batch['type']} exercises for the topic: {topic}. "
                f"Grade level: {grade}. Difficulty: {batch['difficulty']}."
            )
        return (
            f"Generate {batch['type']} exercises for the topic: {topic}. "
            f"Grade level: {grade}. "
            f"Difficulty: {batch['difficulty']}. "
            f"The exercises should be appropriate for a printed math workbook."
        )

    # ─── Deduplication ─────────────────────────────────────────────────────────

    def _deduplicate_exercises(self, exercises: list[dict]) -> list[dict]:
        """Remove duplicate or near-duplicate exercises.

        Compares normalized question text to detect duplicates.
        """
        seen_questions: set = set()
        unique: list[dict] = []

        for ex in exercises:
            # Get the question text (different field names for different types)
            question = ex.get("question", ex.get("statement", ex.get("instruction", ""))).strip()

            # Normalize: lowercase, collapse whitespace, remove punctuation variations
            normalized = " ".join(question.lower().split())

            if normalized and normalized not in seen_questions:
                seen_questions.add(normalized)
                unique.append(ex)
            elif not normalized:
                # Keep exercises without question text (shouldn't happen but safety)
                unique.append(ex)

        if len(unique) < len(exercises):
            logger.info(
                f"[Orchestrator] Deduplication removed {len(exercises) - len(unique)} "
                f"duplicate exercises ({len(exercises)} -> {len(unique)})"
            )

        return unique

    # ─── Solved Examples for Study Book Mode ─────────────────────────────────────

    async def _generate_solved_examples(self) -> list[dict]:
        """Generate LLM-powered solved examples for study book / illustration mode.

        Uses the LLM to generate proper textbook-style worked examples with
        step-by-step solutions, replacing the old garbled OCR approach.

        Returns:
            List of solved example dicts grouped by topic, or empty list if
            mode is workbook_only or generation fails.
        """
        output_mode = self.structure.get("output_mode", "workbook_only")

        if output_mode != "illustration_and_workbook":
            logger.info(
                f"[Orchestrator] Output mode is '{output_mode}', skipping solved examples."
            )
            return []

        logger.info("[Orchestrator] Generating LLM-powered solved examples for study book mode")

        # Calculate how many examples to generate based on page budget
        num_pages = self.structure.get("total_pages", 20)
        # ~40% of content pages for examples, each example takes ~1 page
        content_pages = max(1, num_pages - 1)  # subtract cover
        example_pages = max(1, int(content_pages * 0.4))
        # 1 example per page approximately
        total_examples_budget = example_pages

        # Get topics
        topic_names = self._get_topic_names_from_scope()
        num_topics = max(1, len(topic_names))

        # Distribute examples across topics (1-2 per topic)
        examples_per_topic = max(1, min(3, total_examples_budget // num_topics))

        logger.info(
            f"[Orchestrator] Solved examples budget: {total_examples_budget} total, "
            f"{examples_per_topic} per topic, {num_topics} topics"
        )

        # Try LLM generation
        api_key = settings.GEMINI_API_KEY
        all_examples: list[dict] = []

        if api_key and api_key != "your_gemini_api_key_here":
            try:
                from services.llm_service import LLMService

                llm = LLMService(api_key=api_key, model=settings.GEMINI_MODEL)

                if llm.model is None:
                    logger.warning("[Orchestrator] LLM model not available for solved examples")
                    return []

                # Initialize RAG for context
                rag_service, _ = self._init_rag_services()
                language = self.formatting.get("language", "english")
                grade_level = self.formatting.get("grade", "")
                book_id = self.scope.get("book_id")
                chapter_ids = self.scope.get("chapter_ids", [])

                for topic in topic_names:
                    try:
                        # Build context for this topic
                        context = ""
                        if rag_service and book_id:
                            try:
                                chapter_id = self._get_chapter_id_for_topic(topic, chapter_ids)
                                context = rag_service.retrieve_for_exercise_generation(
                                    book_id=book_id,
                                    topic=topic,
                                    exercise_type="show_work",
                                    difficulty="medium",
                                    chapter_id=chapter_id,
                                    top_k=settings.RAG_TOP_K,
                                )
                            except Exception as e:
                                logger.warning(f"RAG context failed for solved examples topic '{topic}': {e}")

                        if not context:
                            context = (
                                f"Generate solved examples for the topic: {topic}. "
                                f"Grade level: {grade_level}. "
                                f"The examples should be appropriate for Egyptian secondary school curriculum."
                            )

                        # Generate solved examples for this topic
                        topic_examples = await llm.generate_solved_examples(
                            context=context,
                            topic=topic,
                            count=examples_per_topic,
                            difficulty="medium",
                            language=language,
                            grade_level=grade_level,
                        )

                        all_examples.extend(topic_examples)
                        logger.info(
                            f"[Orchestrator] Generated {len(topic_examples)} solved examples for topic: {topic}"
                        )

                    except Exception as e:
                        logger.error(f"[Orchestrator] Failed to generate solved examples for topic '{topic}': {e}")
                        continue

                # Trim to budget
                if len(all_examples) > total_examples_budget:
                    all_examples = all_examples[:total_examples_budget]

                logger.info(f"[Orchestrator] Total solved examples generated: {len(all_examples)}")
                return all_examples

            except Exception as e:
                logger.error(f"[Orchestrator] Solved examples generation failed: {e}")
                return []
        else:
            logger.warning(
                "[Orchestrator] No valid Gemini API key for solved examples. Skipping."
            )
            return []

    async def _generate_lesson_illustrations(self) -> list[dict]:
        """Generate LLM-powered lesson illustrations for study book mode.

        Creates structured textbook-style lesson summaries with key concepts,
        theorems, formulas, and important notes for each topic.

        Returns:
            List of lesson illustration dicts, one per topic.
        """
        output_mode = self.structure.get("output_mode", "workbook_only")

        if output_mode != "illustration_and_workbook":
            logger.info(
                f"[Orchestrator] Output mode is '{output_mode}', skipping lesson illustrations."
            )
            return []

        logger.info("[Orchestrator] Generating LLM-powered lesson illustrations for study book mode")

        # Get topics
        topic_names = self._get_topic_names_from_scope()
        if not topic_names:
            logger.warning("[Orchestrator] No topics found for lesson illustrations")
            return []

        # Try LLM generation
        api_key = settings.GEMINI_API_KEY
        all_illustrations: list[dict] = []

        if api_key and api_key != "your_gemini_api_key_here":
            try:
                from services.llm_service import LLMService

                llm = LLMService(api_key=api_key, model=settings.GEMINI_MODEL)

                if llm.model is None:
                    logger.warning("[Orchestrator] LLM model not available for lesson illustrations")
                    return []

                # Initialize RAG for context
                rag_service, _ = self._init_rag_services()
                language = self.formatting.get("language", "english")
                grade_level = self.formatting.get("grade", "")
                book_id = self.scope.get("book_id")
                chapter_ids = self.scope.get("chapter_ids", [])

                for topic in topic_names:
                    try:
                        # Build context for this topic
                        context = ""
                        if rag_service and book_id:
                            try:
                                chapter_id = self._get_chapter_id_for_topic(topic, chapter_ids)
                                context = rag_service.retrieve_for_exercise_generation(
                                    book_id=book_id,
                                    topic=topic,
                                    exercise_type="show_work",
                                    difficulty="medium",
                                    chapter_id=chapter_id,
                                    top_k=settings.RAG_TOP_K,
                                )
                            except Exception as e:
                                logger.warning(f"RAG context failed for lesson illustration topic '{topic}': {e}")

                        if not context:
                            context = (
                                f"Generate a lesson illustration for the topic: {topic}. "
                                f"Grade level: {grade_level}. "
                                f"The content should be appropriate for Egyptian secondary school curriculum."
                            )

                        # Generate lesson illustration for this topic
                        illustration = await llm.generate_lesson_illustration(
                            context=context,
                            topic=topic,
                            language=language,
                            grade_level=grade_level,
                        )

                        if illustration:
                            all_illustrations.append(illustration)
                            logger.info(
                                f"[Orchestrator] Generated lesson illustration for topic: {topic}"
                            )

                    except Exception as e:
                        logger.error(f"[Orchestrator] Failed to generate lesson illustration for topic '{topic}': {e}")
                        continue

                logger.info(f"[Orchestrator] Total lesson illustrations generated: {len(all_illustrations)}")
                return all_illustrations

            except Exception as e:
                logger.error(f"[Orchestrator] Lesson illustrations generation failed: {e}")
                return []
        else:
            logger.warning(
                "[Orchestrator] No valid Gemini API key for lesson illustrations. Skipping."
            )
            return []

    async def _generate_illustration_content(self) -> list[dict]:
        """Generate lesson illustration content — DISABLED (legacy).

        This method previously retrieved raw OCR chunks from RAG and passed them
        to the DOCX generator, which produced garbled/corrupted text in the output.

        Replaced by _generate_lesson_illustrations() for study book mode.

        Returns:
            Empty list (illustration content generation is disabled).
        """
        logger.info(
            "[Orchestrator] Legacy illustration content generation is DISABLED. "
            "Use _generate_lesson_illustrations() for study book mode."
        )
        return []

    # ─── Exercise Distribution ─────────────────────────────────────────────────

    def _calculate_exercise_distribution(self) -> list[dict]:
        """Calculate how many exercises of each type/difficulty to generate.

        Uses a proper page budget:
        - Available content pages = target_pages - 1 (cover page)
        - Exercises per page based on density (spacious=2, standard=3, dense=5)
        - Total exercises = available_content_pages × exercises_per_page
        - Exercises distributed proportionally across topics (not round-robin)
        - Within each topic, split by exercise type ratios and difficulty ratios

        Returns:
            List of dicts: [{"type": str, "difficulty": str, "count": int, "topic": str}, ...]
        """
        total_pages = self.structure.get("total_pages", 20)
        layout_style = self.structure.get("layout_style", "standard")

        # ─── Page Budget Calculation ───────────────────────────────────────────
        # Subtract cover page
        available_content_pages = max(1, total_pages - 1)

        # Exercises per page based on density
        exercises_per_page = EXERCISES_PER_PAGE_BY_DENSITY.get(layout_style, 3)

        # Total exercise slots (in MCQ-equivalents)
        total_exercise_slots = available_content_pages * exercises_per_page

        # ─── Get exercise types and their ratios ───────────────────────────────
        exercise_types = self.exercise_config.get(
            "types", ["multiple_choice", "fill_blank", "show_work", "word_problems"]
        )
        if not exercise_types:
            exercise_types = ["show_work"]

        # ─── Get difficulty distribution (percentages) ─────────────────────────
        diff_easy = self.exercise_config.get("difficulty_easy", 40)
        diff_medium = self.exercise_config.get("difficulty_medium", 40)
        diff_hard = self.exercise_config.get("difficulty_hard", 20)
        total_pct = diff_easy + diff_medium + diff_hard
        if total_pct == 0:
            total_pct = 100
            diff_easy = diff_medium = diff_hard = 33

        # Normalize percentages
        easy_ratio = diff_easy / total_pct
        medium_ratio = diff_medium / total_pct
        hard_ratio = diff_hard / total_pct

        # ─── Get topic information ─────────────────────────────────────────────
        chapter_ids = self.scope.get("chapter_ids", [])
        topic_names = self._get_topic_names_from_scope()
        num_topics = max(1, len(topic_names))

        # ─── Calculate actual exercise count accounting for type weights ────────
        # If user specified per-type counts, use those directly
        exercises_per_type = self.exercise_config.get("exercises_per_type")

        distribution: list[dict] = []

        if exercises_per_type:
            # Use explicit per-type counts — distribute across topics proportionally
            for ex_type, count in exercises_per_type.items():
                if count <= 0:
                    continue

                # Distribute this type's exercises across topics
                per_topic = max(1, count // num_topics)
                remainder = count - (per_topic * num_topics)

                for t_idx, topic in enumerate(topic_names):
                    topic_count = per_topic + (1 if t_idx < remainder else 0)
                    if topic_count <= 0:
                        continue

                    # Split by difficulty
                    easy_count = max(1, round(topic_count * easy_ratio))
                    medium_count = max(1, round(topic_count * medium_ratio))
                    hard_count = max(0, topic_count - easy_count - medium_count)

                    # Get chapter_id for this topic
                    chapter_id = self._get_chapter_id_for_topic(topic, chapter_ids)

                    if easy_count > 0:
                        distribution.append(
                            {"type": ex_type, "difficulty": "easy", "count": easy_count,
                             "topic": topic, "chapter_id": chapter_id}
                        )
                    if medium_count > 0:
                        distribution.append(
                            {"type": ex_type, "difficulty": "medium", "count": medium_count,
                             "topic": topic, "chapter_id": chapter_id}
                        )
                    if hard_count > 0:
                        distribution.append(
                            {"type": ex_type, "difficulty": "hard", "count": hard_count,
                             "topic": topic, "chapter_id": chapter_id}
                        )
        else:
            # Auto-distribute: proportional across topics, even across types
            # Total exercises per topic
            exercises_per_topic = max(1, total_exercise_slots // num_topics)
            topic_remainder = total_exercise_slots - (exercises_per_topic * num_topics)

            for t_idx, topic in enumerate(topic_names):
                # This topic's total exercise count
                topic_total = exercises_per_topic + (1 if t_idx < topic_remainder else 0)

                # Distribute across exercise types evenly
                per_type = max(1, topic_total // len(exercise_types))
                type_remainder = topic_total - (per_type * len(exercise_types))

                # Get chapter_id for this topic
                chapter_id = self._get_chapter_id_for_topic(topic, chapter_ids)

                for type_idx, ex_type in enumerate(exercise_types):
                    type_count = per_type + (1 if type_idx < type_remainder else 0)
                    if type_count <= 0:
                        continue

                    # Adjust count for exercise type weight
                    # Heavier types (long_answer, show_work) take more page space
                    weight = EXERCISE_TYPE_WEIGHT.get(ex_type, 1.0)
                    adjusted_count = max(1, round(type_count / weight))

                    # Split by difficulty
                    easy_count = max(1, round(adjusted_count * easy_ratio))
                    medium_count = max(1, round(adjusted_count * medium_ratio))
                    hard_count = max(0, adjusted_count - easy_count - medium_count)

                    if easy_count > 0:
                        distribution.append(
                            {"type": ex_type, "difficulty": "easy", "count": easy_count,
                             "topic": topic, "chapter_id": chapter_id}
                        )
                    if medium_count > 0:
                        distribution.append(
                            {"type": ex_type, "difficulty": "medium", "count": medium_count,
                             "topic": topic, "chapter_id": chapter_id}
                        )
                    if hard_count > 0:
                        distribution.append(
                            {"type": ex_type, "difficulty": "hard", "count": hard_count,
                             "topic": topic, "chapter_id": chapter_id}
                        )

        logger.info(
            f"[Orchestrator] Distribution: {len(distribution)} batches, "
            f"total_slots={total_exercise_slots}, topics={num_topics}, "
            f"density={layout_style}"
        )

        return distribution

    def _get_chapter_id_for_topic(self, topic_name: str, chapter_ids: list[int]) -> Optional[int]:
        """Get the chapter_id associated with a topic name.

        Args:
            topic_name: The topic title string.
            chapter_ids: List of chapter IDs from scope.

        Returns:
            The chapter_id or None.
        """
        if not chapter_ids:
            return None

        try:
            from models.topic import Topic

            topic = (
                self.db.query(Topic)
                .filter(Topic.title == topic_name)
                .first()
            )
            if topic and topic.chapter_id in chapter_ids:
                return topic.chapter_id
        except Exception:
            pass

        # Default to first chapter
        return chapter_ids[0] if chapter_ids else None

    def _get_topic_names_from_scope(self) -> list[str]:
        """Extract topic names from the workbook scope configuration.

        Queries the database for topic/chapter titles based on scope IDs.
        Returns topics in curriculum order (by page number).

        Returns:
            List of topic name strings in curriculum order.
        """
        topic_ids = self.scope.get("topic_ids", [])
        chapter_ids = self.scope.get("chapter_ids", [])
        book_id = self.scope.get("book_id")

        if not book_id:
            return []

        topic_names: list[str] = []

        try:
            from models.topic import Topic
            from models.chapter import Chapter

            if topic_ids:
                topics = (
                    self.db.query(Topic)
                    .filter(Topic.id.in_(topic_ids))
                    .order_by(Topic.page_num)
                    .all()
                )
                topic_names = [t.title for t in topics if t.title]

            elif chapter_ids:
                chapters = (
                    self.db.query(Chapter)
                    .filter(Chapter.id.in_(chapter_ids))
                    .order_by(Chapter.chapter_num)
                    .all()
                )
                for chapter in chapters:
                    topics = (
                        self.db.query(Topic)
                        .filter(Topic.chapter_id == chapter.id)
                        .order_by(Topic.page_num)
                        .all()
                    )
                    topic_names.extend([t.title for t in topics if t.title])

                if not topic_names:
                    topic_names = [c.title for c in chapters if c.title]

        except Exception as e:
            logger.warning(f"Failed to get topic names from scope: {e}")

        return topic_names if topic_names else ["Mathematics"]

    # ─── Fallback Exercise Generators ─────────────────────────────────────────

    def _generate_fallback_exercises(self, distribution: list[dict]) -> list[dict]:
        """Generate placeholder exercises when LLM is unavailable.

        Language-aware: generates Arabic exercises for Arabic workbooks.
        """
        import random

        exercises: list[dict] = []
        language = self.formatting.get("language", "english")

        for batch in distribution:
            ex_type = batch["type"]
            difficulty = batch["difficulty"]
            count = batch["count"]
            topic = batch.get("topic", "General Mathematics")

            for i in range(count):
                if language in ("arabic", "bilingual"):
                    exercise = self._fallback_arabic(ex_type, i + 1, difficulty, topic)
                else:
                    exercise = self._fallback_english(ex_type, i + 1, difficulty, topic)

                exercise["type"] = ex_type
                exercise["difficulty"] = difficulty
                exercise["topic"] = topic
                exercises.append(exercise)

        return exercises

    def _fallback_arabic(self, ex_type: str, num: int, difficulty: str, topic: str) -> dict:
        """Generate Arabic fallback exercises with Egyptian context."""
        import random

        names = [
            "\u0623\u062d\u0645\u062f", "\u0641\u0627\u0637\u0645\u0629",
            "\u0645\u062d\u0645\u062f", "\u0646\u0648\u0631\u0627",
            "\u0639\u0644\u064a", "\u0633\u0627\u0631\u0629",
            "\u064a\u0648\u0633\u0641", "\u0645\u0631\u064a\u0645",
        ]

        if ex_type == "multiple_choice":
            return self._fallback_arabic_multiple_choice(num, difficulty)
        elif ex_type == "fill_blank":
            return self._fallback_arabic_fill_blank(num, difficulty)
        elif ex_type == "true_false":
            return self._fallback_arabic_true_false(num, difficulty)
        elif ex_type == "matching":
            return self._fallback_arabic_matching(num, difficulty)
        elif ex_type in ("word_problems", "word_problem"):
            return self._fallback_arabic_word_problem(num, difficulty, names)
        else:  # show_work
            return self._fallback_arabic_show_work(num, difficulty)

    def _fallback_arabic_multiple_choice(self, num: int, difficulty: str) -> dict:
        """Arabic multiple choice fallback."""
        import random

        if difficulty == "easy":
            a = random.randint(2, 15)
            b = random.randint(2, 15)
            answer = a + b
            question = f"\u0645\u0627 \u0646\u0627\u062a\u062c {a} + {b}\u061f"
        elif difficulty == "medium":
            a = random.randint(3, 12)
            b = random.randint(3, 12)
            answer = a * b
            question = f"\u0645\u0627 \u0646\u0627\u062a\u062c {a} \u00d7 {b}\u061f"
        else:
            a = random.randint(10, 30)
            b = random.randint(2, 9)
            answer = a * b
            question = f"\u0625\u0630\u0627 \u0643\u0627\u0646 {a} \u00d7 {b} = \u0633\u060c \u0641\u0645\u0627 \u0642\u064a\u0645\u0629 \u0633\u061f"

        options = [answer]
        while len(options) < 4:
            wrong = answer + random.randint(-5, 5)
            if wrong != answer and wrong > 0 and wrong not in options:
                options.append(wrong)
        random.shuffle(options)
        correct_idx = options.index(answer)

        return {
            "question": question,
            "options": [str(o) for o in options],
            "correct_answer": chr(65 + correct_idx),
            "hint": "",
        }

    def _fallback_arabic_fill_blank(self, num: int, difficulty: str) -> dict:
        """Arabic fill-in-the-blank fallback."""
        import random

        if difficulty == "easy":
            a = random.randint(1, 10)
            b = random.randint(1, 10)
            return {
                "question": f"{a} + {b} = _____",
                "correct_answer": str(a + b),
                "hint": "",
            }
        elif difficulty == "medium":
            a = random.randint(2, 9)
            b = random.randint(2, 9)
            return {
                "question": f"{a} \u00d7 _____ = {a * b}",
                "correct_answer": str(b),
                "hint": "",
            }
        else:
            a = random.randint(10, 50)
            b = random.randint(10, 50)
            return {
                "question": f"{a + b} \u2212 _____ = {a}",
                "correct_answer": str(b),
                "hint": "",
            }

    def _fallback_arabic_true_false(self, num: int, difficulty: str) -> dict:
        """Arabic true/false fallback."""
        import random

        statements = [
            ("\u0645\u062c\u0645\u0648\u0639 \u0623\u064a \u0639\u062f\u062f\u064a\u0646 \u0632\u0648\u062c\u064a\u064a\u0646 \u0647\u0648 \u0639\u062f\u062f \u0632\u0648\u062c\u064a", "true"),
            ("\u0627\u0644\u0645\u0631\u0628\u0639 \u0644\u0647 3 \u0623\u0636\u0644\u0627\u0639", "false"),
            ("\u062d\u0627\u0635\u0644 \u0636\u0631\u0628 \u0623\u064a \u0639\u062f\u062f \u0641\u064a \u0627\u0644\u0635\u0641\u0631 \u064a\u0633\u0627\u0648\u064a \u0627\u0644\u0635\u0641\u0631", "true"),
            ("\u062d\u0627\u0635\u0644 \u0636\u0631\u0628 \u0623\u064a \u0639\u062f\u062f \u0641\u064a 1 \u064a\u0633\u0627\u0648\u064a \u0646\u0641\u0633 \u0627\u0644\u0639\u062f\u062f", "true"),
            ("\u062c\u0645\u064a\u0639 \u0627\u0644\u0623\u0639\u062f\u0627\u062f \u0627\u0644\u0623\u0648\u0644\u064a\u0629 \u0641\u0631\u062f\u064a\u0629", "false"),
            ("\u0627\u0644\u0645\u062b\u0644\u062b \u0644\u0647 3 \u0632\u0648\u0627\u064a\u0627", "true"),
            ("5\u00b2 = 10", "false"),
            ("\u0627\u0644\u062c\u0630\u0631 \u0627\u0644\u062a\u0631\u0628\u064a\u0639\u064a \u0644\u0640 16 \u064a\u0633\u0627\u0648\u064a 4", "true"),
            ("\u0627\u0644\u062e\u0637\u0648\u0637 \u0627\u0644\u0645\u062a\u0648\u0627\u0632\u064a\u0629 \u0644\u0627 \u062a\u062a\u0642\u0627\u0637\u0639 \u0623\u0628\u062f\u0627\u064b", "true"),
            ("\u0627\u0644\u0645\u0633\u062a\u0637\u064a\u0644 \u0644\u0647 4 \u0623\u0636\u0644\u0627\u0639 \u0645\u062a\u0633\u0627\u0648\u064a\u0629", "false"),
        ]
        statement, answer = random.choice(statements)
        return {
            "question": statement,
            "correct_answer": answer,
            "hint": "",
        }

    def _fallback_arabic_matching(self, num: int, difficulty: str) -> dict:
        """Arabic matching fallback."""
        import random

        pairs = [
            ("2 \u00d7 3", "6"),
            ("5 + 7", "12"),
            ("10 \u2212 4", "6"),
            ("8 \u00f7 2", "4"),
            ("3\u00b2", "9"),
            ("\u221a25", "5"),
            ("4 \u00d7 4", "16"),
            ("15 \u2212 8", "7"),
        ]
        selected = random.sample(pairs, min(4, len(pairs)))
        left_items = [p[0] for p in selected]
        right_items = [p[1] for p in selected]
        random.shuffle(right_items)

        return {
            "question": "\u0635\u0644 \u0643\u0644 \u0639\u0645\u0644\u064a\u0629 \u0628\u0646\u0627\u062a\u062c\u0647\u0627:",
            "options": left_items,
            "correct_answer": ", ".join([p[1] for p in selected]),
            "hint": "",
        }

    def _fallback_arabic_word_problem(self, num: int, difficulty: str, names: list) -> dict:
        """Arabic word problem fallback with Egyptian context."""
        import random

        name = random.choice(names)

        if difficulty == "easy":
            a = random.randint(5, 20)
            b = random.randint(1, a - 1)
            items = random.choice([
                "\u0642\u0644\u0645\u0627\u064b", "\u0643\u062a\u0627\u0628\u0627\u064b",
                "\u062a\u0641\u0627\u062d\u0629", "\u0628\u0631\u062a\u0642\u0627\u0644\u0629",
            ])
            return {
                "question": (
                    f"\u0645\u0639 {name} {a} {items}\u060c "
                    f"\u0623\u0639\u0637\u0649 {b} \u0644\u0635\u062f\u064a\u0642\u0647. "
                    f"\u0643\u0645 \u0628\u0642\u064a \u0645\u0639 {name}\u061f"
                ),
                "correct_answer": str(a - b),
                "hint": "",
            }
        elif difficulty == "medium":
            price = random.randint(10, 50)
            qty = random.randint(3, 8)
            return {
                "question": (
                    f"\u062b\u0645\u0646 \u0627\u0644\u0643\u062a\u0627\u0628 \u0627\u0644\u0648\u0627\u062d\u062f "
                    f"{price} \u062c\u0646\u064a\u0647\u0627\u064b. "
                    f"\u0643\u0645 \u064a\u062f\u0641\u0639 {name} \u062b\u0645\u0646 {qty} \u0643\u062a\u0628\u061f"
                ),
                "correct_answer": str(price * qty),
                "hint": "",
            }
        else:
            length = random.randint(10, 30)
            width = random.randint(5, 15)
            return {
                "question": (
                    f"\u062d\u062f\u064a\u0642\u0629 \u0645\u0633\u062a\u0637\u064a\u0644\u0629 "
                    f"\u0627\u0644\u0634\u0643\u0644 \u0637\u0648\u0644\u0647\u0627 {length} \u0645 "
                    f"\u0648\u0639\u0631\u0636\u0647\u0627 {width} \u0645. \u0623\u0648\u062c\u062f:\n"
                    f"(\u0623) \u0645\u062d\u064a\u0637 \u0627\u0644\u062d\u062f\u064a\u0642\u0629\n"
                    f"(\u0628) \u0645\u0633\u0627\u062d\u0629 \u0627\u0644\u062d\u062f\u064a\u0642\u0629\n"
                    f"(\u062c) \u062a\u0643\u0644\u0641\u0629 \u0633\u064a\u0627\u062c\u0647\u0627 "
                    f"\u0625\u0630\u0627 \u0643\u0627\u0646 \u0633\u0639\u0631 \u0627\u0644\u0645\u062a\u0631 12 \u062c\u0646\u064a\u0647\u0627\u064b"
                ),
                "correct_answer": (
                    f"(\u0623) {2 * (length + width)} \u0645\u060c "
                    f"(\u0628) {length * width} \u0645\u00b2\u060c "
                    f"(\u062c) {2 * (length + width) * 12} \u062c\u0646\u064a\u0647\u0627\u064b"
                ),
                "hint": "",
            }

    def _fallback_arabic_show_work(self, num: int, difficulty: str) -> dict:
        """Arabic show-your-work fallback."""
        import random

        if difficulty == "easy":
            a = random.randint(10, 50)
            b = random.randint(10, 50)
            return {
                "question": f"\u0627\u062d\u0633\u0628 {a} + {b}. \u0623\u0638\u0647\u0631 \u062e\u0637\u0648\u0627\u062a \u0627\u0644\u062d\u0644.",
                "correct_answer": str(a + b),
                "hint": "",
            }
        elif difficulty == "medium":
            a = random.randint(12, 30)
            b = random.randint(3, 9)
            return {
                "question": f"\u0627\u062d\u0633\u0628 {a} \u00d7 {b}. \u0623\u0638\u0647\u0631 \u062c\u0645\u064a\u0639 \u0627\u0644\u062e\u0637\u0648\u0627\u062a.",
                "correct_answer": str(a * b),
                "hint": "",
            }
        else:
            a = random.randint(100, 500)
            b = random.randint(5, 15)
            return {
                "question": (
                    f"\u0627\u0642\u0633\u0645 {a} \u0639\u0644\u0649 {b}. "
                    f"\u0627\u0643\u062a\u0628 \u0627\u0644\u0646\u0627\u062a\u062c \u0639\u0644\u0649 "
                    f"\u0635\u0648\u0631\u0629 \u062e\u0627\u0631\u062c \u0627\u0644\u0642\u0633\u0645\u0629 "
                    f"\u0648\u0627\u0644\u0628\u0627\u0642\u064a. \u0623\u0638\u0647\u0631 \u062e\u0637\u0648\u0627\u062a \u0627\u0644\u062d\u0644."
                ),
                "correct_answer": f"\u0627\u0644\u062e\u0627\u0631\u062c: {a // b}\u060c \u0627\u0644\u0628\u0627\u0642\u064a: {a % b}",
                "hint": "",
            }

    def _fallback_english(self, ex_type: str, num: int, difficulty: str, topic: str) -> dict:
        """Generate English fallback exercises."""
        import random

        if ex_type == "multiple_choice":
            return self._fallback_english_multiple_choice(num, difficulty)
        elif ex_type == "fill_blank":
            return self._fallback_english_fill_blank(num, difficulty)
        elif ex_type == "true_false":
            return self._fallback_english_true_false(num, difficulty)
        elif ex_type == "matching":
            return self._fallback_english_matching(num, difficulty)
        elif ex_type in ("word_problems", "word_problem"):
            return self._fallback_english_word_problem(num, difficulty)
        else:  # show_work
            return self._fallback_english_show_work(num, difficulty)

    def _fallback_english_multiple_choice(self, num: int, difficulty: str) -> dict:
        """English multiple choice fallback."""
        import random

        if difficulty == "easy":
            a = random.randint(1, 20)
            b = random.randint(1, 20)
            answer = a + b
            question = f"What is {a} + {b}?"
        elif difficulty == "medium":
            a = random.randint(2, 12)
            b = random.randint(2, 12)
            answer = a * b
            question = f"What is {a} \u00d7 {b}?"
        else:
            a = random.randint(10, 50)
            b = random.randint(10, 50)
            answer = a * b
            question = f"What is {a} \u00d7 {b}?"

        options = [answer]
        while len(options) < 4:
            wrong = answer + random.randint(-5, 5)
            if wrong != answer and wrong > 0 and wrong not in options:
                options.append(wrong)
        random.shuffle(options)
        correct_idx = options.index(answer)

        return {
            "question": question,
            "options": [str(o) for o in options],
            "correct_answer": chr(65 + correct_idx),
            "hint": "",
        }

    def _fallback_english_fill_blank(self, num: int, difficulty: str) -> dict:
        """English fill-in-the-blank fallback."""
        import random

        if difficulty == "easy":
            a = random.randint(1, 10)
            b = random.randint(1, 10)
            return {
                "question": f"{a} + {b} = _____",
                "correct_answer": str(a + b),
                "hint": "",
            }
        elif difficulty == "medium":
            a = random.randint(2, 9)
            b = random.randint(2, 9)
            return {
                "question": f"{a} \u00d7 _____ = {a * b}",
                "correct_answer": str(b),
                "hint": "",
            }
        else:
            a = random.randint(10, 50)
            b = random.randint(10, 50)
            return {
                "question": f"{a + b} \u2212 _____ = {a}",
                "correct_answer": str(b),
                "hint": "",
            }

    def _fallback_english_true_false(self, num: int, difficulty: str) -> dict:
        """English true/false fallback."""
        import random

        statements = [
            ("The sum of two even numbers is always even.", "true"),
            ("A square has exactly 3 sides.", "false"),
            ("10 \u00d7 0 = 10", "false"),
            ("The product of any number and 1 is that number.", "true"),
            ("All prime numbers are odd.", "false"),
            ("A triangle has 3 angles.", "true"),
            ("5\u00b2 = 10", "false"),
            ("The square root of 16 is 4.", "true"),
            ("Parallel lines never intersect.", "true"),
            ("A rectangle has 4 equal sides.", "false"),
        ]
        statement, answer = random.choice(statements)
        return {
            "question": statement,
            "correct_answer": answer,
            "hint": "",
        }

    def _fallback_english_matching(self, num: int, difficulty: str) -> dict:
        """English matching fallback."""
        import random

        pairs = [
            ("2 \u00d7 3", "6"),
            ("5 + 7", "12"),
            ("10 \u2212 4", "6"),
            ("8 \u00f7 2", "4"),
            ("3\u00b2", "9"),
            ("\u221a25", "5"),
            ("4 \u00d7 4", "16"),
            ("15 \u2212 8", "7"),
        ]
        selected = random.sample(pairs, min(4, len(pairs)))
        left_items = [p[0] for p in selected]
        right_items = [p[1] for p in selected]
        random.shuffle(right_items)

        return {
            "question": "Match each expression with its value:",
            "options": left_items,
            "correct_answer": ", ".join([p[1] for p in selected]),
            "hint": "",
        }

    def _fallback_english_word_problem(self, num: int, difficulty: str) -> dict:
        """English word problem fallback."""
        import random

        if difficulty == "easy":
            items = random.choice(["apples", "books", "pencils", "marbles"])
            a = random.randint(5, 20)
            b = random.randint(1, a - 1)
            return {
                "question": (
                    f"Sarah has {a} {items}. She gives {b} to her friend. "
                    f"How many {items} does she have left?"
                ),
                "correct_answer": str(a - b),
                "hint": "",
            }
        elif difficulty == "medium":
            price = random.randint(3, 15)
            qty = random.randint(4, 12)
            change = random.randint(5, 20)
            total_money = price * qty + change
            return {
                "question": (
                    f"A notebook costs {price} LE. Ahmed wants to buy {qty} notebooks. "
                    f"How much money does he need? If he has {total_money} LE, "
                    f"how much change will he receive?"
                ),
                "correct_answer": f"Cost: {price * qty} LE, Change: {change} LE",
                "hint": "",
            }
        else:
            length = random.randint(10, 30)
            width = random.randint(5, 15)
            return {
                "question": (
                    f"A rectangular garden has a length of {length}m and a width of {width}m. "
                    f"Calculate: (a) the perimeter of the garden, "
                    f"(b) the area of the garden, "
                    f"(c) the cost of fencing at 12 LE per metre."
                ),
                "correct_answer": (
                    f"(a) {2 * (length + width)}m, "
                    f"(b) {length * width}m\u00b2, "
                    f"(c) {2 * (length + width) * 12} LE"
                ),
                "hint": "",
            }

    def _fallback_english_show_work(self, num: int, difficulty: str) -> dict:
        """English show-your-work fallback."""
        import random

        if difficulty == "easy":
            a = random.randint(10, 50)
            b = random.randint(10, 50)
            return {
                "question": f"Calculate {a} + {b}. Show your working.",
                "correct_answer": str(a + b),
                "hint": "",
            }
        elif difficulty == "medium":
            a = random.randint(12, 30)
            b = random.randint(3, 9)
            return {
                "question": f"Calculate {a} \u00d7 {b}. Show all steps.",
                "correct_answer": str(a * b),
                "hint": "",
            }
        else:
            a = random.randint(100, 500)
            b = random.randint(5, 15)
            return {
                "question": (
                    f"Divide {a} by {b}. Express your answer as a quotient "
                    f"and remainder. Show your working."
                ),
                "correct_answer": f"{a // b} remainder {a % b}",
                "hint": "",
            }
