"""Configuration management for AAPA (Antigravity Auto Permission Assistant)."""

from __future__ import annotations

import json
import logging
import os
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class RiskLevel(str, Enum):
    """Categorized risk severity levels."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class Decision(str, Enum):
    """Structured decision recommendations."""
    AUTO_APPROVE = "AUTO_APPROVE"
    ASK_USER = "ASK_USER"
    BLOCK = "BLOCK"


class ActionCategory(str, Enum):
    """Semantic action classification."""
    READ_ONLY = "READ_ONLY"
    BUILD_TEST = "BUILD_TEST"
    LINTER = "LINTER"
    PACKAGE_MANAGEMENT = "PACKAGE_MANAGEMENT"
    FILE_MODIFICATION = "FILE_MODIFICATION"
    NETWORK = "NETWORK"
    GIT_OPERATION = "GIT_OPERATION"
    PROCESS_CONTROL = "PROCESS_CONTROL"
    ELEVATED_PRIVILEGE = "ELEVATED_PRIVILEGE"
    DESTRUCTIVE_FILESYSTEM = "DESTRUCTIVE_FILESYSTEM"
    SYSTEM_CONFIG = "SYSTEM_CONFIG"
    UNKNOWN = "UNKNOWN"


class BlockedPattern(BaseModel):
    """Rule definition for inherently blocked command patterns."""
    pattern: str
    category: str
    reason: str


class PolicySettings(BaseModel):
    """Policy engine execution switches."""
    auto_approve_safe_read_only: bool = True
    auto_approve_test_commands: bool = False
    enforce_workspace_boundary: bool = True
    block_destructive_commands: bool = True
    block_elevated_privileges: bool = True
    block_remote_pipe_to_shell: bool = True
    block_sensitive_file_access: bool = True
    allow_prompt_injection_detection: bool = True


def get_default_blocked_patterns() -> List[BlockedPattern]:
    """Default inherent security blocklist for system integrity and safety."""
    return [
        BlockedPattern(
            pattern=r"\b(format\s+[a-z]:|diskpart|mkfs|fdisk|dd\s+if=)",
            category="DISK_WIPE",
            reason="Attempting disk wipe or drive formatting"
        ),
        BlockedPattern(
            pattern=r"(\brm\s+-[rf]{1,2}\s+([/\\~]|\$HOME|%USERPROFILE%)|\b(del|rmdir|erase)\s+(?:/[a-zA-Z]\s+)*[a-z]:[/\\])",
            category="DESTRUCTIVE_FILESYSTEM",
            reason="Attempting catastrophic root, drive, or user profile deletion"
        ),
        BlockedPattern(
            pattern=r"\b(sudo|runas|Start-Process\s+.*-Verb\s+runas|gsudo)\b",
            category="ELEVATED_PRIVILEGE",
            reason="Requesting elevated administrative or root privileges"
        ),
        BlockedPattern(
            pattern=r"(curl|wget|Invoke-WebRequest|iwr)\b.*\|\s*(sh|bash|zsh|powershell|pwsh|cmd)\b",
            category="REMOTE_CODE_EXECUTION",
            reason="Piping unverified remote web content directly into an execution shell"
        ),
        BlockedPattern(
            pattern=r"\b(Set-ExecutionPolicy\s+(Bypass|Unrestricted)|disable-netfirewallrule|netsh\s+advfirewall\s+set\s+.*state\s+off)\b",
            category="SECURITY_BYPASS",
            reason="Attempting to disable operating system security policies or firewall rules"
        ),
        BlockedPattern(
            pattern=r"(\.env|id_rsa|id_ed25519|\.aws/credentials|secrets?\.json|credentials\.json|\.pem|\.key)",
            category="SENSITIVE_DATA_ACCESS",
            reason="Command references sensitive credential or private key files"
        ),
        BlockedPattern(
            pattern=r"\b(shutdown|reboot|init\s+0|init\s+6)\b",
            category="SYSTEM_SHUTDOWN",
            reason="Attempting system shutdown or restart"
        ),
        BlockedPattern(
            pattern=r":\(\)\s*\{\s*:\|:&\s*\};:",
            category="FORK_BOMB",
            reason="Fork bomb denial of service pattern detected"
        ),
    ]


class PolicyConfig(BaseModel):
    """Complete safety policy configuration model."""
    version: str = "1.0.0"
    name: str = "Default AAPA Safety Policy"
    description: str = "Deterministic rules for Antigravity permission requests."
    settings: PolicySettings = Field(default_factory=PolicySettings)
    read_only_commands: List[str] = Field(default_factory=lambda: [
        "ls", "dir", "cat", "type", "head", "tail", "more", "less",
        "pwd", "cd", "echo", "which", "where",
        "grep", "findstr", "wc", "stat", "file",
        "git status", "git log", "git diff", "git show", "git branch", "git rev-parse",
        "python --version", "python3 --version", "node -v", "npm -v", "cargo --version", "go version"
    ])
    allowed_test_commands: List[str] = Field(default_factory=lambda: [
        "pytest", "python -m pytest", "python -m unittest",
        "npm test", "npm run test", "yarn test", "pnpm test",
        "cargo test", "go test ./...", "ctest"
    ])
    allowed_linters: List[str] = Field(default_factory=lambda: [
        "flake8", "ruff", "black --check", "mypy", "pylint",
        "eslint", "prettier --check", "cargo clippy", "golangci-lint",
        "dart analyze"
    ])
    review_required_prefixes: List[str] = Field(default_factory=lambda: [
        "npm install", "npm i", "npm add", "yarn add", "pnpm add",
        "pip install", "pip3 install", "poetry add", "pipenv install",
        "cargo add", "go get",
        "git checkout", "git switch", "git commit", "git push", "git pull", "git merge", "git rebase",
        "curl", "wget", "Invoke-WebRequest", "Invoke-RestMethod",
        "docker", "podman", "kubectl", "terraform"
    ])
    blocked_patterns: List[BlockedPattern] = Field(default_factory=get_default_blocked_patterns)
    sensitive_file_patterns: List[str] = Field(default_factory=lambda: [
        "*.env*", "*id_rsa*", "*id_ed25519*", "*.pem", "*.key",
        "*credentials.json", "*secrets.json", "*token.txt", "*.pfx", "*.p12"
    ])


class AppSettings(BaseModel):
    """User and UI application settings."""
    active_project_path: str = ""
    recent_projects: List[str] = Field(default_factory=list)
    auto_approve_safe_read_only: bool = True
    auto_approve_test_commands: bool = False
    listen_host: str = "127.0.0.1"
    listen_port: int = 49152
    integration_mode: str = "hook"  # 'hook' or 'manual'
    ai_provider: str = "rule_based"  # 'rule_based', 'openai', 'gemini'
    ai_api_key: str = ""
    ai_base_url: str = ""
    ai_model: str = "rule-based-local"
    theme: str = "dark"
    log_level: str = "INFO"
    audit_log_path: str = ""


def get_aapa_data_dir() -> Path:
    """Returns the persistent application data directory."""
    if os.name == "nt":
        base = os.getenv("LOCALAPPDATA") or os.getenv("APPDATA")
        if base:
            path = Path(base) / "aapa"
        else:
            path = Path.home() / ".aapa"
    else:
        path = Path.home() / ".config" / "aapa"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_default_policy_file() -> Path:
    """Finds the default policy file shipped with the repo."""
    repo_policy = Path(__file__).resolve().parent.parent.parent / "config" / "default_policy.json"
    if repo_policy.exists():
        return repo_policy
    return get_aapa_data_dir() / "policy.json"


def load_policy(custom_path: Optional[Path] = None) -> PolicyConfig:
    """Loads policy config from JSON file with fallback to defaults."""
    target_path = custom_path or get_default_policy_file()
    if target_path and target_path.exists():
        try:
            with open(target_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return PolicyConfig.model_validate(data)
        except Exception as exc:
            logger.warning("Failed to load policy from %s: %s. Using in-memory defaults.", target_path, exc)
    return PolicyConfig()


def save_policy(policy: PolicyConfig, target_path: Optional[Path] = None) -> None:
    """Saves policy config to file."""
    dest = target_path or (get_aapa_data_dir() / "policy.json")
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "w", encoding="utf-8") as f:
        json.dump(policy.model_dump(), f, indent=2)
    logger.info("Saved policy to %s", dest)


def load_settings() -> AppSettings:
    """Loads user settings from disk."""
    settings_file = get_aapa_data_dir() / "settings.json"
    if settings_file.exists():
        try:
            with open(settings_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return AppSettings.model_validate(data)
        except Exception as exc:
            logger.warning("Failed to load settings from %s: %s", settings_file, exc)
    return AppSettings()


def save_settings(settings: AppSettings) -> None:
    """Saves user settings to disk."""
    settings_file = get_aapa_data_dir() / "settings.json"
    settings_file.parent.mkdir(parents=True, exist_ok=True)
    with open(settings_file, "w", encoding="utf-8") as f:
        json.dump(settings.model_dump(), f, indent=2)
    logger.info("Saved settings to %s", settings_file)
