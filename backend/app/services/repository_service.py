"""Repository service for validation, cloning, scanning, and chunk indexing."""

import asyncio
import os
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from loguru import logger
from sqlalchemy import select

from app.config import settings
from app.db.database import async_session
from app.db.models import Repository
from app.services.code_processor import code_processor
from app.services.rag_service import rag_service


class RepositoryService:
    """Service to handle repository ingestion, scanning, and ChromaDB indexing."""

    @staticmethod
    def sanitize_repo_name(url_or_path: str) -> str:
        """Extract a clean repository name from URL or path."""
        clean = url_or_path.strip().rstrip("/")
        if clean.endswith(".git"):
            clean = clean[:-4]
        parts = clean.replace("\\", "/").split("/")
        return parts[-1] if parts else "unnamed_repo"

    @staticmethod
    def validate_url_or_path(url_or_path: str) -> Tuple[bool, str]:
        """Validate if input is a valid GitHub URL or existing local path."""
        s = url_or_path.strip()
        if not s:
            return False, "Repository URL or local path cannot be empty."
        if s.startswith("http://") or s.startswith("https://") or s.startswith("git@"):
            return True, "valid_url"
        if os.path.exists(s) and os.path.isdir(s):
            return True, "valid_local_path"
        return False, "Invalid repository URL or non-existent local directory path."

    async def clone_repository(self, repo_url: str, destination: Path) -> None:
        """Clone a Git repository into destination directory."""
        if destination.exists():
            shutil.rmtree(destination, ignore_errors=True)
        destination.mkdir(parents=True, exist_ok=True)

        logger.info(f"Cloning {repo_url} into {destination}...")
        cmd = ["git", "clone", "--depth", "1", repo_url, str(destination)]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            err_msg = stderr.decode().strip() or stdout.decode().strip()
            raise RuntimeError(f"Git clone failed: {err_msg}")
        logger.info(f"Successfully cloned {repo_url}")

    def scan_and_collect_files(self, repo_dir: Path) -> Tuple[List[str], List[Dict[str, Any]], Dict[str, int]]:
        """
        Scan directory recursively, collect supported files, and extract stats.
        """
        all_files: List[str] = []
        supported_files: List[Dict[str, Any]] = []
        languages: Dict[str, int] = {}

        for root, dirs, files in os.walk(repo_dir):
            dirs[:] = [d for d in dirs if not code_processor.should_ignore_dir(d)]

            for file_name in files:
                full_path = Path(root) / file_name
                rel_path = str(full_path.relative_to(repo_dir)).replace("\\", "/")
                all_files.append(rel_path)

                if code_processor.is_supported_file(full_path):
                    language = code_processor.get_language(rel_path)
                    try:
                        with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read()
                        line_count = len(content.splitlines())
                        supported_files.append({
                            "file_path": rel_path,
                            "full_path": str(full_path),
                            "language": language,
                            "line_count": line_count,
                            "content": content,
                        })
                        languages[language] = languages.get(language, 0) + 1
                    except Exception as e:
                        logger.warning(f"Could not read {rel_path}: {e}")

        sorted_languages = dict(sorted(languages.items(), key=lambda x: x[1], reverse=True))
        return all_files, supported_files, sorted_languages

    async def import_repository(self, url_or_path: str, custom_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Full ingestion pipeline:
        1. Validate repository URL or path
        2. Create DB record (status='cloning')
        3. Clone / copy files
        4. Scan & chunk supported code files
        5. Generate embeddings & store in ChromaDB
        6. Update DB record (status='ready')
        """
        is_valid, validation_type = self.validate_url_or_path(url_or_path)
        if not is_valid:
            raise ValueError(validation_type)

        repo_name = custom_name.strip() if custom_name and custom_name.strip() else self.sanitize_repo_name(url_or_path)

        async with async_session() as db:
            repo = Repository(
                name=repo_name,
                url=url_or_path if validation_type == "valid_url" else None,
                local_path="",
                status="cloning",
            )
            db.add(repo)
            await db.commit()
            await db.refresh(repo)
            repo_id = repo.id

        target_dir = Path(settings.repo_storage_path) / str(repo_id)

        try:
            # 1. Clone or copy
            if validation_type == "valid_url":
                await self.clone_repository(url_or_path, target_dir)
            else:
                if target_dir.exists():
                    shutil.rmtree(target_dir, ignore_errors=True)
                shutil.copytree(url_or_path, target_dir, ignore=shutil.ignore_patterns(*code_processor.IGNORE_DIRS))

            # 2. Update status to indexing
            async with async_session() as db:
                db_repo = await db.get(Repository, repo_id)
                if db_repo:
                    db_repo.local_path = str(target_dir)
                    db_repo.status = "indexing"
                    await db.commit()

            # 3. Scan files
            all_files, supported_files, language_stats = self.scan_and_collect_files(target_dir)

            # 4. Chunk files
            all_chunks: List[Dict[str, Any]] = []
            for file_info in supported_files:
                chunks = code_processor.chunk_file_content(
                    file_path=file_info["file_path"],
                    content=file_info["content"],
                    repo_name=repo_name,
                )
                all_chunks.extend(chunks)

            # 5. Store in ChromaDB
            total_indexed = rag_service.index_repository_chunks(repo_id=repo_id, chunks=all_chunks)

            # 6. Mark ready
            async with async_session() as db:
                db_repo = await db.get(Repository, repo_id)
                if db_repo:
                    db_repo.status = "ready"
                    db_repo.file_count = len(all_files)
                    db_repo.supported_files_count = len(supported_files)
                    db_repo.total_lines = sum(f["line_count"] for f in supported_files)
                    db_repo.languages = language_stats
                    await db.commit()

            return {
                "id": repo_id,
                "name": repo_name,
                "url": url_or_path,
                "status": "ready",
                "total_files": len(all_files),
                "supported_files_count": len(supported_files),
                "languages": language_stats,
                "total_chunks": total_indexed,
                "files": [f["file_path"] for f in supported_files],
            }

        except Exception as e:
            logger.exception(f"Error importing repository {url_or_path}: {e}")
            async with async_session() as db:
                db_repo = await db.get(Repository, repo_id)
                if db_repo:
                    db_repo.status = "error"
                    db_repo.error_message = str(e)
                    await db.commit()
            raise

    async def get_repository_details(self, repo_id: int) -> Optional[Dict[str, Any]]:
        """Get repository metadata and file list."""
        async with async_session() as db:
            repo = await db.get(Repository, repo_id)
            if not repo:
                return None

            files = []
            if repo.local_path and Path(repo.local_path).exists():
                _, supported_files, _ = self.scan_and_collect_files(Path(repo.local_path))
                files = [f["file_path"] for f in supported_files]

            return {
                "id": repo.id,
                "name": repo.name,
                "url": repo.url or repo.local_path,
                "status": repo.status,
                "total_files": repo.file_count,
                "supported_files_count": repo.supported_files_count or len(files),
                "languages": repo.languages or {},
                "files": files,
                "total_chunks": rag_service.get_chunk_count(repo_id),
                "error_message": repo.error_message,
            }

    async def list_repositories(self) -> List[Dict[str, Any]]:
        """List all repositories."""
        async with async_session() as db:
            result = await db.execute(select(Repository).order_by(Repository.id.desc()))
            repos = result.scalars().all()
            return [
                {
                    "id": r.id,
                    "name": r.name,
                    "url": r.url or r.local_path,
                    "status": r.status,
                    "total_files": r.file_count,
                    "supported_files_count": r.supported_files_count,
                    "languages": r.languages or {},
                    "error_message": r.error_message,
                }
                for r in repos
            ]

    async def get_file_content(self, repo_id: int, file_path: str) -> str:
        """Read source code of a specific file."""
        async with async_session() as db:
            repo = await db.get(Repository, repo_id)
            if not repo or not repo.local_path:
                raise FileNotFoundError(f"Repository {repo_id} not found.")

            target_file = Path(repo.local_path) / file_path.lstrip("/\\")
            if not target_file.exists() or not target_file.is_file():
                raise FileNotFoundError(f"File '{file_path}' not found in repository.")

            with open(target_file, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()

    async def delete_repository(self, repo_id: int) -> None:
        """Delete repository files, database entry, and ChromaDB collection."""
        async with async_session() as db:
            repo = await db.get(Repository, repo_id)
            if repo:
                if repo.local_path and Path(repo.local_path).exists():
                    shutil.rmtree(repo.local_path, ignore_errors=True)
                await db.delete(repo)
                await db.commit()

        rag_service.delete_repository_collection(repo_id)


repository_service = RepositoryService()
