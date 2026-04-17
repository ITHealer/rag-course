# PR Plan v3 - Project API Control Plane (HOLD SCOPE)

Date: 2026-03-15  
Mode: HOLD SCOPE  
Objective: make the backend API-first for project/domain configuration, document upload/ingestion, chunk inspection, and operational tracing so FE/BE integrations do not depend on local folder conventions.

## 1) Problem to Solve

Current gaps:
- API naming is still index-centric and unclear for product use.
- Missing full `project` lifecycle APIs (create/update/list/delete).
- Missing `domain/preset` management APIs for custom domain behavior.
- Missing upload API for documents (currently dependent on local `data/` folder).
- Missing APIs for ingestion status/statistics/chunk inspection per document.
- Missing explicit trace/log options per request for debugging and operations.

## 2) Approaches Considered

### A) Minimal patch
- Keep existing routes, add only upload endpoint and one stats endpoint.
- Pros: fastest.
- Cons: still fragmented, hard to scale FE workflows, domain config still file-only.

### B) Recommended (selected)
- Add a clear control-plane API:
  - `domains` for config/prompt management
  - `projects` for scope lifecycle
  - `documents` for upload/ingestion/status/chunk inspection
  - `traces` for runtime observability
- Keep current ask/search endpoints backward-compatible.
- Pros: consistent integration contract, production-friendly, minimal architecture risk.
- Cons: medium scope (new models/repos/routes/services).

### C) Full OpenRAG-style task platform
- Add rich task orchestration with realtime progress bus, history timeline, retry engine.
- Pros: closest UX to OpenRAG.
- Cons: too large for current HOLD SCOPE phase.

Decision: **B**.

## 3) API Contract (Target)

### 3.1 Domain Configuration APIs

`POST /api/v1/domains`
- Create domain profile/preset via API.
- Request options:
  - `id`, `display_name`
  - `mode_default`: `strict|augmented`
  - `system_prompt_addon`
  - `allow_external_web_search`
  - `require_human_approval_for_external_search`
  - `allow_image_perception`
  - `allowed_external_domains`
  - `metadata_extract[]`
  - `search_boost[]`
  - `answer_policy`

`GET /api/v1/domains`  
`GET /api/v1/domains/{domain_id}`  
`PATCH /api/v1/domains/{domain_id}`  
`DELETE /api/v1/domains/{domain_id}`

`POST /api/v1/domains/{domain_id}/prompts`
- Update prompt templates by type (`system_addon`, `insufficient_knowledge`, `planner`, etc).

### 3.2 Project APIs

`POST /api/v1/projects`  
`GET /api/v1/projects`  
`GET /api/v1/projects/{project_id}`  
`PATCH /api/v1/projects/{project_id}`  
`DELETE /api/v1/projects/{project_id}`

`POST /api/v1/projects/{project_id}/index/ensure`  
`GET /api/v1/projects/{project_id}/index/validate`  
`DELETE /api/v1/projects/{project_id}/index`

### 3.3 Document APIs (upload + ingestion + inspection)

`POST /api/v1/projects/{project_id}/documents` (multipart/form-data)
- Upload one or many files into `data/projects/{project_id}/`.
- Options:
  - `ingest_mode`: `async|sync` (default `async`)
  - `overwrite`: `true|false`
  - `parser_options` (optional override)

`GET /api/v1/projects/{project_id}/documents`
- Return:
  - `status` (`pending|processing|completed|failed`)
  - `size_bytes`
  - `chunk_count`
  - `embedding_model`
  - `indexed_at`

`GET /api/v1/projects/{project_id}/documents/{document_id}`

`GET /api/v1/projects/{project_id}/documents/{document_id}/chunks`
- Query options: `page`, `page_size`, `query`, `include_vector=false`, `sort`.

`GET /api/v1/projects/{project_id}/ingestions`  
`GET /api/v1/projects/{project_id}/ingestions/{task_id}`  
`POST /api/v1/projects/{project_id}/ingestions/{task_id}/retry`

### 3.4 Chat/Ask API refinements

`POST /api/v1/ask-agentic`
- Keep endpoint and enforce explicit scoped behavior:
  - `project_id` (required in production profile)
  - `domain_id|preset_id` optional override
  - `trace_options`
- Response includes:
  - `citations[]`, `source_count`, `planned_actions`, `preset_id`, `trace_id`.

### 3.5 Observability APIs

`GET /api/v1/projects/{project_id}/stats`
- aggregated processing/search stats.

`GET /api/v1/traces/{trace_id}`  
`GET /api/v1/projects/{project_id}/traces`

## 4) Tracing and Log Options (per request)

Add `trace_options` on ask/upload:
- `enabled`: bool
- `level`: `off|basic|debug`
- `include_planner`
- `include_tool_inputs`
- `include_tool_outputs`
- `include_chunk_preview`
- `persist`: `none|file|db`

Structured log payload:
- `trace_id`, `project_id`, `domain_id`, `request_id`, `node`, `event`, `duration_ms`, `status`, `error_code`.

Minimum trace events:
- `project.scope.validated`
- `domain.config.resolved`
- `document.uploaded`
- `ingestion.started|completed|failed`
- `planner.decision`
- `tool.call`
- `citation.built`

## 5) Data Model Additions

Models:
- `src/models/domain_profile.py`
- `src/models/project.py`
- `src/models/project_document.py`
- `src/models/ingestion_task.py`
- `src/models/trace_event.py` (optional when `persist=db`)

Repositories:
- `src/repositories/domain_profile.py`
- `src/repositories/project.py`
- `src/repositories/project_document.py`
- `src/repositories/ingestion_task.py`
- `src/repositories/trace_event.py` (optional)

## 6) Implementation Chunks

### Chunk 1: Domain + Project control plane
- Add schemas/models/repositories/routers for domain & project CRUD.
- Wire dependencies and OpenAPI examples.

### Chunk 2: Document upload and ingestion job APIs
- Add upload endpoint with safe file storage.
- Add ingestion task lifecycle and async worker integration.

### Chunk 3: Chunk inspection and stats APIs
- Expose chunk list/search/detail per document.
- Expose project-level processing stats.

### Chunk 4: Trace options and structured logs
- Add trace options schema and structured log event service.
- Add trace retrieval APIs.

### Chunk 5: Backward compatibility and docs
- Keep legacy endpoints and mark as legacy in docs.
- Add migration note for FE/BE clients.

## 7) Testing Plan

Unit:
- validators, file upload safety, task transitions, chunk pagination, trace option parsing.

API:
- domains CRUD, projects CRUD, upload+status, chunks API, ask-agentic with trace options.

Integration:
- upload -> ingest -> chunks available -> ask-agentic returns grounded citations.

## 8) Acceptance Criteria

- Domain behavior can be configured entirely via API.
- Project can be created/updated/deleted via API.
- Document upload and ingestion progress are visible via API.
- Chunk inspection API works per document.
- ask-agentic returns citations and trace metadata.
- Trace options produce observable structured logs.

## 9) Risks and Mitigations

Risk: upload abuse/oversize.  
Mitigation: type/size limits + quotas + sanitize filenames.

Risk: ingestion overload.  
Mitigation: bounded concurrency + retry/backoff + failed state.

Risk: config drift.  
Mitigation: DB as runtime source of truth; YAML only bootstrap seed.

## 10) Out of Scope

- Full realtime OpenRAG-like websocket dashboard.
- Full RBAC/tenant IAM.
- ML-based ranking retraining pipeline.
