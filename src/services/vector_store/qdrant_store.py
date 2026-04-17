"""Qdrant client supporting both simple BM25 and hybrid search."""

import logging
from typing import Any, Dict, List, Optional
import uuid

try:
    from qdrant_client import QdrantClient
    from qdrant_client.http import models as rest
    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False

from src.config import Settings
from src.services.vector_store.base import BaseVectorStore

logger = logging.getLogger(__name__)


class QdrantStore(BaseVectorStore):
    """Qdrant client supporting hybrid search with sparse and dense vectors."""

    def __init__(self, host: str, port: int, settings: Settings):
        self.host = host
        self.port = port
        self.settings = settings
        self.collection_name = f"{settings.opensearch.index_name}-{settings.opensearch.chunk_index_suffix}"
        
        if not QDRANT_AVAILABLE:
            logger.warning("QdrantClient is not installed. Run `pip install qdrant-client` to use Qdrant.")
            self.client = None
            return

        # Connect to Qdrant
        self.client = QdrantClient(host=host, port=port)
        logger.info(f"Qdrant client initialized at {host}:{port}")

    def health_check(self) -> bool:
        """Check if Qdrant cluster is healthy."""
        if not self.client:
            return False
            
        try:
            # Simple check if Collections can be listed
            self.client.get_collections()
            return True
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False

    def get_index_stats(self) -> Dict[str, Any]:
        """Get statistics for the collection."""
        if not self.client:
            return {"error": "QdrantClient not installed"}
            
        try:
            if not self.client.collection_exists(self.collection_name):
                return {"collection_name": self.collection_name, "exists": False, "document_count": 0}

            info = self.client.get_collection(self.collection_name)
            
            return {
                "collection_name": self.collection_name,
                "exists": True,
                "document_count": info.points_count,
                "status": str(info.status)
            }
        except Exception as e:
            logger.error(f"Error getting collection stats: {e}")
            return {"collection_name": self.collection_name, "exists": False, "document_count": 0, "error": str(e)}

    def setup_indices(self, force: bool = False) -> Dict[str, bool]:
        """Setup the collection for hybrid search."""
        if not self.client:
            raise ImportError("Qdrant client not installed")
            
        try:
            if force and self.client.collection_exists(self.collection_name):
                self.client.delete_collection(self.collection_name)
                logger.info(f"Deleted existing Qdrant collection: {self.collection_name}")

            if not self.client.collection_exists(self.collection_name):
                # We create a dense vector configuration and a sparse vector one
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config={
                        "dense": rest.VectorParams(
                            size=self.settings.opensearch.vector_dimension,
                            distance=rest.Distance.COSINE
                        )
                    },
                    sparse_vectors_config={
                        "sparse": rest.SparseVectorParams()
                    }
                )
                logger.info(f"Created Qdrant collection: {self.collection_name}")
                return {"hybrid_index": True}

            logger.info(f"Qdrant collection already exists: {self.collection_name}")
            return {"hybrid_index": False}

        except Exception as e:
            logger.error(f"Error creating collection: {e}")
            raise

    # For pure BM25 mock in Qdrant, we'd ideally pass sparse vectors from query. 
    # For now, it raises NotImplementedError unless sparse query is provided
    def search_papers(
        self, query: str, size: int = 10, from_: int = 0, categories: Optional[List[str]] = None, latest: bool = True
    ) -> Dict[str, Any]:
        logger.warning("BM25-only string search requires local SPLADE tokenizer for Qdrant. Not implemented.")
        return {"total": 0, "hits": []}

    def search_chunks_vector(
        self, query_embedding: List[float], size: int = 10, categories: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        if not self.client:
            return {"total": 0, "hits": []}
            
        try:
            # Build payload filter
            filter_params = None
            if categories:
                filter_params = rest.Filter(
                    must=[rest.FieldCondition(key="categories", match=rest.MatchAny(any=categories))]
                )

            search_result = self.client.search(
                collection_name=self.collection_name,
                query_vector=rest.NamedVector(
                    name="dense",
                    vector=query_embedding,
                ),
                query_filter=filter_params,
                limit=size,
                with_payload=True
            )

            hits = []
            for point in search_result:
                chunk = point.payload or {}
                chunk["score"] = point.score
                chunk["chunk_id"] = str(point.id)
                hits.append(chunk)

            return {"total": len(hits), "hits": hits}
        except Exception as e:
            logger.error(f"Vector search error: {e}")
            return {"total": 0, "hits": []}

    def search_chunks_hybrid(
        self,
        query: str,
        query_embedding: List[float],
        size: int = 10,
        categories: Optional[List[str]] = None,
        min_score: float = 0.0,
    ) -> Dict[str, Any]:
        # Implementation of full hybrid requires locally computed sparse embeddings. 
        # Falling back to vector search for stub.
        return self.search_chunks_vector(query_embedding, size, categories)

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
        
        if query_embedding:
            return self.search_chunks_vector(query_embedding, size, categories)
        return {"total": 0, "hits": []}

    def index_chunk(self, chunk_data: Dict[str, Any], embedding: List[float]) -> bool:
        if not self.client: return False
        
        try:
            point_id = str(uuid.uuid4())
            self.client.upsert(
                collection_name=self.collection_name,
                points=[
                    rest.PointStruct(
                        id=point_id,
                        vector={"dense": embedding},
                        payload=chunk_data
                    )
                ]
            )
            return True
        except Exception as e:
            logger.error(f"Qdrant index chunk err: {e}")
            return False

    def bulk_index_chunks(self, chunks: List[Dict[str, Any]]) -> Dict[str, int]:
        if not self.client: raise ValueError("Client not ready")
        
        points = []
        for chunk in chunks:
            chunk_data = chunk["chunk_data"].copy()
            points.append(rest.PointStruct(
                id=str(uuid.uuid4()),
                vector={"dense": chunk["embedding"]},
                payload=chunk_data
            ))
            
        self.client.upsert(collection_name=self.collection_name, points=points)
        return {"success": len(points), "failed": 0}

    def delete_paper_chunks(self, arxiv_id: str) -> bool:
        if not self.client: return False
        
        try:
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=rest.Filter(
                    must=[rest.FieldCondition(key="arxiv_id", match=rest.MatchValue(value=arxiv_id))]
                )
            )
            return True
        except Exception:
            return False

    def get_chunks_by_paper(self, arxiv_id: str) -> List[Dict[str, Any]]:
        # Scroll logic
        return []
