"""Interactive Safety Policy Editor tab for AAPA desktop UI."""

from __future__ import annotations

from typing import Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from aapa.config import BlockedPattern, PolicyConfig


class PolicyEditorWidget(QWidget):
    """View and modify deterministic rules, allowlists, and switches."""

    policy_changed = Signal(PolicyConfig)

    def __init__(self, policy: PolicyConfig, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.policy = policy
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        # 1. Global Safety Toggles
        switches_group = QGroupBox("Core Safety Enforcement Switches")
        switches_layout = QVBoxLayout(switches_group)

        self.cb_ro = QCheckBox("Auto-approve Safe Read-Only commands (ls, dir, cat, git status, etc.)")
        self.cb_ro.setChecked(self.policy.settings.auto_approve_safe_read_only)

        self.cb_test = QCheckBox("Auto-approve Verified Project Test commands (pytest, npm test, cargo test)")
        self.cb_test.setChecked(self.policy.settings.auto_approve_test_commands)

        self.cb_boundary = QCheckBox("Enforce strict Workspace Boundary (block actions outside project root)")
        self.cb_boundary.setChecked(self.policy.settings.enforce_workspace_boundary)

        self.cb_destructive = QCheckBox("Block destructive commands by default (rm -rf, format, diskpart)")
        self.cb_destructive.setChecked(self.policy.settings.block_destructive_commands)

        self.cb_privilege = QCheckBox("Block elevated privilege execution (sudo, runas, gsudo)")
        self.cb_privilege.setChecked(self.policy.settings.block_elevated_privileges)

        self.cb_remote = QCheckBox("Block remote pipe-to-shell commands (curl ... | sh)")
        self.cb_remote.setChecked(self.policy.settings.block_remote_pipe_to_shell)

        self.cb_sensitive = QCheckBox("Block commands referencing protected credential files (.env, keys)")
        self.cb_sensitive.setChecked(self.policy.settings.block_sensitive_file_access)

        for cb in (self.cb_ro, self.cb_test, self.cb_boundary, self.cb_destructive, self.cb_privilege, self.cb_remote, self.cb_sensitive):
            switches_layout.addWidget(cb)
        layout.addWidget(switches_group)

        # 2. Lists & Tables: Allowlist & Test Commands
        lists_layout = QHBoxLayout()

        # Read-Only Allowlist
        ro_group = QGroupBox("Read-Only Allowlist")
        ro_layout = QVBoxLayout(ro_group)
        self.ro_list = QListWidget()
        for cmd in self.policy.read_only_commands:
            self.ro_list.addItem(cmd)
        ro_layout.addWidget(self.ro_list)

        ro_btn_layout = QHBoxLayout()
        add_ro_btn = QPushButton("+ Add")
        add_ro_btn.clicked.connect(self._add_ro_command)
        rem_ro_btn = QPushButton("- Remove")
        rem_ro_btn.setObjectName("btn-secondary")
        rem_ro_btn.clicked.connect(self._rem_ro_command)
        ro_btn_layout.addWidget(add_ro_btn)
        ro_btn_layout.addWidget(rem_ro_btn)
        ro_layout.addLayout(ro_btn_layout)
        lists_layout.addWidget(ro_group)

        # Approved Test Commands
        test_group = QGroupBox("Approved Test Commands")
        test_layout = QVBoxLayout(test_group)
        self.test_list = QListWidget()
        for cmd in self.policy.allowed_test_commands:
            self.test_list.addItem(cmd)
        test_layout.addWidget(self.test_list)

        test_btn_layout = QHBoxLayout()
        add_test_btn = QPushButton("+ Add")
        add_test_btn.clicked.connect(self._add_test_command)
        rem_test_btn = QPushButton("- Remove")
        rem_test_btn.setObjectName("btn-secondary")
        rem_test_btn.clicked.connect(self._rem_test_command)
        test_btn_layout.addWidget(add_test_btn)
        test_btn_layout.addWidget(rem_test_btn)
        test_layout.addLayout(test_btn_layout)
        lists_layout.addWidget(test_group)

        layout.addLayout(lists_layout)

        # 3. Save & Reset Action Bar
        actions_layout = QHBoxLayout()
        self.save_btn = QPushButton("Save Safety Policy Changes")
        self.save_btn.setObjectName("btn-success")
        self.save_btn.clicked.connect(self._save_changes)

        self.reset_btn = QPushButton("Reset to Default Safety Policy")
        self.reset_btn.setObjectName("btn-danger")
        self.reset_btn.clicked.connect(self._reset_defaults)

        actions_layout.addStretch()
        actions_layout.addWidget(self.reset_btn)
        actions_layout.addWidget(self.save_btn)
        layout.addLayout(actions_layout)

    def _add_ro_command(self) -> None:
        cmd, ok = QInputDialog.getText(self, "Add Read-Only Command", "Enter command prefix (e.g. 'tree'):")
        if ok and cmd.strip():
            self.ro_list.addItem(cmd.strip())

    def _rem_ro_command(self) -> None:
        row = self.ro_list.currentRow()
        if row >= 0:
            self.ro_list.takeItem(row)

    def _add_test_command(self) -> None:
        cmd, ok = QInputDialog.getText(self, "Add Test Runner", "Enter test command (e.g. 'pytest -v'):")
        if ok and cmd.strip():
            self.test_list.addItem(cmd.strip())

    def _rem_test_command(self) -> None:
        row = self.test_list.currentRow()
        if row >= 0:
            self.test_list.takeItem(row)

    def _save_changes(self) -> None:
        # Update settings
        self.policy.settings.auto_approve_safe_read_only = self.cb_ro.isChecked()
        self.policy.settings.auto_approve_test_commands = self.cb_test.isChecked()
        self.policy.settings.enforce_workspace_boundary = self.cb_boundary.isChecked()
        self.policy.settings.block_destructive_commands = self.cb_destructive.isChecked()
        self.policy.settings.block_elevated_privileges = self.cb_privilege.isChecked()
        self.policy.settings.block_remote_pipe_to_shell = self.cb_remote.isChecked()
        self.policy.settings.block_sensitive_file_access = self.cb_sensitive.isChecked()

        # Update lists
        self.policy.read_only_commands = [
            self.ro_list.item(i).text() for i in range(self.ro_list.count())
        ]
        self.policy.allowed_test_commands = [
            self.test_list.item(i).text() for i in range(self.test_list.count())
        ]

        self.policy_changed.emit(self.policy)
        QMessageBox.information(self, "Policy Saved", "Deterministic safety policy updated successfully.")

    def _reset_defaults(self) -> None:
        reply = QMessageBox.question(
            self,
            "Reset Policy",
            "Are you sure you want to revert all rules to the default safety baseline?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.policy = PolicyConfig()
            self._reload_ui()
            self.policy_changed.emit(self.policy)

    def _reload_ui(self) -> None:
        self.cb_ro.setChecked(self.policy.settings.auto_approve_safe_read_only)
        self.cb_test.setChecked(self.policy.settings.auto_approve_test_commands)
        self.cb_boundary.setChecked(self.policy.settings.enforce_workspace_boundary)
        self.cb_destructive.setChecked(self.policy.settings.block_destructive_commands)
        self.cb_privilege.setChecked(self.policy.settings.block_elevated_privileges)
        self.cb_remote.setChecked(self.policy.settings.block_remote_pipe_to_shell)
        self.cb_sensitive.setChecked(self.policy.settings.block_sensitive_file_access)

        self.ro_list.clear()
        for cmd in self.policy.read_only_commands:
            self.ro_list.addItem(cmd)

        self.test_list.clear()
        for cmd in self.policy.allowed_test_commands:
            self.test_list.addItem(cmd)
