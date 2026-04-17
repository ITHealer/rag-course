from src.services.domain.models import ExternalSearchDecision, ExternalSearchPolicyConfig, KnowledgeMode


class ExternalWebSearchPolicy:
    """Policy gate for external web search tool usage."""

    def __init__(self, config: ExternalSearchPolicyConfig | None = None):
        self.config = config or ExternalSearchPolicyConfig()

    def evaluate(
        self,
        *,
        mode: str,
        wants_external_search: bool,
        human_approval_granted: bool,
        current_external_calls: int = 0,
    ) -> ExternalSearchDecision:
        """Evaluate whether external web search is allowed for this request."""
        if not wants_external_search:
            return ExternalSearchDecision(allowed=False, reason="External web search not requested.")

        try:
            normalized_mode = KnowledgeMode(mode)
        except ValueError:
            return ExternalSearchDecision(
                allowed=False,
                reason=f"Unknown knowledge mode '{mode}'.",
            )

        if normalized_mode == KnowledgeMode.STRICT:
            return ExternalSearchDecision(
                allowed=False,
                reason="Strict mode forbids external web search.",
            )

        if not self.config.enabled:
            return ExternalSearchDecision(
                allowed=False,
                reason="External web search is disabled by policy.",
            )

        if current_external_calls >= self.config.max_calls_per_request:
            return ExternalSearchDecision(
                allowed=False,
                reason="External web search call limit reached for this request.",
            )

        if self.config.require_human_approval and not human_approval_granted:
            return ExternalSearchDecision(
                allowed=False,
                reason="Human approval is required before external web search.",
                requires_human_approval=True,
            )

        return ExternalSearchDecision(
            allowed=True,
            reason="External web search allowed by policy.",
        )
