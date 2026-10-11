"""Unit tests for AI explanation provider adapters."""

from aapa.ai_provider import (
    LocalRuleBasedProvider,
    MockAIProvider,
    OpenAICompatibleProvider,
    create_ai_provider,
)


def test_local_rule_based_provider():
    provider = LocalRuleBasedProvider()

    # Test flags explanation
    exp = provider.explain(
        command="npm install express --save-dev -f",
        cwd="C:/Projects/myapp",
        project_summary="Node.js App",
        policy_decision="ASK_USER",
        policy_reason="Dependency install"
    )

    assert "Node Package Manager" in exp.detailed_explanation
    assert "--save-dev" in exp.detailed_explanation
    assert "-f" in exp.detailed_explanation
    assert any("High-impact flag" in r for r in exp.identified_risks)
    assert exp.confidence > 0.8


def test_openai_provider_timeout_fallback():
    # Configure an unreachable port to test timeout/error fallback
    provider = OpenAICompatibleProvider(
        base_url="http://127.0.0.1:59999/v1",
        api_key="mock",
        model="mock"
    )

    # Should gracefully catch error and fall back to local rule-based explainer without crashing!
    exp = provider.explain(
        command="pip install pytest",
        cwd="C:/myrepo",
        project_summary="Python App",
        policy_decision="ASK_USER",
        policy_reason="Dependency install"
    )

    assert exp is not None
    assert "Python package installer" in exp.detailed_explanation


def test_factory_creation():
    p1 = create_ai_provider("rule_based")
    assert isinstance(p1, LocalRuleBasedProvider)

    p2 = create_ai_provider("openai", base_url="http://localhost:11434/v1")
    assert isinstance(p2, OpenAICompatibleProvider)
