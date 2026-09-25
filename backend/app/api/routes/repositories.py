"""Repository API routes.

Handles connecting, listing, and managing repositories.
"""

from __future__ import annotations

import asyncio
import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import app_state
from app.config import settings
from app.core.chunker import CodeChunker
from app.core.dependency import DependencyAnalyzer
from app.core.ingestion import RepositoryIngester
from app.core.parser import CodeParser
from app.db.database import get_db
from app.db.models import Analysis, RepoStatus, Repository
from app.graph.knowledge_graph import CodeKnowledgeGraph
from app.models.schemas import (
    GraphData,
    RepoConnectRequest,
    RepoListResponse,
    RepoStatusResponse,
)
from app.search.vector_store import VectorStore

router = APIRouter(prefix="/api/repositories", tags=["repositories"])


@router.post("", response_model=RepoStatusResponse, status_code=201)
async def connect_repository(
    request: RepoConnectRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Connect a new repository for analysis.

    Accepts either a Git URL (clones the repo) or a local filesystem path.
    Ingestion (parsing, indexing, graph building) runs in the background.
    """
    if not request.url and not request.local_path:
        raise HTTPException(
            status_code=400,
            detail="Either 'url' or 'local_path' must be provided.",
        )

    # Determine name
    name = request.name
    if not name:
        if request.url:
            name = request.url.rstrip("/").split("/")[-1].replace(".git", "")
        elif request.local_path:
            name = Path(request.local_path).name
        else:
            name = "repository"

    # Create DB record
    repo = Repository(
        name=name,
        url=request.url,
        local_path=request.local_path or "",
        status=RepoStatus.PENDING,
    )
    db.add(repo)
    await db.flush()
    await db.refresh(repo)

    repo_id = repo.id

    # Start background ingestion immediately
    asyncio.create_task(
        _ingest_repository(repo_id, request.url, request.local_path)
    )

    return RepoStatusResponse.model_validate(repo)


@router.get("", response_model=RepoListResponse)
async def list_repositories(
    db: AsyncSession = Depends(get_db),
):
    """List all connected repositories."""
    result = await db.execute(
        select(Repository).order_by(Repository.created_at.desc())
    )
    repos = result.scalars().all()

    return RepoListResponse(
        repositories=[RepoStatusResponse.model_validate(r) for r in repos],
        total=len(repos),
    )


@router.get("/{repo_id}", response_model=RepoStatusResponse)
async def get_repository(
    repo_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get repository details and status."""
    repo = await db.get(Repository, repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    return RepoStatusResponse.model_validate(repo)


@router.get("/{repo_id}/graph", response_model=GraphData)
async def get_repository_graph(
    repo_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get the knowledge graph data for visualization."""
    repo = await db.get(Repository, repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    graph = app_state.get_graph(repo_id)
    if not graph:
        raise HTTPException(
            status_code=404,
            detail="Knowledge graph not available. Repository may still be processing.",
        )

    return graph.serialize()


@router.get("/{repo_id}/stats")
async def get_repository_stats(
    repo_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get knowledge graph statistics."""
    graph = app_state.get_graph(repo_id)
    if not graph:
        raise HTTPException(status_code=404, detail="Graph not available")
    return graph.get_stats()


@router.delete("/{repo_id}", status_code=204)
async def delete_repository(
    repo_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Remove a repository and all associated data."""
    from sqlalchemy import delete
    repo = await db.get(Repository, repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    # Clean up in-memory state
    app_state.graphs.pop(repo_id, None)
    app_state.vector_stores.pop(repo_id, None)
    app_state.file_contents.pop(repo_id, None)

    # Delete related analyses
    await db.execute(delete(Analysis).where(Analysis.repo_id == repo_id))

    await db.delete(repo)
    await db.commit()


# ──────────────────────────────────────────────
# Background ingestion task
# ──────────────────────────────────────────────

async def _ingest_repository(
    repo_id: int,
    url: Optional[str],
    local_path: Optional[str],
) -> None:
    """Background task: full ingestion pipeline."""
    from app.db.database import async_session

    async with async_session() as db:
        repo = await db.get(Repository, repo_id)
        if not repo:
            return

        try:
            ingester = RepositoryIngester()

            # ── Clone / locate ──
            repo.status = RepoStatus.CLONING
            await db.commit()

            if url:
                repo_path = await asyncio.to_thread(
                    ingester.clone_repository, url
                )
                repo.local_path = str(repo_path)
            else:
                repo_path = await asyncio.to_thread(
                    ingester.use_local_path, local_path
                )

            # ── Detect languages ──
            languages = await asyncio.to_thread(
                ingester.detect_languages, repo_path
            )
            repo.languages = languages

            # ── Identify parseable files ──
            parseable_files = await asyncio.to_thread(
                ingester.identify_parseable_files, repo_path
            )
            all_source_files = await asyncio.to_thread(
                ingester.identify_source_files, repo_path
            )
            repo.file_count = len(all_source_files)

            # ── Parse ──
            repo.status = RepoStatus.PARSING
            await db.commit()

            parser = CodeParser()
            parsed_files = await asyncio.to_thread(
                parser.parse_files, parseable_files
            )

            # Count totals
            repo.function_count = sum(len(pf.functions) for pf in parsed_files)
            repo.class_count = sum(len(pf.classes) for pf in parsed_files)
            repo.total_lines = sum(pf.line_count for pf in parsed_files)

            # Store file contents for search
            file_contents = {pf.file_path: pf.raw_content for pf in parsed_files if pf.raw_content}
            app_state.file_contents[repo_id] = file_contents

            # ── Dependency analysis ──
            dep_analyzer = DependencyAnalyzer()
            dependencies = await asyncio.to_thread(
                dep_analyzer.analyze_all, parsed_files
            )

            # ── Build knowledge graph ──
            repo.status = RepoStatus.INDEXING
            await db.commit()

            graph = CodeKnowledgeGraph()
            await asyncio.to_thread(
                graph.build_from_analysis, parsed_files, dependencies
            )
            app_state.graphs[repo_id] = graph

            # Save graph to disk
            graph_path = Path(settings.graph_storage_path) / str(repo_id)
            graph_path.mkdir(parents=True, exist_ok=True)
            await asyncio.to_thread(
                graph.save, str(graph_path / "graph.json")
            )

            # ── Create chunks & embeddings ──
            chunker = CodeChunker()
            chunks = await asyncio.to_thread(
                chunker.chunk_files, parsed_files
            )

            if chunks:
                embedding_engine = app_state.get_embedding_engine()
                embeddings = await asyncio.to_thread(
                    embedding_engine.embed_chunks, chunks
                )

                # Build vector store
                vector_store = VectorStore(dimension=embeddings.shape[1])
                vector_store.build_index(embeddings, chunks)
                app_state.vector_stores[repo_id] = vector_store

                # Save to disk
                index_path = Path(settings.index_storage_path) / str(repo_id)
                await asyncio.to_thread(vector_store.save, str(index_path))

            # ── Done ──
            repo.status = RepoStatus.READY
            repo.error_message = None
            await db.commit()

            logger.info(
                f"Repository '{repo.name}' ingestion complete: "
                f"{repo.file_count} files, {repo.function_count} functions, "
                f"{repo.class_count} classes, {repo.total_lines} lines"
            )

        except Exception as e:
            logger.error(f"Ingestion failed for repo {repo_id}: {e}", exc_info=True)
            try:
                await db.rollback()
                repo = await db.get(Repository, repo_id)
                if repo:
                    repo.status = RepoStatus.ERROR
                    repo.error_message = str(e)
                    await db.commit()
            except Exception as inner_e:
                logger.error(f"Failed to record ingestion error for repo {repo_id}: {inner_e}")
