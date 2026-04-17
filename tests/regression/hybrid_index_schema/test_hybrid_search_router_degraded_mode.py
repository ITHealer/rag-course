from unittest.mock import AsyncMock, MagicMock

import pytest

from src.routers.hybrid_search import hybrid_search
from src.schemas.api.search import HybridSearchRequest


@pytest.mark.asyncio
async def test_hybrid_search_router_exposes_degraded_fallback():
    request = HybridSearchRequest(query="find AI jobs", use_hybrid=True, size=3)

    opensearch_client = MagicMock()
    opensearch_client.health_check.return_value = True
    opensearch_client.search_unified.return_value = {
        "total": 1,
        "hits": [
            {
                "arxiv_id": "2501.00001v1",
                "title": "AI jobs outlook",
                "score": 0.42,
                "chunk_text": "sample chunk",
            }
        ],
        "search_mode": "bm25",
        "degraded": True,
        "error": "Incompatible schema for index 'arxiv-papers-chunks'",
    }

    embeddings_service = AsyncMock()
    embeddings_service.embed_query.return_value = [0.1, 0.2, 0.3]

    response = await hybrid_search(
        request=request,
        opensearch_client=opensearch_client,
        embeddings_service=embeddings_service,
    )

    assert response.search_mode == "bm25"
    assert response.error is not None
    assert response.total == 1
