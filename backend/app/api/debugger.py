"""API route for Debugger Bot using RAG + Ollama."""

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.config import settings
from app.services.repository_service import repository_service
from app.services.rag_service import rag_service
from app.services.ollama_service import ollama_service

router = APIRouter(prefix="/api/debug", tags=["Debugger Bot"])


class DebugRequest(BaseModel):
    repo_id: int = Field(..., description="Repository ID")
    file_path: Optional[str] = Field(default="", description="Relative file path in repository")
    code: Optional[str] = Field(default=None, description="Explicit code content (optional if file_path is provided)")
    question: Optional[str] = Field(default="Find any bugs or syntax issues in this code and fix them.", description="User debug query or error description")


class RetrievedChunkResponse(BaseModel):
    chunk_id: str
    file_path: str
    start_line: int
    end_line: int
    programming_language: str
    content: str


class DebugResponse(BaseModel):
    debug_result: str
    file_path: str
    question: str
    retrieved_chunks: List[RetrievedChunkResponse]


@router.post("", response_model=DebugResponse)
async def debug_code(request: DebugRequest):
    """
    Debugger Bot endpoint:
    1. Read target file code
    2. Query ChromaDB for top relevant code chunks
    3. Construct RAG context
    4. Send to Ollama with structured debug prompt
    5. Return debugging result (Problem, Reason, Suggested Fix, Corrected Code)
    """
    file_content = ""
    file_p = (request.file_path or "").strip()

    if request.code and request.code.strip():
        file_content = request.code.strip()
    elif file_p:
        try:
            file_content = await repository_service.get_file_content(request.repo_id, file_p)
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Failed to load file '{file_p}': {e}")
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please provide either a valid file_path or code content to debug.",
        )

    # Search query
    query_text = request.question.strip() if request.question and request.question.strip() else f"bugs error in {file_p}"

    # ChromaDB similarity search
    retrieved = rag_service.retrieve_relevant_chunks(
        repo_id=request.repo_id,
        query=query_text,
        file_path=file_p if file_p else None,
        top_k=settings.top_k_chunks,
    )

    if not retrieved and file_content:
        retrieved = [
            {
                "chunk_id": f"{file_p}:1",
                "file_path": file_p or "selected_code",
                "start_line": 1,
                "end_line": len(file_content.splitlines()),
                "programming_language": "text",
                "content": file_content[:1500],
            }
        ]

    # Build RAG Context
    rag_context = rag_service.build_context_prompt(retrieved)

    # Build prompt for Ollama
    prompt = ollama_service.build_debug_prompt(
        file_path=file_p or "Target Code",
        code_content=file_content,
        user_query=query_text,
        rag_context=rag_context,
    )

    # Call Ollama
    ai_answer = await ollama_service.generate_response(prompt)

    retrieved_models = [
        RetrievedChunkResponse(
            chunk_id=c.get("chunk_id", ""),
            file_path=c.get("file_path", ""),
            start_line=c.get("start_line", 1),
            end_line=c.get("end_line", 1),
            programming_language=c.get("programming_language", "text"),
            content=c.get("content", ""),
        )
        for c in retrieved
    ]

    return DebugResponse(
        debug_result=ai_answer,
        file_path=file_p or "Custom Code",
        question=query_text,
        retrieved_chunks=retrieved_models,
    )
