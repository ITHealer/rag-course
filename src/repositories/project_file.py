from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.project_file import ProjectFile


class ProjectFileRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, payload: dict) -> ProjectFile:
        entity = ProjectFile(**payload)
        self.session.add(entity)
        self.session.commit()
        self.session.refresh(entity)
        return entity

    def get_by_id(self, file_id: UUID) -> Optional[ProjectFile]:
        stmt = select(ProjectFile).where(ProjectFile.id == file_id)
        return self.session.scalar(stmt)

    def get_by_project_and_id(self, project_id: UUID, file_id: UUID) -> Optional[ProjectFile]:
        stmt = select(ProjectFile).where(ProjectFile.project_id == project_id, ProjectFile.id == file_id)
        return self.session.scalar(stmt)

    def list_by_project(
        self,
        project_id: UUID,
        limit: int = 100,
        offset: int = 0,
        status: Optional[str] = None,
    ) -> List[ProjectFile]:
        stmt = select(ProjectFile).where(ProjectFile.project_id == project_id)
        if status:
            stmt = stmt.where(ProjectFile.status == status)
        stmt = stmt.order_by(ProjectFile.updated_at.desc()).limit(limit).offset(offset)
        return list(self.session.scalars(stmt))

    def list_by_ids(self, project_id: UUID, file_ids: list[UUID]) -> List[ProjectFile]:
        if not file_ids:
            return []
        stmt = select(ProjectFile).where(ProjectFile.project_id == project_id, ProjectFile.id.in_(file_ids))
        return list(self.session.scalars(stmt))

    def update(self, project_file: ProjectFile, update_data: dict) -> ProjectFile:
        for field, value in update_data.items():
            setattr(project_file, field, value)
        self.session.add(project_file)
        self.session.commit()
        self.session.refresh(project_file)
        return project_file
