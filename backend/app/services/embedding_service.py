"""Embedding service for generating dense vector representations."""

import chromadb.utils.embedding_functions as embedding_functions


class EmbeddingService:
    """Provides local embedding generation using ChromaDB's default ONNX embedding function."""

    def __init__(self):
        try:
            self.ef = embedding_functions.DefaultEmbeddingFunction()
        except Exception:
            self.ef = None

    def get_embedding_function(self):
        """Return the embedding function for ChromaDB collections."""
        return self.ef


embedding_service = EmbeddingService()
