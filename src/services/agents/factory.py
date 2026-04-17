from typing import Optional

from src.repositories.domain_profile import DomainProfileRepository
from src.repositories.project import ProjectRepository
from src.services.embeddings.base import BaseEmbeddingsClient
from src.services.tracing.base import BaseTracer
from src.services.ollama.client import OllamaClient
from src.services.vector_store.base import BaseVectorStore

from .agentic_rag import AgenticRAGService
from .config import GraphConfig


def make_agentic_rag_service(
    opensearch_client: BaseVectorStore,
    ollama_client: OllamaClient,
    embeddings_client: BaseEmbeddingsClient,
    langfuse_tracer: Optional[BaseTracer] = None,
    domain_profile_repository: Optional[DomainProfileRepository] = None,
    project_repository: Optional[ProjectRepository] = None,
    model: str = "llama3.2:1b",
    top_k: int = 3,
    use_hybrid: bool = True,
) -> AgenticRAGService:
    """
    Create AgenticRAGService with dependency injection.

    Args:
        opensearch_client: Client for document search
        ollama_client: Client for LLM generation
        embeddings_client: Client for embeddings
        langfuse_tracer: Optional Langfuse tracer for observability
        top_k: Number of documents to retrieve (default: 3)
        use_hybrid: Use hybrid search (default: True)

    Returns:
        Configured AgenticRAGService instance
    """
    # Create graph configuration with the provided parameters
    graph_config = GraphConfig(
        model=model,
        top_k=top_k,
        use_hybrid=use_hybrid,
    )

    return AgenticRAGService(
        opensearch_client=opensearch_client,
        ollama_client=ollama_client,
        embeddings_client=embeddings_client,
        langfuse_tracer=langfuse_tracer,
        graph_config=graph_config,
        domain_profile_repository=domain_profile_repository,
        project_repository=project_repository,
    )
