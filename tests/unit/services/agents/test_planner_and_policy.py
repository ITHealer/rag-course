from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from langchain_core.messages import HumanMessage
from langgraph.runtime import Runtime

from src.services.agents.nodes.human_approval_node import continue_after_human_approval
from src.services.agents.nodes.planner_node import ainvoke_planner_step, continue_after_planner
from src.services.domain.external_web_search_policy import ExternalWebSearchPolicy
from src.services.domain.models import ExternalSearchPolicyConfig


def _runtime_context(**kwargs):
    defaults = {
        "mode": "strict",
        "human_approval_granted": False,
        "allow_image_perception": True,
        "image_inputs": [],
        "external_web_search_policy": ExternalWebSearchPolicy(ExternalSearchPolicyConfig()),
    }
    defaults.update(kwargs)
    runtime = Mock(spec=Runtime)
    runtime.context = SimpleNamespace(**defaults)
    return runtime


@pytest.mark.asyncio
async def test_planner_strict_blocks_external_search():
    runtime = _runtime_context(
        mode="strict",
        external_web_search_policy=ExternalWebSearchPolicy(
            ExternalSearchPolicyConfig(enabled=True, require_human_approval=False)
        ),
    )
    state = {
        "messages": [HumanMessage(content="Please search web for latest AI job trends")],
        "metadata": {},
    }

    result = await ainvoke_planner_step(state=state, runtime=runtime)

    assert result["routing_decision"] == "insufficient_knowledge"
    assert "Strict mode" in result["metadata"]["planner_reason"]
    assert continue_after_planner(result) == "insufficient_knowledge"


@pytest.mark.asyncio
async def test_planner_augmented_requires_human_approval():
    runtime = _runtime_context(
        mode="augmented",
        human_approval_granted=False,
        external_web_search_policy=ExternalWebSearchPolicy(
            ExternalSearchPolicyConfig(enabled=True, require_human_approval=True)
        ),
    )
    state = {
        "messages": [HumanMessage(content="Search the web for latest LangGraph updates")],
        "metadata": {},
    }

    result = await ainvoke_planner_step(state=state, runtime=runtime)

    assert result["routing_decision"] == "human_approval"
    assert result["metadata"]["approval_required"] is True
    assert continue_after_planner(result) == "human_approval"


@pytest.mark.asyncio
async def test_planner_augmented_approved_can_use_web_search():
    runtime = _runtime_context(
        mode="augmented",
        human_approval_granted=True,
        external_web_search_policy=ExternalWebSearchPolicy(
            ExternalSearchPolicyConfig(enabled=True, require_human_approval=True)
        ),
    )
    state = {
        "messages": [HumanMessage(content="Need latest web updates for this topic")],
        "metadata": {},
        "retrieval_attempts": 1,
    }

    result = await ainvoke_planner_step(state=state, runtime=runtime)

    assert result["routing_decision"] == "retrieve"
    assert result["metadata"]["planned_tool_name"] == "search_web"
    assert "external_web_search" in result["metadata"]["planned_actions"]


@pytest.mark.asyncio
async def test_planner_enforces_project_retrieval_before_external_search():
    runtime = _runtime_context(
        mode="augmented",
        human_approval_granted=True,
        external_web_search_policy=ExternalWebSearchPolicy(
            ExternalSearchPolicyConfig(enabled=True, require_human_approval=False)
        ),
    )
    state = {
        "messages": [HumanMessage(content="Get latest web updates about this project topic")],
        "metadata": {},
        "retrieval_attempts": 0,
    }

    result = await ainvoke_planner_step(state=state, runtime=runtime)

    assert result["routing_decision"] == "retrieve"
    assert result["metadata"]["planned_tool_name"] == "retrieve_papers"
    assert "external_web_search_pending" in result["metadata"]["planned_actions"]


def test_human_approval_router():
    state = {"metadata": {"human_approval_granted": False}}
    runtime = _runtime_context(human_approval_granted=False)
    assert continue_after_human_approval(state, runtime) == "rejected"

    state_granted = {"metadata": {"human_approval_granted": True}}
    assert continue_after_human_approval(state_granted, runtime) == "approved"
