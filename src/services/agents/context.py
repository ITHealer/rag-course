from dataclasses import dataclass
from langfuse._client.span import LangfuseSpan
from typing import TYPE_CHECKING, List, Optional

from src.services.embeddings.base import BaseEmbeddingsClient
from src.services.tracing.base import BaseTracer
from src.services.ollama.client import OllamaClient
from src.services.vector_store.base import BaseVectorStore
from src.services.domain.external_web_search_policy import ExternalWebSearchPolicy


@dataclass
class Context:
    """Runtime context for agent dependencies.

    This contains immutable dependencies that nodes need but don't modify.

    :param ollama_client: Client for LLM generation
    :param opensearch_client: Client for document search
    :param embeddings_client: Client for embeddings
    :param langfuse_tracer: Optional tracer for observability
    :param trace: Current Langfuse trace object (if enabled)
    :param langfuse_enabled: Whether Langfuse tracing is enabled
    :param model_name: Model to use for LLM calls
    :param temperature: Temperature for generation
    :param top_k: Number of documents to retrieve
    :param max_retrieval_attempts: Maximum retrieval attempts
    :param guardrail_threshold: Threshold for guardrail validation (0-100)
    """

    ollama_client: OllamaClient
    opensearch_client: BaseVectorStore
    embeddings_client: BaseEmbeddingsClient
    langfuse_tracer: Optional[BaseTracer]
    trace: Optional["LangfuseSpan"] = None
    langfuse_enabled: bool = False
    model_name: str = "llama3.2:1b"
    temperature: float = 0.0
    top_k: int = 3
    max_retrieval_attempts: int = 2
    guardrail_threshold: int = 60
    mode: str = "strict"
    project_id: Optional[str] = None
    allow_external_web_search: bool = False
    require_human_approval_for_external_search: bool = True
    allow_image_perception: bool = True
    human_approval_granted: bool = False
    image_inputs: List[str] = None
    external_web_search_policy: Optional[ExternalWebSearchPolicy] = None
    preset_id: str = "scoped_knowledge"
    system_prompt_addon: str = ""
