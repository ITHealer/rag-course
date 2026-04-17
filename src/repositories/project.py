from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.project import Project


class ProjectRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, payload: dict) -> Project:
        entity = Project(**payload)
        self.session.add(entity)
        self.session.commit()
        self.session.refresh(entity)
        return entity

    def get_by_id(self, project_id: UUID) -> Optional[Project]:
        stmt = select(Project).where(Project.id == project_id)
        return self.session.scalar(stmt)

    def list(self, limit: int = 100, offset: int = 0) -> List[Project]:
        stmt = select(Project).order_by(Project.updated_at.desc()).limit(limit).offset(offset)
        return list(self.session.scalars(stmt))

    def update(self, project: Project, update_data: dict) -> Project:
        for field, value in update_data.items():
            setattr(project, field, value)
        self.session.add(project)
        self.session.commit()
        self.session.refresh(project)
        return project

    def delete(self, project: Project) -> None:
        self.session.delete(project)
        self.session.commit()
