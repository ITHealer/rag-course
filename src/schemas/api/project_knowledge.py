from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ProjectFileResponse(BaseModel):
    id: UUID
    project_id: UUID
    file_name: str
    file_extension: str
    content_type: str
    size_bytes: int
    status: str
    parser_used: Optional[str] = None
    page_count: int
    chunk_count: int
    error_message: Optional[str] = None
    source_uri: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectFileUploadResponse(BaseModel):
    task_id: UUID
    project_id: UUID
    status: str
    queued_files: list[ProjectFileResponse]


class IngestionTaskResponse(BaseModel):
    id: UUID
    project_id: UUID
    status: str
    total_files: int
    processed_files: int
    failed_files: int
    progress_percent: float
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    queued_file_ids: list[str] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class ProjectChunkResponse(BaseModel):
    chunk_id: str
    chunk_index: int
    page_number: int
    chunk_text: str
    word_count: Optional[int] = None
    section_title: Optional[str] = None


class ProjectChunkListResponse(BaseModel):
    file_id: UUID
    total: int
    items: list[ProjectChunkResponse]


class ProjectKnowledgeStatsResponse(BaseModel):
    project_id: UUID
    total_files: int
    indexed_files: int
    processing_files: int
    failed_files: int
    total_chunks: int
    total_size_bytes: int
    total_tasks: int
    active_tasks: int
    file_type_breakdown: dict[str, int]
    index_document_count: int
    last_ingestion_at: Optional[datetime] = None
