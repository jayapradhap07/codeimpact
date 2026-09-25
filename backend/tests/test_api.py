import pytest
from fastapi.testclient import TestClient
from app.main import app

def test_health_endpoint():
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

def test_repositories_list():
    with TestClient(app) as client:
        response = client.get("/api/repositories")
        assert response.status_code == 200
        data = response.json()
        assert "repositories" in data
        assert isinstance(data["repositories"], list)

def test_analysis_history():
    with TestClient(app) as client:
        response = client.get("/api/analysis/history")
        assert response.status_code == 200
        data = response.json()
        assert "analyses" in data
        assert isinstance(data["analyses"], list)
