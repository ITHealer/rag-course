from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src import dependencies
from src.config import Settings
from src.routers.domains import router as domains_router
from src.routers.projects import router as projects_router


class InMemoryDomainRepository:
    def __init__(self):
        self._items = {}

    def create(self, payload: dict):
        item_id = uuid4()
        now = datetime.now(timezone.utc)
        entity = SimpleNamespace(
            id=item_id,
            domain_id=payload["domain_id"],
            display_name=payload["display_name"],
            mode_default=payload.get("mode_default", "strict"),
            system_prompt_addon=payload.get("system_prompt_addon", ""),
            metadata_extract=payload.get("metadata_extract", []),
            search_boost=payload.get("search_boost", []),
            answer_policy=payload.get("answer_policy", {}),
            allow_external_web_search=payload.get("allow_external_web_search", False),
            require_human_approval_for_external_search=payload.get(
                "require_human_approval_for_external_search", True
            ),
            allow_image_perception=payload.get("allow_image_perception", True),
            allowed_external_domains=payload.get("allowed_external_domains", []),
            version=1,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        self._items[entity.domain_id] = entity
        return entity

    def get_by_domain_id(self, domain_id: str):
        return self._items.get(domain_id)

    def list(self, limit: int = 100, offset: int = 0):
        values = list(self._items.values())
        return values[offset : offset + limit]

    def update(self, domain_profile, update_data: dict):
        for key, value in update_data.items():
            setattr(domain_profile, key, value)
        domain_profile.updated_at = datetime.now(timezone.utc)
        return domain_profile

    def delete(self, domain_profile):
        self._items.pop(domain_profile.domain_id, None)


class InMemoryProjectRepository:
    def __init__(self):
        self._items = {}

    def create(self, payload: dict):
        item_id = uuid4()
        now = datetime.now(timezone.utc)
        entity = SimpleNamespace(
            id=item_id,
            name=payload["name"],
            domain_id=payload["domain_id"],
            mode=payload.get("mode", "strict"),
            description=payload.get("description", ""),
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        self._items[item_id] = entity
        return entity

    def get_by_id(self, project_id: UUID):
        return self._items.get(project_id)

    def list(self, limit: int = 100, offset: int = 0):
        values = list(self._items.values())
        return values[offset : offset + limit]

    def update(self, project, update_data: dict):
        for key, value in update_data.items():
            setattr(project, key, value)
        project.updated_at = datetime.now(timezone.utc)
        return project

    def delete(self, project):
        self._items.pop(project.id, None)


@pytest.fixture
def control_plane_client():
    app = FastAPI()
    app.include_router(domains_router)
    app.include_router(projects_router)

    domain_repo = InMemoryDomainRepository()
    project_repo = InMemoryProjectRepository()

    app.dependency_overrides[dependencies.get_domain_profile_repository] = lambda: domain_repo
    app.dependency_overrides[dependencies.get_project_repository] = lambda: project_repo
    app.dependency_overrides[dependencies.get_settings] = lambda: Settings()

    yield TestClient(app)

    app.dependency_overrides.clear()


def test_domain_crud_flow(control_plane_client: TestClient):
    create_response = control_plane_client.post(
        "/api/v1/domains",
        json={
            "domain_id": "cv_recruitment",
            "display_name": "CV Recruitment",
            "mode_default": "strict",
        },
    )
    assert create_response.status_code == 201
    assert create_response.json()["domain_id"] == "cv_recruitment"

    list_response = control_plane_client.get("/api/v1/domains")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    update_response = control_plane_client.patch(
        "/api/v1/domains/cv_recruitment",
        json={"display_name": "CV Recruitment v2"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["display_name"] == "CV Recruitment v2"

    delete_response = control_plane_client.delete("/api/v1/domains/cv_recruitment")
    assert delete_response.status_code == 200
    assert delete_response.json()["deleted"] is True


def test_project_crud_flow(control_plane_client: TestClient):
    control_plane_client.post(
        "/api/v1/domains",
        json={"domain_id": "app_docs", "display_name": "App Docs", "mode_default": "strict"},
    )

    create_project = control_plane_client.post(
        "/api/v1/projects",
        json={
            "name": "Support Docs Q3",
            "domain_id": "app_docs",
            "mode": "strict",
            "description": "Support docs project",
        },
    )
    assert create_project.status_code == 201
    project_id = create_project.json()["id"]

    get_project = control_plane_client.get(f"/api/v1/projects/{project_id}")
    assert get_project.status_code == 200
    assert get_project.json()["name"] == "Support Docs Q3"

    update_project = control_plane_client.patch(
        f"/api/v1/projects/{project_id}",
        json={"mode": "augmented"},
    )
    assert update_project.status_code == 200
    assert update_project.json()["mode"] == "augmented"

    delete_project = control_plane_client.delete(f"/api/v1/projects/{project_id}")
    assert delete_project.status_code == 200
    assert delete_project.json()["deleted"] is True
