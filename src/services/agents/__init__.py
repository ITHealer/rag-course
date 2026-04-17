from .config import GraphConfig
from .context import Context
from .state import AgentState

__all__ = [
    "AgenticRAGService",
    "GraphConfig",
    "Context",
    "AgentState",
    "make_agentic_rag_service",
]


def __getattr__(name: str):
    """
    Lazily resolve heavy imports so importing ``src.services.agents`` does not
    initialize optional tracing stacks during test collection.
    """
    if name == "AgenticRAGService":
        from .agentic_rag import AgenticRAGService

        return AgenticRAGService
    if name == "make_agentic_rag_service":
        from .factory import make_agentic_rag_service

        return make_agentic_rag_service
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
