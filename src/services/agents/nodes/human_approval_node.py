import logging
from typing import Dict, List, Literal

from langchain_core.messages import AIMessage
from langgraph.runtime import Runtime

from ..context import Context
from ..state import AgentState

logger = logging.getLogger(__name__)


def continue_after_human_approval(
    state: AgentState,
    runtime: Runtime[Context],
) -> Literal["approved", "rejected"]:
    """Route based on approval state."""
    metadata = state.get("metadata") or {}
    granted = runtime.context.human_approval_granted or bool(metadata.get("human_approval_granted"))
    return "approved" if granted else "rejected"


async def ainvoke_human_approval_step(
    state: AgentState,
    runtime: Runtime[Context],
) -> Dict[str, List[AIMessage] | Dict]:
    """Pause boundary-crossing actions unless explicit approval is granted."""
    logger.info("NODE: human_approval")
    metadata = dict(state.get("metadata") or {})
    granted = runtime.context.human_approval_granted or bool(metadata.get("human_approval_granted"))

    if granted:
        metadata["approval_required"] = False
        metadata["human_approval_granted"] = True
        logger.info("Human approval already granted. Continue execution.")
        return {"metadata": metadata}

    reason = metadata.get("approval_reason", "External web search requires human approval in augmented mode.")
    metadata["approval_required"] = True
    metadata["human_approval_granted"] = False
    logger.warning("Human approval required but not granted. Routing to insufficient knowledge.")

    message = AIMessage(
        content=(
            "I need human approval before accessing external web search. "
            f"Reason: {reason} "
            "Please re-send the request with `human_approval_granted=true` if you want to proceed."
        )
    )
    return {"messages": [message], "metadata": metadata}

