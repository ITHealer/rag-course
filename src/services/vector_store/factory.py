"""Factory for initializing vector stores based on configuration."""

from src.config import Settings
from src.services.vector_store.base import BaseVectorStore
import logging

logger = logging.getLogger(__name__)

class VectorStoreFactory:
    """Factory to create vector store instances."""

    @staticmethod
    def get_vector_store(settings: Settings) -> BaseVectorStore:
        """Get the configured vector store implementation.
        
        :param settings: Application settings
        :returns: An instance of BaseVectorStore
        :raises ValueError: If the requested provider is not supported
        """
        provider = settings.vector_db_provider.lower()
        
        if provider == "opensearch":
            # For phase 2, we will refactor OpenSearchClient to implement BaseVectorStore
            # Currently it lives in src.services.opensearch.client. We will assume the refactored path.
            # Lazy import to avoid circular dependencies
            from src.services.vector_store.opensearch_store import OpenSearchStore
            
            # Using the opensearch_host logic, assuming OPENSEARCH_HOST or .opensearch.host exists
            host = settings.opensearch.host if hasattr(settings, 'opensearch') else "http://localhost:9200"
            logger.info(f"Initializing OpenSearch Vector Store at {host}")
            return OpenSearchStore(host=host, settings=settings)
            
        elif provider == "qdrant":
            from src.services.vector_store.qdrant_store import QdrantStore
            logger.info(f"Initializing Qdrant Vector Store at {settings.qdrant_host}:{settings.qdrant_port}")
            return QdrantStore(
                host=settings.qdrant_host,
                port=settings.qdrant_port,
                settings=settings
            )
            
        else:
            raise ValueError(f"Unsupported Vector DB Provider: {provider}. Options are 'opensearch' or 'qdrant'.")
