"""FAISS-based vector store for semantic code search with NumPy fallback.

Stores code chunk embeddings and supports fast nearest-neighbor retrieval.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
from loguru import logger

from app.models.schemas import CodeChunk, SearchResult

try:
    import faiss
    HAS_FAISS = True
except ImportError:
    HAS_FAISS = False
    logger.info("FAISS not installed, using high-performance NumPy cosine similarity fallback.")


class VectorStore:
    """Vector store for code chunk embeddings (supports FAISS & NumPy)."""

    def __init__(self, dimension: int = 384) -> None:
        self.dimension = dimension
        self.index = None
        self._embeddings: Optional[np.ndarray] = None
        self._chunks: List[CodeChunk] = []
        self._id_to_idx: Dict[str, int] = {}

    def build_index(
        self,
        embeddings: np.ndarray,
        chunks: List[CodeChunk],
    ) -> None:
        """Build an index from embeddings.

        Uses IndexFlatIP (Inner Product) with L2-normalized vectors
        for cosine similarity search, or NumPy dot product.

        Args:
            embeddings: Normalized embedding matrix (N, D).
            chunks: Corresponding code chunks.
        """
        if len(embeddings) == 0:
            logger.warning("No embeddings to index")
            return

        assert embeddings.shape[0] == len(chunks), (
            f"Embedding count ({embeddings.shape[0]}) != chunk count ({len(chunks)})"
        )

        self.dimension = embeddings.shape[1]
        self._embeddings = np.ascontiguousarray(embeddings, dtype=np.float32)

        if HAS_FAISS:
            self.index = faiss.IndexFlatIP(self.dimension)
            self.index.add(self._embeddings)

        self._chunks = list(chunks)
        self._id_to_idx = {chunk.id: i for i, chunk in enumerate(chunks)}

        logger.info(
            f"Vector index built: {len(self._chunks)} vectors, "
            f"dimension={self.dimension}, backend={'faiss' if HAS_FAISS else 'numpy'}"
        )

    def search(
        self,
        query_embedding: np.ndarray,
        k: int = 10,
    ) -> List[SearchResult]:
        """Search for the top-k most similar code chunks.

        Args:
            query_embedding: Query vector (1, D), L2-normalized.
            k: Number of results to return.

        Returns:
            List of SearchResult ordered by similarity score.
        """
        if len(self._chunks) == 0 or self._embeddings is None:
            return []

        k = min(k, len(self._chunks))

        if HAS_FAISS and self.index is not None:
            scores, indices = self.index.search(query_embedding, k)
            matched_scores = scores[0]
            matched_indices = indices[0]
        else:
            # NumPy cosine similarity fallback
            q = query_embedding.reshape(1, -1)
            # Both q and self._embeddings are L2 normalized
            sims = np.dot(self._embeddings, q.T).flatten()
            matched_indices = np.argsort(sims)[::-1][:k]
            matched_scores = sims[matched_indices]

        results: List[SearchResult] = []
        for score, idx in zip(matched_scores, matched_indices):
            if idx < 0 or idx >= len(self._chunks):
                continue
            results.append(
                SearchResult(
                    chunk=self._chunks[idx],
                    score=float(score),
                    source="vector",
                )
            )

        return results

    def get_chunk_by_id(self, chunk_id: str) -> Optional[CodeChunk]:
        """Retrieve a chunk by its ID."""
        idx = self._id_to_idx.get(chunk_id)
        if idx is not None and idx < len(self._chunks):
            return self._chunks[idx]
        return None

    @property
    def total_vectors(self) -> int:
        """Number of vectors in the index."""
        return len(self._chunks)

    # ──────────────────────────────────────────
    # Persistence
    # ──────────────────────────────────────────

    def save(self, directory: str) -> None:
        """Save the index and chunk metadata to disk."""
        dir_path = Path(directory)
        dir_path.mkdir(parents=True, exist_ok=True)

        if HAS_FAISS and self.index is not None:
            faiss.write_index(self.index, str(dir_path / "index.faiss"))
        elif self._embeddings is not None:
            np.save(str(dir_path / "embeddings.npy"), self._embeddings)

        chunks_data = [c.model_dump() for c in self._chunks]
        with open(dir_path / "chunks.json", "w", encoding="utf-8") as f:
            json.dump(chunks_data, f, default=str)

        logger.info(f"Vector store saved to {directory}")

    def load(self, directory: str) -> None:
        """Load the index and chunk metadata from disk."""
        dir_path = Path(directory)
        index_path = dir_path / "index.faiss"
        emb_path = dir_path / "embeddings.npy"
        chunks_path = dir_path / "chunks.json"

        if not chunks_path.exists():
            raise FileNotFoundError(f"Vector store metadata not found: {chunks_path}")

        with open(chunks_path, "r", encoding="utf-8") as f:
            chunks_data = json.load(f)

        self._chunks = [CodeChunk(**c) for c in chunks_data]
        self._id_to_idx = {chunk.id: i for i, chunk in enumerate(self._chunks)}

        if HAS_FAISS and index_path.exists():
            self.index = faiss.read_index(str(index_path))
            self.dimension = self.index.d
        elif emb_path.exists():
            self._embeddings = np.load(str(emb_path))
            self.dimension = self._embeddings.shape[1]

        logger.info(
            f"Vector store loaded: {len(self._chunks)} vectors from {directory}"
        )
