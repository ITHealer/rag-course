# Multi-Domain Project-First RAG Implementation Plan v2

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the current arXiv-specific RAG system into a project-first, strictly grounded, multi-domain document QA platform with configurable domain presets, explicit planning, optional human approval, policy-gated external augmentation, and image-aware perception.

**Architecture:** Keep the existing FastAPI + LangGraph + OpenSearch stack, but move the core from a single global arXiv index to project-scoped indexing with a universal chunk schema. Use a workflow-first graph with explicit specialized nodes: `PlannerNode`, `GroundingEvaluator`, `HumanApprovalNode`, `InsufficientKnowledgeNode`, and `CitationEngine`. Add domain presets as YAML + prompt addons and add `strict` vs `augmented` mode semantics at the project level.

**Tech Stack:** FastAPI, LangGraph, OpenSearch, PostgreSQL, Pydantic Settings, Docling PDF parser, Ollama, pytest

---

## Scope Mode

This plan is intentionally written for **HOLD SCOPE**.

- No repo migration to OpenRAG in this implementation.
- No UI rewrite.
- No generic internet/general-knowledge fallback answers.
- No full multi-agent supervisor architecture in this phase.
- No attempt to solve every future preset in the first ship.

## Key Decisions

1. Keep the current codebase and refactor in place.
2. Introduce **project-first scoping** as the main boundary.
3. Use **strict grounded answering only** as the default behavior.
4. Add explicit project modes:
   - `strict`
   - `augmented`
5. Add `PlannerNode`, but keep the system workflow-first rather than upgrading to a full multi-agent architecture.
6. Add `HumanApprovalNode` for boundary-crossing actions rather than forcing approval through every request.
7. Add `ExternalWebSearchPolicy` so external retrieval is explicit, controlled, and testable.
8. Add `ImagePerceptionTool` for request attachments and project-local images/screenshots.
9. Replace arXiv-specific assumptions in prompts, tools, response schemas, and ingestion payloads with a universal document model.
10. Store domain specialization in YAML + prompt-addon files. Because `src/config.py` already exists as a module file, do **not** create `src/config/preset_loader.py`; create `src/services/domain/preset_loader.py` instead.

## Not In Scope

- Rebuilding the Telegram bot for project-first UX in this phase
- Full notebook UI / drag-and-drop UI
- OCR-heavy pipelines for scanned PDFs beyond current parser capabilities
- Cross-project federated retrieval
- Fine-tuned rerankers or learned ranking models
- Rich asynchronous job queue platform beyond current worker/DAG model
- Auto-classification for every document type on day one
- Automatic memory writing into the answer hot path

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
- no planner node
- no approval gate
- no web search policy
- no image perception tool

After this plan:
- project-scoped indexing and retrieval
- universal chunk schema for any document domain
- configurable domain presets
- strict grounded responses with citations and natural insufficient-knowledge handling
- planner-aware workflow for multi-step queries
- explicit approval gate for external augmentation
- image-aware perception within project boundaries

12-month ideal not yet covered:
- richer UI
- project task tracking
- richer preset marketplace
- federated/project collections

## Mode Semantics

### Strict mode

- Only project knowledge and user-provided request inputs may be used as evidence.
- Project-local images and request image attachments are allowed inputs for `ImagePerceptionTool`.
- External web search is forbidden.
- If evidence is insufficient, answer with `insufficient_knowledge`.

### Augmented mode

- Project knowledge remains the first retrieval source.
- External web search may supplement project evidence if allowed by `ExternalWebSearchPolicy`.
- Human approval may be required before external search executes.
- External citations must be labeled separately from project citations.

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
      -> PlannerNode
      -> HumanApprovalNode (optional)
      -> ProjectRetrievalTool
      -> ImagePerceptionTool
      -> ExternalWebSearchTool (augmented only)
      -> GroundingEvaluator
      -> Citation Engine
      -> Insufficient Knowledge Node
  -> Response
```

```text
Happy path:
file upload -> project file record -> parse -> chunk -> embed -> index(project-X) -> plan -> retrieve(project-X) -> reflect -> answer + citations

Nil path:
missing project -> 404 / typed error

Empty path:
project exists but no indexed chunks -> insufficient_knowledge response

Error path:
parser/index/LLM/search failure -> typed error or degraded behavior with explicit signal

External access path:
planner wants web search -> policy check -> optional human approval -> external search -> reflect -> answer with external citations
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

### Task 2: Introduce typed infrastructure failures for agentic flow

**Files:**
- Create: `src/services/agents/errors.py`
- Modify: `src/services/agents/agentic_rag.py`
- Modify: `src/services/agents/nodes/out_of_scope_node.py`
- Modify: `src/services/ollama/client.py`
- Test: `tests/project_first_rag/foundation/test_agentic_infra_failures.py`

