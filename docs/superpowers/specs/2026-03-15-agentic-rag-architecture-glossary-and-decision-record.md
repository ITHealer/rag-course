# Agentic RAG Architecture Glossary and Decision Record

**Author:** Codex
**Date:** 2026-03-15
**Status:** Draft for review

## Overview

This document defines the architecture vocabulary for the project-first RAG refactor and records the decisions that will govern the next implementation PRs.

The immediate purpose is to prevent the implementation from conflating:

- RAG vs Agentic RAG
- tool vs skill/preset
- strict grounded QA vs externally augmented QA
- workflow node vs agent
- routing vs planning vs reflection

## Problem Statement

The current system mixes arXiv-specific policy, retrieval logic, and answer generation into one workflow. That makes it difficult to:

- support multiple knowledge domains
- add image perception without breaking scope rules
- add web search without contaminating grounded answers
- add planning or human approval without overcomplicating the graph

The project needs a shared vocabulary before implementation so that code, prompts, APIs, and docs all use the same architectural terms.

## Current Repository Mapping

Current repository status:

- `src/services/agents/agentic_rag.py` orchestrates a single LangGraph workflow.
- `src/services/agents/nodes/guardrail_node.py` acts as a simple router.
- `src/services/agents/nodes/retrieve_node.py` creates retrieval tool calls.
- `src/services/agents/tools.py` contains the current retrieval tool.
- `src/services/agents/nodes/grade_documents_node.py` acts as an evaluator.
- `src/services/agents/nodes/rewrite_query_node.py` acts as limited replanning.
- `src/services/agents/nodes/out_of_scope_node.py` handles policy fallback.

Conclusion:

- The current system is a **workflow-first Agentic RAG**.
- It is **not** yet a planner-driven architecture.
- It is **not** yet a multi-agent architecture.
- It has **no human-in-the-loop** node.
- It has **no image perception tool**.
- It has **no web search tool**.

## Architecture Glossary

| Term | Definition | Allowed role in this project |
|---|---|---|
| `RAG` | Retrieval-Augmented Generation using indexed project knowledge as evidence for answer generation | Core foundation |
| `Agentic RAG` | RAG wrapped in a control loop that can route, retrieve, retry, evaluate, and optionally call tools | Core orchestration style |
| `Workflow` | A graph of explicit nodes with deterministic edges and bounded loops | Preferred implementation style |
| `Agent` | A runtime decision-maker that can choose actions based on state and tool results | Used inside workflow boundaries |
| `Tool` | A callable runtime capability such as project retrieval, image perception, or web search | Runtime only |
| `Skill` | A reusable capability bundle of instructions, references, policies, and optional scripts | Do not use as product term |
| `DomainPreset` | Product-level bundle of prompts, metadata extraction hints, and policies for a knowledge domain | Preferred product term |
| `PlannerNode` | A workflow node that decomposes the user goal into explicit steps or an execution plan | Added in refactor |
| `Reflection` / `Evaluator` | A node that judges evidence quality, grounding sufficiency, or whether another action is required | Required |
| `HumanApprovalNode` | A node that pauses the graph and requires a human decision before proceeding | Added for gated actions |
| `ImagePerceptionTool` | A tool that extracts grounded observations from images or screenshots provided by the user or stored in project assets | Added with mode rules |
| `ExternalWebSearchTool` | A tool that retrieves information from trusted external web sources | Only for augmented mode |
| `ExternalWebSearchPolicy` | The policy layer that determines whether external search is allowed and under what controls | Required if web search exists |
| `Strict mode` | A project mode where only project knowledge and user-provided inputs are allowed as evidence | Default |
| `Augmented mode` | A project mode where external web search may supplement project knowledge under policy and approval rules | Optional |
| `Grounding` | The property that every answer claim is supported by explicit evidence | Mandatory |
| `Citation Engine` | The formatter that turns evidence into user-facing citations | Mandatory |
| `Memory` | Persisted state that can affect future behavior | Optional and out of hot path |
| `Learn` | The act of writing new memory, rules, or summaries after a run | Not part of answer hot path |

## Tool vs Skill vs Preset

```text
Tool        = runtime action
Skill       = reusable expertise/instructions bundle
DomainPreset= product configuration bundle for one knowledge domain
```

Rules:

1. Runtime code should use the term `tool` only for callable actions.
2. Product architecture should use the term `DomainPreset`, not `skill`.
3. Internal documentation may refer to external platform skills, but that is separate from runtime architecture.

## Mode Definitions

### Strict Mode

Strict mode is the default mode for project QA.

Allowed evidence:

- indexed chunks from the current project
- user-provided text in the current request
- user-provided images in the current request
- project-local images or screenshots already uploaded into the project

Forbidden evidence:

- external web search
- unrelated project data
- model background knowledge as answer evidence
- external image lookup

Response rule:

- if evidence is insufficient, the assistant must return a natural `insufficient_knowledge` answer
- the answer may suggest follow-up questions based on project contents
- the answer may not fabricate claims from general knowledge

### Augmented Mode

Augmented mode is an explicit opt-in mode.

Allowed evidence:

- all strict mode evidence
- external web search results returned by approved trusted tools

Conditions:

- external search must be gated by `ExternalWebSearchPolicy`
- external citations must be labeled separately from project citations
- the graph should prefer internal project retrieval first
- external search may require human approval depending on policy

## Mode Matrix

