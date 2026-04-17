# FastAPI Test Guide - PR Plan v2 (PresetLoader + ProjectIndexManager + CitationEngine)

Date: 2026-03-15

## 1) Start API locally

Use local Python environment (no Docker required):

```powershell
uv run uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

If `uv` is unavailable:

```powershell
.\.venv\Scripts\python.exe -m uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

## 2) Verify health

```powershell
curl http://127.0.0.1:8000/api/v1/ping
```

Expected:
- HTTP `200`
- service responds healthy

## 3) Verify project index lifecycle endpoints

### 3.1 Ensure project index

```powershell
curl -X POST http://127.0.0.1:8000/api/v1/projects/recruitment-q3/index/ensure
```

Expected:
- HTTP `200`
- `index_name` like `project-recruitment-q3`
- `created=true` on first run, `created=false` on repeated run
- `validated=true`

### 3.2 Validate project index

```powershell
curl http://127.0.0.1:8000/api/v1/projects/recruitment-q3/index/validate
```

Expected:
- HTTP `200`
- `is_compatible=true`
- `issues=[]`

### 3.3 Delete project index

```powershell
curl -X DELETE http://127.0.0.1:8000/api/v1/projects/recruitment-q3/index
```

Expected:
- HTTP `200`
- `deleted=true` if index existed

## 4) Verify agentic ask with preset + mode

```powershell
curl -X POST http://127.0.0.1:8000/api/v1/ask-agentic ^
  -H "Content-Type: application/json" ^
  -d "{\"query\":\"Summarize key skills from uploaded CVs\",\"preset_id\":\"cv_matching\",\"mode\":\"strict\",\"allow_external_web_search\":false}"
```

Expected:
- HTTP `200`
- response contains:
  - `preset_id`
  - `planned_actions`
  - `mode`
  - `citations`
  - `source_count`
  - `sources` (URL list)

## 5) Verify augmented mode approval gate

Without approval:

```powershell
curl -X POST http://127.0.0.1:8000/api/v1/ask-agentic ^
  -H "Content-Type: application/json" ^
  -d "{\"query\":\"Search latest web updates on this topic\",\"mode\":\"augmented\",\"allow_external_web_search\":true,\"human_approval_granted\":false}"
```

Expected:
- HTTP `200`
- `approval_required=true`
- planner routes through approval logic

With approval:

```powershell
curl -X POST http://127.0.0.1:8000/api/v1/ask-agentic ^
  -H "Content-Type: application/json" ^
  -d "{\"query\":\"Search latest web updates on this topic\",\"mode\":\"augmented\",\"allow_external_web_search\":true,\"human_approval_granted\":true}"
```

Expected:
- HTTP `200`
- planner allows external path after internal retrieval attempt

## 6) Automated tests to run

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/services/test_preset_loader.py -q
.\.venv\Scripts\python.exe -m pytest tests/unit/services/indexing/test_project_index_manager.py -q
.\.venv\Scripts\python.exe -m pytest tests/unit/services/citation/test_citation_engine.py -q
.\.venv\Scripts\python.exe -m pytest tests/api/routers/test_projects.py -q
.\.venv\Scripts\python.exe -m pytest tests/unit/services/agents tests/api/routers/test_agentic_ask.py -q
```

## 7) Production readiness checklist for this chunk

- Preset directory exists and contains `scoped_knowledge` preset.
- OpenSearch reachable and `index.knn=true` for project indexes.
- `ask-agentic` returns structured `citations` and `source_count`.
- Strict mode blocks external search.
- Augmented mode enforces approval gate as configured.