- [ ] Add typed errors for `ModelUnavailableError`, `PromptRenderError`, `InsufficientKnowledgeError`, `ProjectScopeError`, `PlannerValidationError`, `ApprovalRequiredError`.
- [ ] Ensure model/network failures are not silently translated into domain-policy answers.
- [ ] Keep current `out_of_scope_node` only as a temporary compatibility node until the replacement lands in Chunk 4.

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

## Chunk 4: Domain Preset Layer, Modes, and Tool Governance

### Task 7: Introduce KnowledgeDomainConfig, project modes, and policy loader

**Files:**
- Create: `src/services/domain/models.py`
- Create: `src/services/domain/preset_loader.py`
- Create: `src/services/domain/prompt_renderer.py`
- Create: `src/services/domain/external_web_search_policy.py`
- Create: `presets/scoped_knowledge.yaml`
- Create: `presets/cv_matching.yaml`
- Create: `presets/app_docs.yaml`
- Create: `presets/prompts/default_grounded.txt`
- Create: `presets/prompts/cv_matching_addon.txt`
- Create: `presets/prompts/app_docs_addon.txt`
- Modify: `src/config.py`
- Test: `tests/project_first_rag/domain/test_preset_loader.py`
- Test: `tests/project_first_rag/domain/test_external_web_search_policy.py`

- [ ] Load preset YAML from configurable preset directory.
- [ ] Support fields:
  - `id`
  - `display_name`
  - `system_prompt_addon`
  - `metadata_extract`
  - `search_boost`
  - `routing_rules`
  - `answer_policy`
  - `allow_external_web_search`
  - `require_human_approval_for_external_search`
  - `allow_image_perception`
  - `allowed_external_domains`
- [ ] Default bare project uses `scoped_knowledge`.
- [ ] Missing preset should fail fast during project creation, not at answer time.
- [ ] Model `strict` vs `augmented` behavior explicitly in config and APIs.

## Chunk 5: Planner, Approval, and Agent Graph Refactor

### Task 8: Replace arXiv hard-coding in the agent graph and add planning

**Files:**
- Modify: `src/services/agents/context.py`
- Modify: `src/services/agents/models.py`
- Modify: `src/services/agents/prompts.py`
- Modify: `src/services/agents/tools.py`
- Modify: `src/services/agents/agentic_rag.py`
- Modify: `src/services/agents/nodes/guardrail_node.py`
- Create: `src/services/agents/nodes/planner_node.py`
- Create: `src/services/agents/nodes/human_approval_node.py`
- Create: `src/services/agents/nodes/insufficient_knowledge_node.py`
- Create: `src/services/agents/web_search_tool.py`
- Create: `src/services/agents/image_perception_tool.py`
- Modify: `src/services/agents/nodes/generate_answer_node.py`
- Test: `tests/project_first_rag/agentic/test_scope_router.py`
- Test: `tests/project_first_rag/agentic/test_planner_node.py`
- Test: `tests/project_first_rag/agentic/test_human_approval_node.py`
- Test: `tests/project_first_rag/agentic/test_insufficient_knowledge_node.py`
- Test: `tests/project_first_rag/agentic/test_project_chat_grounding.py`
- Test: `tests/project_first_rag/agentic/test_augmented_mode_external_search.py`
- Test: `tests/project_first_rag/agentic/test_image_perception_tool.py`

- [ ] Replace arXiv/CS/AI/ML prompt constants with project/preset-aware prompts.
- [ ] Add `PlannerNode` before tool execution.
- [ ] `PlannerNode` must decide:
  - internal retrieval only
  - image perception needed
  - external web search eligibility
  - approval required or not
- [ ] Add `HumanApprovalNode` for boundary-crossing actions, especially external web search.
- [ ] Rename the behavior from `out_of_scope` to `insufficient_knowledge` for strict projects.
- [ ] Ensure the fallback answer is LLM-generated but grounded in:
  - project name
  - file list
  - retrieval outcome
  - missing evidence explanation
  - suggested next questions based on indexed material
- [ ] Do not answer from model background knowledge when scope is strict.
- [ ] Allow external web search only in augmented mode and only after project retrieval has already been attempted.
- [ ] Ensure external citations are tagged separately from project citations.
- [ ] Add `ImagePerceptionTool` for:
  - request image attachments
  - project-local screenshots/images
- [ ] Forbid external image lookup in strict mode.
- [ ] Update `SourceItem` to generic source metadata instead of `arxiv_id`-only structure.

## Chunk 6: Citation Engine and Domain Behaviors

### Task 9: Add citation engine and structured cited responses

**Files:**
- Create: `src/services/citation/citation_engine.py`
- Modify: `src/schemas/api/ask.py`
- Modify: `src/routers/agentic_ask.py`
- Modify: `src/services/ollama/prompts.py`
- Test: `tests/project_first_rag/citations/test_citation_engine.py`
- Test: `tests/project_first_rag/citations/test_agentic_chat_citations.py`

