# Multi-Domain Project-First RAG Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the current arXiv-specific RAG system into a project-first, strictly grounded, multi-domain document QA platform with configurable domain presets and natural insufficient-knowledge responses.

**Architecture:** Keep the existing FastAPI + LangGraph + OpenSearch stack, but move the core from a single global arXiv index to project-scoped indexing with a universal chunk schema. Add a thin preset layer for domain behavior, metadata extraction, and prompt/tool customization without rebuilding the core ingestion and retrieval pipeline for every domain.

**Tech Stack:** FastAPI, LangGraph, OpenSearch, PostgreSQL, Pydantic Settings, Docling PDF parser, Ollama, pytest

---

## Scope Mode

This plan is intentionally written for **HOLD SCOPE**.

- No repo migration to OpenRAG in this implementation.
- No UI rewrite.
- No generic internet/general-knowledge fallback answers.
- No multi-agent orchestration beyond the current LangGraph workflow.
- No attempt to solve every future preset in the first ship.

## Key Decisions

1. Keep the current codebase and refactor in place.
2. Introduce **project-first scoping** as the main boundary.
3. Use **strict grounded answering only**. If retrieval cannot support the answer, route to an LLM-generated `insufficient_knowledge` response grounded in known project contents and metadata.
4. Replace arXiv-specific assumptions in prompts, tools, response schemas, and ingestion payloads with a universal document model.
5. Store domain specialization in YAML + prompt-addon files. Because `src/config.py` already exists as a module file, do **not** create `src/config/preset_loader.py`; create `src/services/domain/preset_loader.py` instead.

## Not In Scope

- Rebuilding the Telegram bot for project-first UX in this phase
- Full notebook UI / drag-and-drop UI
- OCR-heavy pipelines for scanned PDFs beyond current parser capabilities
- Cross-project federated retrieval
- Fine-tuned rerankers or learned ranking models
- Rich asynchronous job queue platform beyond current worker/DAG model
- Auto-classification for every document type on day one

## What Already Exists

- Hybrid search with schema validation: `src/services/vector_store/opensearch_store.py`
- Current hybrid index mapping and RRF pipeline: `src/services/opensearch/index_config_hybrid.py`
- Chunking and indexing pipeline: `src/services/indexing/text_chunker.py`, `src/services/indexing/hybrid_indexer.py`
- Local PDF ingestion watcher and worker: `src/services/ingestion/local_watcher.py`, `src/workers/ingestion_worker.py`
- Agentic LangGraph workflow: `src/services/agents/agentic_rag.py`
- Existing structured API entrypoints: `src/routers/agentic_ask.py`, `src/routers/ask.py`, `src/routers/hybrid_search.py`
- PostgreSQL bootstrap and repository pattern: `src/db/interfaces/postgresql.py`, `src/repositories/paper.py`

## Dream State Delta

Current state:
- Single global index
- arXiv-first metadata model
- hard-coded prompts and source formatting
- local PDF support only in ingestion, not in agent behavior

After this plan:
- project-scoped indexing and retrieval
- universal chunk schema for any document domain
- configurable domain presets
- strict grounded responses with citations and natural insufficient-knowledge handling

12-month ideal not yet covered:
- richer UI
- project task tracking
- richer preset marketplace
- federated/project collections

## System Architecture

```text
User/API
  -> Project Router
  -> Project Service / Preset Loader
  -> Ingestion Service
      -> ProjectIndexManager
      -> PDF Parser
      -> Chunker
      -> Embeddings
      -> OpenSearch (project-scoped index)
  -> Agentic Chat Service
      -> Scope Router
      -> Retriever Tool
      -> Citation Engine
      -> Insufficient Knowledge Node
  -> Response
```

```text
Happy path:
file upload -> project file record -> parse -> chunk -> embed -> index(project-X) -> retrieve(project-X) -> answer + citations

Nil path:
missing project -> 404 / typed error

Empty path:
project exists but no indexed chunks -> insufficient_knowledge response

Error path:
parser/index/LLM/search failure -> typed error or degraded behavior with explicit signal
```

## Chunk 1: Foundation Hardening Before Feature Refactor

### Task 1: Stabilize ingestion and API contracts

**Files:**
- Modify: `src/workers/ingestion_worker.py`
- Modify: `src/services/ingestion/local_watcher.py`
- Modify: `src/routers/agentic_ask.py`
- Modify: `src/services/agents/nodes/guardrail_node.py`
- Test: `tests/project_first_rag/foundation/test_ingestion_worker_setup.py`
- Test: `tests/project_first_rag/foundation/test_agentic_response_contract.py`

