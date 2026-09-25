"""API dependency injection."""

from __future__ import annotations

from typing import Dict, Optional

from app.agent.impact_agent import ImpactAgent
from app.core.embeddings import EmbeddingEngine
from app.graph.knowledge_graph import CodeKnowledgeGraph
from app.search.code_search import CodeSearchEngine
from app.search.rag import RAGEngine
from app.search.vector_store import VectorStore


class AppState:
    """Holds application-wide state (loaded models, indexes, graphs)."""

    def __init__(self) -> None:
        self.repositories: Dict[int, dict] = {}  # repo_id -> repo metadata
        self.graphs: Dict[int, CodeKnowledgeGraph] = {}
        self.vector_stores: Dict[int, VectorStore] = {}
        self.embedding_engine: Optional[EmbeddingEngine] = None
        self.file_contents: Dict[int, Dict[str, str]] = {}  # repo_id -> {file_path: content}

    def get_graph(self, repo_id: int) -> Optional[CodeKnowledgeGraph]:
        return self.graphs.get(repo_id)

    def get_vector_store(self, repo_id: int) -> Optional[VectorStore]:
        return self.vector_stores.get(repo_id)

    def get_embedding_engine(self) -> EmbeddingEngine:
        if self.embedding_engine is None:
            self.embedding_engine = EmbeddingEngine()
        return self.embedding_engine

    def get_rag_engine(self, repo_id: int) -> Optional[RAGEngine]:
        vs = self.get_vector_store(repo_id)
        if vs is None:
            return None
        return RAGEngine(
            vector_store=vs,
            embedding_engine=self.get_embedding_engine(),
            file_contents=self.file_contents.get(repo_id, {}),
        )

    def get_code_search(self, repo_id: int) -> Optional[CodeSearchEngine]:
        graph = self.get_graph(repo_id)
        if graph is None:
            return None
        return CodeSearchEngine(
            knowledge_graph=graph,
            file_contents=self.file_contents.get(repo_id, {}),
        )

    def get_impact_agent(self, repo_id: int) -> Optional[ImpactAgent]:
        graph = self.get_graph(repo_id)
        rag = self.get_rag_engine(repo_id)
        code_search = self.get_code_search(repo_id)

        if not graph or not rag or not code_search:
            return None

        return ImpactAgent(
            knowledge_graph=graph,
            rag_engine=rag,
            code_search=code_search,
        )


# Global application state
app_state = AppState()
