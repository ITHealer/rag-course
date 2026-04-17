from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ProjectCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    domain_id: str = Field(..., min_length=1, max_length=100)
    mode: Literal["strict", "augmented"] = "strict"
    description: str = ""


class ProjectUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    domain_id: Optional[str] = Field(None, min_length=1, max_length=100)
    mode: Optional[Literal["strict", "augmented"]] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class ProjectResponse(BaseModel):
    id: UUID
    name: str
    domain_id: str
    mode: str
    description: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectDeleteResponse(BaseModel):
    project_id: UUID
    deleted: bool


class ProjectIndexEnsureResponse(BaseModel):
    project_id: str = Field(..., description="Project identifier")
    index_name: str = Field(..., description="Resolved OpenSearch index name")
    created: bool = Field(..., description="Whether a new index was created")
    validated: bool = Field(..., description="Whether schema validation passed")
    issues: List[str] = Field(default_factory=list, description="Validation issues if any")


class ProjectIndexValidationResponse(BaseModel):
    project_id: str = Field(..., description="Project identifier")
    index_name: str = Field(..., description="Resolved OpenSearch index name")
    is_compatible: bool = Field(..., description="Whether index schema is compatible")
    issues: List[str] = Field(default_factory=list, description="Schema incompatibility details")


class ProjectIndexDeleteResponse(BaseModel):
    project_id: str = Field(..., description="Project identifier")
    index_name: str = Field(..., description="Resolved OpenSearch index name")
    deleted: bool = Field(..., description="Whether the index was deleted")
