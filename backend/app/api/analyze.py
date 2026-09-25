"""API routes for Code Analysis, Explanation, Debugging, and Health checks."""

from typing import List, Dict, Any, Optional, Literal
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.config import settings
from app.services.code_processor import code_processor
from app.services.rag_service import rag_service
from app.services.ollama_service import ollama_service

router = APIRouter()


# ---------------------------------------------------------------------------
# Request & Response Schemas
# ---------------------------------------------------------------------------

class AnalyzeRequest(BaseModel):
    code: str = Field(..., description="Source code to explain, debug, or query")
    language: str = Field(default="python", description="Programming language of the code")
    mode: Literal["explain", "debug", "ask"] = Field(
        default="explain",
        description="Analysis mode: 'explain', 'debug', or 'ask'",
    )
    question: Optional[str] = Field(
        default=None,
        description="User question (required when mode is 'ask')",
    )


class RetrievedChunk(BaseModel):
    chunk_id: str
    content: str
    start_line: int
    end_line: int
    language: str
    metadata: Optional[Dict[str, Any]] = None


class AnalyzeResponse(BaseModel):
    answer: str
    retrieved_chunks: List[RetrievedChunk]
    mode: str
    language: str
    syntax_valid: bool
    syntax_error: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    app_name: str
    version: str
    ollama: Dict[str, Any]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint indicating backend status and Ollama availability."""
    ollama_status = await ollama_service.check_health()
    return HealthResponse(
        status="healthy",
        app_name=settings.APP_NAME,
        version=settings.APP_VERSION,
        ollama=ollama_status,
    )


@router.get("/models")
async def get_models():
    """List available models from local Ollama instance."""
    health = await ollama_service.check_health()
    return {
        "current_model": settings.OLLAMA_MODEL,
        "available_models": health.get("available_models", []),
        "ollama_available": health.get("available", False),
    }


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_code(request: AnalyzeRequest):
    """
    Core End-to-End RAG Pipeline:
    1. Validate input code & question
    2. Syntax validation
    3. Code chunking with line metadata
    4. ChromaDB embedding & similarity retrieval
    5. Context-augmented prompt construction
    6. Ollama inference & structured response
    """
    # 1. Input Validation
    clean_code = request.code.strip()
    if not clean_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Source code cannot be empty. Please provide code to analyze.",
        )

    if request.mode == "ask":
        if not request.question or not request.question.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A question is required when using 'Ask Question' mode.",
            )

    # 2. Syntax validation
    is_valid_syntax, syntax_error = code_processor.validate_syntax(
        clean_code, request.language
    )

    # 3. Code Chunking
    chunks = code_processor.chunk_code(
        code=clean_code,
        language=request.language,
        chunk_lines=15,
        overlap_lines=3,
    )

    # 4. RAG Retrieval via ChromaDB
    # Determine retrieval query based on mode and question
    if request.mode == "ask" and request.question:
        query_text = request.question.strip()
    elif request.mode == "debug":
        query_text = (
            f"bugs errors syntax issues exception handling {syntax_error or ''}"
        )
    else:  # explain
        query_text = "main function logic purpose classes architecture entrypoint"

    retrieved_raw = rag_service.index_and_retrieve(
        chunks=chunks,
        query=query_text,
        top_k=settings.TOP_K_CHUNKS,
    )

    # Format retrieved chunks for response
    retrieved_chunks = [
        RetrievedChunk(
            chunk_id=c["chunk_id"],
            content=c["content"],
            start_line=c["start_line"],
            end_line=c["end_line"],
            language=c.get("language", request.language),
            metadata=c.get("metadata"),
        )
        for c in retrieved_raw
    ]

    # 5. Build RAG Context Block
    rag_context = rag_service.build_context_prompt(
        code=clean_code,
        retrieved_chunks=retrieved_raw,
        language=request.language,
    )

    # 6. Query Ollama with RAG Context
    ai_answer = await ollama_service.generate_response(
        code=clean_code,
        language=request.language,
        mode=request.mode,
        question=request.question,
        rag_context=rag_context,
    )

    return AnalyzeResponse(
        answer=ai_answer,
        retrieved_chunks=retrieved_chunks,
        mode=request.mode,
        language=request.language,
        syntax_valid=is_valid_syntax,
        syntax_error=syntax_error,
    )
