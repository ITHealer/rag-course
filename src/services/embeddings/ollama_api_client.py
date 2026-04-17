import logging
from typing import List
import httpx
from src.services.embeddings.base import BaseEmbeddingsClient

logger = logging.getLogger(__name__)

class OllamaAPIEmbeddingsClient(BaseEmbeddingsClient):
    """Client for generating embeddings using the Ollama remote API."""

    def __init__(self, host: str, model: str = "nomic-embed-text"):
        """Initialize Ollama API client.
        
        :param host: The base URL of the Ollama server (e.g., http://10.10.0.7:11445)
        :param model: The model name on the Ollama server.
        """
        self.host = host
        self.model = model
        self.timeout = httpx.Timeout(60.0)
        logger.info(f"Initialized Remote Ollama Embeddings Client for model: {model} at {host}")

    async def embed_passages(self, texts: List[str], batch_size: int = 100) -> List[List[float]]:
        embeddings = []
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for i in range(0, len(texts), batch_size):
                batch = texts[i : i + batch_size]
                batch_embeddings = []
                for text in batch:
                    response = await client.post(
                        f"{self.host}/api/embeddings",
                        json={"model": self.model, "prompt": text}
                    )
                    response.raise_for_status()
                    batch_embeddings.append(response.json()["embedding"])
                embeddings.extend(batch_embeddings)
        return embeddings

    async def embed_query(self, query: str) -> List[float]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.host}/api/embeddings",
                json={"model": self.model, "prompt": query}
            )
            response.raise_for_status()
            return response.json()["embedding"]

    async def close(self):
        pass
