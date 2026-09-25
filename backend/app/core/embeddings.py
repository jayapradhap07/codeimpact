"""Embedding generation engine.

Generates vector embeddings for code chunks using sentence-transformers,
with an ultra-fast deterministic n-gram feature hashing fallback.
"""

from __future__ import annotations

import hashlib
import re
from typing import List, Optional

import numpy as np
from loguru import logger

from app.config import settings
from app.models.schemas import CodeChunk


class EmbeddingEngine:
    """Generates embeddings for code chunks (sentence-transformers or fast hashing fallback)."""

    def __init__(self, model_name: Optional[str] = None) -> None:
        self.model_name = model_name or settings.embedding_model
        self._model = None
        self._fallback_mode = False
        self._dimension = 384

    @property
    def model(self):
        """Lazy-load the embedding model with graceful fallback."""
        if self._model is None and not self._fallback_mode:
            try:
                from sentence_transformers import SentenceTransformer
                logger.info(f"Loading embedding model: {self.model_name}...")
                self._model = SentenceTransformer(self.model_name)
                self._dimension = self._model.get_sentence_embedding_dimension()
                logger.info(f"Embedding model loaded. Dimension: {self._dimension}")
            except Exception as e:
                logger.warning(
                    f"SentenceTransformer not available ({e}). "
                    "Using fast deterministic vector hashing fallback."
                )
                self._fallback_mode = True
        return self._model

    @property
    def dimension(self) -> int:
        """Get the embedding dimension."""
        _ = self.model
        return self._dimension

    def embed_chunks(self, chunks: List[CodeChunk], batch_size: int = 64) -> np.ndarray:
        """Encode a list of code chunks into embeddings."""
        if not chunks:
            return np.array([], dtype=np.float32).reshape(0, self.dimension)

        texts = [self._chunk_to_text(chunk) for chunk in chunks]

        if self.model is not None and not self._fallback_mode:
            try:
                embeddings = self.model.encode(
                    texts,
                    batch_size=batch_size,
                    show_progress_bar=len(texts) > 100,
                    normalize_embeddings=True,
                )
                return np.array(embeddings, dtype=np.float32)
            except Exception as e:
                logger.warning(f"SentenceTransformer encode failed: {e}. Falling back to hash vectors.")
                self._fallback_mode = True

        # Ultra-fast deterministic hashing vectors
        return self._hash_embeddings(texts)

    def embed_query(self, query: str) -> np.ndarray:
        """Encode a search query into an embedding vector."""
        if self.model is not None and not self._fallback_mode:
            try:
                embedding = self.model.encode([query], normalize_embeddings=True)
                return np.array(embedding, dtype=np.float32)
            except Exception:
                self._fallback_mode = True

        return self._hash_embeddings([query])

    def embed_text(self, text: str) -> np.ndarray:
        """Encode arbitrary text into an embedding vector."""
        return self.embed_query(text)

    def _hash_embeddings(self, texts: List[str]) -> np.ndarray:
        """Generate high-dimensional normalized n-gram hashed embeddings quickly."""
        dim = self._dimension
        matrix = np.zeros((len(texts), dim), dtype=np.float32)

        for row_idx, text in enumerate(texts):
            # Tokenize words and 3-grams
            words = re.findall(r"\w+", text.lower())
            if not words:
                matrix[row_idx, 0] = 1.0
                continue

            vec = np.zeros(dim, dtype=np.float32)
            for w in words:
                # Word hash
                h = int(hashlib.md5(w.encode("utf-8")).hexdigest(), 16)
                idx = h % dim
                sign = 1.0 if (h >> 8) % 2 == 0 else -1.0
                vec[idx] += sign

                # Character sub-ngrams
                for n in range(3, min(len(w) + 1, 6)):
                    for i in range(len(w) - n + 1):
                        sub = w[i:i + n]
                        h_sub = int(hashlib.md5(sub.encode("utf-8")).hexdigest(), 16)
                        vec[h_sub % dim] += 0.5

            norm = np.linalg.norm(vec)
            if norm > 0:
                matrix[row_idx] = vec / norm
            else:
                matrix[row_idx, 0] = 1.0

        return matrix

    # ──────────────────────────────────────────
    # Text representation
    # ──────────────────────────────────────────

    @staticmethod
    def _chunk_to_text(chunk: CodeChunk) -> str:
        """Convert a code chunk to a text representation for embedding."""
        parts = []
        header = f"{chunk.chunk_type.value}: {chunk.name}"
        if chunk.language:
            header += f" ({chunk.language})"
        parts.append(header)

        docstring = chunk.metadata.get("docstring")
        if docstring:
            parts.append(f"Description: {docstring}")

        params = chunk.metadata.get("parameters")
        if params:
            parts.append(f"Parameters: {', '.join(params)}")

        filename = chunk.file_path.split("/")[-1].split("\\")[-1]
        parts.append(f"File: {filename}")
        parts.append(f"Code:\n{chunk.content}")

        return "\n".join(parts)
