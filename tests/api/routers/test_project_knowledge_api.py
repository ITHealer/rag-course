from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI, UploadFile
from fastapi.testclient import TestClient

from src import dependencies
from src.routers.project_knowledge import router


class InMemoryProjectRepository:
    def __init__(self):
        self._items = {}

    def add(self, project_id: UUID, domain_id: str = "default_domain"):
        now = datetime.now(timezone.utc)
        self._items[project_id] = SimpleNamespace(
            id=project_id,
            name="Demo Project",
            domain_id=domain_id,
            mode="strict",
            description="",
            is_active=True,
            created_at=now,
            updated_at=now,
        )

    def get_by_id(self, project_id: UUID):
        return self._items.get(project_id)


class InMemoryProjectFileRepository:
    def __init__(self):
        self._items = {}

    def create(self, payload: dict):
        now = datetime.now(timezone.utc)
        file_id = payload.get("id", uuid4())
        entity = SimpleNamespace(
            id=file_id,
            project_id=payload["project_id"],
            file_name=payload["file_name"],
            file_extension=payload["file_extension"],
            content_type=payload.get("content_type", "application/octet-stream"),
            size_bytes=payload.get("size_bytes", 0),
            checksum_md5=payload.get("checksum_md5", ""),
            storage_path=payload.get("storage_path", ""),
            source_uri=payload.get("source_uri", ""),
            status=payload.get("status", "uploaded"),
            parser_used=payload.get("parser_used"),
            page_count=payload.get("page_count", 0),
            chunk_count=payload.get("chunk_count", 0),
            extra_metadata=payload.get("extra_metadata", {}),
            error_message=payload.get("error_message"),
            created_at=now,
            updated_at=now,
        )
        self._items[file_id] = entity
        return entity

    def get_by_id(self, file_id: UUID):
        return self._items.get(file_id)

    def get_by_project_and_id(self, project_id: UUID, file_id: UUID):
        entity = self._items.get(file_id)
        if entity and entity.project_id == project_id:
            return entity
        return None

    def list_by_project(self, project_id: UUID, limit: int = 100, offset: int = 0, status: str | None = None):
        items = [item for item in self._items.values() if item.project_id == project_id]
        if status:
            items = [item for item in items if item.status == status]
        items.sort(key=lambda item: item.updated_at, reverse=True)
        return items[offset : offset + limit]

    def update(self, file_record, update_data: dict):
        for key, value in update_data.items():
            setattr(file_record, key, value)
        file_record.updated_at = datetime.now(timezone.utc)
        return file_record


class InMemoryIngestionTaskRepository:
    def __init__(self):
        self._items = {}

    def create(self, payload: dict):
        now = datetime.now(timezone.utc)
        task_id = payload.get("id", uuid4())
        entity = SimpleNamespace(
            id=task_id,
            project_id=payload["project_id"],
            status=payload.get("status", "pending"),
            total_files=payload.get("total_files", 0),
            processed_files=payload.get("processed_files", 0),
            failed_files=payload.get("failed_files", 0),
            queued_file_ids=payload.get("queued_file_ids", []),
            error_message=payload.get("error_message"),
            started_at=payload.get("started_at"),
            completed_at=payload.get("completed_at"),
            created_at=now,
            updated_at=now,
        )
        self._items[task_id] = entity
        return entity

    def get_by_id(self, task_id: UUID):
        return self._items.get(task_id)

    def get_by_project_and_id(self, project_id: UUID, task_id: UUID):
        entity = self._items.get(task_id)
        if entity and entity.project_id == project_id:
            return entity
        return None

    def list_by_project(self, project_id: UUID, limit: int = 100, offset: int = 0):
        items = [item for item in self._items.values() if item.project_id == project_id]
        items.sort(key=lambda item: item.created_at, reverse=True)
        return items[offset : offset + limit]

    def update(self, task, update_data: dict):
        for key, value in update_data.items():
            setattr(task, key, value)
        task.updated_at = datetime.now(timezone.utc)
        return task


