"""Deterministic safety policy engine for AAPA.

Performs deep structural inspection of shell commands, arguments, operators,
redirections, and directory boundaries to produce explainable safety decisions.
"""

from __future__ import annotations

import logging
import os
import re
import shlex
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from aapa.config import (
    ActionCategory,
    BlockedPattern,
    Decision,
    PolicyConfig,
    RiskLevel,
)
from aapa.project_context import ProjectProfile
from aapa.secret_filter import contains_secrets, is_sensitive_path

logger = logging.getLogger(__name__)

CHAIN_OPERATOR_SPLIT_REGEX = re.compile(r"(&&|\|\||;|\||&|\n)")

DANGEROUS_SYSTEM_PATHS = [
    re.compile(r"(?i)^[a-z]:\\windows", re.IGNORECASE),
    re.compile(r"(?i)^[a-z]:\\program files", re.IGNORECASE),
    re.compile(r"(?i)^[a-z]:\\system32", re.IGNORECASE),
    re.compile(r"^/(etc|usr|bin|sbin|boot|sys|dev|proc|var)(/|$)", re.IGNORECASE),
]


class PolicyEvaluationResult:
    """Outcome of safety policy evaluation."""

    def __init__(
        self,
        decision: Decision,
        risk_level: RiskLevel,
        category: ActionCategory,
        rule_name: str,
        explanation: str,
        requires_user_confirmation: bool,
        antigravity_hook_decision: str = "ask",
    ):
        self.decision = decision
        self.risk_level = risk_level
        self.category = category
        self.rule_name = rule_name
        self.explanation = explanation
        self.requires_user_confirmation = requires_user_confirmation
        self.antigravity_hook_decision = antigravity_hook_decision

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision": self.decision.value,
            "risk_level": self.risk_level.value,
            "category": self.category.value,
            "rule_name": self.rule_name,
            "explanation": self.explanation,
            "requires_user_confirmation": self.requires_user_confirmation,
            "antigravity_hook_decision": self.antigravity_hook_decision,
        }


