import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID

from src.db.interfaces.postgresql import Base


class DomainProfile(Base):
    __tablename__ = "domain_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    domain_id = Column(String, unique=True, nullable=False, index=True)
    display_name = Column(String, nullable=False)
    mode_default = Column(String, nullable=False, default="strict")
    system_prompt_addon = Column(Text, nullable=False, default="")
    metadata_extract = Column(JSON, nullable=False, default=list)
    search_boost = Column(JSON, nullable=False, default=list)
    answer_policy = Column(JSON, nullable=False, default=dict)
    allow_external_web_search = Column(Boolean, nullable=False, default=False)
    require_human_approval_for_external_search = Column(Boolean, nullable=False, default=True)
    allow_image_perception = Column(Boolean, nullable=False, default=True)
    allowed_external_domains = Column(JSON, nullable=False, default=list)
    version = Column(Integer, nullable=False, default=1)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
