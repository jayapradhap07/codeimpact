"""Search API routes.

Handles code search and semantic (RAG) search requests.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import app_state
from app.db.database import get_db
from app.db.models import Repository
from app.models.schemas import (
    AssistantChatRequest,
    AssistantChatResponse,
    GraphData,
    SearchRequest,
    SearchResponse,
)

router = APIRouter(prefix="/api/search", tags=["search"])


@router.post("/code", response_model=SearchResponse)
async def search_code(
    request: SearchRequest,
    db: AsyncSession = Depends(get_db),
):
    """Search code by name or pattern."""
    repo = await db.get(Repository, request.repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    code_search = app_state.get_code_search(request.repo_id)
    if not code_search:
        raise HTTPException(status_code=404, detail="Search index not available")

    results = code_search.search_by_name(request.query, limit=request.top_k)

    return SearchResponse(
        results=results,
        total=len(results),
        query=request.query,
    )


@router.post("/semantic", response_model=SearchResponse)
async def search_semantic(
    request: SearchRequest,
    db: AsyncSession = Depends(get_db),
):
    """Semantic (RAG) search for code matching a natural language query."""
    repo = await db.get(Repository, request.repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    rag = app_state.get_rag_engine(request.repo_id)
    if not rag:
        raise HTTPException(status_code=404, detail="Vector store not available")

    results = rag.search_with_context(request.query, k=request.top_k)

    return SearchResponse(
        results=results,
        total=len(results),
        query=request.query,
    )


@router.get("/graph/{repo_id}/{node_id:path}", response_model=GraphData)
async def search_graph_neighborhood(
    repo_id: int,
    node_id: str,
    depth: int = 2,
):
    """Get the graph neighborhood around a specific node."""
    graph = app_state.get_graph(repo_id)
    if not graph:
        raise HTTPException(status_code=404, detail="Knowledge graph not available")

    subgraph = graph.get_subgraph(node_id, depth=depth)
    return subgraph


@router.post("/assistant", response_model=AssistantChatResponse)
async def chat_with_assistant(
    request: AssistantChatRequest,
    db: AsyncSession = Depends(get_db),
):
    """Interactive AI Assistant conversation with RAG & Knowledge Graph context."""
    repo = await db.get(Repository, request.repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    agent = app_state.get_impact_agent(request.repo_id)
    if agent:
        return await agent.answer_question(
            question=request.message,
            repo_name=repo.name,
            history=request.history,
        )

    # Fallback if agent is not fully initialized
    rag = app_state.get_rag_engine(request.repo_id)
    code_search = app_state.get_code_search(request.repo_id)

    relevant_chunks = []
    if rag:
        relevant_chunks = rag.search_with_context(request.message, k=4)
    elif code_search:
        relevant_chunks = code_search.search_by_name(request.message, limit=4)

    return AssistantChatResponse(
        response=f"Repository '{repo.name}' index is ready. No agent instance available.",
        relevant_chunks=relevant_chunks,
        suggested_followups=["Try re-indexing repository", "Run impact analysis"],
    )


