import logging

from langchain_core.documents import Document
from langchain_core.tools import tool

from src.services.embeddings.base import BaseEmbeddingsClient
from src.services.vector_store.base import BaseVectorStore

logger = logging.getLogger(__name__)


def _resolve_source_url(hit: dict) -> str:
    """Resolve source URL with backward compatibility for legacy arXiv documents."""
    source_uri = hit.get("source_uri")
    if source_uri:
        return source_uri

    arxiv_id = hit.get("arxiv_id", "")
    if arxiv_id:
        arxiv_id_clean = arxiv_id.split("v")[0] if "v" in arxiv_id else arxiv_id
        return f"https://arxiv.org/pdf/{arxiv_id_clean}.pdf"

    return ""


def create_retriever_tool(
    opensearch_client: BaseVectorStore,
    embeddings_client: BaseEmbeddingsClient,
    top_k: int = 3,
    use_hybrid: bool = True,
):
    """Create a retriever tool that wraps OpenSearch service.

    :param opensearch_client: Existing OpenSearch service
    :param embeddings_client: Existing embeddings service
    :param top_k: Number of chunks to retrieve
    :param use_hybrid: Use hybrid search (BM25 + vector)
    :returns: LangChain tool for retrieving grounded documents
    """

    @tool
    async def retrieve_papers(query: str) -> list[Document]:
        """Search and return relevant grounded documents.

        :param query: The search query describing what documents to find
        :returns: List of relevant excerpts with metadata
        """
        logger.info(f"Retrieving grounded documents for query: {query[:100]}...")
        logger.debug(f"Search mode: {'hybrid' if use_hybrid else 'bm25'}, top_k: {top_k}")

        query_embedding = await embeddings_client.embed_query(query)
        logger.debug(f"Generated embedding with {len(query_embedding)} dimensions")

        search_results = opensearch_client.search_unified(
            query=query,
            query_embedding=query_embedding,
            size=top_k,
            use_hybrid=use_hybrid,
        )

        documents = []
        hits = search_results.get("hits", [])
        logger.info(f"Found {len(hits)} documents from OpenSearch")

        for hit in hits:
            doc = Document(
                page_content=hit.get("chunk_text", ""),
                metadata={
                    "arxiv_id": hit.get("arxiv_id"),
                    "title": hit.get("title", ""),
                    "authors": hit.get("authors", ""),
                    "score": hit.get("score", 0.0),
                    "source": _resolve_source_url(hit),
                    "source_type": hit.get("source_type", "project"),
                    "doc_name": hit.get("doc_name", ""),
                    "page_number": hit.get("page_number"),
                    "section": hit.get("section_name", ""),
                    "search_mode": "hybrid" if use_hybrid else "bm25",
                    "top_k": top_k,
                },
            )
            documents.append(doc)

        logger.debug(f"Converted {len(documents)} hits to LangChain Documents")
        logger.info(f"Retrieved {len(documents)} grounded documents successfully")

        return documents

    return retrieve_papers
