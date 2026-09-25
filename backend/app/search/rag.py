"""RAG (Retrieval-Augmented Generation) search engine.

Combines semantic vector search with context augmentation for
retrieving relevant code and documentation.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from loguru import logger

from app.core.embeddings import EmbeddingEngine
from app.models.schemas import CodeChunk, SearchResult
from app.search.vector_store import VectorStore


class RAGEngine:
    """RAG engine combining semantic search with context augmentation."""

    def __init__(
        self,
        vector_store: VectorStore,
        embedding_engine: EmbeddingEngine,
        file_contents: Optional[Dict[str, str]] = None,
    ) -> None:
        self.vector_store = vector_store
        self.embedding_engine = embedding_engine
        self._file_contents = file_contents or {}

    def search(
        self, query: str, k: int = 10
    ) -> List[SearchResult]:
        """Perform semantic search for code chunks matching the query.

        Args:
            query: Natural language query.
            k: Number of results.

        Returns:
            List of SearchResult ordered by relevance.
        """
        if self.vector_store.total_vectors == 0:
            logger.warning("Vector store is empty")
            return []

        query_embedding = self.embedding_engine.embed_query(query)
        results = self.vector_store.search(query_embedding, k=k)

        # Re-label source
        for r in results:
            r.source = "rag"

        return results

    def search_with_context(
        self, query: str, k: int = 10, context_lines: int = 10
    ) -> List[SearchResult]:
        """Semantic search with expanded code context.

        Each result includes surrounding lines from the source file
        for better understanding.

        Args:
            query: Natural language query.
            k: Number of results.
            context_lines: Number of context lines to include above/below.

        Returns:
            List of SearchResult with augmented context.
        """
        results = self.search(query, k=k)

        # Augment results with file context
        augmented: List[SearchResult] = []
        for result in results:
            chunk = result.chunk
            file_content = self._file_contents.get(chunk.file_path)

            if file_content:
                lines = file_content.split("\n")
                start = max(0, chunk.start_line - 1 - context_lines)
                end = min(len(lines), chunk.end_line + context_lines)
                expanded_content = "\n".join(lines[start:end])

                augmented_chunk = chunk.model_copy(
                    update={
                        "content": expanded_content,
                        "start_line": start + 1,
                        "end_line": end,
                    }
                )
                augmented.append(
                    SearchResult(
                        chunk=augmented_chunk,
                        score=result.score,
                        source="rag",
                    )
                )
            else:
                augmented.append(result)

        return augmented

    def search_similar_code(
        self, code_snippet: str, k: int = 5
    ) -> List[SearchResult]:
        """Find code similar to a given snippet.

        Args:
            code_snippet: Code to find similar matches for.
            k: Number of results.

        Returns:
            List of similar code chunks.
        """
        return self.search(f"Code:\n{code_snippet}", k=k)
