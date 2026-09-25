"""RAG Service for ChromaDB indexing, similarity retrieval, and context building."""

import uuid
from typing import List, Dict, Any
import chromadb
from app.config import settings
from app.services.embedding_service import embedding_service


class RAGService:
    """Manages vector storage and similarity retrieval using ChromaDB."""

    def __init__(self):
        # Using ChromaDB client with persistent or in-memory storage
        try:
            self.client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
        except Exception:
            self.client = chromadb.Client()
        self.ef = embedding_service.get_embedding_function()

    def index_and_retrieve(
        self,
        chunks: List[Dict[str, Any]],
        query: str,
        top_k: int = 4,
    ) -> List[Dict[str, Any]]:
        """
        Indexes code chunks into ChromaDB and retrieves the top-k most relevant chunks.
        
        Returns a list of retrieved chunks with content, line numbers, and metadata.
        """
        if not chunks:
            return []

        # If only 1 chunk exists (small code), return it directly
        if len(chunks) == 1:
            return chunks

        # Create a unique ephemeral collection for this query analysis
        collection_id = f"analysis_{uuid.uuid4().hex[:12]}"
        collection = self.client.create_collection(
            name=collection_id,
            embedding_function=self.ef,
            metadata={"hnsw:space": "cosine"},
        )

        try:
            # Prepare documents, metadatas, and ids for ChromaDB
            ids = [chunk["chunk_id"] for chunk in chunks]
            documents = [chunk["content"] for chunk in chunks]
            metadatas = [
                {
                    "start_line": chunk["start_line"],
                    "end_line": chunk["end_line"],
                    "language": chunk.get("language", "python"),
                    "source": chunk.get("metadata", {}).get("source", "user_code"),
                }
                for chunk in chunks
            ]

            # Add to ChromaDB collection
            collection.add(
                ids=ids,
                documents=documents,
                metadatas=metadatas,
            )

            # Query ChromaDB
            n_results = min(top_k, len(chunks))
            results = collection.query(
                query_texts=[query],
                n_results=n_results,
            )

            retrieved: List[Dict[str, Any]] = []
            if results and results.get("documents") and len(results["documents"]) > 0:
                doc_list = results["documents"][0]
                meta_list = results["metadatas"][0] if results.get("metadatas") else []
                id_list = results["ids"][0] if results.get("ids") else []

                for i, doc in enumerate(doc_list):
                    meta = meta_list[i] if i < len(meta_list) else {}
                    c_id = id_list[i] if i < len(id_list) else f"chunk_{i+1}"
                    retrieved.append(
                        {
                            "chunk_id": c_id,
                            "content": doc,
                            "start_line": meta.get("start_line", 1),
                            "end_line": meta.get("end_line", 1),
                            "language": meta.get("language", "python"),
                            "metadata": meta,
                        }
                    )

            # Sort retrieved chunks by their starting line number for logical reading
            retrieved.sort(key=lambda x: x["start_line"])
            return retrieved if retrieved else chunks[:n_results]

        finally:
            # Clean up temporary collection
            try:
                self.client.delete_collection(name=collection_id)
            except Exception:
                pass

    @staticmethod
    def build_context_prompt(
        code: str,
        retrieved_chunks: List[Dict[str, Any]],
        language: str,
    ) -> str:
        """Construct the retrieved RAG context block for prompt injection."""
        context_parts = []
        for i, chunk in enumerate(retrieved_chunks, 1):
            context_parts.append(
                f"--- [Code Chunk {i} | Lines {chunk['start_line']}-{chunk['end_line']}] ---\n"
                f"{chunk['content']}\n"
            )
        return "\n".join(context_parts)


rag_service = RAGService()
