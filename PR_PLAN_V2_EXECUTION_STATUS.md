# Multi-Domain Project-First RAG Hold Scope v2 - Execution Status

Date: 2026-03-15
Scope mode: HOLD SCOPE

## Implemented in this PR slice

1. Strict vs augmented runtime control
- Added mode and tool-governance configuration fields in:
  - `src/services/agents/config.py`
  - `src/services/agents/context.py`
  - `src/schemas/api/ask.py`
  - `src/routers/agentic_ask.py`
- Added domain policy primitives:
  - `src/services/domain/models.py`
  - `src/services/domain/external_web_search_policy.py`

2. Planner and approval nodes
- Added planner node:
  - `src/services/agents/nodes/planner_node.py`
- Added human approval node:
  - `src/services/agents/nodes/human_approval_node.py`
- Added insufficient knowledge node:
  - `src/services/agents/nodes/insufficient_knowledge_node.py`
- Integrated new routes into LangGraph workflow:
  - `src/services/agents/agentic_rag.py`
  - `src/services/agents/nodes/__init__.py`

3. Tool layer expansion
- Added external web search tool:
  - `src/services/agents/web_search_tool.py`
- Added image perception tool:
  - `src/services/agents/image_perception_tool.py`
- Updated retrieval flow to honor planner-selected tool name:
  - `src/services/agents/nodes/retrieve_node.py`

4. Policy correctness hardening
- Strict mode blocks external search.
- Augmented mode supports approval-gated external search.
- Planner enforces project retrieval before external web search execution.

5. Prompt/model response contract cleanup
- Replaced arXiv-specific hard-coded prompt language with project-grounded wording:
  - `src/services/agents/prompts.py`
  - `src/services/agents/nodes/out_of_scope_node.py`
  - `src/services/agents/nodes/rewrite_query_node.py`

6. Import stability and test reliability
- Added lazy package export to avoid heavy import side effects in test collection:
  - `src/services/agents/__init__.py`
- Added fixtures and updated tests:
  - `tests/unit/services/agents/conftest.py`
  - `tests/unit/services/agents/test_planner_and_policy.py`
  - `tests/unit/services/agents/test_nodes.py`
  - `tests/unit/services/agents/test_tools.py`
  - `tests/unit/services/test_external_web_search_policy.py`

## Verification results

Executed:
- `python -m pytest tests/unit/services/agents -q`
- `python -m pytest tests/unit/services/test_external_web_search_policy.py -q`

Result:
- agents unit tests: 48 passed
- external search policy tests: 4 passed

## Intentionally deferred (still in plan)

1. Project model/repository/API/index-manager full migration
2. Preset YAML loader and prompt-rendering pipeline
3. Citation engine with structured project/external citation objects
4. Full project-scoped API surface and ingestion pipeline migration

