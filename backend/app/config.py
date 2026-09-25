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
    )

    # Application
    app_name: str = "CodeImpact"
    app_env: str = "development"
    debug: bool = True
    host: str = "0.0.0.0"
    port: int = 8000

    # Database
    database_url: str = "sqlite+aiosqlite:///./data/codeimpact.db"

    # LLM Provider
    llm_provider: str = "openai"  # "openai", "gemini", "ollama"
    openai_api_key: str = ""
    gemini_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "codellama"

    # Embeddings
    embedding_model: str = "all-MiniLM-L6-v2"

    # Storage paths
    repo_storage_path: str = "./data/repos"
    index_storage_path: str = "./data/indexes"
    graph_storage_path: str = "./data/graphs"

    # CORS
    cors_origins: str = '["http://localhost:5173"]'

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins from JSON string."""
        try:
            return json.loads(self.cors_origins)
        except (json.JSONDecodeError, TypeError):
            return ["http://localhost:5173"]

    def ensure_directories(self) -> None:
        """Create required data directories if they don't exist."""
        for path_str in [
            self.repo_storage_path,
            self.index_storage_path,
            self.graph_storage_path,
        ]:
            Path(path_str).mkdir(parents=True, exist_ok=True)
        # Ensure the database directory exists
        db_path = self.database_url.replace("sqlite+aiosqlite:///", "")
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)


# Global settings singleton
settings = Settings()
