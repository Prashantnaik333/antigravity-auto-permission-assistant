"""Unit tests for Antigravity integration manager."""

import json
from pathlib import Path
from aapa.integration_manager import HOOK_IDENTIFIER, IntegrationManager


def test_install_and_uninstall_workspace_hook(tmp_path: Path):
    # Test installation
    ok, msg = IntegrationManager.install_workspace_hook(tmp_path)
    assert ok
    hook_file = tmp_path / ".agents" / "hooks.json"
    assert hook_file.exists()

    with open(hook_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert HOOK_IDENTIFIER in data
    assert data[HOOK_IDENTIFIER]["enabled"] is True
    pre_tool = data[HOOK_IDENTIFIER]["PreToolUse"][0]
    assert pre_tool["matcher"] == "run_command"
    assert "aapa.hook" in pre_tool["hooks"][0]["command"]

    # Verify status detects installed hook
    status = IntegrationManager.get_status(tmp_path)
    assert status.workspace_hook_installed is True
    assert status.active_mode == "WORKSPACE_HOOK"

    # Test uninstallation
    ok_un, msg_un = IntegrationManager.uninstall_workspace_hook(tmp_path)
    assert ok_un
    with open(hook_file, "r", encoding="utf-8") as f:
        data_after = json.load(f)
    assert HOOK_IDENTIFIER not in data_after

    status_after = IntegrationManager.get_status(tmp_path)
    assert status_after.workspace_hook_installed is False
    assert status_after.active_mode == "MANUAL_ONLY"


def test_missing_directory_handling():
    fake_path = Path("C:/NonExistentPathXYZ123")
    ok, msg = IntegrationManager.install_workspace_hook(fake_path)
    assert not ok
    assert "Invalid project directory" in msg
