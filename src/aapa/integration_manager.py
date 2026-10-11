"""Google Antigravity integration manager for AAPA.

Safely installs, audits, and removes lifecycle hooks in workspace (.agents/hooks.json)
or global configuration (~/.gemini/config/hooks.json) without bypassing permissions.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, Optional
from pydantic import BaseModel

logger = logging.getLogger(__name__)

HOOK_IDENTIFIER = "aapa-permission-assistant"


class IntegrationStatus(BaseModel):
    """Detailed status of Antigravity integration state."""
    antigravity_detected: bool
    workspace_hook_installed: bool
    global_hook_installed: bool
    ipc_server_online: bool
    hook_command: str
    active_mode: str  # 'WORKSPACE_HOOK', 'GLOBAL_HOOK', 'MANUAL_ONLY'
    description: str


class IntegrationManager:
    """Manages integration hooks with Antigravity AI platform."""

    @staticmethod
    def get_global_gemini_dir() -> Path:
        """Returns standard global Gemini/Antigravity configuration path."""
        return Path.home() / ".gemini" / "config"

    @staticmethod
    def detect_antigravity() -> bool:
        """Checks if Antigravity is installed or configured on the machine."""
        gemini_home = Path.home() / ".gemini"
        if gemini_home.exists():
            return True
        if shutil.which("agy"):
            return True
        return False

    @classmethod
    def get_status(cls, project_dir: Optional[str | Path] = None, ipc_online: bool = False) -> IntegrationStatus:
        """Evaluates live integration status."""
        agy_detected = cls.detect_antigravity()

        ws_installed = False
        if project_dir:
            ws_hook_path = Path(project_dir) / ".agents" / "hooks.json"
            ws_installed = cls._is_hook_present(ws_hook_path)

        global_hook_path = cls.get_global_gemini_dir() / "hooks.json"
        global_installed = cls._is_hook_present(global_hook_path)

        if ws_installed:
            active_mode = "WORKSPACE_HOOK"
            desc = "AAPA hook is active for the current project workspace."
        elif global_installed:
            active_mode = "GLOBAL_HOOK"
            desc = "AAPA hook is active globally across all Antigravity workspaces."
        else:
            active_mode = "MANUAL_ONLY"
            desc = "Manual review mode. Paste requests directly into the dashboard, or click 'Install Hook'."

        return IntegrationStatus(
            antigravity_detected=agy_detected,
            workspace_hook_installed=ws_installed,
            global_hook_installed=global_installed,
            ipc_server_online=ipc_online,
            hook_command=cls._build_hook_command(),
            active_mode=active_mode,
            description=desc
        )

    @classmethod
    def install_workspace_hook(cls, project_dir: str | Path) -> Tuple[bool, str]:
        """Installs AAPA PreToolUse hook into project_dir/.agents/hooks.json."""
        p_path = Path(project_dir).resolve()
        if not p_path.exists() or not p_path.is_dir():
            return False, f"Invalid project directory: {p_path}"

        agents_dir = p_path / ".agents"
        agents_dir.mkdir(parents=True, exist_ok=True)
        hook_path = agents_dir / "hooks.json"

        return cls._write_hook_entry(hook_path)

    @classmethod
    def uninstall_workspace_hook(cls, project_dir: str | Path) -> Tuple[bool, str]:
        """Removes AAPA hook from project_dir/.agents/hooks.json."""
        p_path = Path(project_dir).resolve()
        hook_path = p_path / ".agents" / "hooks.json"
        return cls._remove_hook_entry(hook_path)

    @classmethod
    def install_global_hook(cls) -> Tuple[bool, str]:
        """Installs AAPA PreToolUse hook into ~/.gemini/config/hooks.json."""
        global_dir = cls.get_global_gemini_dir()
        global_dir.mkdir(parents=True, exist_ok=True)
        hook_path = global_dir / "hooks.json"
        return cls._write_hook_entry(hook_path)

    @classmethod
    def uninstall_global_hook(cls) -> Tuple[bool, str]:
        """Removes AAPA hook from ~/.gemini/config/hooks.json."""
        hook_path = cls.get_global_gemini_dir() / "hooks.json"
        return cls._remove_hook_entry(hook_path)

    @classmethod
    def _build_hook_command(cls) -> str:
        """Constructs reliable command string to invoke AAPA hook module."""
        py_exe = sys.executable or "python"
        # If path contains spaces, quote it
        if " " in py_exe:
            py_exe = f'"{py_exe}"'
        return f"{py_exe} -m aapa.hook"

    @classmethod
    def _write_hook_entry(cls, hook_file: Path) -> Tuple[bool, str]:
        """Merges AAPA hook configuration into a hooks.json file."""
        data: Dict[str, Any] = {}
        if hook_file.exists():
            try:
                with open(hook_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception as exc:
                logger.warning("Existing hooks.json could not be parsed: %s", exc)

        hook_spec = {
            "enabled": True,
            "PreToolUse": [
                {
                    "matcher": "run_command",
                    "hooks": [
                        {
                            "type": "command",
                            "command": cls._build_hook_command(),
                            "timeout": 30
                        }
                    ]
                }
            ]
        }

        data[HOOK_IDENTIFIER] = hook_spec

        try:
            with open(hook_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            logger.info("Successfully wrote AAPA hook to %s", hook_file)
            return True, f"AAPA PreToolUse hook successfully installed in {hook_file}."
        except Exception as exc:
            return False, f"Failed to write hook file {hook_file}: {exc}"

    @classmethod
    def _remove_hook_entry(cls, hook_file: Path) -> Tuple[bool, str]:
        """Removes AAPA hook configuration from a hooks.json file."""
        if not hook_file.exists():
            return True, "No hook file found."

        try:
            with open(hook_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            if HOOK_IDENTIFIER in data:
                del data[HOOK_IDENTIFIER]
                with open(hook_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
                return True, f"AAPA hook removed from {hook_file}."
            return True, "AAPA hook was not active in this file."
        except Exception as exc:
            return False, f"Failed to modify {hook_file}: {exc}"

    @classmethod
    def _is_hook_present(cls, hook_file: Path) -> bool:
        """Checks if AAPA hook is configured in the specified hooks.json."""
        if not hook_file.exists():
            return False
        try:
            with open(hook_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return HOOK_IDENTIFIER in data
        except Exception:
            return False