- [ ] Format inline citations as `[doc_name - page X]` or the localized display variant chosen by product.
- [ ] Return structured citation objects with `doc_name`, `page_number`, `excerpt`, `file_id`, `source_uri`.
- [ ] Ensure no answer claim is returned without at least one citation when grounded context exists.
- [ ] When no grounded support exists, return no fake citations.
- [ ] Add a citation type discriminator:
  - `project`
  - `external_web`

### Task 10: Domain-specific first presets and metadata extraction hooks

**Files:**
- Modify: `src/services/indexing/hybrid_indexer.py`
- Create: `src/services/domain/metadata_extractor.py`
- Modify: `presets/cv_matching.yaml`
- Modify: `presets/app_docs.yaml`
- Modify: `presets/scoped_knowledge.yaml`
- Test: `tests/project_first_rag/domain/test_cv_matching_preset.py`
- Test: `tests/project_first_rag/domain/test_app_docs_preset.py`
- Test: `tests/project_first_rag/domain/test_preset_planner_routing.py`

- [ ] Add metadata extraction hook interface, but keep first implementation minimal and synchronous.
- [ ] `cv_matching` first ship:
  - extract skills
  - extract experience years
  - allow planner-generated JD comparison steps
  - support grounded interview question generation
- [ ] `app_docs` first ship:
  - extract step number
  - action type
  - screen name
  - allow planner-generated screenshot-aware instructions
- [ ] `scoped_knowledge` should default to internal retrieval only and deny external web search.
- [ ] Keep scoring heuristic explainable; do not add opaque rank fusion beyond current hybrid search.

## Chunk 7: Rollout Docs and Operational Runbooks

### Task 11: Rollout docs and operational runbooks

**Files:**
- Create: `docs/runbooks/project-index-rebuild.md`
- Create: `docs/runbooks/create-project-and-ingest.md`
- Create: `docs/runbooks/augmented-mode-approval-flow.md`
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
- [ ] Document strict vs augmented mode behavior.
- [ ] Document operator expectations for external search approval.

## Error and Rescue Registry

| Codepath | Failure | Exception / Signal | Rescue | User sees |
|---|---|---|---|---|
| Project creation | invalid preset | `ValueError` / custom preset error | 422 | clear validation message |
| Project index setup | incompatible mapping | `IncompatibleIndexSchemaError` | no silent fallback | 503 typed error |
| File ingest | parser failure | parser-specific exception | mark file failed + log | file status failed |
| File ingest | embedding failure | provider exception | retry or fail file | file status failed |
| Planner | invalid plan output | planner validation error | fallback to internal retrieval-only plan | grounded response or insufficient_knowledge |
| External search | policy denied | policy decision | skip tool | project-only answer or insufficient_knowledge |
| External search | approval denied | approval signal | skip tool | project-only answer or insufficient_knowledge |
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
- chat in augmented mode with policy deny -> no external access
- chat in augmented mode with approval grant -> external citations appear separately
- image-based question over uploaded screenshot -> grounded cited answer
- same query across two projects -> no cross-project leakage
- preset loading failure -> create project blocked early
- model unavailable -> typed infrastructure error, not fake policy answer

## Rollout Order

1. Ship foundation hardening first.
2. Ship project models and universal schema.
3. Ship project-scoped ingestion and retrieval.
4. Ship preset loader and mode semantics.
5. Ship planner node, approval node, and policy-gated external search.
6. Ship image perception and citation engine updates.
7. Ship first two presets with planner-aware behavior.
8. Migrate documentation and deprecate legacy arXiv-only endpoints.

## Post-Deploy Verification

- create one test project
- ingest one CV PDF and one manual PDF into separate projects
- verify each project only retrieves its own chunks
- verify chat returns citations
- verify unsupported query returns insufficient-knowledge explanation, not generic LLM knowledge
- verify strict mode denies external search
- verify augmented mode requires or bypasses approval according to policy
- verify image perception works only on allowed image sources
- verify logs distinguish retrieval miss vs model failure vs schema failure

## Risks to Watch

- arXiv assumptions are deep and repeated; search, agent, tracing, and schemas must be cleaned consistently
- current chunk model is named around papers/arxiv; partial conversion will leave confusing compatibility bugs
- project-per-index increases operational index count; acceptable for HOLD SCOPE, but monitor cluster limits
- adding web search without hard mode boundaries would break grounded semantics, so policy enforcement is non-negotiable
- image perception can silently widen scope if external image fetch is not explicitly blocked in strict mode
- `Base.metadata.create_all` is tolerable for this phase but will become a limit once schema evolution accelerates

## Plan Complete

This v2 plan supersedes `docs/superpowers/plans/2026-03-15-multi-domain-project-rag-hold-scope.md`.
