from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.domain_profile import DomainProfile


class DomainProfileRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, payload: dict) -> DomainProfile:
        entity = DomainProfile(**payload)
        self.session.add(entity)
        self.session.commit()
        self.session.refresh(entity)
        return entity

    def get_by_id(self, domain_profile_id: UUID) -> Optional[DomainProfile]:
        stmt = select(DomainProfile).where(DomainProfile.id == domain_profile_id)
        return self.session.scalar(stmt)

    def get_by_domain_id(self, domain_id: str) -> Optional[DomainProfile]:
        stmt = select(DomainProfile).where(DomainProfile.domain_id == domain_id)
        return self.session.scalar(stmt)

    def list(self, limit: int = 100, offset: int = 0) -> List[DomainProfile]:
        stmt = select(DomainProfile).order_by(DomainProfile.updated_at.desc()).limit(limit).offset(offset)
        return list(self.session.scalars(stmt))

    def update(self, domain_profile: DomainProfile, update_data: dict) -> DomainProfile:
        if update_data:
            current_version = int(getattr(domain_profile, "version", 1) or 1)
            update_data["version"] = current_version + 1
        for field, value in update_data.items():
            setattr(domain_profile, field, value)
        self.session.add(domain_profile)
        self.session.commit()
        self.session.refresh(domain_profile)
        return domain_profile

    def delete(self, domain_profile: DomainProfile) -> None:
        self.session.delete(domain_profile)
        self.session.commit()
