# Backend AI Python Project Style Guide & Coding Rules

This document outlines the architectural patterns, folder structure, and coding conventions for the arXiv Paper Curator project. When implementing new features, AI agents and human developers alike must strictly adhere to these rules to maintain consistency, testability, and production readiness.

## 1. Directory Structure & Responsibilities

The codebase follows a Domain-Driven, Layered Architecture located under the `src/` directory.

- **`src/routers/`**: Contains FastAPI route definitions (`AskRouter`, `SearchRouter`). Minimal business logic should live here. Responsibilities include accepting requests, calling injected services, and returning formatted responses.
- **`src/services/`**: The core business logic layer interacting with external APIs (arXiv), AI models (Ollama, Jina Embeddings), and Search Engines (OpenSearch). Each service should be encapsulated in its own folder (e.g., `src/services/ollama/`).
- **`src/repositories/`**: The Data Access Layer. Contains classes (e.g., `PaperRepository`) that handle direct database interactions using SQLAlchemy. Services and Routers should NEVER write raw SQL; they must use Repositories.
- **`src/models/`**: SQLAlchemy ORM models representing the database schema (e.g., `Paper`).
- **`src/schemas/`**: Pydantic models for data validation, serialization, and typing (e.g., `AskRequest`, `AskResponse`). 
- **`src/db/`**: Database connection management, session creation, and migrations.
- **`src/config.py`**: Centralized configuration management using Pydantic `BaseSettings`.

---

## 2. Core Architectural Patterns

### 2.1 Dependency Injection (DI)
FastAPI's `Depends` system must be used to inject dependencies into routers. **Never instantiate services or establish database connections directly inside a route.**

**Rule:** All dependencies are defined centrally in `src/dependencies.py`.
```python
# In src/dependencies.py
OpenSearchDep = Annotated[OpenSearchClient, Depends(get_opensearch_client)]

# In src/routers/my_router.py
@router.post("/example")
async def my_endpoint(request: MyRequest, search_client: OpenSearchDep):
    results = search_client.search(request.query)
    return results
```

### 2.2 The Factory Pattern for Services
Service instantiation logic must not pollute the application startup file (`main.py`). Every service inside `src/services/` must provide a `factory.py` file exposing a `make_<service_name>()` function.

**Rule:** Dependencies are instantiated via their factory functions using centralized configuration from `get_settings()`.
```python
# src/services/arxiv/factory.py
from src.config import get_settings
from .client import ArxivClient

def make_arxiv_client() -> ArxivClient:
    settings = get_settings()
    return ArxivClient(settings=settings.arxiv)
```

### 2.3 Repository Pattern for Database Access
Direct interactions with the database session should be isolated within Repository classes.

**Rule:** Pass the SQLAlchemy `Session` into the repository via `__init__`, and implement specific data access methods.
```python
# src/repositories/paper.py
class PaperRepository:
    def __init__(self, session: Session):
        self.session = session
        
    def get_by_arxiv_id(self, arxiv_id: str) -> Optional[Paper]:
        stmt = select(Paper).where(Paper.arxiv_id == arxiv_id)
        return self.session.scalar(stmt)
```

---

## 3. Coding Conventions & Best Practices

### 3.1 Strict Type Hinting
Every function, method, and variable (when ambiguous) MUST employ Python type hinting (`typing` module).
- Always define return types (`-> List[Paper]:`, `-> AskResponse:`).
- Use `Optional[Type]` for variables that can be `None`.

### 3.2 Error Handling & Exceptions
- Raise standard `fastapi.HTTPException` within routers for API-level errors (4xx, 5xx).
- Custom domain exceptions should be defined in `src/exceptions.py`.
- Services should throw standard Python exceptions (e.g., `ValueError`) or domain exceptions, leaving the router to catch and translate them to `HTTPException`.

### 3.3 Observability and Tracing
When building AI features (RAG, generation, search), use the `LangfuseTracer` dependency to trace spans. 
- Always trace Retrieval (`trace_search`), Prompt Construction (`trace_prompt_construction`), and LLM Generation (`trace_generation`).

### 3.4 Pydantic Schemas for API Contracts
- Request and Response bodies must be explicitly modeled using Pydantic classes inside `src/schemas/api/`. 
- Ensure that you never leak raw internal Database Models (SQLAlchemy `Paper`) directly to the API user; map them to a Pydantic `ResponseModel` first.

---

## 4. Feature Implementation Workflow (Example)

When instructed to add a new feature (e.g., *a new endpoint to fetch similar papers*), follow this sequence:

1. **Schema Check:** Add the Input/Output models to `src/schemas/api/`.
2. **Repository Update:** Add the necessary SQL query function to the relevant model in `src/repositories/`.
3. **Service Logic:** If it requires AI computation, add the logic to `src/services/`.
4. **Dependency Injection:** Add any new services to `src/dependencies.py`.
5. **Router Creation:** Add the route to `src/routers/`, injecting the dependencies. Ensure the route has `response_model` configured.
6. **Main Registration:** If it's a new router file, include it in `app.include_router()` in `src/main.py`.
