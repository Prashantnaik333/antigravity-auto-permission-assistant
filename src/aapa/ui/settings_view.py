"""Settings and integration manager view for AAPA desktop UI."""

from __future__ import annotations

from typing import Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from aapa.config import AppSettings
from aapa.integration_manager import IntegrationManager


class SettingsViewWidget(QWidget):
    """Configuration interface for Antigravity hooks, IPC server, and AI adapter."""

    settings_updated = Signal(AppSettings)

    def __init__(self, settings: AppSettings, project_path: str = "", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.settings = settings
        self.project_path = project_path
        self._init_ui()
        self.refresh_integration_status()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        # 1. Antigravity Integration Status & Actions
        integ_group = QGroupBox("Google Antigravity Integration")
        integ_layout = QVBoxLayout(integ_group)

        self.status_label = QLabel("Detecting integration state...")
        self.status_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        integ_layout.addWidget(self.status_label)

        self.details_label = QLabel("")
        self.details_label.setWordWrap(True)
        self.details_label.setStyleSheet("color: #a0aec0;")
        integ_layout.addWidget(self.details_label)

        hook_btns = QHBoxLayout()
        self.install_ws_btn = QPushButton("Install Hook in Project (.agents/hooks.json)")
        self.install_ws_btn.clicked.connect(self._install_workspace_hook)

        self.install_glob_btn = QPushButton("Install Hook Globally (~/.gemini/config)")
        self.install_glob_btn.setObjectName("btn-secondary")
        self.install_glob_btn.clicked.connect(self._install_global_hook)

        self.uninstall_btn = QPushButton("Uninstall Hooks")
        self.uninstall_btn.setObjectName("btn-danger")
        self.uninstall_btn.clicked.connect(self._uninstall_hooks)

        hook_btns.addWidget(self.install_ws_btn)
        hook_btns.addWidget(self.install_glob_btn)
        hook_btns.addWidget(self.uninstall_btn)
        integ_layout.addLayout(hook_btns)

        layout.addWidget(integ_group)

        # 2. Local IPC Server Configuration
        ipc_group = QGroupBox("Local Loopback IPC Service")
        ipc_layout = QHBoxLayout(ipc_group)

        ipc_layout.addWidget(QLabel("Listen Host:"))
        self.host_edit = QLineEdit(self.settings.listen_host)
        self.host_edit.setReadOnly(True)
        ipc_layout.addWidget(self.host_edit)

        ipc_layout.addWidget(QLabel("Port:"))
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1024, 65535)
        self.port_spin.setValue(self.settings.listen_port)
        ipc_layout.addWidget(self.port_spin)

        layout.addWidget(ipc_group)

        # 3. AI Provider Configuration
        ai_group = QGroupBox("AI Explanation Provider")
        ai_layout = QVBoxLayout(ai_group)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Provider Mode:"))
        self.ai_combo = QComboBox()
        self.ai_combo.addItems(["rule_based (Offline, Free, Zero-Config)", "openai (Ollama, LocalAI, OpenAI)"])
        if "openai" in self.settings.ai_provider:
            self.ai_combo.setCurrentIndex(1)
        row1.addWidget(self.ai_combo)
        ai_layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Endpoint URL:"))
        self.base_url_edit = QLineEdit(self.settings.ai_base_url or "http://localhost:11434/v1")
        row2.addWidget(self.base_url_edit)
        ai_layout.addLayout(row2)

        row3 = QHBoxLayout()
        row3.addWidget(QLabel("Model Name:"))
        self.model_edit = QLineEdit(self.settings.ai_model or "llama3")
        row3.addWidget(self.model_edit)
        ai_layout.addLayout(row3)

        row4 = QHBoxLayout()
        row4.addWidget(QLabel("API Key (Optional):"))
        self.api_key_edit = QLineEdit(self.settings.ai_api_key)
        self.api_key_edit.setEchoMode(QLineEdit.Password)
        row4.addWidget(self.api_key_edit)
        ai_layout.addLayout(row4)

        layout.addWidget(ai_group)

        # 4. Troubleshooting & Instructions
        help_group = QGroupBox("Quick Troubleshooting & Integration Help")
        help_layout = QVBoxLayout(help_group)
        help_text = QTextEdit()
        help_text.setReadOnly(True)
        help_text.setMaximumHeight(120)
        help_text.setHtml(
            "<b>How Antigravity Integration Works:</b><br>"
            "1. Antigravity uses official <code>hooks.json</code> lifecycle hooks on <code>PreToolUse</code>.<br>"
            "2. When Antigravity requests tool execution, it pipes JSON to <code>python -m aapa.hook</code>.<br>"
            "3. The hook forwards requests to this running desktop app on port 49152.<br>"
            "4. If this app is closed, AAPA evaluates the policy offline in headless CLI mode.<br>"
            "5. If you do not wish to use hooks, you can paste requests directly into the <i>Manual Review</i> dialog."
        )
        help_layout.addWidget(help_text)
        layout.addWidget(help_group)

        # 5. Save Button
        save_layout = QHBoxLayout()
        self.save_btn = QPushButton("Save Settings")
        self.save_btn.setObjectName("btn-success")
        self.save_btn.clicked.connect(self._save_settings)
        save_layout.addStretch()
        save_layout.addWidget(self.save_btn)
        layout.addLayout(save_layout)

    def refresh_integration_status(self) -> None:
        """Queries IntegrationManager for current status."""
        status = IntegrationManager.get_status(self.project_path, ipc_online=True)
        if status.active_mode == "WORKSPACE_HOOK":
            self.status_label.setText("● Integration Active: Workspace Hook (.agents/hooks.json)")
            self.status_label.setStyleSheet("color: #68d391; font-weight: bold;")
        elif status.active_mode == "GLOBAL_HOOK":
            self.status_label.setText("● Integration Active: Global Hook (~/.gemini/config/hooks.json)")
            self.status_label.setStyleSheet("color: #63b3ed; font-weight: bold;")
        else:
            self.status_label.setText("○ Integration: Manual Review Mode (No Hook Active)")
            self.status_label.setStyleSheet("color: #f6e05e; font-weight: bold;")
        self.details_label.setText(status.description)

    def _install_workspace_hook(self) -> None:
        if not self.project_path:
            QMessageBox.warning(self, "No Project Active", "Please select a project folder first before installing workspace hooks.")
            return
        ok, msg = IntegrationManager.install_workspace_hook(self.project_path)
        if ok:
            QMessageBox.information(self, "Hook Installed", msg)
        else:
            QMessageBox.critical(self, "Installation Error", msg)
        self.refresh_integration_status()

    def _install_global_hook(self) -> None:
        ok, msg = IntegrationManager.install_global_hook()
        if ok:
            QMessageBox.information(self, "Global Hook Installed", msg)
        else:
            QMessageBox.critical(self, "Installation Error", msg)
        self.refresh_integration_status()

    def _uninstall_hooks(self) -> None:
        if self.project_path:
            IntegrationManager.uninstall_workspace_hook(self.project_path)
        IntegrationManager.uninstall_global_hook()
        QMessageBox.information(self, "Hooks Removed", "AAPA hooks have been removed from both workspace and global configs.")
        self.refresh_integration_status()

    def _save_settings(self) -> None:
        self.settings.listen_port = self.port_spin.value()
        is_openai = "openai" in self.ai_combo.currentText()
        self.settings.ai_provider = "openai" if is_openai else "rule_based"
        self.settings.ai_base_url = self.base_url_edit.text().strip()
        self.settings.ai_model = self.model_edit.text().strip()
        self.settings.ai_api_key = self.api_key_edit.text().strip()
        self.settings_updated.emit(self.settings)
        QMessageBox.information(self, "Settings Saved", "Application preferences updated.")