| Capability | Strict | Augmented |
|---|---|---|
| Project retrieval | Yes | Yes |
| User-uploaded image understanding | Yes | Yes |
| Project-local screenshot/image understanding | Yes | Yes |
| External web search | No | Yes |
| External image retrieval | No | Policy-dependent |
| General model background knowledge as final evidence | No | No |
| Human approval for external access | N/A | Yes, when configured |

## Reference Architecture

```text
User Input
  -> Perception Layer
      -> text input
      -> file/project context
      -> optional image perception
  -> PlannerNode
      -> decide plan
      -> decide tools
      -> decide whether approval is needed
  -> Tool Execution
      -> ProjectRetrievalTool
      -> ImagePerceptionTool
      -> ExternalWebSearchTool (augmented only)
  -> Reflection Layer
      -> grounding evaluator
      -> citation sufficiency check
      -> retry / refine / stop
  -> Answer Generation
      -> CitationEngine
      -> grounded response or insufficient_knowledge response
```

```text
External access gate:

PlannerNode
  -> wants external web search?
      -> no  -> continue with internal tools
      -> yes -> ExternalWebSearchPolicy
                  -> denied  -> insufficient_knowledge or ask user to switch mode
                  -> allowed -> HumanApprovalNode (if required)
                                  -> approved -> execute search
                                  -> rejected -> continue without external search
```

## Decision Record

### DR-001: Use workflow-first Agentic RAG, not full multi-agent, for this phase

**Context**

The current system already uses LangGraph and explicit nodes. The requested refactor adds project scoping, presets, web search policy, image perception, and approval gates. Full multi-agent orchestration would increase complexity sharply.

**Options considered**

1. Full multi-agent supervisor architecture
2. Workflow-first graph with explicit specialized nodes
3. Single prompt-driven monolith with tool calling

**Decision**

Choose option 2.

**Rationale**

- aligns with current codebase
- keeps state transitions inspectable
- is easier to test and gate
- supports planning and approvals without introducing agent sprawl

**Implication**

`PlannerNode`, `GroundingEvaluator`, and `HumanApprovalNode` are nodes in one graph, not separate long-lived agents.

### DR-002: Add PlannerNode, but keep it lightweight

**Context**

The current graph has routing and limited query rewriting, but no explicit planning stage.

**Decision**

Add `PlannerNode` before tool execution.

**Planner responsibilities**

- classify the task shape
- decide whether a single retrieval is enough
- decide whether image perception is needed
- decide whether external search is even eligible
- output a bounded step plan, not free-form chain-of-thought

**Implication**

Simple requests may produce a one-step plan. Complex requests such as JD-to-CV matching may produce a short structured plan.

### DR-003: Add HumanApprovalNode for boundary-crossing actions

**Context**

Human-in-the-loop is not required for basic strict QA, but becomes important when the graph wants to cross knowledge boundaries.

**Decision**

Add `HumanApprovalNode` as an optional gate, not a mandatory hop in every request.

**Approval cases**

- external web search in augmented mode
- future side-effect tools
- ambiguous project/preset selection

**Implication**

Strict mode usually bypasses approval because external search is forbidden. Augmented mode may pause for approval.

### DR-004: External web search is policy-controlled and mode-scoped

**Context**

Web search is useful, but it breaks pure project-grounded semantics unless controlled.

**Decision**

Introduce `ExternalWebSearchPolicy`.

**Policy requirements**

- disabled in strict mode
- enabled only in augmented mode
- project retrieval must run first
- allowlist/denylist domains supported
- external citations labeled distinctly
- max web search steps bounded

**Implication**

Web search becomes an explicit product capability, not a hidden fallback.

### DR-005: ImagePerceptionTool is allowed in strict mode only for project-local or user-provided images

**Context**

Image understanding is useful for CV scans, certificates, screenshots, and app guide images. It does not necessarily violate grounding if the image belongs to the project or request.

**Decision**

Introduce `ImagePerceptionTool` with source-boundary rules.

**Strict mode rules**

- allowed for current request image attachments
- allowed for project-uploaded images and screenshots
- not allowed to fetch external images

**Augmented mode**

- may combine image perception with external results if policy allows

**Implication**

Image input is modeled as part of `Perceive`, not as external knowledge by default.

### DR-006: Learning and memory stay out of the answer hot path

**Context**

The generic loop includes `Learn`, but automatic learning can pollute the grounded corpus.

**Decision**

Do not add automatic memory writing into the main answer flow for this phase.

**Implication**

- project knowledge remains ingestion-driven
- optional memory can be added later for user preferences or workflow summaries
- no chat output should silently mutate retrieval truth

## Naming Rules for the PR

Use these terms consistently:

- `DomainPreset`
- `PlannerNode`
- `HumanApprovalNode`
- `GroundingEvaluator`
- `InsufficientKnowledge`
- `ExternalWebSearchPolicy`
- `ImagePerceptionTool`

Avoid these terms in code and product docs for the new runtime:

- `out_of_scope` for retrieval misses in strict projects
- `skill` as a product/runtime term
- `agent` for every node

## Implications for the Updated PR Plan

The implementation plan must now include:

1. `PlannerNode`
2. `HumanApprovalNode`
3. `ExternalWebSearchPolicy`
4. `ImagePerceptionTool`
5. explicit `strict` vs `augmented` mode semantics
6. separate handling of `project citations` vs `external citations`

## References

- Anthropic, *Building effective agents*, 2024-12-19
- LangGraph docs on agentic RAG
- LangGraph docs on workflows and agents
- LangGraph docs on human-in-the-loop
- OpenAI docs on function calling, web search, file search, and image inputs
- OpenAI Codex docs on skills
