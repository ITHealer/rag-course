import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID

from src.db.interfaces.postgresql import Base


class ProjectFile(Base):
    __tablename__ = "project_files"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    file_name = Column(String, nullable=False)
    file_extension = Column(String, nullable=False)
    content_type = Column(String, nullable=False, default="application/octet-stream")
    size_bytes = Column(Integer, nullable=False, default=0)
    checksum_md5 = Column(String, nullable=False)
    storage_path = Column(Text, nullable=False)
    source_uri = Column(Text, nullable=False)
    status = Column(String, nullable=False, default="uploaded", index=True)
    parser_used = Column(String, nullable=True)
    page_count = Column(Integer, nullable=False, default=0)
    chunk_count = Column(Integer, nullable=False, default=0)
    extra_metadata = Column(JSON, nullable=False, default=dict)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
