"""Embedding and FAISS vector store service.

Uses paraphrase-multilingual-MiniLM-L12-v2 for Arabic+English bilingual support.
Stores chunk metadata as JSON sidecar alongside FAISS indices.
"""

import json
import logging
import shutil
from pathlib import Path
from typing import Optional, TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

# Default embedding dimension for paraphrase-multilingual-MiniLM-L12-v2
EMBEDDING_DIM = 384


class EmbeddingService:
    """Manages text embeddings and FAISS vector store per book.

    Uses a multilingual sentence-transformer model that supports Arabic,
    English, and mixed content natively.
    """

    def __init__(
        self,
        model_name: str = "paraphrase-multilingual-MiniLM-L12-v2",
        faiss_dir: str = "./data/faiss_indices",
    ) -> None:
        """Initialize the embedding service.

        Args:
            model_name: Name of the sentence-transformer model to use.
                        Default is multilingual model supporting 50+ languages.
            faiss_dir: Directory to store FAISS indices.
        """
        self.model_name = model_name
        self.faiss_dir = Path(faiss_dir)
        self.faiss_dir.mkdir(parents=True, exist_ok=True)
        self.model: Optional["SentenceTransformer"] = None
        self._faiss = None  # Lazy loaded

    def _load_model(self) -> None:
        """Lazy load the sentence-transformer model."""
        if self.model is None:
            try:
                from sentence_transformers import SentenceTransformer

                logger.info(f"Loading embedding model: {self.model_name}")
                self.model = SentenceTransformer(self.model_name)
                logger.info(
                    f"Model loaded. Embedding dimension: "
                    f"{self.model.get_sentence_embedding_dimension()}"
                )
            except ImportError:
                logger.error(
                    "sentence-transformers not installed. "
                    "Run: pip install sentence-transformers"
                )
                raise

    def _get_faiss(self):
        """Lazy load faiss."""
        if self._faiss is None:
            try:
                import faiss

                self._faiss = faiss
            except ImportError:
                logger.error("faiss-cpu not installed. Run: pip install faiss-cpu")
                raise
        return self._faiss

    def get_embedding_dim(self) -> int:
        """Return the embedding dimension of the current model.

        Returns:
            Integer dimension (384 for multilingual-MiniLM-L12-v2).
        """
        return EMBEDDING_DIM

    def embed_texts(self, texts: list[str]) -> np.ndarray:
        """Generate embeddings for a list of texts.

        Args:
            texts: List of text strings to embed.

        Returns:
            Numpy array of shape (len(texts), embedding_dim) with normalized embeddings.
        """
        self._load_model()

        embeddings = self.model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=len(texts) > 100,
            batch_size=64,
        )
        return np.array(embeddings, dtype=np.float32)

    def embed_batch(self, texts: list[str]) -> np.ndarray:
        """Bulk embedding method — alias for embed_texts with optimized batch size.

        Args:
            texts: List of text strings to embed.

        Returns:
            Numpy array of shape (len(texts), embedding_dim) with normalized embeddings.
        """
        self._load_model()

        embeddings = self.model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=len(texts) > 50,
            batch_size=128,
        )
        return np.array(embeddings, dtype=np.float32)

    def embed_query(self, query: str) -> np.ndarray:
        """Embed a single query string.

        Args:
            query: The search query text.

        Returns:
            Numpy array of shape (1, embedding_dim) with normalized embedding.
        """
        return self.embed_texts([query])

    def create_index(
        self, book_id: int, chunks: list, embeddings: np.ndarray
    ) -> None:
        """Create and save a FAISS index for a book with metadata sidecar.

        Args:
            book_id: The book's database ID.
            chunks: List of ContentChunk objects (from semantic_chunker).
            embeddings: Numpy array of embeddings corresponding to chunks.
        """
        if len(chunks) == 0:
            logger.warning(f"No chunks to index for book {book_id}")
            return

        faiss = self._get_faiss()

        # Get embedding dimension
        dim = embeddings.shape[1]

        # Create FAISS index using inner product (cosine similarity for normalized vectors)
        index = faiss.IndexFlatIP(dim)
        index.add(embeddings)

        # Create book index directory
        book_dir = self.faiss_dir / f"book_{book_id}"
        book_dir.mkdir(parents=True, exist_ok=True)

        # Save FAISS index
        index_path = book_dir / "index.faiss"
        faiss.write_index(index, str(index_path))

        # Save chunk metadata as JSON sidecar
        metadata = []
        for i, chunk in enumerate(chunks):
            # Support both ContentChunk dataclass and legacy dict-like objects
            if hasattr(chunk, "text"):
                meta_entry = {
                    "index": i,
                    "text": chunk.text,
                    "book_id": getattr(chunk, "book_id", book_id),
                    "chapter_id": getattr(chunk, "chapter_id", None),
                    "lesson_title": getattr(chunk, "lesson_title", None),
                    "unit_title": getattr(chunk, "unit_title", None),
                    "page_number": getattr(chunk, "page_number", None),
                    "content_type": getattr(chunk, "content_type", "explanation"),
                    "language": getattr(chunk, "language", "ar"),
                    "token_count": getattr(chunk, "token_count", 0),
                }
                # Legacy fields for backward compatibility
                if hasattr(chunk, "chunk_id"):
                    meta_entry["chunk_id"] = chunk.chunk_id
                if hasattr(chunk, "chapter_num"):
                    meta_entry["chapter_num"] = chunk.chapter_num
                if hasattr(chunk, "topic"):
                    meta_entry["topic"] = chunk.topic
                if hasattr(chunk, "difficulty"):
                    meta_entry["difficulty"] = chunk.difficulty
                if hasattr(chunk, "page_num"):
                    meta_entry["page_number"] = chunk.page_num
            else:
                # Fallback for dict-like chunks
                meta_entry = {
                    "index": i,
                    "text": str(chunk),
                }
            metadata.append(meta_entry)

        metadata_path = book_dir / "metadata.json"
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        logger.info(
            f"Created FAISS index for book {book_id}: "
            f"{len(chunks)} vectors, dim={dim}"
        )

    def search(
        self, book_id: int, query: str, top_k: int = 10
    ) -> list[dict]:
        """Search the FAISS index for a book and return top-k relevant chunks.

        Args:
            book_id: The book's database ID.
            query: Search query text.
            top_k: Number of results to return.

        Returns:
            List of dicts with chunk metadata and similarity scores.
        """
        faiss = self._get_faiss()

        book_dir = self.faiss_dir / f"book_{book_id}"
        index_path = book_dir / "index.faiss"
        metadata_path = book_dir / "metadata.json"

        if not index_path.exists():
            logger.warning(f"No FAISS index found for book {book_id}")
            return []

        # Load index
        index = faiss.read_index(str(index_path))

        # Load metadata
        with open(metadata_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)

        # Embed the query
        query_embedding = self.embed_texts([query])

        # Clamp top_k to available vectors
        actual_k = min(top_k, index.ntotal)
        if actual_k == 0:
            return []

        # Search
        scores, indices = index.search(query_embedding, actual_k)

        # Build results
        results: list[dict] = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0:
                continue  # FAISS returns -1 for empty slots
            if idx < len(metadata):
                chunk_meta = metadata[idx].copy()
                chunk_meta["score"] = float(score)
                results.append(chunk_meta)

        return results

    def search_with_embeddings(
        self, book_id: int, query_embedding: np.ndarray, top_k: int = 10
    ) -> tuple[np.ndarray, np.ndarray, list[dict]]:
        """Search using a pre-computed query embedding.

        Returns scores, indices, and metadata for use in hybrid search.

        Args:
            book_id: The book's database ID.
            query_embedding: Pre-computed query embedding (1, dim).
            top_k: Number of results to return.

        Returns:
            Tuple of (scores array, indices array, metadata list).
        """
        faiss = self._get_faiss()

        book_dir = self.faiss_dir / f"book_{book_id}"
        index_path = book_dir / "index.faiss"
        metadata_path = book_dir / "metadata.json"

        if not index_path.exists():
            logger.warning(f"No FAISS index found for book {book_id}")
            empty = np.array([[]], dtype=np.float32)
            return empty, np.array([[]], dtype=np.int64), []

        # Load index
        index = faiss.read_index(str(index_path))

        # Load metadata
        with open(metadata_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)

        # Clamp top_k to available vectors
        actual_k = min(top_k, index.ntotal)
        if actual_k == 0:
            empty = np.array([[]], dtype=np.float32)
            return empty, np.array([[]], dtype=np.int64), metadata

        # Search
        scores, indices = index.search(query_embedding, actual_k)

        return scores, indices, metadata

    def get_all_embeddings(self, book_id: int) -> Optional[np.ndarray]:
        """Retrieve all embeddings from a book's FAISS index.

        Useful for MMR diversity calculation.

        Args:
            book_id: The book's database ID.

        Returns:
            Numpy array of all embeddings, or None if index doesn't exist.
        """
        faiss = self._get_faiss()

        book_dir = self.faiss_dir / f"book_{book_id}"
        index_path = book_dir / "index.faiss"

        if not index_path.exists():
            return None

        index = faiss.read_index(str(index_path))
        n_vectors = index.ntotal

        if n_vectors == 0:
            return None

        # Reconstruct all vectors from the flat index
        all_embeddings = np.zeros((n_vectors, index.d), dtype=np.float32)
        for i in range(n_vectors):
            all_embeddings[i] = index.reconstruct(i)

        return all_embeddings

    def get_metadata(self, book_id: int) -> list[dict]:
        """Load metadata for a book's chunks.

        Args:
            book_id: The book's database ID.

        Returns:
            List of metadata dicts, or empty list if not found.
        """
        book_dir = self.faiss_dir / f"book_{book_id}"
        metadata_path = book_dir / "metadata.json"

        if not metadata_path.exists():
            return []

        with open(metadata_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def delete_index(self, book_id: int) -> None:
        """Delete a book's FAISS index and metadata.

        Args:
            book_id: The book's database ID.
        """
        book_dir = self.faiss_dir / f"book_{book_id}"
        if book_dir.exists():
            shutil.rmtree(book_dir)
            logger.info(f"Deleted FAISS index for book {book_id}")
        else:
            logger.warning(f"No FAISS index directory found for book {book_id}")

    def rebuild_index_from_metadata(self, book_id: int) -> bool:
        """Rebuild a FAISS index from stored metadata sidecar.

        Re-embeds all chunk texts and creates a fresh index.
        Useful after model changes.

        Args:
            book_id: The book's database ID.

        Returns:
            True if rebuild succeeded, False otherwise.
        """
        book_dir = self.faiss_dir / f"book_{book_id}"
        metadata_path = book_dir / "metadata.json"

        if not metadata_path.exists():
            logger.warning(f"No metadata found for book {book_id}, cannot rebuild")
            return False

        with open(metadata_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)

        if not metadata:
            logger.warning(f"Empty metadata for book {book_id}")
            return False

        # Extract texts and re-embed
        texts = [m.get("text", "") for m in metadata]
        texts = [t for t in texts if t.strip()]

        if not texts:
            logger.warning(f"No valid texts in metadata for book {book_id}")
            return False

        logger.info(f"Rebuilding index for book {book_id}: {len(texts)} chunks")
        embeddings = self.embed_batch(texts)

        faiss = self._get_faiss()
        dim = embeddings.shape[1]
        index = faiss.IndexFlatIP(dim)
        index.add(embeddings)

        # Save updated index
        index_path = book_dir / "index.faiss"
        faiss.write_index(index, str(index_path))

        logger.info(f"Rebuilt FAISS index for book {book_id}: {len(texts)} vectors")
        return True
