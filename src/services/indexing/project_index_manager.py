from __future__ import annotations

import logging
import re
from typing import Any, Dict, List

from opensearchpy import OpenSearch

from src.config import Settings
from src.services.opensearch.index_config_hybrid import PROJECT_INDEX_PREFIX, get_universal_project_index_mapping
from src.services.vector_store.errors import IncompatibleIndexSchemaError

logger = logging.getLogger(__name__)


class ProjectIndexManager:
    """Ensure project-scoped OpenSearch indices exist with the universal schema."""

    REQUIRED_FIELD_TYPES = {
        "project_id": "keyword",
        "file_id": "keyword",
        "doc_name": "keyword",
        "page_number": "integer",
        "chunk_index": "integer",
        "chunk_text": "text",
        "source_type": "keyword",
        "source_uri": "keyword",
        "doc_type": "keyword",
        "metadata": "object",
        "embedding": "knn_vector",
    }

    def __init__(
        self,
        opensearch_client: OpenSearch,
        settings: Settings,
        index_prefix: str = PROJECT_INDEX_PREFIX,
    ):
        self.client = opensearch_client
        self.settings = settings
        self.index_prefix = index_prefix

    def get_index_name(self, project_id: str) -> str:
        normalized_id = re.sub(r"[^a-zA-Z0-9_-]+", "-", project_id.strip()).strip("-").lower()
        if not normalized_id:
            raise ValueError("project_id must contain at least one valid character")
        return f"{self.index_prefix}-{normalized_id}"

    def ensure_project_ready(self, project_id: str) -> Dict[str, Any]:
        """Create or validate project index and fail fast on incompatible schema."""
        index_name = self.get_index_name(project_id)

        if not self.client.indices.exists(index=index_name):
            self.create_index(project_id)
            return {
                "project_id": project_id,
                "index_name": index_name,
                "created": True,
                "validated": True,
                "issues": [],
            }

        validation = self.validate_schema(index_name)
        if not validation["is_compatible"]:
            repaired_fields = self.reconcile_additive_schema(index_name=index_name)
            if repaired_fields:
                logger.warning(
                    "Applied additive schema repair for project index '%s': %s",
                    index_name,
                    ", ".join(repaired_fields),
                )
                validation = self.validate_schema(index_name)

            if not validation["is_compatible"]:
                raise IncompatibleIndexSchemaError(index_name=index_name, issues=validation["issues"])

        return {
            "project_id": project_id,
            "index_name": index_name,
            "created": False,
            "validated": True,
            "issues": [],
        }

    def create_index(self, project_id: str, force: bool = False) -> Dict[str, Any]:
        """Create project index with universal schema. Never rely on auto-create mapping."""
        index_name = self.get_index_name(project_id)

        if force and self.client.indices.exists(index=index_name):
            self.client.indices.delete(index=index_name)

        if not self.client.indices.exists(index=index_name):
            mapping = get_universal_project_index_mapping(dimension=self.settings.opensearch.vector_dimension)
            self.client.indices.create(index=index_name, body=mapping)

        return {"project_id": project_id, "index_name": index_name}

    def delete_index(self, project_id: str) -> Dict[str, Any]:
        """Delete project index if present."""
        index_name = self.get_index_name(project_id)
        if self.client.indices.exists(index=index_name):
            self.client.indices.delete(index=index_name)
            return {"project_id": project_id, "index_name": index_name, "deleted": True}
        return {"project_id": project_id, "index_name": index_name, "deleted": False}

    def validate_schema(self, index_name: str) -> Dict[str, Any]:
        """Validate index mapping/settings against universal project schema."""
        issues: List[str] = []

        if not self.client.indices.exists(index=index_name):
            issues.append("Index does not exist.")
            return {"is_compatible": False, "issues": issues}

        mapping_response = self.client.indices.get_mapping(index=index_name)
        mapping = mapping_response.get(index_name, {}).get("mappings", {})
        properties = mapping.get("properties", {})

        settings_response = self.client.indices.get_settings(index=index_name)
        index_settings = settings_response.get(index_name, {}).get("settings", {}).get("index", {})
        knn_enabled = str(index_settings.get("knn", "false")).lower() == "true"
        if not knn_enabled:
            issues.append("index.knn must be true.")

        for field_name, expected_type in self.REQUIRED_FIELD_TYPES.items():
            actual_type = self._resolve_field_type(properties.get(field_name, {}))
            if actual_type != expected_type:
                issues.append(f"Field '{field_name}' expected '{expected_type}' but got '{actual_type}'.")

        embedding_dimension = properties.get("embedding", {}).get("dimension")
        expected_dimension = self.settings.opensearch.vector_dimension
        if embedding_dimension != expected_dimension:
            issues.append(
                f"Field 'embedding' dimension expected '{expected_dimension}' but got '{embedding_dimension}'."
            )

        return {"is_compatible": len(issues) == 0, "issues": issues}

    def _resolve_field_type(self, field_mapping: Dict[str, Any]) -> str | None:
        """Resolve OpenSearch field type with support for implicit object mappings.

        OpenSearch can return object fields without explicit `"type": "object"` and only
        include keys like `properties` / `dynamic`. We normalize that shape to "object".
        """
        explicit_type = field_mapping.get("type")
        if explicit_type:
            return explicit_type

        if "properties" in field_mapping or "dynamic" in field_mapping:
            return "object"

        return None

    def reconcile_additive_schema(self, index_name: str) -> List[str]:
        """Repair missing fields that can be safely added without rebuilding the index."""
        if not self.client.indices.exists(index=index_name):
            return []

        mapping_response = self.client.indices.get_mapping(index=index_name)
        current_properties = mapping_response.get(index_name, {}).get("mappings", {}).get("properties", {})
        expected_properties = get_universal_project_index_mapping(
            dimension=self.settings.opensearch.vector_dimension
        )["mappings"]["properties"]

        missing_fields = {
            field_name: expected_properties[field_name]
            for field_name in self.REQUIRED_FIELD_TYPES
            if field_name not in current_properties and field_name in expected_properties
        }
        if not missing_fields:
            return []

        self.client.indices.put_mapping(index=index_name, body={"properties": missing_fields})
        return sorted(missing_fields.keys())
