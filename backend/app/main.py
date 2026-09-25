"""FastAPI Application Entrypoint for AI Code Explanation & Debugger Bot."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.config import settings
from app.db.database import init_db
from app.services.ollama_service import ollama_service
from app.api.repositories import router as repositories_router
from app.api.explain import router as explain_router
from app.api.debugger import router as debugger_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup/shutdown lifecycle."""
    logger.info(f"Starting {settings.app_name} v{settings.app_version}...")
    settings.ensure_directories()
    await init_db()

    # Verify Ollama status at startup
    health = await ollama_service.check_health()
    if health.get("available"):
        logger.info(f"Ollama is online at {settings.ollama_base_url}. Model: {settings.ollama_model}")
    else:
        logger.warning(f"Ollama is offline or unreachable at {settings.ollama_base_url}: {health.get('error')}")

    yield
    logger.info(f"Shutting down {settings.app_name}...")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="AI Code Explanation & Debugger Bot using RAG + Ollama",
    lifespan=lifespan,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API routers
app.include_router(repositories_router)
app.include_router(explain_router)
app.include_router(debugger_router)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "status": "running",
        "docs_url": "/docs",
    }


@app.get("/health")
@app.get("/api/health")
async def health_check():
    """Health check endpoint indicating Ollama connectivity."""
    ollama_status = await ollama_service.check_health()
    return {
        "status": "healthy" if ollama_status.get("available") else "degraded",
        "app": settings.app_name,
        "version": settings.app_version,
        "ollama": ollama_status,
    }
