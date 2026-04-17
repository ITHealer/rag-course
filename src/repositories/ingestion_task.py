from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.ingestion_task import IngestionTask


class IngestionTaskRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, payload: dict) -> IngestionTask:
        entity = IngestionTask(**payload)
        self.session.add(entity)
        self.session.commit()
        self.session.refresh(entity)
        return entity

    def get_by_id(self, task_id: UUID) -> Optional[IngestionTask]:
        stmt = select(IngestionTask).where(IngestionTask.id == task_id)
        return self.session.scalar(stmt)

    def get_by_project_and_id(self, project_id: UUID, task_id: UUID) -> Optional[IngestionTask]:
        stmt = select(IngestionTask).where(IngestionTask.project_id == project_id, IngestionTask.id == task_id)
        return self.session.scalar(stmt)

    def list_by_project(self, project_id: UUID, limit: int = 100, offset: int = 0) -> List[IngestionTask]:
        stmt = (
            select(IngestionTask)
            .where(IngestionTask.project_id == project_id)
            .order_by(IngestionTask.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(self.session.scalars(stmt))

    def update(self, task: IngestionTask, update_data: dict) -> IngestionTask:
        for field, value in update_data.items():
            setattr(task, field, value)
        self.session.add(task)
        self.session.commit()
        self.session.refresh(task)
        return task
