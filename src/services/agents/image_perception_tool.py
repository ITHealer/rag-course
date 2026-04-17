import logging
from typing import List

from langchain_core.tools import tool

logger = logging.getLogger(__name__)


def create_image_perception_tool(
    *,
    enabled: bool,
    image_inputs: List[str] | None = None,
):
    """Create a project-scoped image perception tool."""

    known_images = image_inputs or []

    @tool
    async def perceive_image(query: str) -> str:
        """Analyze user-provided or project-local image references."""
        if not enabled:
            return "Image perception is disabled by policy."

        if not known_images:
            return (
                "No image inputs were provided for this request. "
                "Attach images or provide project-local image references to use image perception."
            )

        logger.info("Image perception requested for query: %s", query[:120])
        preview = ", ".join(known_images[:5])
        return (
            "Image perception inputs detected. "
            f"Available image references: {preview}. "
            "Use these references as grounded context for the answer."
        )

    return perceive_image

