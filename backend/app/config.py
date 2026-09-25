"""Application configuration using pydantic-settings."""

import json
from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "CodeImpact & AI Code Explainer"
    app_env: str = "development"
    debug: bool = True
    host: str = "0.0.0.0"
    port: int = 8000

    # Database
    database_url: str = "sqlite+aiosqlite:///./data/codeimpact.db"

    # LLM Provider
    llm_provider: str = "ollama"  # "openai", "gemini", "ollama"
    openai_api_key: str = ""
    gemini_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5-coder:7b"
    ollama_timeout_seconds: float = 120.0

    # ChromaDB & RAG Storage
    chroma_persist_dir: str = "./chroma_data"
    embedding_model: str = "all-MiniLM-L6-v2"
    top_k_chunks: int = 4

    # Storage paths
    repo_storage_path: str = "./data/repos"
    index_storage_path: str = "./data/indexes"
    graph_storage_path: str = "./data/graphs"

    # CORS
    cors_origins: str = '["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000"]'

    # Uppercase aliases for compatibility
    @property
    def APP_NAME(self) -> str:
        return self.app_name

    @property
    def APP_VERSION(self) -> str:
        return "1.0.0"

    @property
    def DEBUG(self) -> bool:
        return self.debug

    @property
    def HOST(self) -> str:
        return self.host

    @property
    def PORT(self) -> int:
        return self.port

    @property
    def OLLAMA_BASE_URL(self) -> str:
        return self.ollama_base_url

    @property
    def OLLAMA_MODEL(self) -> str:
        return self.ollama_model

    @property
    def OLLAMA_TIMEOUT_SECONDS(self) -> float:
        return self.ollama_timeout_seconds

    @property
    def CHROMA_PERSIST_DIR(self) -> str:
        return self.chroma_persist_dir

    @property
    def EMBEDDING_MODEL(self) -> str:
        return self.embedding_model

    @property
    def TOP_K_CHUNKS(self) -> int:
        return self.top_k_chunks

    @property
    def CORS_ORIGINS(self) -> List[str]:
        return self.cors_origins_list

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins from JSON string or list."""
        if isinstance(self.cors_origins, list):
            return self.cors_origins
        try:
            return json.loads(self.cors_origins)
        except (json.JSONDecodeError, TypeError):
            return ["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000"]

    def ensure_directories(self) -> None:
        """Create required data directories if they don't exist."""
        for path_str in [
            self.repo_storage_path,
            self.index_storage_path,
            self.graph_storage_path,
            self.chroma_persist_dir,
        ]:
            Path(path_str).mkdir(parents=True, exist_ok=True)
        # Ensure the database directory exists
        db_path = self.database_url.replace("sqlite+aiosqlite:///", "")
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)


# Global settings singleton
settings = Settings()

