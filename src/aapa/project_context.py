"""Project-aware context engine for AAPA.

Extracts technology stack, test/build runners, dependencies, and security boundaries
from permitted project files while filtering sensitive information and detecting prompt injections.
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from pydantic import BaseModel, Field

from aapa.secret_filter import is_sensitive_path, redact_secrets

logger = logging.getLogger(__name__)

PROMPT_INJECTION_PATTERNS = [
    re.compile(r"(?i)\bignore\s+(?:all\s+)?(?:previous|prior|system)\s+instructions\b"),
    re.compile(r"(?i)\bsystem\s+override\b"),
    re.compile(r"(?i)\b(auto-?approve|always\s+allow)\s+(?:all\s+)?(?:commands|actions|requests|permissions)\b"),
    re.compile(r"(?i)\bbypass\s+(?:all\s+)?(?:safety|security|policy|restrictions)\b"),
    re.compile(r"(?i)\bdeveloper\s+mode\s+enabled\b"),
    re.compile(r"(?i)\bdo\s+not\s+(?:ask|prompt)\s+(?:the\s+)?user\b"),
]

PERMITTED_CONFIG_FILENAMES = {
    "readme.md",
    "agents.md",
    "gemini.md",
    "package.json",
    "requirements.txt",
    "pyproject.toml",
    "cargo.toml",
    "go.mod",
    ".gitignore",
}


class ProjectProfile(BaseModel):
    """Structured representation of active project characteristics."""
    project_path: str
    project_name: str
    purpose: str = "General software project"
    languages: List[str] = Field(default_factory=list)
    frameworks: List[str] = Field(default_factory=list)
    package_managers: List[str] = Field(default_factory=list)
    dependencies: List[str] = Field(default_factory=list)
    test_commands: List[str] = Field(default_factory=list)
    build_commands: List[str] = Field(default_factory=list)
    linters: List[str] = Field(default_factory=list)
    read_files: List[str] = Field(default_factory=list)
    ignored_files: List[str] = Field(default_factory=list)
    security_warnings: List[str] = Field(default_factory=list)
    detected_injections: List[str] = Field(default_factory=list)

    def to_markdown_summary(self) -> str:
        """Renders an easily human-readable profile summary."""
        lines = [
            f"### Project Profile: {self.project_name}",
            f"- **Path:** `{self.project_path}`",
            f"- **Languages:** {', '.join(self.languages) if self.languages else 'Not detected'}",
            f"- **Frameworks / Tools:** {', '.join(self.frameworks) if self.frameworks else 'None'}",
            f"- **Approved Test Commands:** {', '.join(self.test_commands) if self.test_commands else 'None detected'}",
            f"- **Permitted Config Files Read:** {len(self.read_files)} files",
        ]
        if self.detected_injections:
            lines.append(f"\n⚠️ **PROMPT INJECTION WARNINGS DETECTED:**")
            for inj in self.detected_injections:
                lines.append(f"  - `{inj}`")
        if self.security_warnings:
            lines.append(f"\n⚠️ **SECURITY NOTICES:**")
            for w in self.security_warnings:
                lines.append(f"  - {w}")
        return "\n".join(lines)


class ProjectContextEngine:
    """Safely inspects project directory and compiles contextual boundaries."""

    def __init__(self, max_file_bytes: int = 65536):
        self.max_file_bytes = max_file_bytes

    def scan_project(self, project_dir: str | Path) -> ProjectProfile:
        """Inspects the specified directory and builds a ProjectProfile."""
        p_path = Path(project_dir).resolve()
        if not p_path.exists() or not p_path.is_dir():
            return ProjectProfile(
                project_path=str(p_path),
                project_name=p_path.name or "Unknown",
                security_warnings=["Target directory does not exist or is not a directory."]
            )

        profile = ProjectProfile(
            project_path=str(p_path),
            project_name=p_path.name or "Unnamed Project"
        )

        for entry in p_path.iterdir():
            if not entry.is_file():
                continue

            fname_lower = entry.name.lower()

            if is_sensitive_path(entry):
                profile.ignored_files.append(entry.name)
                profile.security_warnings.append(f"Excluded sensitive credential file: {entry.name}")
                continue

            if fname_lower in PERMITTED_CONFIG_FILENAMES:
                self._process_file(entry, profile)

        # Infer default build/test commands if found in languages
        if "Python" in profile.languages and not profile.test_commands:
            profile.test_commands.append("pytest")
        if "JavaScript/TypeScript" in profile.languages and not profile.test_commands:
            profile.test_commands.append("npm test")
        if "Rust" in profile.languages and not profile.test_commands:
            profile.test_commands.append("cargo test")
        if "Go" in profile.languages and not profile.test_commands:
            profile.test_commands.append("go test ./...")

        return profile

    def _process_file(self, file_path: Path, profile: ProjectProfile) -> None:
        """Reads and analyzes individual configuration or documentation files."""
        try:
            size = file_path.stat().st_size
            if size > self.max_file_bytes:
                profile.security_warnings.append(
                    f"File {file_path.name} exceeds max size limit ({size} bytes > {self.max_file_bytes} bytes). Skipped."
                )
                return

            content = file_path.read_text(encoding="utf-8", errors="replace")
            sanitized = redact_secrets(content)

            # Check for adversarial prompt injection in comments/markdown
            for pattern in PROMPT_INJECTION_PATTERNS:
                for match in pattern.finditer(sanitized):
                    warning_msg = f"Potential prompt injection in {file_path.name}: '{match.group(0)}'"
                    profile.detected_injections.append(warning_msg)
                    logger.warning(warning_msg)

            fname = file_path.name.lower()
            profile.read_files.append(file_path.name)

            if fname == "package.json":
                self._parse_package_json(sanitized, profile)
            elif fname == "pyproject.toml":
                self._parse_pyproject_toml(sanitized, profile)
            elif fname == "requirements.txt":
                self._parse_requirements_txt(sanitized, profile)
            elif fname == "cargo.toml":
                self._parse_cargo_toml(sanitized, profile)
            elif fname == "go.mod":
                self._parse_go_mod(sanitized, profile)
            elif fname in ("readme.md", "agents.md", "gemini.md"):
                self._parse_markdown_docs(sanitized, profile)

        except Exception as exc:
            profile.security_warnings.append(f"Error parsing {file_path.name}: {exc}")

    def _parse_package_json(self, content: str, profile: ProjectProfile) -> None:
        """Parses package.json scripts and dependencies."""
        if "JavaScript/TypeScript" not in profile.languages:
            profile.languages.append("JavaScript/TypeScript")
        if "npm" not in profile.package_managers:
            profile.package_managers.append("npm")

        try:
            data = json.loads(content)
            scripts = data.get("scripts", {})
            if "test" in scripts and "npm test" not in profile.test_commands:
                profile.test_commands.append("npm test")
            if "build" in scripts and "npm run build" not in profile.build_commands:
                profile.build_commands.append("npm run build")
            if "lint" in scripts and "npm run lint" not in profile.linters:
                profile.linters.append("npm run lint")

            deps = list(data.get("dependencies", {}).keys())
            dev_deps = list(data.get("devDependencies", {}).keys())
            profile.dependencies.extend(deps[:15])

            if "react" in deps or "vue" in deps or "next" in deps:
                profile.frameworks.append("Web Frontend")
            if "express" in deps or "fastify" in deps or "nestjs" in deps:
                profile.frameworks.append("Node.js Backend")
        except json.JSONDecodeError:
            pass

    def _parse_pyproject_toml(self, content: str, profile: ProjectProfile) -> None:
        """Parses pyproject.toml for Python project info."""
        if "Python" not in profile.languages:
            profile.languages.append("Python")
        if "pip" not in profile.package_managers:
            profile.package_managers.append("pip")

        if "pytest" in content and "pytest" not in profile.test_commands:
            profile.test_commands.append("pytest")
        if "ruff" in content and "ruff check" not in profile.linters:
            profile.linters.append("ruff check")
        if "black" in content and "black --check" not in profile.linters:
            profile.linters.append("black --check")
        if "mypy" in content and "mypy" not in profile.linters:
            profile.linters.append("mypy")
        if "fastapi" in content:
            profile.frameworks.append("FastAPI")
        if "django" in content:
            profile.frameworks.append("Django")
        if "flask" in content:
            profile.frameworks.append("Flask")

    def _parse_requirements_txt(self, content: str, profile: ProjectProfile) -> None:
        """Parses requirements.txt lines."""
        if "Python" not in profile.languages:
            profile.languages.append("Python")
        for line in content.splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                pkg = re.split(r"[=<>]", line)[0].strip()
                if pkg and pkg not in profile.dependencies and len(profile.dependencies) < 20:
                    profile.dependencies.append(pkg)
                if pkg == "pytest" and "pytest" not in profile.test_commands:
                    profile.test_commands.append("pytest")

    def _parse_cargo_toml(self, content: str, profile: ProjectProfile) -> None:
        """Parses Cargo.toml for Rust tools."""
        if "Rust" not in profile.languages:
            profile.languages.append("Rust")
        if "cargo" not in profile.package_managers:
            profile.package_managers.append("cargo")
        if "cargo test" not in profile.test_commands:
            profile.test_commands.append("cargo test")
        if "cargo build" not in profile.build_commands:
            profile.build_commands.append("cargo build")
        if "cargo clippy" not in profile.linters:
            profile.linters.append("cargo clippy")

    def _parse_go_mod(self, content: str, profile: ProjectProfile) -> None:
        """Parses go.mod for Go tools."""
        if "Go" not in profile.languages:
            profile.languages.append("Go")
        if "go" not in profile.package_managers:
            profile.package_managers.append("go")
        if "go test ./..." not in profile.test_commands:
            profile.test_commands.append("go test ./...")
        if "go build" not in profile.build_commands:
            profile.build_commands.append("go build")

    def _parse_markdown_docs(self, content: str, profile: ProjectProfile) -> None:
        """Extracts brief purpose description from Markdown documentation."""
        lines = content.splitlines()
        for i, line in enumerate(lines[:30]):
            line = line.strip()
            if line.startswith("# "):
                profile.project_name = line.lstrip("# ").strip()
            elif line and not line.startswith("#") and not line.startswith("!") and not line.startswith("["):
                if profile.purpose == "General software project":
                    profile.purpose = line[:150]
                break
