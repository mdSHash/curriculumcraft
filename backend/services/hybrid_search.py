"""Hybrid search service combining semantic (FAISS) and keyword (BM25) retrieval.

Implements:
- BM25 keyword search via rank_bm25
- Reciprocal Rank Fusion (RRF) to merge semantic and keyword results
- Metadata pre-filtering before search
- Maximal Marginal Relevance (MMR) for diversity
"""

import logging
import pickle
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


class HybridSearch:
    """Combines semantic vector search with BM25 keyword search.

    Uses Reciprocal Rank Fusion (RRF) to merge results from both
    retrieval methods, with MMR for diversity in final ranking.
    """

    def __init__(
        self,
        embedding_service,
        faiss_dir: str = "./data/faiss_indices",
        semantic_weight: float = 0.6,
        mmr_lambda: float = 0.7,
    ) -> None:
        """Initialize hybrid search.

        Args:
            embedding_service: The EmbeddingService instance for vector search.
            faiss_dir: Directory where FAISS and BM25 indices are stored.
            semantic_weight: Weight for semantic results in RRF (0-1).
                            Keyword weight = 1 - semantic_weight.
            mmr_lambda: Lambda parameter for MMR diversity.
                       1.0 = pure relevance, 0.0 = pure diversity.
        """
        self.embedding_service = embedding_service
        self.faiss_dir = Path(faiss_dir)
        self.semantic_weight = semantic_weight
        self.mmr_lambda = mmr_lambda

    def search(
        self,
        book_id: int,
        query: str,
        top_k: int = 15,
        filters: Optional[dict] = None,
    ) -> list[dict]:
        """Execute hybrid search combining semantic and keyword retrieval.

        Args:
            book_id: The book's database ID.
            query: Search query text.
            top_k: Number of final results to return.
            filters: Optional metadata filters:
                     {"chapter_id": int, "lesson_title": str, "content_type": str}

        Returns:
            List of result dicts with text, score, and metadata.
        """
        # Load metadata for filtering
        metadata = self.embedding_service.get_metadata(book_id)
        if not metadata:
            logger.warning(f"No metadata found for book {book_id}")
            return []

        # Apply metadata pre-filtering
        if filters:
            filtered_indices = self._apply_metadata_filters(metadata, filters)
        else:
            filtered_indices = list(range(len(metadata)))

        if not filtered_indices:
            logger.debug(f"No chunks match filters for book {book_id}: {filters}")
            return []

        # Retrieve more candidates than needed for RRF merging
        candidate_k = min(top_k * 3, len(filtered_indices))

        # Semantic search
        semantic_results = self._semantic_search(
            book_id, query, candidate_k, filtered_indices, metadata
        )

        # BM25 keyword search
        keyword_results = self._keyword_search(
            book_id, query, candidate_k, filtered_indices, metadata
        )

        # Merge with Reciprocal Rank Fusion
        merged_results = self._reciprocal_rank_fusion(
            semantic_results, keyword_results
        )

        # Apply MMR for diversity
        if len(merged_results) > top_k:
            merged_results = self._apply_mmr(
                book_id, query, merged_results, top_k
            )
        else:
            merged_results = merged_results[:top_k]

        logger.debug(
            f"Hybrid search for book {book_id}: "
            f"{len(semantic_results)} semantic + {len(keyword_results)} keyword "
            f"→ {len(merged_results)} final results"
        )

        return merged_results

    def build_bm25_index(self, book_id: int, metadata: list[dict]) -> None:
        """Build and save a BM25 index for a book.

        Args:
            book_id: The book's database ID.
            metadata: List of chunk metadata dicts (must have 'text' field).
        """
        from rank_bm25 import BM25Okapi

        # Tokenize all documents
        corpus = []
        for meta in metadata:
            text = meta.get("text", "")
            tokens = self._tokenize(text)
            corpus.append(tokens)

        if not corpus:
            logger.warning(f"No documents to build BM25 index for book {book_id}")
            return

        # Build BM25 index
        bm25 = BM25Okapi(corpus)

        # Save to disk
        book_dir = self.faiss_dir / f"book_{book_id}"
        book_dir.mkdir(parents=True, exist_ok=True)
        bm25_path = book_dir / "bm25_index.pkl"

        with open(bm25_path, "wb") as f:
            pickle.dump({"bm25": bm25, "corpus": corpus}, f)

        logger.info(
            f"Built BM25 index for book {book_id}: {len(corpus)} documents"
        )

    def _semantic_search(
        self,
        book_id: int,
        query: str,
        top_k: int,
        filtered_indices: list[int],
        metadata: list[dict],
    ) -> list[dict]:
        """Execute semantic (vector) search with pre-filtering.

        Args:
            book_id: The book's database ID.
            query: Search query text.
            top_k: Number of results to retrieve.
            filtered_indices: Indices that pass metadata filters.
            metadata: Full metadata list.

        Returns:
            List of result dicts sorted by semantic score.
        """
        # Embed query
        query_embedding = self.embedding_service.embed_query(query)

        # Search FAISS (retrieve more to account for filtering)
        scores, indices, _ = self.embedding_service.search_with_embeddings(
            book_id, query_embedding, top_k=min(top_k * 2, len(metadata))
        )

        if scores.size == 0 or indices.size == 0:
            return []

        # Filter results to only include allowed indices
        filtered_set = set(filtered_indices)
        results: list[dict] = []

        for score, idx in zip(scores[0], indices[0]):
            if idx < 0:
                continue
            if int(idx) not in filtered_set:
                continue
            if int(idx) >= len(metadata):
                continue

            result = metadata[int(idx)].copy()
            result["score"] = float(score)
            result["_faiss_index"] = int(idx)
            results.append(result)

            if len(results) >= top_k:
                break

        return results

    def _keyword_search(
        self,
        book_id: int,
        query: str,
        top_k: int,
        filtered_indices: list[int],
        metadata: list[dict],
    ) -> list[dict]:
        """Execute BM25 keyword search.

        Falls back gracefully if BM25 index doesn't exist.

        Args:
            book_id: The book's database ID.
            query: Search query text.
            top_k: Number of results to retrieve.
            filtered_indices: Indices that pass metadata filters.
            metadata: Full metadata list.

        Returns:
            List of result dicts sorted by BM25 score.
        """
        book_dir = self.faiss_dir / f"book_{book_id}"
        bm25_path = book_dir / "bm25_index.pkl"

        if not bm25_path.exists():
            logger.debug(
                f"No BM25 index for book {book_id}, skipping keyword search"
            )
            return []

        try:
            with open(bm25_path, "rb") as f:
                bm25_data = pickle.load(f)

            bm25 = bm25_data["bm25"]
        except Exception as e:
            logger.warning(f"Failed to load BM25 index for book {book_id}: {e}")
            return []

        # Tokenize query
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        # Get BM25 scores for all documents
        scores = bm25.get_scores(query_tokens)

        # Filter to allowed indices and sort by score
        filtered_set = set(filtered_indices)
        scored_indices = [
            (float(scores[i]), i)
            for i in filtered_indices
            if i < len(scores) and scores[i] > 0
        ]
        scored_indices.sort(reverse=True, key=lambda x: x[0])

        # Build results
        results: list[dict] = []
        for score, idx in scored_indices[:top_k]:
            if idx >= len(metadata):
                continue
            result = metadata[idx].copy()
            result["score"] = score
            result["_faiss_index"] = idx
            results.append(result)

        return results

    def _reciprocal_rank_fusion(
        self,
        semantic_results: list[dict],
        keyword_results: list[dict],
        k: int = 60,
    ) -> list[dict]:
        """Merge semantic and keyword results using Reciprocal Rank Fusion.

        RRF score = sum(1 / (k + rank_i)) for each retrieval method.

        Args:
            semantic_results: Results from semantic search.
            keyword_results: Results from keyword search.
            k: RRF constant (default 60, standard in literature).

        Returns:
            Merged and re-ranked results.
        """
        # Build score map keyed by FAISS index
        rrf_scores: dict[int, float] = {}
        result_map: dict[int, dict] = {}

        # Score semantic results
        for rank, result in enumerate(semantic_results):
            idx = result.get("_faiss_index", result.get("index", rank))
            rrf_score = self.semantic_weight * (1.0 / (k + rank + 1))
            rrf_scores[idx] = rrf_scores.get(idx, 0) + rrf_score
            result_map[idx] = result

        # Score keyword results
        keyword_weight = 1.0 - self.semantic_weight
        for rank, result in enumerate(keyword_results):
            idx = result.get("_faiss_index", result.get("index", rank))
            rrf_score = keyword_weight * (1.0 / (k + rank + 1))
            rrf_scores[idx] = rrf_scores.get(idx, 0) + rrf_score
            if idx not in result_map:
                result_map[idx] = result

        # Sort by RRF score
        sorted_indices = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)

        # Build final results
        merged: list[dict] = []
        for idx in sorted_indices:
            result = result_map[idx].copy()
            result["rrf_score"] = rrf_scores[idx]
            result["score"] = rrf_scores[idx]
            merged.append(result)

        return merged

    def _apply_mmr(
        self,
        book_id: int,
        query: str,
        candidates: list[dict],
        top_k: int,
    ) -> list[dict]:
        """Apply Maximal Marginal Relevance for diversity.

        MMR = λ * sim(q, d) - (1-λ) * max(sim(d, d_selected))

        Args:
            book_id: The book's database ID.
            query: Original query text.
            candidates: Candidate results to re-rank.
            top_k: Number of results to select.

        Returns:
            Diverse subset of candidates.
        """
        if len(candidates) <= top_k:
            return candidates

        # Get embeddings for MMR calculation
        all_embeddings = self.embedding_service.get_all_embeddings(book_id)
        if all_embeddings is None:
            # Fall back to simple truncation
            return candidates[:top_k]

        query_embedding = self.embedding_service.embed_query(query)

        # Get candidate embeddings
        candidate_indices = []
        for c in candidates:
            idx = c.get("_faiss_index", c.get("index", -1))
            if 0 <= idx < len(all_embeddings):
                candidate_indices.append(idx)
            else:
                candidate_indices.append(-1)

        # MMR selection
        selected: list[int] = []  # indices into candidates list
        remaining = list(range(len(candidates)))

        for _ in range(top_k):
            if not remaining:
                break

            best_score = -float("inf")
            best_idx = remaining[0]

            for cand_pos in remaining:
                faiss_idx = candidate_indices[cand_pos]
                if faiss_idx < 0:
                    # Can't compute MMR, use RRF score
                    relevance = candidates[cand_pos].get("score", 0)
                    redundancy = 0
                else:
                    # Relevance: similarity to query
                    cand_emb = all_embeddings[faiss_idx].reshape(1, -1)
                    relevance = float(np.dot(query_embedding, cand_emb.T)[0, 0])

                    # Redundancy: max similarity to already selected
                    redundancy = 0.0
                    for sel_pos in selected:
                        sel_faiss_idx = candidate_indices[sel_pos]
                        if sel_faiss_idx < 0:
                            continue
                        sel_emb = all_embeddings[sel_faiss_idx].reshape(1, -1)
                        sim = float(np.dot(cand_emb, sel_emb.T)[0, 0])
                        redundancy = max(redundancy, sim)

                # MMR score
                mmr_score = (
                    self.mmr_lambda * relevance
                    - (1 - self.mmr_lambda) * redundancy
                )

                if mmr_score > best_score:
                    best_score = mmr_score
                    best_idx = cand_pos

            selected.append(best_idx)
            remaining.remove(best_idx)

        # Return selected candidates in MMR order
        return [candidates[i] for i in selected]

    def _apply_metadata_filters(
        self, metadata: list[dict], filters: dict
    ) -> list[int]:
        """Filter metadata indices by the given filter criteria.

        Args:
            metadata: Full metadata list.
            filters: Dict of filter criteria.

        Returns:
            List of indices that pass all filters.
        """
        passing_indices: list[int] = []

        for i, meta in enumerate(metadata):
            passes = True

            if "chapter_id" in filters and filters["chapter_id"] is not None:
                if meta.get("chapter_id") != filters["chapter_id"]:
                    passes = False

            if "lesson_title" in filters and filters["lesson_title"] is not None:
                meta_lesson = (meta.get("lesson_title") or "").lower()
                filter_lesson = filters["lesson_title"].lower()
                if filter_lesson not in meta_lesson and meta_lesson not in filter_lesson:
                    passes = False

            if "content_type" in filters and filters["content_type"] is not None:
                if meta.get("content_type") != filters["content_type"]:
                    passes = False

            if "language" in filters and filters["language"] is not None:
                if meta.get("language") != filters["language"]:
                    passes = False

            if "page_number" in filters and filters["page_number"] is not None:
                meta_page = meta.get("page_number")
                if meta_page is not None and meta_page != filters["page_number"]:
                    passes = False

            if passes:
                passing_indices.append(i)

        return passing_indices

    def _tokenize(self, text: str) -> list[str]:
        """Tokenize text for BM25 indexing.

        Handles Arabic and English text with basic normalization.

        Args:
            text: Input text to tokenize.

        Returns:
            List of token strings.
        """
        import re

        if not text:
            return []

        # Normalize Arabic characters
        text = text.replace("\u0640", "")  # Remove tatweel
        # Remove diacritics (tashkeel)
        text = re.sub(r"[\u064B-\u065F\u0670]", "", text)

        # Split on whitespace and punctuation (keep alphanumeric + Arabic)
        tokens = re.findall(r"[\w\u0600-\u06FF]+", text.lower())

        # Remove very short tokens (single chars except Arabic)
        tokens = [
            t for t in tokens
            if len(t) > 1 or any("\u0600" <= c <= "\u06FF" for c in t)
        ]

        return tokens
