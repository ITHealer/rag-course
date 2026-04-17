from unittest.mock import MagicMock, patch

from src.config import Settings
from src.services.indexing.factory import make_hybrid_indexing_service


def test_make_hybrid_indexing_service_runs_setup_indices():
    settings = Settings()
    mock_opensearch_client = MagicMock()

    with (
        patch("src.services.indexing.factory.make_embeddings_client", return_value=MagicMock()),
        patch("src.services.indexing.factory.make_opensearch_client_fresh", return_value=mock_opensearch_client),
    ):
        indexing_service = make_hybrid_indexing_service(settings=settings)

    mock_opensearch_client.setup_indices.assert_called_once_with(force=False)
    assert indexing_service.opensearch_client is mock_opensearch_client
