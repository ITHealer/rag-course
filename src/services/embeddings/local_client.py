import logging
from typing import List

from sentence_transformers import SentenceTransformer
from src.services.embeddings.base import BaseEmbeddingsClient

logger = logging.getLogger(__name__)


class LocalEmbeddingsClient(BaseEmbeddingsClient):
    """Client for local embeddings generation using SentenceTransformers.
    
    Provides a free, local alternative to Jina API. Defaults to a lightweight model.
    """

    def __init__(self, host: str, model: str = "all-MiniLM-L6-v2"):
        """Initialize local embeddings client.
        
        :param host: ignored for sentence-transformers, kept for symmetry.
        :param model: The HuggingFace model string to use.
        """
        self.model_name = model
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"Loading local SentenceTransformer model: {model}...")
        
        # Load the model locally
        self.model = SentenceTransformer(model)
        self.logger.info("Local embeddings model loaded successfully.")

    async def embed_passages(self, texts: List[str], batch_size: int = 100) -> List[List[float]]:
        self.logger.debug(f"Computing embeddings for {len(texts)} passages in batches of {batch_size}")
        
        # SentenceTransformers handles batching internally if we pass batch_size
        embeddings = self.model.encode(texts, batch_size=batch_size, convert_to_numpy=True)
        return embeddings.tolist()

    async def embed_query(self, query: str) -> List[float]:
        self.logger.debug(f"Computing embedding for query: '{query[:50]}...'")
        embedding = self.model.encode([query], convert_to_numpy=True)[0]
        return embedding.tolist()

    async def close(self):
        """No HTTP client to close for local model."""
        pass