class FakeProjectKnowledgeService:
    async def save_uploaded_files(self, project_id: UUID, files: list[UploadFile], project_file_repository):
        created = []
        for upload in files:
            content = await upload.read()
            await upload.close()
            extension = "." + upload.filename.split(".")[-1].lower()
            created.append(
                project_file_repository.create(
                    {
                        "project_id": project_id,
                        "file_name": upload.filename,
                        "file_extension": extension,
                        "content_type": upload.content_type or "application/octet-stream",
                        "size_bytes": len(content),
                        "checksum_md5": "fake-md5",
                        "storage_path": "/tmp/fake",
                        "source_uri": "file:///tmp/fake",
                        "status": "uploaded",
                        "page_count": 1,
                        "chunk_count": 0,
                        "extra_metadata": {},
                    }
                )
            )
        return created

    def create_ingestion_task(self, project_id: UUID, file_ids: list[UUID], ingestion_task_repository):
        return ingestion_task_repository.create(
            {
                "project_id": project_id,
                "status": "pending",
                "total_files": len(file_ids),
                "processed_files": 0,
                "failed_files": 0,
                "queued_file_ids": [str(file_id) for file_id in file_ids],
                "error_message": None,
                "started_at": None,
                "completed_at": None,
            }
        )

    def start_ingestion_task(self, task_id: UUID):
        asyncio.get_running_loop()
        return None

    def get_file_chunks(self, project_id: UUID, file_id: UUID, limit: int = 20, offset: int = 0):
        return {
            "total": 1,
            "items": [
                {
                    "chunk_id": f"{file_id}-0",
                    "chunk_index": 0,
                    "page_number": 1,
                    "chunk_text": "Sample chunk text",
                    "word_count": 3,
                    "section_title": None,
                }
            ],
        }

    def get_project_stats(self, project_id: UUID, project_file_repository, ingestion_task_repository):
        files = project_file_repository.list_by_project(project_id=project_id, limit=1000, offset=0)
        tasks = ingestion_task_repository.list_by_project(project_id=project_id, limit=1000, offset=0)
        return {
            "project_id": project_id,
            "total_files": len(files),
            "indexed_files": 0,
            "processing_files": len(files),
            "failed_files": 0,
            "total_chunks": sum(file_record.chunk_count for file_record in files),
            "total_size_bytes": sum(file_record.size_bytes for file_record in files),
            "total_tasks": len(tasks),
            "active_tasks": len(tasks),
            "file_type_breakdown": {".txt": len(files)} if files else {},
            "index_document_count": 0,
            "last_ingestion_at": None,
        }


@pytest.fixture
def project_knowledge_client():
    app = FastAPI()
    app.include_router(router)

    project_repo = InMemoryProjectRepository()
    file_repo = InMemoryProjectFileRepository()
    task_repo = InMemoryIngestionTaskRepository()
    service = FakeProjectKnowledgeService()

    project_id = uuid4()
    project_repo.add(project_id)

    app.dependency_overrides[dependencies.get_project_repository] = lambda: project_repo
    app.dependency_overrides[dependencies.get_project_file_repository] = lambda: file_repo
    app.dependency_overrides[dependencies.get_ingestion_task_repository] = lambda: task_repo
    app.dependency_overrides[dependencies.get_project_knowledge_service] = lambda: service

    yield TestClient(app), project_id

    app.dependency_overrides.clear()


def test_upload_files_and_list_resources(project_knowledge_client: tuple[TestClient, UUID]):
    client, project_id = project_knowledge_client
    upload_response = client.post(
        f"/api/v1/projects/{project_id}/files/upload",
        data={"auto_start": "true"},
        files=[("files", ("candidate_profile.txt", b"Python engineer with 5 years experience", "text/plain"))],
    )

    assert upload_response.status_code == 202
    payload = upload_response.json()
    assert payload["project_id"] == str(project_id)
    assert len(payload["queued_files"]) == 1
    file_id = payload["queued_files"][0]["id"]
    task_id = payload["task_id"]

    files_response = client.get(f"/api/v1/projects/{project_id}/files")
    assert files_response.status_code == 200
    assert len(files_response.json()) == 1

    file_detail_response = client.get(f"/api/v1/projects/{project_id}/files/{file_id}")
    assert file_detail_response.status_code == 200
    assert file_detail_response.json()["file_name"] == "candidate_profile.txt"

    tasks_response = client.get(f"/api/v1/projects/{project_id}/ingestion/tasks")
    assert tasks_response.status_code == 200
    assert len(tasks_response.json()) == 1

    task_detail_response = client.get(f"/api/v1/projects/{project_id}/ingestion/tasks/{task_id}")
    assert task_detail_response.status_code == 200
    assert task_detail_response.json()["status"] == "pending"

    start_response = client.post(f"/api/v1/projects/{project_id}/ingestion/tasks/{task_id}/start")
    assert start_response.status_code == 200


def test_project_file_chunks_and_stats(project_knowledge_client: tuple[TestClient, UUID]):
    client, project_id = project_knowledge_client
    upload_response = client.post(
        f"/api/v1/projects/{project_id}/files/upload",
        data={"auto_start": "true"},
        files=[("files", ("guide.txt", b"Step 1: login. Step 2: click dashboard.", "text/plain"))],
    )
    assert upload_response.status_code == 202
    file_id = upload_response.json()["queued_files"][0]["id"]

    chunks_response = client.get(f"/api/v1/projects/{project_id}/files/{file_id}/chunks")
    assert chunks_response.status_code == 200
    assert chunks_response.json()["total"] == 1
    assert chunks_response.json()["items"][0]["chunk_text"] == "Sample chunk text"

    stats_response = client.get(f"/api/v1/projects/{project_id}/knowledge/stats")
    assert stats_response.status_code == 200
    stats = stats_response.json()
    assert stats["total_files"] == 1
    assert stats["total_tasks"] == 1