- [ ] Add `setup_indices(force=False)` or future `ensure_project_ready()` call in worker startup before any indexing occurs.
- [ ] Add explicit ingestion logs for `files_found`, `files_skipped`, `files_processed`, `parse_failures`, `index_failures`.
- [ ] Fix `chunks_used` to reflect actual retrieved chunks rather than `request.top_k`.
- [ ] Replace the current `score=50` fallback behavior with a typed failure path that surfaces LLM/guardrail infrastructure issues in logs and metadata.
- [ ] Add tests for worker setup and accurate `chunks_used`.

**Expected verification:**
- `uv run python src/workers/ingestion_worker.py` logs scan/process decisions clearly.
- `pytest tests/project_first_rag/foundation -q`

### Task 2: Introduce typed infrastructure failures for agentic flow

**Files:**
- Create: `src/services/agents/errors.py`
- Modify: `src/services/agents/agentic_rag.py`
- Modify: `src/services/agents/nodes/out_of_scope_node.py`
- Modify: `src/services/ollama/client.py`
- Test: `tests/project_first_rag/foundation/test_agentic_infra_failures.py`

- [ ] Add typed errors for `ModelUnavailableError`, `PromptRenderError`, `InsufficientKnowledgeError`, `ProjectScopeError`.
- [ ] Ensure model/network failures are not silently translated into domain-policy answers.
- [ ] Keep current `out_of_scope_node` only as a temporary compatibility node until the replacement lands in Chunk 4.

**Done when:**
- an unreachable Ollama host no longer causes a fake domain-policy response
- logs distinguish policy decisions from infrastructure failures

## Chunk 2: Project Core and Universal Schema

### Task 3: Add project and project-file domain models

**Files:**
- Create: `src/models/project.py`
- Create: `src/models/project_file.py`
- Create: `src/repositories/project.py`
- Create: `src/repositories/project_file.py`
- Create: `src/schemas/api/projects.py`
- Modify: `src/db/interfaces/postgresql.py`
- Modify: `src/dependencies.py`
- Test: `tests/project_first_rag/projects/test_project_repository.py`
- Test: `tests/project_first_rag/projects/test_project_api_models.py`

- [ ] Add `Project` model with `id`, `name`, `preset_id`, `scope`, `created_at`, `updated_at`.
- [ ] Add `ProjectFile` model with `id`, `project_id`, `file_name`, `source_type`, `source_uri`, `content_type`, `ingest_status`, `metadata_json`, `created_at`, `updated_at`.
- [ ] Add repositories and API schemas for create/list/get operations.
- [ ] Keep `Base.metadata.create_all` compatibility for now; do not introduce Alembic migration tooling in this PR series unless blocked.

### Task 4: Build project index manager and universal mapping

**Files:**
- Create: `src/services/indexing/project_index_manager.py`
- Modify: `src/services/opensearch/index_config_hybrid.py`
- Modify: `src/services/vector_store/base.py`
- Modify: `src/services/vector_store/opensearch_store.py`
- Test: `tests/project_first_rag/indexing/test_project_index_manager.py`
- Test: `tests/project_first_rag/indexing/test_universal_schema_validation.py`

- [ ] Replace arXiv-specific required fields with universal chunk fields:
  - `project_id`
  - `file_id`
  - `doc_name`
  - `page_number`
  - `chunk_index`
  - `chunk_text`
  - `source_type`
  - `source_uri`
  - `doc_type`
  - `metadata`
  - `embedding`
- [ ] Add index creation and validation via `ProjectIndexManager.ensure_project_ready(project_id)`.
- [ ] Route every write path through `ProjectIndexManager`.
- [ ] Keep typed schema incompatibility failures.

**Decision locked in for this plan:**
- Use **physical project-scoped indexes**: `project-{project_id}`.
- Keep one universal mapping builder and one shared search pipeline definition.

## Chunk 3: Project-Scoped Ingestion and Retrieval

### Task 5: Replace arXiv-shaped ingestion payload with generic document payload

**Files:**
- Modify: `src/services/indexing/hybrid_indexer.py`
- Modify: `src/services/indexing/text_chunker.py`
- Modify: `src/services/ingestion/local_watcher.py`
- Modify: `src/workers/ingestion_worker.py`
- Create: `src/schemas/indexing/project_document.py`
- Test: `tests/project_first_rag/ingestion/test_local_watcher_project_payload.py`
- Test: `tests/project_first_rag/ingestion/test_hybrid_indexer_generic_document.py`

