from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class DomainProfileCreateRequest(BaseModel):
    domain_id: str = Field(..., min_length=1, max_length=100)
    display_name: str = Field(..., min_length=1, max_length=255)
    mode_default: Literal["strict", "augmented"] = "strict"
    system_prompt_addon: str = ""
    metadata_extract: List[Dict[str, Any]] = Field(default_factory=list)
    search_boost: List[Dict[str, Any]] = Field(default_factory=list)
    answer_policy: Dict[str, Any] = Field(default_factory=dict)
    allow_external_web_search: bool = False
    require_human_approval_for_external_search: bool = True
    allow_image_perception: bool = True
    allowed_external_domains: List[str] = Field(default_factory=list)


class DomainProfileUpdateRequest(BaseModel):
    display_name: Optional[str] = Field(None, min_length=1, max_length=255)
    mode_default: Optional[Literal["strict", "augmented"]] = None
    system_prompt_addon: Optional[str] = None
    metadata_extract: Optional[List[Dict[str, Any]]] = None
    search_boost: Optional[List[Dict[str, Any]]] = None
    answer_policy: Optional[Dict[str, Any]] = None
    allow_external_web_search: Optional[bool] = None
    require_human_approval_for_external_search: Optional[bool] = None
    allow_image_perception: Optional[bool] = None
    allowed_external_domains: Optional[List[str]] = None
    is_active: Optional[bool] = None


class DomainProfileResponse(BaseModel):
    id: UUID
    domain_id: str
    display_name: str
    mode_default: str
    system_prompt_addon: str
    metadata_extract: List[Dict[str, Any]]
    search_boost: List[Dict[str, Any]]
    answer_policy: Dict[str, Any]
    allow_external_web_search: bool
    require_human_approval_for_external_search: bool
    allow_image_perception: bool
    allowed_external_domains: List[str]
    version: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DomainDeleteResponse(BaseModel):
    domain_id: str
    deleted: bool


class DomainPromptResponse(BaseModel):
    domain_id: str
    system_prompt_addon: str
    answer_policy: Dict[str, Any]
    mode_default: str
    version: int
    updated_at: datetime


class DomainPromptUpdateRequest(BaseModel):
    system_prompt_addon: str = Field(..., min_length=1)
    answer_policy: Dict[str, Any] = Field(default_factory=dict)
    mode_default: Optional[Literal["strict", "augmented"]] = None


class DomainConfigUpsertRequest(BaseModel):
    display_name: str = Field(..., min_length=1, max_length=255)
    mode_default: Literal["strict", "augmented"] = "strict"
    system_prompt_addon: str = ""
    metadata_extract: List[Dict[str, Any]] = Field(default_factory=list)
    search_boost: List[Dict[str, Any]] = Field(default_factory=list)
    answer_policy: Dict[str, Any] = Field(default_factory=dict)
    allow_external_web_search: bool = False
    require_human_approval_for_external_search: bool = True
    allow_image_perception: bool = True
    allowed_external_domains: List[str] = Field(default_factory=list)
    is_active: bool = True


class PresetLibraryItemResponse(BaseModel):
    id: str
    display_name: str
    mode_default: str
    allow_external_web_search: bool
    require_human_approval_for_external_search: bool
    allow_image_perception: bool


class DomainImportPresetResponse(BaseModel):
    domain_id: str
    imported_from_preset: str
    created: bool
    version: int


class BatchPresetImportRequest(BaseModel):
    upsert: bool = False
    dry_run: bool = False
    preset_ids: Optional[List[str]] = None


class BatchPresetImportItemResponse(BaseModel):
    preset_id: str
    domain_id: str
    status: Literal["created", "updated", "conflict", "planned"]
    version: Optional[int] = None
    message: str = ""


class BatchPresetImportResponse(BaseModel):
    total_presets: int
    created_count: int
    updated_count: int
    conflict_count: int
    planned_count: int
    dry_run: bool
    items: List[BatchPresetImportItemResponse] = Field(default_factory=list)
