"""Unified factory for OpenSearch client."""

from functools import lru_cache
from typing import Optional

from src.config import Settings, get_settings

# from src.services.vector_store.opensearch_store import OpenSearchStore  # Moved to local imports to avoid cycle


@lru_cache(maxsize=1)
def make_opensearch_client(settings: Optional[Settings] = None):
    """Factory function to create cached OpenSearch client.

    :param settings: Optional settings instance
    :returns: Cached OpenSearchClient instance
    """
    from src.services.vector_store.opensearch_store import OpenSearchStore

    if settings is None:
        settings = get_settings()

    return OpenSearchStore(host=settings.opensearch.host, settings=settings)


def make_opensearch_client_fresh(settings: Optional[Settings] = None, host: Optional[str] = None):
    """Factory function to create a fresh OpenSearch client (not cached).

    Use this when you need a new client instance (e.g., for testing
    or when connection issues occur).

    :param settings: Optional settings instance
    :param host: Optional host override
    :returns: New OpenSearchClient instance
    """
    from src.services.vector_store.opensearch_store import OpenSearchStore

    if settings is None:
        settings = get_settings()

    # Use provided host or settings host
    opensearch_host = host or settings.opensearch.host

    return OpenSearchStore(host=opensearch_host, settings=settings)