class PolicyEngine:
    """Evaluates proposed actions against deterministic safety policies."""

    def __init__(self, policy: Optional[PolicyConfig] = None):
        self.policy = policy or PolicyConfig()

    def update_policy(self, policy: PolicyConfig) -> None:
        self.policy = policy

    def evaluate(
        self,
        command: str,
        cwd: str = "",
        action_type: str = "run_command",
        project_profile: Optional[ProjectProfile] = None,
        target_files: Optional[List[str]] = None
    ) -> PolicyEvaluationResult:
        """Performs comprehensive multi-stage deterministic safety analysis."""
        clean_cmd = (command or "").strip()
        target_files = target_files or []

        # 1. Non-command actions: file writes / edits
        if action_type in ("file_write", "file_edit"):
            return self._evaluate_file_write(clean_cmd, target_files, cwd, project_profile)

        if not clean_cmd:
            return PolicyEvaluationResult(
                decision=Decision.ASK_USER,
                risk_level=RiskLevel.LOW,
                category=ActionCategory.UNKNOWN,
                rule_name="EMPTY_ACTION",
                explanation="No command specified in the request.",
                requires_user_confirmation=True,
                antigravity_hook_decision="ask"
            )

        # 2. Secret exposure check in raw command
        has_secret, secret_types = contains_secrets(clean_cmd)
        if has_secret:
            return PolicyEvaluationResult(
                decision=Decision.BLOCK,
                risk_level=RiskLevel.CRITICAL,
                category=ActionCategory.ELEVATED_PRIVILEGE,
                rule_name="SECRET_TOKEN_IN_COMMAND",
                explanation=f"Command contains raw credential or secret ({', '.join(secret_types)}). Automatic execution blocked to prevent token exposure.",
                requires_user_confirmation=True,
                antigravity_hook_decision="deny"
            )

        # 3. Sensitive file access in command string
        for word in clean_cmd.split():
            clean_word = word.strip("'\"")
            if is_sensitive_path(clean_word):
                return PolicyEvaluationResult(
                    decision=Decision.BLOCK,
                    risk_level=RiskLevel.HIGH,
                    category=ActionCategory.DESTRUCTIVE_FILESYSTEM,
                    rule_name="SENSITIVE_FILE_ACCESS",
                    explanation=f"Command targets or references protected credential file '{clean_word}'.",
                    requires_user_confirmation=True,
                    antigravity_hook_decision="deny"
                )

        # 4. Check explicit blocked patterns against entire command
        for rule in self.policy.blocked_patterns:
            try:
                matched = bool(re.search(rule.pattern, clean_cmd, re.IGNORECASE))
            except re.error:
                matched = rule.pattern.lower() in clean_cmd.lower()
            if matched:
                return PolicyEvaluationResult(
                    decision=Decision.BLOCK,
                    risk_level=RiskLevel.CRITICAL,
                    category=ActionCategory.DESTRUCTIVE_FILESYSTEM if "DESTRUCTIVE" in rule.category else ActionCategory.ELEVATED_PRIVILEGE,
                    rule_name=f"BLOCKED_RULE:{rule.category}",
                    explanation=f"Security Violation: {rule.reason}.",
                    requires_user_confirmation=True,
                    antigravity_hook_decision="deny"
                )

        # 5. Check subshell / backtick / command substitution injection
        if re.search(r"(\$\([^\)]+\)|`[^`]+`)", clean_cmd):
            # Nested subshell execution requires human review
            return PolicyEvaluationResult(
                decision=Decision.ASK_USER,
                risk_level=RiskLevel.HIGH,
                category=ActionCategory.PROCESS_CONTROL,
                rule_name="COMMAND_SUBSTITUTION_DETECTED",
                explanation="Command uses subshell expansion $(...) or backticks `...`. Requires human review for safety.",
                requires_user_confirmation=True,
                antigravity_hook_decision="ask"
            )

        # 6. Decompose chained commands (&&, ||, ;, |, &)
        sub_commands = self._decompose_pipeline(clean_cmd)

        # If multiple commands are chained, evaluate each individually
        if len(sub_commands) > 1:
            return self._evaluate_command_chain(sub_commands, cwd, project_profile)

        # Single command evaluation
        return self._evaluate_single_command(clean_cmd, cwd, project_profile)

    def _decompose_pipeline(self, command: str) -> List[str]:
        """Splits commands chained via &&, ||, ;, |, & while ignoring quotes."""
        parts = [p.strip() for p in CHAIN_OPERATOR_SPLIT_REGEX.split(command)]
        # Filter out bare operator tokens
        return [p for p in parts if p and p not in ("&&", "||", ";", "|", "&", "\n")]

    def _evaluate_command_chain(
        self,
        sub_commands: List[str],
        cwd: str,
        project_profile: Optional[ProjectProfile]
    ) -> PolicyEvaluationResult:
        """Evaluates a multi-command chain; if ANY is dangerous, block or escalate."""
        worst_decision = Decision.AUTO_APPROVE
        highest_risk = RiskLevel.LOW
        reasons: List[str] = []
        triggered_rules: List[str] = []

        for sub_cmd in sub_commands:
            res = self._evaluate_single_command(sub_cmd, cwd, project_profile)
            if res.decision == Decision.BLOCK:
                return PolicyEvaluationResult(
                    decision=Decision.BLOCK,
                    risk_level=RiskLevel.CRITICAL,
                    category=res.category,
                    rule_name=f"CHAIN_BLOCKED:{res.rule_name}",
                    explanation=f"Chained command blocked by sub-action: {res.explanation}",
                    requires_user_confirmation=True,
                    antigravity_hook_decision="deny"
                )
            if res.decision == Decision.ASK_USER:
                worst_decision = Decision.ASK_USER
                if res.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
                    highest_risk = RiskLevel.HIGH
                elif highest_risk != RiskLevel.HIGH:
                    highest_risk = RiskLevel.MEDIUM
                reasons.append(res.explanation)
                triggered_rules.append(res.rule_name)

        if worst_decision == Decision.ASK_USER:
            return PolicyEvaluationResult(
                decision=Decision.ASK_USER,
                risk_level=highest_risk,
                category=ActionCategory.PROCESS_CONTROL,
                rule_name=",".join(triggered_rules) or "CHAINED_COMMAND_REVIEW",
                explanation=f"Chained command requires review: {'; '.join(reasons)}",
                requires_user_confirmation=True,
                antigravity_hook_decision="ask"
            )

        # All parts passed safe checks
        return PolicyEvaluationResult(
            decision=Decision.AUTO_APPROVE if self.policy.settings.auto_approve_safe_read_only else Decision.ASK_USER,
            risk_level=RiskLevel.LOW,
            category=ActionCategory.READ_ONLY,
            rule_name="CHAINED_SAFE_READ_ONLY",
            explanation=f"All {len(sub_commands)} chained operations are verified safe read-only operations.",
            requires_user_confirmation=not self.policy.settings.auto_approve_safe_read_only,
            antigravity_hook_decision="allow" if self.policy.settings.auto_approve_safe_read_only else "ask"
        )

    def _evaluate_single_command(
        self,
        command: str,
        cwd: str,
        project_profile: Optional[ProjectProfile]
    ) -> PolicyEvaluationResult:
        """Evaluates an individual isolated shell command."""
        # 1. Output redirection to files: check write targets
        if ">" in command:
            # Overwriting or appending files requires review
            return PolicyEvaluationResult(
                decision=Decision.ASK_USER,
                risk_level=RiskLevel.MEDIUM,
                category=ActionCategory.FILE_MODIFICATION,
                rule_name="SHELL_REDIRECTION_WRITE",
                explanation="Command uses shell redirection ('>' or '>>') to create or overwrite files.",
                requires_user_confirmation=True,
                antigravity_hook_decision="ask"
            )

        # 2. Workspace boundary check: prevent directory traversal outside workspace
        if self.policy.settings.enforce_workspace_boundary and project_profile and project_profile.project_path:
            norm_proj = os.path.abspath(project_profile.project_path).lower()
            if cwd:
                norm_cwd = os.path.abspath(cwd).lower()
                if not norm_cwd.startswith(norm_proj):
                    return PolicyEvaluationResult(
                        decision=Decision.ASK_USER,
                        risk_level=RiskLevel.HIGH,
                        category=ActionCategory.SYSTEM_CONFIG,
                        rule_name="OUTSIDE_WORKSPACE_CWD",
                        explanation=f"Command runs in working directory '{cwd}' outside the active project workspace root.",
                        requires_user_confirmation=True,
                        antigravity_hook_decision="ask"
                    )

            # Check for path traversal '..' in command tokens
            for token in command.split():
                if ".." in token:
                    return PolicyEvaluationResult(
                        decision=Decision.ASK_USER,
                        risk_level=RiskLevel.HIGH,
                        category=ActionCategory.FILE_MODIFICATION,
                        rule_name="PATH_TRAVERSAL_DETECTED",
                        explanation=f"Command references parent directory traversal ('..'). Requires human verification.",
                        requires_user_confirmation=True,
                        antigravity_hook_decision="ask"
                    )

        # 3. Known Safe Read-Only commands
        for ro_cmd in self.policy.read_only_commands:
            if command == ro_cmd or command.startswith(ro_cmd + " "):
                # Safe read-only
                auto_ok = self.policy.settings.auto_approve_safe_read_only
                return PolicyEvaluationResult(
                    decision=Decision.AUTO_APPROVE if auto_ok else Decision.ASK_USER,
                    risk_level=RiskLevel.LOW,
                    category=ActionCategory.READ_ONLY,
                    rule_name="ALLOWLIST_READ_ONLY",
                    explanation=f"Explicitly allowlisted read-only inspection command ('{ro_cmd}').",
                    requires_user_confirmation=not auto_ok,
                    antigravity_hook_decision="allow" if auto_ok else "ask"
                )

        # 4. Approved Linters
        for linter in self.policy.allowed_linters:
            if command == linter or command.startswith(linter + " "):
                auto_ok = self.policy.settings.auto_approve_safe_read_only
                return PolicyEvaluationResult(
                    decision=Decision.AUTO_APPROVE if auto_ok else Decision.ASK_USER,
                    risk_level=RiskLevel.LOW,
                    category=ActionCategory.LINTER,
                    rule_name="ALLOWLIST_LINTER",
                    explanation=f"Explicitly allowlisted project linter/analyzer command ('{linter}').",
                    requires_user_confirmation=not auto_ok,
                    antigravity_hook_decision="allow" if auto_ok else "ask"
                )

        # 5. Approved Test commands
        allowed_tests = set(self.policy.allowed_test_commands)
        if project_profile and project_profile.test_commands:
            allowed_tests.update(project_profile.test_commands)

        for test_cmd in allowed_tests:
            if command == test_cmd or command.startswith(test_cmd + " "):
                auto_tests = self.policy.settings.auto_approve_test_commands
                return PolicyEvaluationResult(
                    decision=Decision.AUTO_APPROVE if auto_tests else Decision.ASK_USER,
                    risk_level=RiskLevel.LOW if auto_tests else RiskLevel.MEDIUM,
                    category=ActionCategory.BUILD_TEST,
                    rule_name="PROJECT_TEST_RUNNER",
                    explanation=f"Approved test execution command ('{test_cmd}').",
                    requires_user_confirmation=not auto_tests,
                    antigravity_hook_decision="allow" if auto_tests else "ask"
                )

        # 6. Review Required prefixes (package install, git, network)
        for req_prefix in self.policy.review_required_prefixes:
            if command == req_prefix or command.startswith(req_prefix + " "):
                cat = ActionCategory.PACKAGE_MANAGEMENT if any(p in req_prefix for p in ("install", "add", "get")) else ActionCategory.GIT_OPERATION
                return PolicyEvaluationResult(
                    decision=Decision.ASK_USER,
                    risk_level=RiskLevel.MEDIUM,
                    category=cat,
                    rule_name=f"REVIEW_REQUIRED:{req_prefix}",
                    explanation=f"Operation modifies state, installs dependencies, or contacts external network ('{req_prefix}').",
                    requires_user_confirmation=True,
                    antigravity_hook_decision="ask"
                )

        # 7. Unknown / Unclassified command -> default to ASK_USER
        return PolicyEvaluationResult(
            decision=Decision.ASK_USER,
            risk_level=RiskLevel.MEDIUM,
            category=ActionCategory.UNKNOWN,
            rule_name="UNKNOWN_COMMAND_DEFAULT_REVIEW",
            explanation=f"Unknown command with unspecified side effects. In accordance with zero-trust safety principles, manual approval is required.",
            requires_user_confirmation=True,
            antigravity_hook_decision="ask"
        )

    def _evaluate_file_write(
        self,
        command: str,
        target_files: List[str],
        cwd: str,
        project_profile: Optional[ProjectProfile]
    ) -> PolicyEvaluationResult:
        """Evaluates non-command file write or modification requests."""
        for target in target_files:
            if is_sensitive_path(target):
                return PolicyEvaluationResult(
                    decision=Decision.BLOCK,
                    risk_level=RiskLevel.CRITICAL,
                    category=ActionCategory.DESTRUCTIVE_FILESYSTEM,
                    rule_name="WRITE_TO_SENSITIVE_FILE",
                    explanation=f"Attempting to write or modify protected credential file '{target}'.",
                    requires_user_confirmation=True,
                    antigravity_hook_decision="deny"
                )

            # Check if outside project workspace
            if self.policy.settings.enforce_workspace_boundary and project_profile and project_profile.project_path:
                norm_proj = os.path.abspath(project_profile.project_path).lower()
                norm_target = os.path.abspath(target).lower()
                if not norm_target.startswith(norm_proj):
                    return PolicyEvaluationResult(
                        decision=Decision.BLOCK,
                        risk_level=RiskLevel.HIGH,
                        category=ActionCategory.DESTRUCTIVE_FILESYSTEM,
                        rule_name="WRITE_OUTSIDE_WORKSPACE",
                        explanation=f"File modification target '{target}' is outside the authorized project workspace.",
                        requires_user_confirmation=True,
                        antigravity_hook_decision="deny"
                    )

        return PolicyEvaluationResult(
            decision=Decision.ASK_USER,
            risk_level=RiskLevel.MEDIUM,
            category=ActionCategory.FILE_MODIFICATION,
            rule_name="FILE_MODIFICATION_REVIEW",
            explanation=f"Modification proposed for: {', '.join(target_files) or 'specified file'}.",
            requires_user_confirmation=True,
            antigravity_hook_decision="ask"
        )
