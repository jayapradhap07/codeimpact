"""RAG Service for ChromaDB indexing, similarity retrieval, and context building."""

from typing import List, Dict, Any, Optional
import chromadb
from loguru import logger

from app.config import settings
from app.services.embedding_service import embedding_service


class RAGService:
    """Manages vector storage and similarity retrieval using ChromaDB."""

    def __init__(self):
        settings.ensure_directories()
        self.client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
        self.ef = embedding_service.get_embedding_function()

    def _get_collection_name(self, repo_id: int) -> str:
        """Standard collection name for a given repository ID."""
        return f"repo_{repo_id}"

    def index_repository_chunks(self, repo_id: int, chunks: List[Dict[str, Any]]) -> int:
        """
        Store chunks + embeddings + metadata into ChromaDB collection for the repository.
        """
        if not chunks:
            return 0

        collection_name = self._get_collection_name(repo_id)

        # Delete existing collection if re-indexing
        try:
            self.client.delete_collection(name=collection_name)
        except Exception:
            pass

        collection = self.client.create_collection(
            name=collection_name,
            embedding_function=self.ef,
            metadata={"hnsw:space": "cosine"},
        )

        # ChromaDB batch size
        batch_size = 200
        total_chunks = len(chunks)

        for i in range(0, total_chunks, batch_size):
            batch = chunks[i : i + batch_size]
            ids = [f"{repo_id}_{c['file_path']}_{c['start_line']}_{c['end_line']}_{idx}" for idx, c in enumerate(batch, start=i)]
            documents = [c["content"] for c in batch]
            metadatas = [
                {
                    "repository": str(c.get("repository", "")),
                    "file_path": str(c.get("file_path", "")),
                    "programming_language": str(c.get("programming_language", "text")),
                    "start_line": int(c.get("start_line", 1)),
                    "end_line": int(c.get("end_line", 1)),
                }
                for c in batch
            ]

            collection.add(
                ids=ids,
                documents=documents,
                metadatas=metadatas,
            )

        logger.info(f"Indexed {total_chunks} chunks into ChromaDB collection '{collection_name}'.")
        return total_chunks

    def retrieve_relevant_chunks(
        self,
        repo_id: int,
        query: str,
        file_path: Optional[str] = None,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve top-k relevant code chunks from ChromaDB for a given repository and query.
        Optionally filters by a specific file_path.
        """
        collection_name = self._get_collection_name(repo_id)

        try:
            collection = self.client.get_collection(
                name=collection_name,
                embedding_function=self.ef,
            )
        except Exception as e:
            logger.warning(f"Collection {collection_name} not found: {e}")
            return []

        count = collection.count()
        if count == 0:
            return []

        n_results = min(top_k, count)
        where_clause = None
        if file_path and file_path.strip():
            where_clause = {"file_path": file_path.strip()}

        try:
            results = collection.query(
                query_texts=[query],
                n_results=n_results,
                where=where_clause,
            )
        except Exception as e:
            # If where filter yielded no results or errored, fallback to search without filter
            logger.warning(f"Query with where filter failed: {e}. Retrying without filter...")
            results = collection.query(
                query_texts=[query],
                n_results=n_results,
            )

        retrieved: List[Dict[str, Any]] = []
        if results and results.get("documents") and len(results["documents"]) > 0:
            doc_list = results["documents"][0]
            meta_list = results.get("metadatas", [[]])[0]
            id_list = results.get("ids", [[]])[0]

            for i, doc in enumerate(doc_list):
                meta = meta_list[i] if i < len(meta_list) else {}
                c_id = id_list[i] if i < len(id_list) else f"chunk_{i+1}"
                retrieved.append(
                    {
                        "chunk_id": c_id,
                        "content": doc,
                        "file_path": meta.get("file_path", ""),
                        "programming_language": meta.get("programming_language", "text"),
                        "start_line": meta.get("start_line", 1),
                        "end_line": meta.get("end_line", 1),
                        "repository": meta.get("repository", ""),
                    }
                )

        return retrieved

    def get_chunk_count(self, repo_id: int) -> int:
        """Get total number of chunks stored in ChromaDB for a repository."""
        collection_name = self._get_collection_name(repo_id)
        try:
            collection = self.client.get_collection(
                name=collection_name,
                embedding_function=self.ef,
            )
            return collection.count()
        except Exception:
            return 0

    def delete_repository_collection(self, repo_id: int) -> None:
        """Delete ChromaDB collection for a repository."""
        collection_name = self._get_collection_name(repo_id)
        try:
            self.client.delete_collection(name=collection_name)
            logger.info(f"Successfully deleted ChromaDB collection '{collection_name}' for repository {repo_id}.")
        except Exception as e:
            logger.info(f"ChromaDB collection '{collection_name}' not found or already removed: {e}")

    def delete_file_chunks(self, repo_id: int, file_path: str) -> None:
        """Delete specific file chunks from the repository's ChromaDB collection."""
        collection_name = self._get_collection_name(repo_id)
        norm_path = file_path.lstrip("/\\").replace("\\", "/")
        alt_path = file_path.lstrip("/\\").replace("/", "\\")
        try:
            collection = self.client.get_collection(
                name=collection_name,
                embedding_function=self.ef,
            )
            collection.delete(where={"file_path": norm_path})
            if alt_path != norm_path:
                try:
                    collection.delete(where={"file_path": alt_path})
                except Exception:
                    pass
            logger.info(f"Deleted ChromaDB chunks for file '{norm_path}' in repo {repo_id}.")
        except Exception as e:
            logger.warning(f"Failed to delete ChromaDB chunks for file '{file_path}': {e}")



    @staticmethod
    def build_context_prompt(retrieved_chunks: List[Dict[str, Any]]) -> str:
        """Build formatted code context block for Ollama."""
        if not retrieved_chunks:
            return "No specific code chunks retrieved from repository."

        context_parts = []
        for i, chunk in enumerate(retrieved_chunks, 1):
            file_p = chunk.get("file_path", "unknown")
            s_line = chunk.get("start_line", 1)
            e_line = chunk.get("end_line", 1)
            lang = chunk.get("programming_language", "")
            context_parts.append(
                f"### [Reference {i}: {file_p} (Lines {s_line}-{e_line})]\n"
                f"```{lang}\n{chunk['content']}\n```"
            )
        return "\n\n".join(context_parts)


rag_service = RAGService()
