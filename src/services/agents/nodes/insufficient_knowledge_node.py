import logging
from typing import Dict, List

from langchain_core.messages import AIMessage
from langgraph.runtime import Runtime

from ..context import Context
from ..state import AgentState
from .utils import get_latest_query

logger = logging.getLogger(__name__)


INSUFFICIENT_KNOWLEDGE_PROMPT = """You are a grounded assistant.

Project mode: {mode}
Planner reason: {planner_reason}
Approval required: {approval_required}

User question:
{question}

Instructions:
1. Explain naturally that current project knowledge is insufficient to answer fully.
2. Do NOT answer using general background knowledge.
3. Suggest 3 follow-up questions the user can ask that are likely answerable from the loaded documents.
4. Keep tone concise and professional.
"""


async def ainvoke_insufficient_knowledge_step(
    state: AgentState,
    runtime: Runtime[Context],
) -> Dict[str, List[AIMessage]]:
    """Generate natural insufficient-knowledge responses without hallucinating."""
    logger.info("NODE: insufficient_knowledge")
    question = get_latest_query(state["messages"])
    metadata = state.get("metadata") or {}

    try:
        prompt = INSUFFICIENT_KNOWLEDGE_PROMPT.format(
            mode=runtime.context.mode,
            planner_reason=metadata.get("planner_reason", "No sufficient grounded evidence found."),
            approval_required=metadata.get("approval_required", False),
            question=question,
        )
        if runtime.context.system_prompt_addon:
            prompt = f"{runtime.context.system_prompt_addon}\n\n{prompt}"

        llm = runtime.context.ollama_client.get_langchain_model(
            model=runtime.context.model_name,
            temperature=0.2,
        )
        response = await llm.ainvoke(prompt)
        response_text = response.content if hasattr(response, "content") else str(response)
    except Exception as exc:
        logger.error("Insufficient knowledge generation failed: %s", exc)
        response_text = (
            "I cannot find enough grounded evidence in the current project knowledge to answer this reliably. "
            "Please upload more relevant documents or ask a question tied to existing files."
        )

    return {"messages": [AIMessage(content=response_text)]}
