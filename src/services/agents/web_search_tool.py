import logging
from typing import List

from langchain_core.tools import tool

logger = logging.getLogger(__name__)


def create_web_search_tool(
    *,
    enabled: bool,
    allowed_domains: List[str] | None = None,
):
    """Create an external web search tool.

    This is intentionally provider-agnostic. In production, plug in a real web
    search provider behind this interface.
    """

    configured_domains = allowed_domains or []

    @tool
    async def search_web(query: str) -> str:
        """Search external web sources for up-to-date information."""
        if not enabled:
            return "External web search is disabled by policy."

        logger.info("External web search requested for query: %s", query[:120])
        if configured_domains:
            return (
                "External web search provider is not configured in this deployment. "
                f"Allowed domains policy is set to: {', '.join(configured_domains)}."
            )

        return "External web search provider is not configured in this deployment."

    return search_web

