from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from src.dependencies import DomainProfileRepoDep, OpenSearchDep, ProjectRepoDep, SettingsDep
from src.schemas.api.projects import (
    ProjectCreateRequest,
    ProjectDeleteResponse,
    ProjectIndexDeleteResponse,
    ProjectIndexEnsureResponse,
    ProjectIndexValidationResponse,
    ProjectResponse,
    ProjectUpdateRequest,
)
from src.services.indexing.project_index_manager import ProjectIndexManager
from src.services.vector_store.errors import IncompatibleIndexSchemaError

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


def _build_index_manager(opensearch_client: OpenSearchDep, settings: SettingsDep) -> ProjectIndexManager:
    if not hasattr(opensearch_client, "client"):
        raise HTTPException(status_code=400, detail="Current vector store does not support project index management.")
    return ProjectIndexManager(opensearch_client=opensearch_client.client, settings=settings)


@router.post("", response_model=ProjectResponse, status_code=201)
def create_project(
    request: ProjectCreateRequest,
    project_repository: ProjectRepoDep,
    domain_repository: DomainProfileRepoDep,
) -> ProjectResponse:
    domain = domain_repository.get_by_domain_id(request.domain_id)
    if not domain:
        raise HTTPException(status_code=404, detail=f"Domain '{request.domain_id}' not found.")

    project = project_repository.create(request.model_dump())
    return ProjectResponse.model_validate(project)


@router.get("", response_model=list[ProjectResponse])
def list_projects(
    project_repository: ProjectRepoDep,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> list[ProjectResponse]:
    projects = project_repository.list(limit=limit, offset=offset)
    return [ProjectResponse.model_validate(project) for project in projects]


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: UUID,
    project_repository: ProjectRepoDep,
) -> ProjectResponse:
    project = project_repository.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found.")
    return ProjectResponse.model_validate(project)


@router.patch("/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: UUID,
    request: ProjectUpdateRequest,
    project_repository: ProjectRepoDep,
    domain_repository: DomainProfileRepoDep,
) -> ProjectResponse:
    project = project_repository.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found.")

    update_data = request.model_dump(exclude_unset=True)
    if "domain_id" in update_data:
        domain = domain_repository.get_by_domain_id(update_data["domain_id"])
        if not domain:
            raise HTTPException(status_code=404, detail=f"Domain '{update_data['domain_id']}' not found.")

    if not update_data:
        return ProjectResponse.model_validate(project)

    updated = project_repository.update(project=project, update_data=update_data)
    return ProjectResponse.model_validate(updated)


@router.delete("/{project_id}", response_model=ProjectDeleteResponse)
def delete_project(
    project_id: UUID,
    project_repository: ProjectRepoDep,
) -> ProjectDeleteResponse:
    project = project_repository.get_by_id(project_id)
    if not project:
        return ProjectDeleteResponse(project_id=project_id, deleted=False)

    project_repository.delete(project=project)
    return ProjectDeleteResponse(project_id=project_id, deleted=True)


@router.post("/{project_id}/index/ensure", response_model=ProjectIndexEnsureResponse)
def ensure_project_index(
    project_id: str,
    opensearch_client: OpenSearchDep,
    settings: SettingsDep,
) -> ProjectIndexEnsureResponse:
    manager = _build_index_manager(opensearch_client=opensearch_client, settings=settings)
    try:
        result = manager.ensure_project_ready(project_id=project_id)
        return ProjectIndexEnsureResponse(**result)
    except IncompatibleIndexSchemaError as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "error_code": "INDEX_SCHEMA_INCOMPATIBLE",
                "message": str(exc),
                "issues": exc.issues,
            },
        ) from exc


@router.get("/{project_id}/index/validate", response_model=ProjectIndexValidationResponse)
def validate_project_index(
    project_id: str,
    opensearch_client: OpenSearchDep,
    settings: SettingsDep,
) -> ProjectIndexValidationResponse:
    manager = _build_index_manager(opensearch_client=opensearch_client, settings=settings)
    index_name = manager.get_index_name(project_id)
    validation = manager.validate_schema(index_name=index_name)
    return ProjectIndexValidationResponse(
        project_id=project_id,
        index_name=index_name,
        is_compatible=validation["is_compatible"],
        issues=validation["issues"],
    )


@router.delete("/{project_id}/index", response_model=ProjectIndexDeleteResponse)
def delete_project_index(
    project_id: str,
    opensearch_client: OpenSearchDep,
    settings: SettingsDep,
) -> ProjectIndexDeleteResponse:
    manager = _build_index_manager(opensearch_client=opensearch_client, settings=settings)
    result = manager.delete_index(project_id=project_id)
    return ProjectIndexDeleteResponse(**result)
