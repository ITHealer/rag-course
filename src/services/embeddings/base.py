"""Abstract base class for embeddings clients."""

from abc import ABC, abstractmethod
from typing import List


class BaseEmbeddingsClient(ABC):
    """Abstract base class for embedding model clients."""

    @abstractmethod
    async def embed_passages(self, texts: List[str], batch_size: int = 100) -> List[List[float]]:
        """Embed a batch of text passages for indexing.
        
        :param texts: List of text passages to embed
        :param batch_size: Number of texts to process in each batch
        :returns: List of embedding vectors
        """
        pass

    @abstractmethod
    async def embed_query(self, query: str) -> List[float]:
        """Embed a search query.
        
        :param query: Query text to embed
        :returns: Embedding vector for the query
        """
        pass

    @abstractmethod
    async def close(self):
        """Close any opened client sessions."""
        pass

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
