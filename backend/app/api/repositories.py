"""API routes for repository management."""

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from app.services.repository_service import repository_service

router = APIRouter(prefix="/api/repositories", tags=["Repositories"])


class ImportRepoRequest(BaseModel):
    url_or_path: str = Field(..., description="GitHub repository URL or local path")
    custom_name: Optional[str] = Field(default=None, description="Optional custom name")


@router.post("/import", status_code=status.HTTP_201_CREATED)
@router.post("", status_code=status.HTTP_201_CREATED)
async def import_repository(request: ImportRepoRequest):
    """
    Import repository: Validate URL -> Clone -> Scan files -> Chunk -> Embed & Store in ChromaDB.
    """
    try:
        result = await repository_service.import_repository(
            url_or_path=request.url_or_path,
            custom_name=request.custom_name,
        )
        return result
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("")
async def list_repositories():
    """List all imported repositories."""
    return await repository_service.list_repositories()


@router.get("/{repo_id}")
async def get_repository(repo_id: int):
    """Get single repository details and supported file list."""
    repo = await repository_service.get_repository_details(repo_id)
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found.")
    return repo


@router.get("/{repo_id}/file")
async def get_repository_file(repo_id: int, path: str = Query(..., description="Relative file path")):
    """Get source code of a specific file in the repository."""
    try:
        content = await repository_service.get_file_content(repo_id, path)
        return {"file_path": path, "content": content}
    except FileNotFoundError as fe:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(fe))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.delete("/{repo_id}/file")
async def delete_repository_file(repo_id: int, path: str = Query(..., description="Relative file path")):
    """Delete a specific file in the repository and remove its embeddings from ChromaDB."""
    try:
        result = await repository_service.delete_file(repo_id, path)
        return result
    except FileNotFoundError as fe:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(fe))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.delete("/{repo_id}")
async def delete_repository(repo_id: int):
    """Delete repository, local files, and ChromaDB collection."""
    try:
        await repository_service.delete_repository(repo_id)
        return {"status": "deleted", "id": repo_id}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/cleanup")
async def cleanup_orphaned_repositories():
    """Clean any orphaned repository folders in data/repos that do not exist in the database."""
    try:
        removed = await repository_service.cleanup_orphans()
        return {"status": "success", "removed_folders": removed}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))



