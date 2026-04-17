"""Abstract base class for vector stores."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class BaseVectorStore(ABC):
    """Abstract base class for vector store implementations."""

    @abstractmethod
    def health_check(self) -> bool:
        """Check if vector store is healthy."""
        pass

    @abstractmethod
    def get_index_stats(self) -> Dict[str, Any]:
        """Get statistics for the store."""
        pass

    @abstractmethod
    def setup_indices(self, force: bool = False) -> Dict[str, bool]:
        """Setup necessary indices or collections."""
        pass

    @abstractmethod
    def search_papers(
        self, query: str, size: int = 10, from_: int = 0, categories: Optional[List[str]] = None, latest: bool = True
    ) -> Dict[str, Any]:
        """Keyword (BM25) search for papers."""
        pass

    @abstractmethod
    def search_chunks_vector(
        self, query_embedding: List[float], size: int = 10, categories: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Pure vector search on chunks."""
        pass

    @abstractmethod
    def search_chunks_hybrid(
        self,
        query: str,
        query_embedding: List[float],
        size: int = 10,
        categories: Optional[List[str]] = None,
        min_score: float = 0.0,
    ) -> Dict[str, Any]:
        """Hybrid search combining keyword and vector similarity."""
        pass

    @abstractmethod
    def search_unified(
        self,
        query: str,
        query_embedding: Optional[List[float]] = None,
        size: int = 10,
        from_: int = 0,
        categories: Optional[List[str]] = None,
        latest: bool = False,
        use_hybrid: bool = True,
        min_score: float = 0.0,
    ) -> Dict[str, Any]:
        """Unified search method supporting multiple modes (BM25, vector, hybrid)."""
        pass

    @abstractmethod
    def index_chunk(self, chunk_data: Dict[str, Any], embedding: List[float]) -> bool:
        """Index a single chunk with its embedding."""
        pass

    @abstractmethod
    def bulk_index_chunks(self, chunks: List[Dict[str, Any]]) -> Dict[str, int]:
        """Bulk index multiple chunks."""
        pass

    @abstractmethod
    def delete_paper_chunks(self, arxiv_id: str) -> bool:
        """Delete all chunks for a specific paper."""
        pass

    @abstractmethod
    def get_chunks_by_paper(self, arxiv_id: str) -> List[Dict[str, Any]]:
        """Get all chunks for a specific paper."""
        pass
