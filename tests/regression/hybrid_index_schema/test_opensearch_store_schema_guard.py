from unittest.mock import MagicMock

import pytest

from src.config import Settings
from src.services.vector_store.errors import IncompatibleIndexSchemaError, IndexNotReadyError
from src.services.vector_store.opensearch_store import OpenSearchStore


def _build_store() -> OpenSearchStore:
    settings = Settings()
    store = OpenSearchStore(host="http://localhost:9200", settings=settings)
    store.client = MagicMock()
    return store


def _incompatible_mapping(index_name: str) -> dict:
    return {
        index_name: {
            "mappings": {
                "properties": {
                    "embedding": {"type": "float"},
                    "categories": {"type": "text"},
                    "arxiv_id": {"type": "text"},
                    "paper_id": {"type": "text"},
                    "chunk_index": {"type": "long"},
                    "published_date": {"type": "date"},
                }
            }
        }
    }


def _incompatible_settings(index_name: str) -> dict:
    return {
        index_name: {
            "settings": {
                "index": {
                    "number_of_shards": "1",
                    "number_of_replicas": "1",
                }
            }
        }
    }


def test_validate_index_compatibility_detects_wrong_schema():
    store = _build_store()
    store.client.indices.exists.return_value = True
    store.client.indices.get_mapping.return_value = _incompatible_mapping(store.index_name)
    store.client.indices.get_settings.return_value = _incompatible_settings(store.index_name)

    compatibility = store.validate_index_compatibility()

    assert compatibility["is_compatible"] is False
    assert any("embedding" in issue and "knn_vector" in issue for issue in compatibility["issues"])
    assert any("index.knn" in issue for issue in compatibility["issues"])


def test_setup_indices_raises_for_existing_incompatible_index():
    store = _build_store()
    store.client.indices.exists.return_value = True
    store.client.indices.get_mapping.return_value = _incompatible_mapping(store.index_name)
    store.client.indices.get_settings.return_value = _incompatible_settings(store.index_name)

    with pytest.raises(IncompatibleIndexSchemaError):
        store.setup_indices(force=False)


def test_search_unified_falls_back_to_bm25_with_degraded_signal():
    store = _build_store()
    store._search_hybrid_native = MagicMock(
        side_effect=IncompatibleIndexSchemaError(
            index_name=store.index_name,
            issues=["Field 'embedding' expected 'knn_vector' but got 'float'."],
        )
    )
    store._search_bm25_only = MagicMock(
        return_value={
            "total": 1,
            "hits": [{"arxiv_id": "1234.5678v1", "title": "test", "score": 0.1}],
            "search_mode": "bm25",
            "degraded": False,
            "error": None,
        }
    )

    result = store.search_unified(
        query="machine learning",
        query_embedding=[0.1, 0.2],
        size=3,
        use_hybrid=True,
    )

    assert result["search_mode"] == "bm25"
    assert result["degraded"] is True
    assert "Incompatible schema" in result["error"]
    assert result["total"] == 1


def test_bulk_index_chunks_fails_fast_when_index_missing():
    store = _build_store()
    store.client.indices.exists.return_value = False

    with pytest.raises(IndexNotReadyError):
        store.bulk_index_chunks(chunks=[{"chunk_data": {"title": "test"}, "embedding": [0.1, 0.2]}])
