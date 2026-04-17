from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import shutil
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src import dependencies
from src.config import Settings
from src.routers.domains import router


class InMemoryDomainRepository:
    def __init__(self):
        self._items = {}

    def create(self, payload: dict):
        now = datetime.now(timezone.utc)
        entity = SimpleNamespace(
            id=uuid4(),
            domain_id=payload["domain_id"],
            display_name=payload["display_name"],
            mode_default=payload.get("mode_default", "strict"),
            system_prompt_addon=payload.get("system_prompt_addon", ""),
            metadata_extract=payload.get("metadata_extract", []),
            search_boost=payload.get("search_boost", []),
            answer_policy=payload.get("answer_policy", {}),
            allow_external_web_search=payload.get("allow_external_web_search", False),
            require_human_approval_for_external_search=payload.get(
                "require_human_approval_for_external_search",
                True,
            ),
            allow_image_perception=payload.get("allow_image_perception", True),
            allowed_external_domains=payload.get("allowed_external_domains", []),
            version=payload.get("version", 1),
            is_active=payload.get("is_active", True),
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
        domain_profile.version += 1
        domain_profile.updated_at = datetime.now(timezone.utc)
        return domain_profile

    def delete(self, domain_profile):
        self._items.pop(domain_profile.domain_id, None)


@pytest.fixture
def domains_runtime_client():
    app = FastAPI()
    app.include_router(router)
    repository = InMemoryDomainRepository()

    temp_preset_dir = Path.cwd() / f"tests_runtime_presets_{uuid4().hex}"
    temp_preset_dir.mkdir(parents=True, exist_ok=True)

    preset_file = temp_preset_dir / "custom_runtime.yaml"
    preset_file.write_text(
        "\n".join(
            [
                "id: custom_runtime",
                "display_name: Custom Runtime",
                "mode_default: strict",
                "system_prompt_addon: |",
                "  You are a runtime-configured assistant.",
                "metadata_extract: []",
                "search_boost: []",
                "answer_policy: {}",
                "allow_external_web_search: false",
                "require_human_approval_for_external_search: true",
                "allow_image_perception: true",
                "allowed_external_domains: []",
            ]
        ),
        encoding="utf-8",
    )

    settings = Settings(
        preset_dir=str(temp_preset_dir),
        default_preset_id="custom_runtime",
    )

    app.dependency_overrides[dependencies.get_domain_profile_repository] = lambda: repository
    app.dependency_overrides[dependencies.get_settings] = lambda: settings

    yield TestClient(app)

    app.dependency_overrides.clear()
    shutil.rmtree(temp_preset_dir, ignore_errors=True)


def test_domain_config_and_prompt_roundtrip(domains_runtime_client: TestClient):
    config_response = domains_runtime_client.put(
        "/api/v1/domains/recruitment/config",
        json={
            "display_name": "Recruitment Domain",
            "mode_default": "augmented",
            "system_prompt_addon": "Recruitment prompt v1",
            "metadata_extract": [{"field": "skills", "prompt": "Extract skills"}],
            "search_boost": [{"field": "metadata.skills", "weight": 1.5}],
            "answer_policy": {"grounded_only": True},
            "allow_external_web_search": False,
            "require_human_approval_for_external_search": True,
            "allow_image_perception": True,
            "allowed_external_domains": [],
            "is_active": True,
        },
    )
    assert config_response.status_code == 200
    assert config_response.json()["domain_id"] == "recruitment"
    assert config_response.json()["mode_default"] == "augmented"

    prompt_response = domains_runtime_client.get("/api/v1/domains/recruitment/prompt")
    assert prompt_response.status_code == 200
    assert prompt_response.json()["system_prompt_addon"] == "Recruitment prompt v1"
    assert prompt_response.json()["version"] == 1

    prompt_update = domains_runtime_client.put(
        "/api/v1/domains/recruitment/prompt",
        json={
            "system_prompt_addon": "Recruitment prompt v2",
            "answer_policy": {"grounded_only": True, "suggest_followups": True},
            "mode_default": "strict",
        },
    )
    assert prompt_update.status_code == 200
    assert prompt_update.json()["system_prompt_addon"] == "Recruitment prompt v2"
    assert prompt_update.json()["version"] == 2


def test_import_preset_library_to_domain(domains_runtime_client: TestClient):
    library_response = domains_runtime_client.get("/api/v1/domains/presets/library")
    assert library_response.status_code == 200
    assert any(item["id"] == "custom_runtime" for item in library_response.json())

    import_response = domains_runtime_client.post("/api/v1/domains/presets/library/custom_runtime/import")
    assert import_response.status_code == 201
    assert import_response.json()["domain_id"] == "custom_runtime"
    assert import_response.json()["created"] is True

    get_domain = domains_runtime_client.get("/api/v1/domains/custom_runtime")
    assert get_domain.status_code == 200
    assert "runtime-configured assistant" in get_domain.json()["system_prompt_addon"]


def test_batch_import_all_presets_supports_dry_run_and_conflicts(domains_runtime_client: TestClient):
    dry_run_response = domains_runtime_client.post(
        "/api/v1/domains/presets/library/import-all",
        json={"dry_run": True},
    )
    assert dry_run_response.status_code == 200
    dry_run_payload = dry_run_response.json()
    assert dry_run_payload["dry_run"] is True
    assert dry_run_payload["planned_count"] == 1
    assert dry_run_payload["created_count"] == 0

    import_response = domains_runtime_client.post(
        "/api/v1/domains/presets/library/import-all",
        json={"dry_run": False, "upsert": False},
    )
    assert import_response.status_code == 200
    import_payload = import_response.json()
    assert import_payload["created_count"] == 1
    assert import_payload["conflict_count"] == 0

    conflict_response = domains_runtime_client.post(
        "/api/v1/domains/presets/library/import-all",
        json={"dry_run": False, "upsert": False},
    )
    assert conflict_response.status_code == 200
    conflict_payload = conflict_response.json()
    assert conflict_payload["created_count"] == 0
    assert conflict_payload["conflict_count"] == 1
    assert conflict_payload["items"][0]["status"] == "conflict"