- [ ] Introduce a generic `ProjectDocumentPayload`.
- [ ] Stop manufacturing `arxiv_id` and `categories=["local.Upload"]` for local documents.
- [ ] Preserve page-aware metadata from parser output where available.
- [ ] Write `doc_name`, `page_number`, `source_uri`, and `metadata` into chunk payloads.
- [ ] Support one document belonging to exactly one project file record.

### Task 6: Add project-aware retrieval APIs and filters

**Files:**
- Modify: `src/services/vector_store/opensearch_store.py`
- Modify: `src/services/agents/tools.py`
- Modify: `src/routers/hybrid_search.py`
- Modify: `src/routers/ask.py`
- Create: `src/routers/projects.py`
- Test: `tests/project_first_rag/retrieval/test_project_scoped_search.py`
- Test: `tests/project_first_rag/retrieval/test_projects_router.py`

- [ ] Add `project_id` to project chat/search endpoints.
- [ ] Add project filter enforcement to every search request.
- [ ] Add `POST /api/v1/projects`, `POST /api/v1/projects/{id}/files`, `POST /api/v1/projects/{id}/chat`, `DELETE /api/v1/projects/{id}`.
- [ ] Keep current legacy endpoints alive during transition, but mark them legacy in docstrings and response metadata.

**Error rules:**
- unknown project -> 404
- project exists but no indexed knowledge -> 200 with insufficient-knowledge answer for chat, 200 with zero results for raw search
- incompatible index schema -> 503 typed error

## Chunk 4: Domain Preset Layer and Strict Grounded Agent Flow

### Task 7: Introduce KnowledgeDomainConfig and preset loader

**Files:**
- Create: `src/services/domain/models.py`
- Create: `src/services/domain/preset_loader.py`
- Create: `src/services/domain/prompt_renderer.py`
- Create: `presets/scoped_knowledge.yaml`
- Create: `presets/cv_matching.yaml`
- Create: `presets/app_docs.yaml`
- Create: `presets/prompts/default_grounded.txt`
- Create: `presets/prompts/cv_matching_addon.txt`
- Create: `presets/prompts/app_docs_addon.txt`
- Modify: `src/config.py`
- Test: `tests/project_first_rag/domain/test_preset_loader.py`

- [ ] Load preset YAML from configurable preset directory.
- [ ] Support fields:
  - `id`
  - `display_name`
  - `system_prompt_addon`
  - `metadata_extract`
  - `search_boost`
  - `routing_rules`
  - `answer_policy`
- [ ] Default bare project uses `scoped_knowledge`.
- [ ] Missing preset should fail fast during project creation, not at answer time.

### Task 8: Replace arXiv hard-coding in the agent graph

**Files:**
- Modify: `src/services/agents/context.py`
- Modify: `src/services/agents/models.py`
- Modify: `src/services/agents/prompts.py`
- Modify: `src/services/agents/tools.py`
- Modify: `src/services/agents/agentic_rag.py`
- Modify: `src/services/agents/nodes/guardrail_node.py`
- Create: `src/services/agents/nodes/insufficient_knowledge_node.py`
- Modify: `src/services/agents/nodes/generate_answer_node.py`
- Test: `tests/project_first_rag/agentic/test_scope_router.py`
- Test: `tests/project_first_rag/agentic/test_insufficient_knowledge_node.py`
- Test: `tests/project_first_rag/agentic/test_project_chat_grounding.py`

- [ ] Replace arXiv/CS/AI/ML prompt constants with project/preset-aware prompts.
- [ ] Rename the behavior from `out_of_scope` to `insufficient_knowledge` for strict projects.
- [ ] Ensure the fallback answer is LLM-generated but grounded in:
  - project name
  - file list
  - retrieval outcome
  - missing evidence explanation
  - suggested next questions based on indexed material
- [ ] Do not answer from model background knowledge when scope is strict.
- [ ] Update `SourceItem` to generic source metadata instead of `arxiv_id`-only structure.

## Chunk 5: Citation Engine, Domain Behaviors, and Rollout

### Task 9: Add citation engine and structured cited responses

**Files:**
- Create: `src/services/citation/citation_engine.py`
- Modify: `src/schemas/api/ask.py`
- Modify: `src/routers/agentic_ask.py`
- Modify: `src/services/ollama/prompts.py`
- Test: `tests/project_first_rag/citations/test_citation_engine.py`
- Test: `tests/project_first_rag/citations/test_agentic_chat_citations.py`

