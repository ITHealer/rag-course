import logging
from typing import Dict, List

from langchain_core.messages import AIMessage
from langgraph.runtime import Runtime

from ..context import Context
from ..prompts import DIRECT_RESPONSE_PROMPT
from ..state import AgentState
from .utils import get_latest_query

logger = logging.getLogger(__name__)


async def ainvoke_out_of_scope_step(
    state: AgentState,
    runtime: Runtime[Context],
) -> Dict[str, List[AIMessage]]:
    """Handle out-of-scope queries with a helpful message.

    This node responds to queries that are outside configured guardrail scope
    with a polite, informative message.

    :param state: Current agent state
    :param runtime: Runtime context (not used in this node)
    :returns: Dictionary with messages containing the out-of-scope response
    """
    logger.info("NODE: out_of_scope")

    question = get_latest_query(state["messages"])
    logger.debug(f"Handling out-of-scope query: {question[:100]}...")

    try:
        # Create prompt from template
        prompt = DIRECT_RESPONSE_PROMPT.format(question=question)

        # Get LLM from runtime context
        llm = runtime.context.ollama_client.get_langchain_model(
            model=runtime.context.model_name,
            temperature=0.7,  # Slight creativity for conversational response
        )

        # Invoke LLM for response generation
        logger.info("Invoking LLM for out-of-scope response")
        response = await llm.ainvoke(prompt)
        
        # Extract content
        response_text = response.content if hasattr(response, 'content') else str(response)
        logger.info(f"Generated dynamic out-of-scope response (length: {len(response_text)})")

    except Exception as e:
        logger.error(f"LLM out-of-scope generation failed: {e}, falling back to template")
        # Fallback to a generic scoped response if LLM fails
        response_text = (
            "I can only answer using the currently configured project scope.\n\n"
            f"Your question: '{question}'\n\n"
            "This appears to be outside the current scope. "
            "Please ask a question tied to uploaded project documents."
        )

    return {"messages": [AIMessage(content=response_text)]}
