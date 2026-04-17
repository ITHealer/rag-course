from src.services.domain.external_web_search_policy import ExternalWebSearchPolicy
from src.services.domain.models import ExternalSearchPolicyConfig


def test_policy_denies_when_disabled():
    policy = ExternalWebSearchPolicy(ExternalSearchPolicyConfig(enabled=False))
    decision = policy.evaluate(
        mode="augmented",
        wants_external_search=True,
        human_approval_granted=True,
    )
    assert decision.allowed is False
    assert "disabled" in decision.reason.lower()


def test_policy_denies_strict_mode():
    policy = ExternalWebSearchPolicy(ExternalSearchPolicyConfig(enabled=True))
    decision = policy.evaluate(
        mode="strict",
        wants_external_search=True,
        human_approval_granted=True,
    )
    assert decision.allowed is False
    assert "strict mode" in decision.reason.lower()


def test_policy_requires_approval():
    policy = ExternalWebSearchPolicy(
        ExternalSearchPolicyConfig(enabled=True, require_human_approval=True)
    )
    decision = policy.evaluate(
        mode="augmented",
        wants_external_search=True,
        human_approval_granted=False,
    )
    assert decision.allowed is False
    assert decision.requires_human_approval is True


def test_policy_allows_augmented_when_approved():
    policy = ExternalWebSearchPolicy(
        ExternalSearchPolicyConfig(enabled=True, require_human_approval=True)
    )
    decision = policy.evaluate(
        mode="augmented",
        wants_external_search=True,
        human_approval_granted=True,
    )
    assert decision.allowed is True

