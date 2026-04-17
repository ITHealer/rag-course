from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from src.services.agents.agentic_rag import AgenticRAGService
from src.services.agents.config import GraphConfig
from src.services.agents.models import GuardrailScoring


@pytest.fixture
def service_with_defaults(mock_opensearch_client, mock_ollama_client, mock_jina_embeddings_client):
    config = GraphConfig(model="llama3.2:1b", top_k=3, use_hybrid=True)
    return AgenticRAGService(
        opensearch_client=mock_opensearch_client,
        ollama_client=mock_ollama_client,
        embeddings_client=mock_jina_embeddings_client,
        langfuse_tracer=None,
        graph_config=config,
    )


@pytest.mark.asyncio
async def test_ask_returns_preset_and_structured_citations(service_with_defaults):
    service_with_defaults.graph.ainvoke = AsyncMock(
        return_value={
            "messages": [HumanMessage(content="test"), AIMessage(content="Grounded answer")],
            "retrieval_attempts": 1,
            "guardrail_result": GuardrailScoring(score=90, reason="ok"),
            "relevant_sources": [
                {
                    "source_type": "project",
                    "doc_name": "sample.pdf",
                    "page_number": 5,
                    "source_uri": "file://sample.pdf",
                    "excerpt": "Evidence excerpt",
                }
            ],
            "grading_results": [],
            "metadata": {"planned_actions": ["project_retrieval"]},
            "rewritten_query": None,
        }
    )

    result = await service_with_defaults.ask(query="test")

    assert result["preset_id"] == "scoped_knowledge"
    assert result["source_count"] == 1
    assert len(result["citations"]) == 1
    assert result["citations"][0]["doc_name"] == "sample.pdf"


@pytest.mark.asyncio
async def test_ask_resolves_domain_profile_from_project_context(
    mock_opensearch_client,
    mock_ollama_client,
    mock_jina_embeddings_client,
):
    project_id = uuid4()

    class FakeDomainRepo:
        def get_by_domain_id(self, domain_id: str):
            if domain_id != "cv_recruitment":
                return None
            return type(
                "DomainProfileEntity",
                (),
                {
                    "domain_id": "cv_recruitment",
                    "display_name": "CV Recruitment",
                    "mode_default": "augmented",
                    "system_prompt_addon": "You are a recruitment expert.",
                    "metadata_extract": [],
                    "search_boost": [],
                    "answer_policy": {"grounded_only": True},
                    "allow_external_web_search": False,
                    "require_human_approval_for_external_search": True,
                    "allow_image_perception": True,
                    "allowed_external_domains": [],
                },
            )()

    class FakeProjectRepo:
        def get_by_id(self, lookup_project_id):
            if lookup_project_id != project_id:
                return None
            return type("ProjectEntity", (), {"domain_id": "cv_recruitment"})()

    service = AgenticRAGService(
        opensearch_client=mock_opensearch_client,
        ollama_client=mock_ollama_client,
        embeddings_client=mock_jina_embeddings_client,
        graph_config=GraphConfig(model="llama3.2:1b", top_k=3, use_hybrid=True),
        domain_profile_repository=FakeDomainRepo(),
        project_repository=FakeProjectRepo(),
    )

    service.graph.ainvoke = AsyncMock(
        return_value={
            "messages": [HumanMessage(content="test"), AIMessage(content="Grounded answer")],
            "retrieval_attempts": 1,
            "guardrail_result": GuardrailScoring(score=90, reason="ok"),
            "relevant_sources": [],
            "grading_results": [],
            "metadata": {"planned_actions": ["project_retrieval"]},
            "rewritten_query": None,
        }
    )

    result = await service.ask(query="test", project_id=str(project_id))

    assert result["preset_id"] == "cv_recruitment"
    assert result["mode"] == "augmented"
