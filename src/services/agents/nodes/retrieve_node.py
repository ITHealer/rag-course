import logging
import time
from typing import Dict, Union

from langchain_core.messages import AIMessage
from langgraph.runtime import Runtime

from ..context import Context
from ..state import AgentState
from .utils import get_latest_query

logger = logging.getLogger(__name__)


async def ainvoke_retrieve_step(
    state: AgentState,
    runtime: Runtime[Context],
) -> Dict[str, Union[int, str, list]]:
    """Initiate retrieval or return fallback if max attempts reached.

    This node creates a tool call to retrieve documents, or returns a fallback
    message if the maximum number of retrieval attempts has been reached.

    :param state: Current agent state
    :param runtime: Runtime context containing max_retrieval_attempts
    :returns: Dictionary with updated state (retrieval_attempts, messages, original_query)
    """
    logger.info("NODE: retrieve")
    start_time = time.time()

    messages = state["messages"]
    question = get_latest_query(messages)
    current_attempts = state.get("retrieval_attempts", 0)

    # Get max attempts from context
    max_attempts = runtime.context.max_retrieval_attempts

    # Store original query if not set
    updates = {}
    if state.get("original_query") is None:
        updates["original_query"] = question
        logger.debug(f"Stored original query: {question[:100]}...")

    # Create span for retrieval initiation
    span = None
    if runtime.context.langfuse_enabled and runtime.context.trace:
        try:
            span = runtime.context.langfuse_tracer.create_span(
                trace=runtime.context.trace,
                name="document_retrieval_initiation",
                input_data={
                    "query": question,
                    "attempt": current_attempts + 1,
                    "max_attempts": max_attempts,
                },
                metadata={
                    "node": "retrieve",
                    "top_k": runtime.context.top_k,
                },
            )
            logger.debug(f"Created Langfuse span for retrieval attempt {current_attempts + 1}")
        except Exception as e:
            logger.warning(f"Failed to create span for retrieve node: {e}")

    # Check if max attempts reached
    if current_attempts >= max_attempts:
        logger.warning(f"Max retrieval attempts ({max_attempts}) reached")
        fallback_msg = (
            f"I could not find enough grounded evidence after {max_attempts} attempts.\n"
            "This may be because:\n"
            "1. The current project documents do not contain the required details\n"
            "2. The query terms do not match indexed document content\n\n"
            "Please rephrase your question or upload more relevant documents."
        )

        # Update span with max attempts reached
        if span:
            execution_time = (time.time() - start_time) * 1000
            runtime.context.langfuse_tracer.end_span(
                span,
                output={"status": "max_attempts_reached", "fallback": True},
                metadata={"execution_time_ms": execution_time},
            )

        return {**updates, "messages": [AIMessage(content=fallback_msg)]}

    # Increment retrieval attempts
    new_attempt_count = current_attempts + 1
    updates["retrieval_attempts"] = new_attempt_count
    logger.info(f"Retrieval attempt {new_attempt_count}/{max_attempts}")

    metadata = dict(state.get("metadata") or {})
    planned_tool_name = metadata.get("planned_tool_name", "retrieve_papers")

    # Create tool call for retrieval
    updates["messages"] = [
        AIMessage(
            content="",
            tool_calls=[
                {
                    "id": f"retrieve_{new_attempt_count}",
                    "name": planned_tool_name,
                    "args": {"query": question},
                }
            ],
        )
    ]

    logger.debug(f"Created tool call for query: {question[:100]}...")

    # Update span with successful tool call creation
    if span:
        execution_time = (time.time() - start_time) * 1000
        runtime.context.langfuse_tracer.end_span(
            span,
            output={
                "status": "tool_call_created",
                "query": question,
                "attempt": new_attempt_count,
            },
            metadata={"execution_time_ms": execution_time},
        )

    return updates
