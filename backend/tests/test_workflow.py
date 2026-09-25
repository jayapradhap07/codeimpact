"""End-to-end integration tests for AI Code Explanation & Debugger Bot."""

import asyncio
import os
import shutil
import tempfile
from pathlib import Path
import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.config import settings
from app.db.database import init_db
from app.services.repository_service import repository_service
from app.services.rag_service import rag_service
from app.services.ollama_service import ollama_service


def test_full_pipeline_sync():
    """Run the async test suite inside a single event loop."""
    async def _run():
        settings.ensure_directories()
        await init_db()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Health check
            health_res = await client.get("/api/health")
            assert health_res.status_code == 200
            health_data = health_res.json()
            assert "status" in health_data
            assert "ollama" in health_data

            # 2. End-to-end repository ingestion
            temp_dir = tempfile.mkdtemp(prefix="test_repo_")
            try:
                calc_file = Path(temp_dir) / "calculator.py"
                calc_file.write_text(
                    """def add(a: int, b: int) -> int:
    \"\"\"Add two numbers.\"\"\"
    return a + b

def divide(a: float, b: float) -> float:
    \"\"\"Divide two numbers safely.\"\"\"
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b
""",
                    encoding="utf-8",
                )

                buggy_file = Path(temp_dir) / "buggy.py"
                buggy_file.write_text(
                    """def calculate_average(numbers):
    total = sum(numbers)
    return total / len(numbers)
""",
                    encoding="utf-8",
                )

                # Import repository
                import_res = await client.post(
                    "/api/repositories/import",
                    json={"url_or_path": temp_dir, "custom_name": "TestMathRepo"},
                )
                assert import_res.status_code == 201
                repo_data = import_res.json()
                repo_id = repo_data["id"]
                assert repo_data["name"] == "TestMathRepo"
                assert repo_data["supported_files_count"] == 2
                assert "python" in repo_data["languages"]
                assert repo_data["total_chunks"] >= 2

                # Verify ChromaDB contains chunks
                chunk_count = rag_service.get_chunk_count(repo_id)
                assert chunk_count >= 2

                # Verify repository details
                get_res = await client.get(f"/api/repositories/{repo_id}")
                assert get_res.status_code == 200
                assert len(get_res.json()["files"]) == 2

                # Fetch specific file
                file_res = await client.get(
                    f"/api/repositories/{repo_id}/file?path=calculator.py"
                )
                assert file_res.status_code == 200
                assert "def add" in file_res.json()["content"]

                # Explain Code
                explain_res = await client.post(
                    "/api/explain",
                    json={
                        "repo_id": repo_id,
                        "file_path": "calculator.py",
                        "question": "What does this calculator module do?",
                    },
                )
                assert explain_res.status_code == 200
                exp_data = explain_res.json()
                assert "explanation" in exp_data
                assert len(exp_data["explanation"]) > 0
                assert len(exp_data["retrieved_chunks"]) > 0

                # Debugger Bot
                debug_res = await client.post(
                    "/api/debug",
                    json={
                        "repo_id": repo_id,
                        "file_path": "buggy.py",
                        "question": "Why does calculate_average fail when given an empty list?",
                    },
                )
                assert debug_res.status_code == 200
                debug_data = debug_res.json()
                assert "debug_result" in debug_data
                assert len(debug_data["debug_result"]) > 0
                assert len(debug_data["retrieved_chunks"]) > 0

                # Clean up repo and verify ChromaDB deletion
                del_res = await client.delete(f"/api/repositories/{repo_id}")
                assert del_res.status_code == 200
                assert rag_service.get_chunk_count(repo_id) == 0

            finally:
                shutil.rmtree(temp_dir, ignore_errors=True)

    asyncio.run(_run())
