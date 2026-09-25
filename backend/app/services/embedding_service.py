"""Embedding service for generating dense vector representations locally."""

from typing import List
import chromadb.utils.embedding_functions as embedding_functions


class EmbeddingService:
    """Provides local embedding generation using ChromaDB's ONNX embedding model."""

    def __init__(self):
        # DefaultEmbeddingFunction uses all-MiniLM-L6-v2 ONNX model locally
        try:
            self.ef = embedding_functions.DefaultEmbeddingFunction()
        except Exception:
            self.ef = None

    def get_embedding_function(self):
        """Return the embedding function for ChromaDB collections."""
        return self.ef

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of texts."""
        if not texts:
            return []
        if self.ef is not None:
            return self.ef(texts)
        # Fallback if ONNX runtime is initializing
        return [[0.0] * 384 for _ in texts]

    def embed_query(self, query: str) -> List[float]:
        """Generate embedding for a single search query."""
        results = self.embed_documents([query])
        return results[0] if results else [0.0] * 384


embedding_service = EmbeddingService()
