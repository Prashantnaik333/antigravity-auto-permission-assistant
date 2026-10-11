"""Provider-independent AI explanation adapter for AAPA.

Provides contextual risk analysis and command explanations with guaranteed offline
rule-based operation and robust safety constraints (AI cannot override safety blocks).
"""

from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from aapa.secret_filter import redact_secrets

logger = logging.getLogger(__name__)


class AIExplanation(BaseModel):
    """Structured explanation returned by the AI adapter."""
    summary: str
    detailed_explanation: str
    suggested_decision: Optional[str] = None  # Advisory only
    identified_risks: List[str] = Field(default_factory=list)
    confidence: float = 1.0


class BaseAIProvider(ABC):
    """Abstract base class for AI explanation providers."""

    @abstractmethod
    def explain(
        self,
        command: str,
        cwd: str,
        project_summary: str,
        policy_decision: str,
        policy_reason: str
    ) -> AIExplanation:
        """Explains a command and potential side effects."""
        pass


class LocalRuleBasedProvider(BaseAIProvider):
    """100% offline, zero-cost, deterministic rule-based explainer."""

    FLAG_EXPLANATIONS = {
        "-f": "Forces operation without confirmation prompt.",
        "--force": "Forces operation without confirmation prompt.",
        "-y": "Automatically answers yes to all installation prompts.",
        "--yes": "Automatically answers yes to all prompts.",
        "-r": "Operates recursively over directories and subdirectories.",
        "-R": "Operates recursively over directories.",
        "-g": "Installs globally on the host operating system.",
        "--global": "Installs package globally on host system.",
        "-v": "Enables verbose logging output.",
        "--all": "Applies action to all matched resources.",
        "--save-dev": "Installs as development-only dependency.",
        "-D": "Installs as development dependency.",
    }

    TOOL_EXPLANATIONS = {
        "npm": "Node Package Manager for installing JavaScript libraries or running scripts.",
        "pip": "Python package installer for downloading and installing packages from PyPI.",
        "git": "Version control system for tracking changes in source code.",
        "pytest": "Python testing framework for running unit and integration tests.",
        "cargo": "Rust package manager and build orchestrator.",
        "go": "Go toolchain for compiling and testing Go code.",
        "curl": "Command-line tool for transferring data via URLs over network.",
        "wget": "Utility for non-interactive download of files from the web.",
        "docker": "Containerization platform managing images and containers.",
    }

    def explain(
        self,
        command: str,
        cwd: str,
        project_summary: str,
        policy_decision: str,
        policy_reason: str
    ) -> AIExplanation:
        clean_cmd = command.strip()
        tokens = clean_cmd.split()
        tool = tokens[0].lower() if tokens else ""

        risks: List[str] = []
        details: List[str] = []

        # Tool purpose
        if tool in self.TOOL_EXPLANATIONS:
            details.append(f"Tool Purpose: {self.TOOL_EXPLANATIONS[tool]}")

        # Check flags
        for token in tokens[1:]:
            if token in self.FLAG_EXPLANATIONS:
                details.append(f"Flag '{token}': {self.FLAG_EXPLANATIONS[token]}")
                if token in ("-f", "--force", "-g", "--global"):
                    risks.append(f"High-impact flag detected: {token}")

        if "install" in tokens or "add" in tokens:
            risks.append("Installs external code/dependencies from public repositories into project.")
            details.append("This operation modifies dependency lockfiles and downloads third-party packages.")

        if policy_decision == "BLOCK":
            summary = f"BLOCKED: {policy_reason}"
            risks.append("This action violates strict deterministic security rules.")
        elif policy_decision == "AUTO_APPROVE":
            summary = f"SAFE: Low-risk verified operation ({policy_reason})."
        else:
            summary = f"REVIEW REQUIRED: {policy_reason}"

        if not details:
            details.append("Executes local command with standard user shell permissions.")

        return AIExplanation(
            summary=summary,
            detailed_explanation=" ".join(details),
            suggested_decision=policy_decision,
            identified_risks=risks,
            confidence=0.95
        )


class OpenAICompatibleProvider(BaseAIProvider):
    """Adapter for OpenAI-compatible local/remote endpoints (Ollama, vLLM, OpenAI)."""

    def __init__(self, base_url: str = "http://localhost:11434/v1", api_key: str = "", model: str = "llama3"):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.fallback = LocalRuleBasedProvider()

    def explain(
        self,
        command: str,
        cwd: str,
        project_summary: str,
        policy_decision: str,
        policy_reason: str
    ) -> AIExplanation:
        sanitized_cmd = redact_secrets(command)
        prompt = (
            f"You are a cybersecurity assistant auditing developer tool commands for Antigravity AI.\n"
            f"Active Project Info: {project_summary}\n"
            f"Working Directory: {cwd}\n"
            f"Command Proposed: {sanitized_cmd}\n"
            f"Deterministic Policy Decision: {policy_decision} ({policy_reason})\n\n"
            f"Analyze this command concisely. Explain what it does, what side effects it produces, and if there are risks.\n"
            f"IMPORTANT: Respond in valid JSON with keys: summary, detailed_explanation, identified_risks (array)."
        )

        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are a cybersecurity analyzer. Reply strictly in JSON."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2,
            "max_tokens": 400
        }

        try:
            req = urllib.request.Request(
                f"{self.base_url}/chat/completions",
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                content = data["choices"][0]["message"]["content"]
                
                # Attempt to extract JSON from content
                json_match = re.search(r"\{[\s\S]*\}", content)
                if json_match:
                    parsed = json.loads(json_match.group(0))
                    return AIExplanation(
                        summary=parsed.get("summary", "Analysis completed."),
                        detailed_explanation=parsed.get("detailed_explanation", ""),
                        suggested_decision=policy_decision,
                        identified_risks=parsed.get("identified_risks", []),
                        confidence=0.9
                    )
        except Exception as exc:
            logger.warning("AI provider failed or timed out (%s). Falling back to rule-based explainer.", exc)

        return self.fallback.explain(command, cwd, project_summary, policy_decision, policy_reason)


class MockAIProvider(BaseAIProvider):
    """Deterministic test double for testing AI interaction workflows."""

    def __init__(self, override_summary: str = "", force_error: bool = False):
        self.override_summary = override_summary
        self.force_error = force_error
        self.fallback = LocalRuleBasedProvider()

    def explain(
        self,
        command: str,
        cwd: str,
        project_summary: str,
        policy_decision: str,
        policy_reason: str
    ) -> AIExplanation:
        if self.force_error:
            # Emulates network timeout/error with fallback
            return self.fallback.explain(command, cwd, project_summary, policy_decision, policy_reason)
        
        return AIExplanation(
            summary=self.override_summary or f"Mock analysis: {command}",
            detailed_explanation=f"Detailed mock reasoning for: {command}",
            suggested_decision="AUTO_APPROVE",  # Deliberately tests that policy overrides this if blocked!
            identified_risks=["Mock risk indicator"],
            confidence=1.0
        )


def create_ai_provider(provider_type: str = "rule_based", **kwargs) -> BaseAIProvider:
    """Factory creating configured AI provider."""
    ptype = provider_type.lower()
    if ptype in ("openai", "ollama", "local"):
        return OpenAICompatibleProvider(
            base_url=kwargs.get("base_url") or "http://localhost:11434/v1",
            api_key=kwargs.get("api_key") or "",
            model=kwargs.get("model") or "llama3"
        )
    return LocalRuleBasedProvider()
