from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile

from src.dependencies import (
    IngestionTaskRepoDep,
    ProjectFileRepoDep,
    ProjectKnowledgeDep,
    ProjectRepoDep,
)
from src.schemas.api.project_knowledge import (
    IngestionTaskResponse,
    ProjectChunkListResponse,
    ProjectChunkResponse,
    ProjectFileResponse,
    ProjectFileUploadResponse,
    ProjectKnowledgeStatsResponse,
)

router = APIRouter(prefix="/api/v1/projects", tags=["project-knowledge"])


def _task_to_response(task) -> IngestionTaskResponse:
    progress_percent = 0.0
    if task.total_files > 0:
        progress_percent = round((task.processed_files / task.total_files) * 100, 2)
    return IngestionTaskResponse(
        id=task.id,
        project_id=task.project_id,
        status=task.status,
        total_files=task.total_files,
        processed_files=task.processed_files,
        failed_files=task.failed_files,
        progress_percent=progress_percent,
        error_message=task.error_message,
        started_at=task.started_at,
        completed_at=task.completed_at,
        created_at=task.created_at,
        updated_at=task.updated_at,
        queued_file_ids=list(task.queued_file_ids or []),
    )


def _file_to_response(file_record) -> ProjectFileResponse:
    return ProjectFileResponse.model_validate(file_record)


@router.post("/{project_id}/files/upload", response_model=ProjectFileUploadResponse, status_code=202)
async def upload_project_files(
    project_id: UUID,
    project_repository: ProjectRepoDep,
    project_file_repository: ProjectFileRepoDep,
    ingestion_task_repository: IngestionTaskRepoDep,
    project_knowledge_service: ProjectKnowledgeDep,
    files: list[UploadFile] = File(...),
    auto_start: bool = Form(True),
) -> ProjectFileUploadResponse:
    project = project_repository.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found.")

    try:
        queued_files = await project_knowledge_service.save_uploaded_files(
            project_id=project_id,
            files=files,
            project_file_repository=project_file_repository,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    task = project_knowledge_service.create_ingestion_task(
        project_id=project_id,
        file_ids=[file_record.id for file_record in queued_files],
        ingestion_task_repository=ingestion_task_repository,
    )
    if auto_start:
        project_knowledge_service.start_ingestion_task(task.id)

    return ProjectFileUploadResponse(
        task_id=task.id,
        project_id=project_id,
        status=task.status,
        queued_files=[_file_to_response(file_record) for file_record in queued_files],
    )


@router.get("/{project_id}/files", response_model=list[ProjectFileResponse])
def list_project_files(
    project_id: UUID,
    project_repository: ProjectRepoDep,
    project_file_repository: ProjectFileRepoDep,
    status: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[ProjectFileResponse]:
    project = project_repository.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found.")

    files = project_file_repository.list_by_project(project_id=project_id, limit=limit, offset=offset, status=status)
    return [_file_to_response(file_record) for file_record in files]


@router.get("/{project_id}/files/{file_id}", response_model=ProjectFileResponse)
def get_project_file(
    project_id: UUID,
    file_id: UUID,
    project_repository: ProjectRepoDep,
    project_file_repository: ProjectFileRepoDep,
) -> ProjectFileResponse:
    project = project_repository.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found.")

    file_record = project_file_repository.get_by_project_and_id(project_id=project_id, file_id=file_id)
    if not file_record:
        raise HTTPException(status_code=404, detail=f"File '{file_id}' not found in project '{project_id}'.")
    return _file_to_response(file_record)


@router.get("/{project_id}/files/{file_id}/chunks", response_model=ProjectChunkListResponse)
def get_project_file_chunks(
    project_id: UUID,
    file_id: UUID,
    project_repository: ProjectRepoDep,
    project_file_repository: ProjectFileRepoDep,
    project_knowledge_service: ProjectKnowledgeDep,
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ProjectChunkListResponse:
    project = project_repository.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found.")

    file_record = project_file_repository.get_by_project_and_id(project_id=project_id, file_id=file_id)
    if not file_record:
        raise HTTPException(status_code=404, detail=f"File '{file_id}' not found in project '{project_id}'.")

    result = project_knowledge_service.get_file_chunks(
        project_id=project_id,
        file_id=file_id,
        limit=limit,
        offset=offset,
    )
    return ProjectChunkListResponse(
        file_id=file_id,
        total=result["total"],
        items=[ProjectChunkResponse(**item) for item in result["items"]],
    )


@router.get("/{project_id}/ingestion/tasks", response_model=list[IngestionTaskResponse])
def list_ingestion_tasks(
    project_id: UUID,
    project_repository: ProjectRepoDep,
    ingestion_task_repository: IngestionTaskRepoDep,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[IngestionTaskResponse]:
    project = project_repository.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found.")

    tasks = ingestion_task_repository.list_by_project(project_id=project_id, limit=limit, offset=offset)
    return [_task_to_response(task) for task in tasks]


@router.get("/{project_id}/ingestion/tasks/{task_id}", response_model=IngestionTaskResponse)
def get_ingestion_task(
    project_id: UUID,
    task_id: UUID,
    project_repository: ProjectRepoDep,
    ingestion_task_repository: IngestionTaskRepoDep,
) -> IngestionTaskResponse:
    project = project_repository.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found.")

    task = ingestion_task_repository.get_by_project_and_id(project_id=project_id, task_id=task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found in project '{project_id}'.")
    return _task_to_response(task)


@router.post("/{project_id}/ingestion/tasks/{task_id}/start", response_model=IngestionTaskResponse)
async def start_ingestion_task(
    project_id: UUID,
    task_id: UUID,
    project_repository: ProjectRepoDep,
    ingestion_task_repository: IngestionTaskRepoDep,
    project_knowledge_service: ProjectKnowledgeDep,
) -> IngestionTaskResponse:
    project = project_repository.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found.")

    task = ingestion_task_repository.get_by_project_and_id(project_id=project_id, task_id=task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found in project '{project_id}'.")

    # Idempotent start: avoid restarting completed/running jobs from UI retries.
    if task.status in {"running", "completed", "completed_with_errors"}:
        return _task_to_response(task)

    project_knowledge_service.start_ingestion_task(task.id)
    refreshed = ingestion_task_repository.get_by_project_and_id(project_id=project_id, task_id=task_id)
    return _task_to_response(refreshed or task)


@router.get("/{project_id}/knowledge/stats", response_model=ProjectKnowledgeStatsResponse)
def get_project_knowledge_stats(
    project_id: UUID,
    project_repository: ProjectRepoDep,
    project_file_repository: ProjectFileRepoDep,
    ingestion_task_repository: IngestionTaskRepoDep,
    project_knowledge_service: ProjectKnowledgeDep,
) -> ProjectKnowledgeStatsResponse:
    project = project_repository.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found.")

    stats = project_knowledge_service.get_project_stats(
        project_id=project_id,
        project_file_repository=project_file_repository,
        ingestion_task_repository=ingestion_task_repository,
    )
    return ProjectKnowledgeStatsResponse(**stats)
