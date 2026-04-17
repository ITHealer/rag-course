from unittest.mock import Mock

import pytest

from src.config import Settings
from src.services.indexing.project_index_manager import ProjectIndexManager
from src.services.vector_store.errors import IncompatibleIndexSchemaError


def _build_manager(indices_mock: Mock) -> ProjectIndexManager:
    client = Mock()
    client.indices = indices_mock
    return ProjectIndexManager(opensearch_client=client, settings=Settings())


def test_ensure_project_ready_creates_index_when_missing():
    indices = Mock()
    indices.exists.side_effect = [False, False]
    manager = _build_manager(indices)

    result = manager.ensure_project_ready("Recruitment-Q3")

    assert result["created"] is True
    assert result["validated"] is True
    assert result["index_name"] == "project-recruitment-q3"
    indices.create.assert_called_once()


def test_ensure_project_ready_raises_on_incompatible_schema():
    indices = Mock()
    indices.exists.return_value = True
    indices.get_mapping.return_value = {
        "project-demo": {
            "mappings": {
                "properties": {
                    "project_id": {"type": "keyword"},
                    "file_id": {"type": "keyword"},
                    "doc_name": {"type": "keyword"},
                    "page_number": {"type": "integer"},
                    "chunk_index": {"type": "long"},
                    "chunk_text": {"type": "text"},
                    "source_type": {"type": "keyword"},
                    "source_uri": {"type": "keyword"},
                    "doc_type": {"type": "keyword"},
                    "metadata": {"type": "object"},
                    "embedding": {"type": "float"},
                }
            }
        }
    }
    indices.get_settings.return_value = {"project-demo": {"settings": {"index": {"knn": "false"}}}}
    manager = _build_manager(indices)

    with pytest.raises(IncompatibleIndexSchemaError):
        manager.ensure_project_ready("demo")


def test_validate_schema_success():
    settings = Settings()
    indices = Mock()
    indices.exists.return_value = True
    indices.get_mapping.return_value = {
        "project-demo": {
            "mappings": {
                "properties": {
                    "project_id": {"type": "keyword"},
                    "file_id": {"type": "keyword"},
                    "doc_name": {"type": "keyword"},
                    "page_number": {"type": "integer"},
                    "chunk_index": {"type": "integer"},
                    "chunk_text": {"type": "text"},
                    "source_type": {"type": "keyword"},
                    "source_uri": {"type": "keyword"},
                    "doc_type": {"type": "keyword"},
                    "metadata": {"type": "object"},
                    "embedding": {"type": "knn_vector", "dimension": settings.opensearch.vector_dimension},
                }
            }
        }
    }
    indices.get_settings.return_value = {"project-demo": {"settings": {"index": {"knn": "true"}}}}

    manager = _build_manager(indices)
    result = manager.validate_schema("project-demo")

    assert result["is_compatible"] is True
    assert result["issues"] == []


def test_validate_schema_accepts_implicit_object_mapping():
    settings = Settings()
    indices = Mock()
    indices.exists.return_value = True
    indices.get_mapping.return_value = {
        "project-demo": {
            "mappings": {
                "properties": {
                    "project_id": {"type": "keyword"},
                    "file_id": {"type": "keyword"},
                    "doc_name": {"type": "keyword"},
                    "page_number": {"type": "integer"},
                    "chunk_index": {"type": "integer"},
                    "chunk_text": {"type": "text"},
                    "source_type": {"type": "keyword"},
                    "source_uri": {"type": "keyword"},
                    "doc_type": {"type": "keyword"},
                    "metadata": {"dynamic": "true", "properties": {"word_count": {"type": "long"}}},
                    "embedding": {"type": "knn_vector", "dimension": settings.opensearch.vector_dimension},
                }
            }
        }
    }
    indices.get_settings.return_value = {"project-demo": {"settings": {"index": {"knn": "true"}}}}

    manager = _build_manager(indices)
    result = manager.validate_schema("project-demo")

    assert result["is_compatible"] is True
    assert result["issues"] == []


def test_ensure_project_ready_repairs_missing_metadata_field():
    settings = Settings()
    indices = Mock()
    indices.exists.return_value = True
    indices.get_mapping.side_effect = [
        {
            "project-demo": {
                "mappings": {
                    "properties": {
                        "project_id": {"type": "keyword"},
                        "file_id": {"type": "keyword"},
                        "doc_name": {"type": "keyword"},
                        "page_number": {"type": "integer"},
                        "chunk_index": {"type": "integer"},
                        "chunk_text": {"type": "text"},
                        "source_type": {"type": "keyword"},
                        "source_uri": {"type": "keyword"},
                        "doc_type": {"type": "keyword"},
                        "embedding": {"type": "knn_vector", "dimension": settings.opensearch.vector_dimension},
                    }
                }
            }
        },
        {
            "project-demo": {
                "mappings": {
                    "properties": {
                        "project_id": {"type": "keyword"},
                        "file_id": {"type": "keyword"},
                        "doc_name": {"type": "keyword"},
                        "page_number": {"type": "integer"},
                        "chunk_index": {"type": "integer"},
                        "chunk_text": {"type": "text"},
                        "source_type": {"type": "keyword"},
                        "source_uri": {"type": "keyword"},
                        "doc_type": {"type": "keyword"},
                        "embedding": {"type": "knn_vector", "dimension": settings.opensearch.vector_dimension},
                    }
                }
            }
        },
        {
            "project-demo": {
                "mappings": {
                    "properties": {
                        "project_id": {"type": "keyword"},
                        "file_id": {"type": "keyword"},
                        "doc_name": {"type": "keyword"},
                        "page_number": {"type": "integer"},
                        "chunk_index": {"type": "integer"},
                        "chunk_text": {"type": "text"},
                        "source_type": {"type": "keyword"},
                        "source_uri": {"type": "keyword"},
                        "doc_type": {"type": "keyword"},
                        "metadata": {"type": "object"},
                        "embedding": {"type": "knn_vector", "dimension": settings.opensearch.vector_dimension},
                    }
                }
            }
        },
    ]
    indices.get_settings.return_value = {"project-demo": {"settings": {"index": {"knn": "true"}}}}

    manager = _build_manager(indices)
    result = manager.ensure_project_ready("demo")

    assert result["created"] is False
    assert result["validated"] is True
    indices.put_mapping.assert_called_once()
    put_mapping_body = indices.put_mapping.call_args.kwargs["body"]
    assert put_mapping_body == {"properties": {"metadata": {"type": "object", "dynamic": True}}}
