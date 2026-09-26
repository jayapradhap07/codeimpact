"""Application configuration using pydantic-settings."""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings for AI Code Explanation & Debugger Bot."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "AI Code Explanation & Debugger Bot"
    app_version: str = "1.0.0"
    app_env: str = "development"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000

    # Database
    database_url: str = "sqlite+aiosqlite:///./data/coderag.db"

    # Ollama Configuration (Local ONLY)
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5-coder:3b"
    ollama_timeout_seconds: float = 240.0

    # ChromaDB & RAG Storage
    chroma_persist_dir: str = "./data/chroma_data"
    top_k_chunks: int = 5

    # Storage paths
    repo_storage_path: str = "./data/repos"

    # CORS
    cors_origins: str = '["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:5174", "http://localhost:3000"]'

    def ensure_directories(self) -> None:
        """Create required data directories if they don't exist."""
        for path_str in [
            self.repo_storage_path,
            self.chroma_persist_dir,
            "./data",
        ]:
            Path(path_str).mkdir(parents=True, exist_ok=True)


settings = Settings()
