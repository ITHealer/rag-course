from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Dict, List

from pydantic import BaseModel, Field


class KnowledgeMode(StrEnum):
    """Project knowledge usage mode."""

    STRICT = "strict"
    AUGMENTED = "augmented"


@dataclass(frozen=True)
class ExternalSearchPolicyConfig:
    """Configuration for external web search behavior."""

    enabled: bool = False
    require_human_approval: bool = True
    allowed_domains: List[str] = field(default_factory=list)
    max_calls_per_request: int = 1


@dataclass(frozen=True)
class ExternalSearchDecision:
    """Decision output from external search policy evaluation."""

    allowed: bool
    reason: str
    requires_human_approval: bool = False


class MetadataExtractRule(BaseModel):
    """Rule describing one metadata extraction field for a preset."""

    field: str = Field(..., min_length=1)
    prompt: str = Field(..., min_length=1)


class SearchBoostRule(BaseModel):
    """Optional retrieval scoring boost rule for one field."""

    field: str = Field(..., min_length=1)
    weight: float = Field(default=1.0, gt=0.0)


class DomainPreset(BaseModel):
    """Typed domain preset loaded from YAML."""

    id: str = Field(..., min_length=1)
    display_name: str = Field(..., min_length=1)
    mode_default: str = KnowledgeMode.STRICT.value
    system_prompt_addon: str = ""
    metadata_extract: List[MetadataExtractRule] = Field(default_factory=list)
    search_boost: List[SearchBoostRule] = Field(default_factory=list)
    routing_rules: Dict[str, Any] = Field(default_factory=dict)
    answer_policy: Dict[str, Any] = Field(default_factory=dict)
    allow_external_web_search: bool = False
    require_human_approval_for_external_search: bool = True
    allow_image_perception: bool = True
    allowed_external_domains: List[str] = Field(default_factory=list)
