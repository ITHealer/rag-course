"""Factory for initializing embeddings clients based on configuration."""

from typing import Optional

from src.config import Settings, get_settings
from src.services.embeddings.base import BaseEmbeddingsClient
import logging

logger = logging.getLogger(__name__)

def get_embeddings_client(settings: Optional[Settings] = None) -> BaseEmbeddingsClient:
    """Factory function to create embeddings client based on settings.

    Creates a new client instance each time to avoid closed client issues.

    :param settings: Optional settings instance
    :returns: BaseEmbeddingsClient instance
    """
    if settings is None:
        settings = get_settings()

    provider = settings.embedding_provider.lower()
    
    if provider == "jina":
        from src.services.embeddings.jina_client import JinaEmbeddingsClient
        logger.debug("Initializing Jina Embeddings Client")
        return JinaEmbeddingsClient(api_key=settings.jina_api_key)
        
    elif provider == "ollama":
        from src.services.embeddings.ollama_api_client import OllamaAPIEmbeddingsClient
        logger.debug(f"Initializing Remote Ollama API Embeddings Client at {settings.ollama_host}")
        return OllamaAPIEmbeddingsClient(
            host=settings.ollama_host,
            model=settings.embedding_model
        )
        
    elif provider == "sentence-transformers":
        from src.services.embeddings.local_client import LocalEmbeddingsClient
        logger.debug("Initializing Local SentenceTransformers Embeddings Client")
        return LocalEmbeddingsClient(
            host=settings.ollama_host,
            model=settings.embedding_model
        )
        
    else:
        raise ValueError(f"Unsupported Embedding Provider: {provider}. Options are 'jina' or 'ollama'.")

def make_embeddings_service(settings: Optional[Settings] = None) -> BaseEmbeddingsClient:
    """Alias for backwards compatibility."""
    return get_embeddings_client(settings)

def make_embeddings_client(settings: Optional[Settings] = None) -> BaseEmbeddingsClient:
    """Alias for backwards compatibility."""
    return get_embeddings_client(settings)
