from functools import lru_cache
from typing import TYPE_CHECKING, Annotated, Generator, Optional

if TYPE_CHECKING:
    from fastapi import Depends, Request
    from sqlalchemy.orm import Session
else:
    try:
        from fastapi import Depends, Request
        from sqlalchemy.orm import Session
    except ImportError:
        pass

from src.config import Settings
from src.db.interfaces.base import BaseDatabase
from src.repositories.domain_profile import DomainProfileRepository
from src.repositories.ingestion_task import IngestionTaskRepository
from src.repositories.project import ProjectRepository
from src.repositories.project_file import ProjectFileRepository
from src.services.arxiv.client import ArxivClient
from src.services.cache.client import CacheClient
from src.services.embeddings.base import BaseEmbeddingsClient
from src.services.tracing.base import BaseTracer
from src.services.ollama.client import OllamaClient
from src.services.vector_store.base import BaseVectorStore
from src.services.pdf_parser.parser import PDFParserService
from src.services.telegram.bot import TelegramBot
from src.services.agents.agentic_rag import AgenticRAGService
from src.services.agents.factory import make_agentic_rag_service
from src.services.ingestion.project_knowledge_service import ProjectKnowledgeService


@lru_cache
def get_settings() -> Settings:
    """Get application settings."""
    return Settings()


def get_request_settings(request: Request) -> Settings:
    """Get settings from the request state."""
    return request.app.state.settings


def get_database(request: Request) -> BaseDatabase:
    """Get database from the request state."""
    return request.app.state.database


def get_db_session(database: Annotated[BaseDatabase, Depends(get_database)]) -> Generator[Session, None, None]:
    """Get database session dependency."""
    with database.get_session() as session:
        yield session


def get_opensearch_client(request: Request) -> BaseVectorStore:
    """Get Vector Store client from the request state."""
    return request.app.state.opensearch_client


def get_arxiv_client(request: Request) -> ArxivClient:
    """Get arXiv client from the request state."""
    return request.app.state.arxiv_client


def get_pdf_parser(request: Request) -> PDFParserService:
    """Get PDF parser service from the request state."""
    return request.app.state.pdf_parser


def get_embeddings_service(request: Request) -> BaseEmbeddingsClient:
    """Get embeddings service from the request state."""
    return request.app.state.embeddings_service


def get_ollama_client(request: Request) -> OllamaClient:
    """Get Ollama client from the request state."""
    return request.app.state.ollama_client


def get_langfuse_tracer(request: Request) -> BaseTracer:
    """Get Tracer from the request state."""
    return request.app.state.langfuse_tracer


def get_cache_client(request: Request) -> CacheClient | None:
    """Get cache client from the request state."""
    return getattr(request.app.state, "cache_client", None)


def get_telegram_service(request: Request) -> Optional[TelegramBot]:
    """Get Telegram service from the request state."""
    return getattr(request.app.state, "telegram_service", None)


def get_project_knowledge_service(request: Request) -> ProjectKnowledgeService:
    """Get project knowledge ingestion and stats service from request state."""
    return request.app.state.project_knowledge_service


# Dependency annotations
SettingsDep = Annotated[Settings, Depends(get_settings)]
DatabaseDep = Annotated[BaseDatabase, Depends(get_database)]
SessionDep = Annotated[Session, Depends(get_db_session)]
OpenSearchDep = Annotated[BaseVectorStore, Depends(get_opensearch_client)]
ArxivDep = Annotated[ArxivClient, Depends(get_arxiv_client)]
PDFParserDep = Annotated[PDFParserService, Depends(get_pdf_parser)]
EmbeddingsDep = Annotated[BaseEmbeddingsClient, Depends(get_embeddings_service)]
OllamaDep = Annotated[OllamaClient, Depends(get_ollama_client)]
LangfuseDep = Annotated[BaseTracer, Depends(get_langfuse_tracer)]
CacheDep = Annotated[CacheClient | None, Depends(get_cache_client)]
TelegramDep = Annotated[Optional[TelegramBot], Depends(get_telegram_service)]
ProjectKnowledgeDep = Annotated[ProjectKnowledgeService, Depends(get_project_knowledge_service)]


def get_domain_profile_repository(session: SessionDep) -> DomainProfileRepository:
    """Get domain profile repository."""
    return DomainProfileRepository(session)


def get_project_repository(session: SessionDep) -> ProjectRepository:
    """Get project repository."""
    return ProjectRepository(session)


def get_agentic_rag_service(
    opensearch: OpenSearchDep,
    ollama: OllamaDep,
    embeddings: EmbeddingsDep,
    langfuse: LangfuseDep,
    domain_profile_repository: Annotated[DomainProfileRepository, Depends(get_domain_profile_repository)],
    project_repository: Annotated[ProjectRepository, Depends(get_project_repository)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AgenticRAGService:
    """Get agentic RAG service."""
    return make_agentic_rag_service(
        opensearch_client=opensearch,
        ollama_client=ollama,
        embeddings_client=embeddings,
        langfuse_tracer=langfuse,
        domain_profile_repository=domain_profile_repository,
        project_repository=project_repository,
        model=settings.ollama_model,
    )


AgenticRAGDep = Annotated[AgenticRAGService, Depends(get_agentic_rag_service)]


def get_project_file_repository(session: SessionDep) -> ProjectFileRepository:
    """Get project file repository."""
    return ProjectFileRepository(session)


def get_ingestion_task_repository(session: SessionDep) -> IngestionTaskRepository:
    """Get ingestion task repository."""
    return IngestionTaskRepository(session)


DomainProfileRepoDep = Annotated[DomainProfileRepository, Depends(get_domain_profile_repository)]
ProjectRepoDep = Annotated[ProjectRepository, Depends(get_project_repository)]
ProjectFileRepoDep = Annotated[ProjectFileRepository, Depends(get_project_file_repository)]
IngestionTaskRepoDep = Annotated[IngestionTaskRepository, Depends(get_ingestion_task_repository)]
