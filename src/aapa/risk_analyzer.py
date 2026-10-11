"""Core risk analysis orchestrator for AAPA.

Combines deterministic policy enforcement, project context boundaries, sensitive data scanning,
and AI explanation models into a unified decision workflow.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from aapa.ai_provider import BaseAIProvider, LocalRuleBasedProvider
from aapa.audit_logger import AuditLogger
from aapa.config import (
    ActionCategory,
    Decision,
    PolicyConfig,
    RiskLevel,
)
from aapa.policy_engine import PolicyEngine, PolicyEvaluationResult
from aapa.project_context import ProjectContextEngine, ProjectProfile
from aapa.request_parser import NormalizedRequest
from aapa.secret_filter import redact_secrets

logger = logging.getLogger(__name__)


class AnalysisResult(BaseModel):
    """Complete, structured decision result returned to callers, UI, and hooks."""
    request_id: str
    action_category: ActionCategory
    risk_level: RiskLevel
    decision: Decision
    explanation: str
    detailed_explanation: str = ""
    relevant_rule: str
    requires_user_confirmation: bool
    antigravity_hook_decision: str  # 'allow', 'deny', 'ask', 'force_ask'
    sanitized_command: str
    cwd: str
    target_files: List[str] = Field(default_factory=list)
    identified_risks: List[str] = Field(default_factory=list)
    project_name: str = ""
    user_action_taken: Optional[str] = None

    def to_antigravity_hook_response(self) -> Dict[str, Any]:
        """Formats output to match official Google Antigravity PreToolUse hook contract."""
        return {
            "decision": self.antigravity_hook_decision,
            "reason": self.explanation,
        }


class RiskAnalyzer:
    """Orchestrates end-to-end evaluation of Antigravity permission requests."""

    def __init__(
        self,
        policy: Optional[PolicyConfig] = None,
        ai_provider: Optional[BaseAIProvider] = None,
        audit_logger: Optional[AuditLogger] = None
    ):
        self.policy_engine = PolicyEngine(policy)
        self.ai_provider = ai_provider or LocalRuleBasedProvider()
        self.context_engine = ProjectContextEngine()
        self.audit_logger = audit_logger or AuditLogger()

    def update_policy(self, policy: PolicyConfig) -> None:
        self.policy_engine.update_policy(policy)

    def set_ai_provider(self, provider: BaseAIProvider) -> None:
        self.ai_provider = provider

    def analyze(
        self,
        request: NormalizedRequest,
        project_profile: Optional[ProjectProfile] = None
    ) -> AnalysisResult:
        """Executes full analysis pipeline following the strict safety hierarchy."""
        sanitized_cmd = redact_secrets(request.command)

        # 1. Deterministic Policy Evaluation (Always Supreme)
        policy_res = self.policy_engine.evaluate(
            command=request.command,
            cwd=request.cwd,
            action_type=request.action_type,
            project_profile=project_profile,
            target_files=request.target_files
        )

        final_decision = policy_res.decision
        final_risk = policy_res.risk_level
        final_hook_dec = policy_res.antigravity_hook_decision
        final_rule = policy_res.rule_name
        req_confirm = policy_res.requires_user_confirmation
        risks: List[str] = []

        # 2. Check for Prompt Injections in Project Context
        if project_profile and project_profile.detected_injections:
            risks.extend(project_profile.detected_injections)
            if final_decision == Decision.AUTO_APPROVE:
                # Demote auto-approve to manual review if project contains injection attempts!
                final_decision = Decision.ASK_USER
                final_risk = RiskLevel.HIGH
                final_hook_dec = "ask"
                req_confirm = True
                final_rule = "INJECTION_WARNING_REVIEW"

        # 3. AI Explanation Generation
        project_summary = project_profile.to_markdown_summary() if project_profile else "No project context"
        ai_res = self.ai_provider.explain(
            command=sanitized_cmd,
            cwd=request.cwd,
            project_summary=project_summary,
            policy_decision=final_decision.value,
            policy_reason=policy_res.explanation
        )

        risks.extend(ai_res.identified_risks)

        # 4. Strict Security Invariant: AI CANNOT OVERRIDE A POLICY BLOCK
        if policy_res.decision == Decision.BLOCK:
            final_decision = Decision.BLOCK
            final_risk = RiskLevel.CRITICAL
            final_hook_dec = "deny"
            req_confirm = True
            explanation = policy_res.explanation
        else:
            explanation = policy_res.explanation

        # 5. Build Result
        result = AnalysisResult(
            request_id=request.request_id,
            action_category=policy_res.category,
            risk_level=final_risk,
            decision=final_decision,
            explanation=explanation,
            detailed_explanation=ai_res.detailed_explanation,
            relevant_rule=final_rule,
            requires_user_confirmation=req_confirm,
            antigravity_hook_decision=final_hook_dec,
            sanitized_command=sanitized_cmd,
            cwd=request.cwd,
            target_files=request.target_files,
            identified_risks=list(set(risks)),
            project_name=project_profile.project_name if project_profile else ""
        )

        # 6. Audit Logging
        self.audit_logger.log_event(
            event_type="PERMISSION_ANALYZED",
            request_id=result.request_id,
            action=result.sanitized_command,
            cwd=result.cwd,
            risk_level=result.risk_level.value,
            decision=result.decision.value,
            recommendation=result.decision.value,
            explanation=result.explanation,
            rule_name=result.relevant_rule,
            user_confirmed=not result.requires_user_confirmation if result.decision == Decision.AUTO_APPROVE else None,
            antigravity_response=result.antigravity_hook_decision,
            metadata={"category": result.action_category.value, "source": request.source}
        )

        return result
