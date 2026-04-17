from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src import dependencies
from src.config import Settings
from src.routers.projects import router


@pytest.fixture
def projects_client():
    app = FastAPI()
    app.include_router(router)

    settings = Settings()
    indices = Mock()
    os_client = Mock()
    os_client.indices = indices
    vector_store = Mock()
    vector_store.client = os_client

    app.dependency_overrides[dependencies.get_settings] = lambda: settings
    app.dependency_overrides[dependencies.get_opensearch_client] = lambda: vector_store

    yield TestClient(app), indices, settings

    app.dependency_overrides.clear()


def test_ensure_project_index_creates_when_missing(projects_client):
    client, indices, _ = projects_client
    indices.exists.side_effect = [False, False]

    response = client.post("/api/v1/projects/recruitment-q3/index/ensure")

    assert response.status_code == 200
    data = response.json()
    assert data["created"] is True
    assert data["validated"] is True
    assert data["index_name"] == "project-recruitment-q3"


def test_validate_project_index_returns_issues(projects_client):
    client, indices, _ = projects_client
    indices.exists.return_value = True
    indices.get_mapping.return_value = {
        "project-demo": {"mappings": {"properties": {"project_id": {"type": "keyword"}}}}
    }
    indices.get_settings.return_value = {"project-demo": {"settings": {"index": {"knn": "false"}}}}

    response = client.get("/api/v1/projects/demo/index/validate")

    assert response.status_code == 200
    data = response.json()
    assert data["is_compatible"] is False
    assert len(data["issues"]) > 0


def test_delete_project_index(projects_client):
    client, indices, _ = projects_client
    indices.exists.return_value = True

    response = client.delete("/api/v1/projects/demo/index")

    assert response.status_code == 200
    assert response.json()["deleted"] is True