- [ ] Format inline citations as `[doc_name · trang X]`.
- [ ] Return structured citation objects with `doc_name`, `page_number`, `excerpt`, `file_id`, `source_uri`.
- [ ] Ensure no answer claim is returned without at least one citation when grounded context exists.
- [ ] When no grounded support exists, return no fake citations.

### Task 10: Domain-specific first presets and metadata extraction hooks

**Files:**
- Modify: `src/services/indexing/hybrid_indexer.py`
- Create: `src/services/domain/metadata_extractor.py`
- Test: `tests/project_first_rag/domain/test_cv_matching_preset.py`
- Test: `tests/project_first_rag/domain/test_app_docs_preset.py`

- [ ] Add metadata extraction hook interface, but keep first implementation minimal and synchronous.
- [ ] `cv_matching` first ship:
  - extract skills
  - extract experience years
  - support JD-to-CV comparison prompts
- [ ] `app_docs` first ship:
  - extract step number
  - action type
  - screen name
- [ ] Keep scoring heuristic explainable; do not add opaque rank fusion beyond current hybrid search.

### Task 11: Rollout docs and operational runbooks

**Files:**
- Create: `docs/runbooks/project-index-rebuild.md`
- Create: `docs/runbooks/create-project-and-ingest.md`
- Modify: `docs/SETUP_GUIDE.md`
- Modify: `README.md`
- Test: `tests/project_first_rag/smoke/test_project_first_smoke.py`

- [ ] Document local dev flow:
  - create project
  - upload/register files
  - run ingestion worker
  - chat against project
- [ ] Document rebuild procedure for a project index.
- [ ] Document preset authoring format and validation rules.

## Error and Rescue Registry

| Codepath | Failure | Exception / Signal | Rescue | User sees |
|---|---|---|---|---|
| Project creation | invalid preset | `ValueError` / custom preset error | 422 | clear validation message |
| Project index setup | incompatible mapping | `IncompatibleIndexSchemaError` | no silent fallback | 503 typed error |
| File ingest | parser failure | parser-specific exception | mark file failed + log | file status failed |
| File ingest | embedding failure | provider exception | retry or fail file | file status failed |
| Chat | no relevant chunks | explicit insufficient-knowledge route | natural grounded explanation | 200 answer with no unsupported claim |
| Chat | model unavailable | `ModelUnavailableError` | no fake domain fallback | 503 typed error |
| Search | timeout/network | backend exception | optional BM25 degrade if same project index works | degraded response with flag |

## Test Strategy

- `tests/project_first_rag/foundation/`
- `tests/project_first_rag/projects/`
- `tests/project_first_rag/indexing/`
- `tests/project_first_rag/ingestion/`
- `tests/project_first_rag/retrieval/`
- `tests/project_first_rag/agentic/`
- `tests/project_first_rag/citations/`
- `tests/project_first_rag/domain/`
- `tests/project_first_rag/smoke/`

Critical ship tests:
- create project -> ensure project index exists and validates
- ingest PDF into project -> chunks indexed with project/file/page metadata
- chat in strict mode with matching evidence -> cited grounded answer
- chat in strict mode without evidence -> natural insufficient-knowledge answer
- same query across two projects -> no cross-project leakage
- preset loading failure -> create project blocked early
- model unavailable -> typed infrastructure error, not fake policy answer

## Rollout Order

1. Ship foundation hardening first.
2. Ship project models and universal schema.
3. Ship project-scoped ingestion and retrieval.
4. Ship preset loader and agent graph refactor.
5. Ship citation engine and first two presets.
6. Migrate documentation and deprecate legacy arXiv-only endpoints.

## Post-Deploy Verification

- create one test project
- ingest one CV PDF and one manual PDF into separate projects
- verify each project only retrieves its own chunks
- verify chat returns citations
- verify unsupported query returns insufficient-knowledge explanation, not generic LLM knowledge
- verify logs distinguish retrieval miss vs model failure vs schema failure

## Risks to Watch

- arXiv assumptions are deep and repeated; search, agent, tracing, and schemas must be cleaned consistently
- current chunk model is named around papers/arxiv; partial conversion will leave confusing compatibility bugs
- project-per-index increases operational index count; acceptable for HOLD SCOPE, but monitor cluster limits
- `Base.metadata.create_all` is tolerable for this phase but will become a limit once schema evolution accelerates

## Plan Complete

Plan complete and saved to `docs/superpowers/plans/2026-03-15-multi-domain-project-rag-hold-scope.md`. Ready to execute?
