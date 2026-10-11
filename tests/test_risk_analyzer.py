"""Unit tests for RiskAnalyzer and safety hierarchy enforcement."""

from aapa.ai_provider import MockAIProvider
from aapa.audit_logger import AuditLogger
from aapa.config import Decision, PolicyConfig, RiskLevel
from aapa.project_context import ProjectProfile
from aapa.request_parser import NormalizedRequest
from aapa.risk_analyzer import RiskAnalyzer


def test_ai_cannot_override_blocked_command(tmp_path):
    audit_log = tmp_path / "test_audit.jsonl"
    logger = AuditLogger(log_path=audit_log)

    # Deliberately configure an AI provider that advises AUTO_APPROVE
    adversarial_ai = MockAIProvider(override_summary="Advising approve")
    analyzer = RiskAnalyzer(policy=PolicyConfig(), ai_provider=adversarial_ai, audit_logger=logger)

    # Request a dangerous command
    req = NormalizedRequest(
        command="rm -rf /",
        cwd="C:/myrepo",
        tool_name="run_command"
    )

    res = analyzer.analyze(req)

    # INVARIANT: Must remain BLOCK!
    assert res.decision == Decision.BLOCK
    assert res.risk_level == RiskLevel.CRITICAL
    assert res.antigravity_hook_decision == "deny"
    assert res.requires_user_confirmation is True


def test_injection_warning_demotes_auto_approve(tmp_path):
    audit_log = tmp_path / "test_audit.jsonl"
    logger = AuditLogger(log_path=audit_log)

    analyzer = RiskAnalyzer(policy=PolicyConfig(), audit_logger=logger)

    # Project that contains prompt injection warning
    injected_project = ProjectProfile(
        project_path="C:/myrepo",
        project_name="injected",
        detected_injections=["Potential prompt injection detected in README.md"]
    )

    # Even for safe read-only command, auto-approval must be demoted to ASK_USER
    req = NormalizedRequest(
        command="ls -la",
        cwd="C:/myrepo",
        tool_name="run_command"
    )

    res = analyzer.analyze(req, project_profile=injected_project)
    assert res.decision == Decision.ASK_USER
    assert res.risk_level == RiskLevel.HIGH
    assert res.antigravity_hook_decision == "ask"
    assert "INJECTION" in res.relevant_rule


def test_hook_response_contract(tmp_path):
    analyzer = RiskAnalyzer(policy=PolicyConfig())

    # Safe command
    req = NormalizedRequest(command="dir", cwd="C:/myrepo")
    res = analyzer.analyze(req)
    hook_resp = res.to_antigravity_hook_response()
    assert hook_resp["decision"] == "allow"
    assert "reason" in hook_resp

    # Blocked command
    req2 = NormalizedRequest(command="format c:", cwd="C:/myrepo")
    res2 = analyzer.analyze(req2)
    hook_resp2 = res2.to_antigravity_hook_response()
    assert hook_resp2["decision"] == "deny"
    assert "reason" in hook_resp2
