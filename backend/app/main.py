"""FastAPI Application Entrypoint for CodeImpact & AI Code Explanation / Debugger."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.api.deps import app_state
from app.api.routes import analysis, repositories, search
from app.api.analyze import router as analyze_router
from app.config import settings
from app.db.database import init_db
from app.graph.knowledge_graph import CodeKnowledgeGraph
from app.search.vector_store import VectorStore
from app.services.ollama_service import ollama_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup/shutdown lifecycle."""
    logger.info(f"Starting {settings.app_name} v{settings.APP_VERSION}...")
    settings.ensure_directories()
    await init_db()

    # Reload any persisted graphs and indexes
    await _reload_persisted_data()

    # Check Ollama connection on startup
    health = await ollama_service.check_health()
    if health.get("available"):
        logger.info(f"Ollama is online! Model: {settings.OLLAMA_MODEL}, Available: {health.get('available_models')}")
    else:
        logger.warning(f"Ollama is offline or unreachable at {settings.OLLAMA_BASE_URL}: {health.get('error')}")

    logger.info(f"{settings.app_name} is ready!")
    yield
    logger.info(f"Shutting down {settings.app_name}...")


app = FastAPI(
    title=settings.app_name,
    version=settings.APP_VERSION,
    description=(
        "AI-powered platform for Code Impact Analysis, Knowledge Graphs, "
        "and RAG-assisted Code Explanation & Debugging with Local Ollama LLM."
    ),
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(repositories.router)
app.include_router(analysis.router)
app.include_router(search.router)
app.include_router(analyze_router, prefix="/api")


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "app": settings.app_name,
        "version": settings.APP_VERSION,
        "status": "running",
        "docs_url": "/docs",
    }


@app.get("/health")
@app.get("/api/health")
async def health_check():
    """Combined health check endpoint."""
    ollama_status = await ollama_service.check_health()
    return {
        "status": "healthy",
        "app": settings.app_name,
        "version": settings.APP_VERSION,
        "repositories_loaded": len(app_state.graphs),
        "llm_provider": settings.llm_provider,
        "ollama": ollama_status,
    }


@app.get("/api/stats")
async def global_stats():
    """Global application statistics."""
    total_nodes = sum(
        g.graph.number_of_nodes() for g in app_state.graphs.values()
    )
    total_edges = sum(
        g.graph.number_of_edges() for g in app_state.graphs.values()
    )
    total_vectors = sum(
        vs.total_vectors for vs in app_state.vector_stores.values()
    )

    return {
        "repositories": len(app_state.graphs),
        "total_nodes": total_nodes,
        "total_edges": total_edges,
        "total_vectors": total_vectors,
    }


async def _reload_persisted_data() -> None:
    """Reload graphs and indexes from disk on startup."""
    graph_dir = Path(settings.graph_storage_path)
    index_dir = Path(settings.index_storage_path)

    if not graph_dir.exists():
        return

    for repo_dir in graph_dir.iterdir():
        if not repo_dir.is_dir():
            continue

        try:
            repo_id = int(repo_dir.name)
        except ValueError:
            continue

        graph_file = repo_dir / "graph.json"
        if graph_file.exists():
            try:
                graph = CodeKnowledgeGraph()
                await asyncio.to_thread(graph.load, str(graph_file))
                app_state.graphs[repo_id] = graph
                logger.info(f"Reloaded graph for repo {repo_id}")
            except Exception as e:
                logger.warning(f"Failed to reload graph for repo {repo_id}: {e}")

        # Reload vector store
        index_path = index_dir / str(repo_id)
        if index_path.exists():
            try:
                vs = VectorStore()
                await asyncio.to_thread(vs.load, str(index_path))
                app_state.vector_stores[repo_id] = vs
                logger.info(f"Reloaded vector store for repo {repo_id}")
            except Exception as e:
                logger.warning(f"Failed to reload vector store for repo {repo_id}: {e}")

