import logging
import re
from typing import Dict, Literal

from langgraph.runtime import Runtime

from src.services.domain.models import KnowledgeMode

from ..context import Context
from ..state import AgentState
from .utils import get_latest_query

logger = logging.getLogger(__name__)

EXTERNAL_INTENT_PATTERN = re.compile(
    r"\b(web|internet|google|latest|today|current|news|price|weather|live|real-time)\b",
    re.IGNORECASE,
)
IMAGE_INTENT_PATTERN = re.compile(
    r"\b(image|screenshot|figure|diagram|photo|picture|visual)\b",
    re.IGNORECASE,
)


def continue_after_planner(state: AgentState) -> Literal["retrieve", "human_approval", "insufficient_knowledge"]:
    """Route graph flow after planning."""
    route = state.get("routing_decision") or "retrieve"
    if route not in {"retrieve", "human_approval", "insufficient_knowledge"}:
        return "retrieve"
    return route


async def ainvoke_planner_step(
    state: AgentState,
    runtime: Runtime[Context],
) -> Dict[str, object]:
    """Plan tool usage based on mode, policy, and query intent."""
    logger.info("NODE: planner")
    query = get_latest_query(state["messages"])
    metadata = dict(state.get("metadata") or {})
    retrieval_attempts = int(state.get("retrieval_attempts", 0))

    wants_external_search = bool(EXTERNAL_INTENT_PATTERN.search(query))
    wants_image_perception = bool(IMAGE_INTENT_PATTERN.search(query) or (runtime.context.image_inputs or []))

    planned_actions: list[str] = []
    planned_tool_name = "retrieve_papers"
    routing_decision: Literal["retrieve", "human_approval", "insufficient_knowledge"] = "retrieve"
    planner_reason = "Use project retrieval."

    if wants_external_search:
        policy = runtime.context.external_web_search_policy
        if not policy:
            planner_reason = "External search requested but no policy object available."
            routing_decision = "insufficient_knowledge"
        else:
            decision = policy.evaluate(
                mode=runtime.context.mode,
                wants_external_search=True,
                human_approval_granted=runtime.context.human_approval_granted,
                current_external_calls=int(metadata.get("external_web_search_calls", 0)),
            )
            planner_reason = decision.reason

            if decision.allowed:
                if retrieval_attempts < 1:
                    # Enforce project-first retrieval before external augmentation.
                    planned_actions.append("project_retrieval")
                    planned_actions.append("external_web_search_pending")
                    planned_tool_name = "retrieve_papers"
                    planner_reason = (
                        "External search is allowed, but project retrieval must run first. "
                        "External search can run on the next attempt if needed."
                    )
                    metadata["external_web_search_eligible_next_attempt"] = True
                else:
                    planned_actions.append("external_web_search")
                    planned_tool_name = "search_web"
            elif decision.requires_human_approval:
                routing_decision = "human_approval"
                metadata["approval_required"] = True
                metadata["approval_reason"] = decision.reason
            else:
                routing_decision = "insufficient_knowledge"
    elif wants_image_perception and runtime.context.allow_image_perception:
        planned_actions.append("image_perception")
        planned_tool_name = "perceive_image"
        planner_reason = "Image-aware query detected; run image perception."

    if not planned_actions:
        planned_actions.append("project_retrieval")
        planned_tool_name = "retrieve_papers"

    if runtime.context.mode == KnowledgeMode.STRICT.value and "external_web_search" in planned_actions:
        # Defensive check: strict mode should never execute external search.
        planned_actions.remove("external_web_search")
        planned_tool_name = "retrieve_papers"
        planner_reason = "Strict mode enforces project-only grounding."

    metadata["planned_actions"] = planned_actions
    metadata["planned_tool_name"] = planned_tool_name
    metadata["planner_reason"] = planner_reason
    metadata["mode"] = runtime.context.mode
    metadata["wants_external_search"] = wants_external_search
    metadata["wants_image_perception"] = wants_image_perception

    logger.info(
        "Planner decision: route=%s, tool=%s, actions=%s, reason=%s",
        routing_decision,
        planned_tool_name,
        planned_actions,
        planner_reason,
    )

    return {
        "routing_decision": routing_decision,
        "metadata": metadata,
    }
