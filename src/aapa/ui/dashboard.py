"""Main desktop application window and dashboard for AAPA."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional
from PySide6.QtCore import QObject, Qt, Signal, Slot
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from aapa.audit_logger import AuditLogger
from aapa.config import (
    AppSettings,
    Decision,
    PolicyConfig,
    RiskLevel,
    load_policy,
    load_settings,
    save_policy,
    save_settings,
)
from aapa.integration_manager import IntegrationManager
from aapa.ipc_server import AAPAIPCServer
from aapa.project_context import ProjectContextEngine, ProjectProfile
from aapa.request_parser import NormalizedRequest, RequestParser
from aapa.risk_analyzer import AnalysisResult, RiskAnalyzer
from aapa.ui.history_view import HistoryViewWidget
from aapa.ui.policy_view import PolicyEditorWidget
from aapa.ui.project_view import ProjectProfileWidget
from aapa.ui.request_view import ManualRequestDialog, RequestInspectorWidget
from aapa.ui.settings_view import SettingsViewWidget
from aapa.ui.theme import DARK_STYLESHEET

logger = logging.getLogger(__name__)


class BridgeSignals(QObject):
    """Thread-safe signal bridge between background IPC server and Qt GUI."""
    new_request = Signal(object, object)  # NormalizedRequest, AnalysisResult


class AAPADashboard(QMainWindow):
    """Primary desktop dashboard for Antigravity Auto Permission Assistant."""

    def __init__(self, project_path: Optional[str] = None):
        super().__init__()
        self.setWindowTitle("Antigravity Auto Permission Assistant (AAPA)")
        self.setMinimumSize(1080, 720)
        self.setStyleSheet(DARK_STYLESHEET)

        # Core State
        self.settings: AppSettings = load_settings()
        self.policy: PolicyConfig = load_policy()
        self.audit_logger = AuditLogger()
        self.analyzer = RiskAnalyzer(policy=self.policy, audit_logger=self.audit_logger)
        self.context_engine = ProjectContextEngine()

        # Active Project
        self.active_project_path = project_path or self.settings.active_project_path or ""
        self.active_profile: Optional[ProjectProfile] = None

        # Request Tracking
        self.pending_inbox: Dict[str, tuple[NormalizedRequest, AnalysisResult]] = {}
        self.stat_analyzed = 0
        self.stat_auto_approved = 0
        self.stat_blocked = 0

        # Signal Bridge for IPC Server
        self.signals = BridgeSignals()
        self.signals.new_request.connect(self._on_request_received_threadsafe)

        # Start IPC Server
        self._start_ipc_server()

        # Build UI
        self._init_ui()

        # Scan initial project if set
        if self.active_project_path:
            self._load_project(self.active_project_path)

    def _init_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(12, 10, 12, 10)
        main_layout.setSpacing(8)

        # 1. Top Header Bar (Status, Project, Stats)
        header_frame = QFrame()
        header_frame.setStyleSheet("background-color: #171923; border: 1px solid #2d3748; border-radius: 6px; padding: 6px 12px;")
        header_layout = QHBoxLayout(header_frame)

        app_title = QLabel("🛡️ AAPA")
        app_title.setFont(QFont("Segoe UI", 13, QFont.Bold))
        header_layout.addWidget(app_title)

        self.status_pill = QLabel("● Manual Mode")
        self.status_pill.setStyleSheet("background-color: #744210; color: #fefcbf; padding: 3px 8px; border-radius: 4px; font-weight: bold; font-size: 11px;")
        header_layout.addWidget(self.status_pill)

        header_layout.addSpacing(20)

        self.project_label = QLabel("Project: None")
        self.project_label.setStyleSheet("color: #cbd5e0; font-weight: 500;")
        header_layout.addWidget(self.project_label)

        header_layout.addStretch()

        # Metrics Pills
        self.metrics_label = QLabel("Analyzed: 0 | Auto-Approved: 0 | Blocked: 0")
        self.metrics_label.setStyleSheet("color: #a0aec0; font-size: 11px;")
        header_layout.addWidget(self.metrics_label)

        self.manual_btn = QPushButton("+ Analyze Request")
        self.manual_btn.setObjectName("btn-success")
        self.manual_btn.clicked.connect(self._open_manual_dialog)
        header_layout.addWidget(self.manual_btn)

        main_layout.addWidget(header_frame)

        # 2. Tabs
        self.tabs = QTabWidget()

        # Tab 1: Live Inbox & Inspector
        self.inbox_tab = QWidget()
        self._init_inbox_tab()
        self.tabs.addTab(self.inbox_tab, "Live Inbox & Inspector")

        # Tab 2: Project Profile
        self.project_widget = ProjectProfileWidget()
        self.project_widget.project_selected.connect(self._load_project)
        self.project_widget.rescan_requested.connect(lambda: self._load_project(self.active_project_path))
        self.tabs.addTab(self.project_widget, "Project Context & Boundaries")

        # Tab 3: Safety Policy
        self.policy_widget = PolicyEditorWidget(self.policy)
        self.policy_widget.policy_changed.connect(self._on_policy_changed)
        self.tabs.addTab(self.policy_widget, "Safety Policy Editor")

        # Tab 4: History & Audit Log
        self.history_widget = HistoryViewWidget(self.audit_logger)
        self.tabs.addTab(self.history_widget, "Audit Log & History")

        # Tab 5: Settings & Integration
        self.settings_widget = SettingsViewWidget(self.settings, self.active_project_path)
        self.settings_widget.settings_updated.connect(self._on_settings_updated)
        self.tabs.addTab(self.settings_widget, "Settings & Integration")

        main_layout.addWidget(self.tabs)

        # Status Bar
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage(f"AAPA Daemon ready on 127.0.0.1:{self.settings.listen_port}")

    def _init_inbox_tab(self) -> None:
        tab_layout = QHBoxLayout(self.inbox_tab)
        tab_layout.setContentsMargins(4, 8, 4, 4)

        splitter = QSplitter(Qt.Horizontal)

        # Left: Inbox List
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        inbox_hdr = QHBoxLayout()
        inbox_lbl = QLabel("Permission Requests Inbox")
        inbox_lbl.setFont(QFont("Segoe UI", 11, QFont.Bold))
        inbox_hdr.addWidget(inbox_lbl)
        inbox_hdr.addStretch()

        self.clear_btn = QPushButton("Clear Completed")
        self.clear_btn.setObjectName("btn-secondary")
        self.clear_btn.setMaximumWidth(120)
        self.clear_btn.clicked.connect(self._clear_inbox)
        inbox_hdr.addWidget(self.clear_btn)
        left_layout.addLayout(inbox_hdr)

        self.inbox_list = QListWidget()
        self.inbox_list.itemClicked.connect(self._on_inbox_item_clicked)
        left_layout.addWidget(self.inbox_list)

        splitter.addWidget(left_widget)

        # Right: Inspector Widget
        self.inspector = RequestInspectorWidget()
        self.inspector.decision_made.connect(self._handle_user_decision)
        splitter.addWidget(self.inspector)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 5)

        tab_layout.addWidget(splitter)

    def _start_ipc_server(self) -> None:
        """Starts background local loopback IPC server."""
        try:
            self.ipc_server = AAPAIPCServer(
                (self.settings.listen_host, self.settings.listen_port),
                analyzer=self.analyzer,
                on_request_received=lambda req, res: self.signals.new_request.emit(req, res)
            )
            self.ipc_server.start_background()
        except Exception as exc:
            logger.warning("Could not start AAPA IPC server on %d: %s", self.settings.listen_port, exc)
            self.ipc_server = None

    def _load_project(self, folder_path: str) -> None:
        """Loads and scans project metadata."""
        if not folder_path:
            return
        p_path = Path(folder_path).resolve()
        if not p_path.exists():
            return

        self.active_project_path = str(p_path)
        self.settings.active_project_path = str(p_path)
        save_settings(self.settings)

        self.active_profile = self.context_engine.scan_project(p_path)
        if self.ipc_server:
            self.ipc_server.current_project_profile = self.active_profile

        self.project_label.setText(f"Project: {self.active_profile.project_name}")
        self.project_widget.set_profile(self.active_profile)
        self.settings_widget.project_path = str(p_path)
        self.settings_widget.refresh_integration_status()

        # Update integration status pill
        status = IntegrationManager.get_status(p_path, ipc_online=self.ipc_server is not None)
        if status.active_mode == "WORKSPACE_HOOK":
            self.status_pill.setText("● Hook Active (Workspace)")
            self.status_pill.setStyleSheet("background-color: #22543d; color: #c6f6d5; padding: 3px 8px; border-radius: 4px; font-weight: bold; font-size: 11px;")
        elif status.active_mode == "GLOBAL_HOOK":
            self.status_pill.setText("● Hook Active (Global)")
            self.status_pill.setStyleSheet("background-color: #2a4365; color: #bee3f8; padding: 3px 8px; border-radius: 4px; font-weight: bold; font-size: 11px;")
        else:
            self.status_pill.setText("○ Manual Review Mode")
            self.status_pill.setStyleSheet("background-color: #744210; color: #fefcbf; padding: 3px 8px; border-radius: 4px; font-weight: bold; font-size: 11px;")

    @Slot(object, object)
    def _on_request_received_threadsafe(self, request: NormalizedRequest, analysis: AnalysisResult) -> None:
        """Processes request event delivered to Qt main thread."""
        self.stat_analyzed += 1
        if analysis.decision == Decision.AUTO_APPROVE:
            self.stat_auto_approved += 1
        elif analysis.decision == Decision.BLOCK:
            self.stat_blocked += 1

        self._update_metrics()
        self.pending_inbox[request.request_id] = (request, analysis)

        # Add item to list
        prefix = "✓ [SAFE]" if analysis.risk_level == RiskLevel.LOW else ("⚠️ [REVIEW]" if analysis.risk_level == RiskLevel.MEDIUM else "🛑 [BLOCK]")
        display_text = f"{prefix} {analysis.sanitized_command[:45]}"
        item = QListWidgetItem(display_text)
        item.setData(Qt.UserRole, request.request_id)

        if analysis.risk_level == RiskLevel.LOW:
            item.setForeground(Qt.green)
        elif analysis.risk_level == RiskLevel.MEDIUM:
            item.setForeground(Qt.yellow)
        else:
            item.setForeground(Qt.red)

        self.inbox_list.insertItem(0, item)
        self.inbox_list.setCurrentItem(item)
        self.inspector.set_request(analysis)
        self.history_widget.refresh_logs()

    def _on_inbox_item_clicked(self, item: QListWidgetItem) -> None:
        req_id = item.data(Qt.UserRole)
        pair = self.pending_inbox.get(req_id)
        if pair:
            _, analysis = pair
            self.inspector.set_request(analysis)

    def _handle_user_decision(self, req_id: str, decision: str, reason: str) -> None:
        """Resolves a pending interactive prompt and forwards decision to Antigravity."""
        if self.ipc_server and req_id in self.ipc_server.pending_requests:
            slot = self.ipc_server.pending_requests[req_id]
            slot.user_decision = decision
            slot.user_reason = reason
            slot.event.set()

        pair = self.pending_inbox.get(req_id)
        if pair:
            req, analysis = pair
            analysis.user_action_taken = decision
            self.audit_logger.log_event(
                event_type="USER_INTERACTION",
                request_id=req_id,
                action=analysis.sanitized_command,
                cwd=analysis.cwd,
                risk_level=analysis.risk_level.value,
                decision=decision,
                recommendation=analysis.decision.value,
                explanation=reason,
                rule_name=analysis.relevant_rule,
                user_confirmed=(decision == "allow"),
                antigravity_response=decision
            )

        self.history_widget.refresh_logs()
        self.statusBar.showMessage(f"Decision '{decision}' recorded for request {req_id}", 5000)

    def _clear_inbox(self) -> None:
        self.inbox_list.clear()
        self.pending_inbox.clear()
        self.inspector._set_empty_state()

    def _open_manual_dialog(self) -> None:
        dlg = ManualRequestDialog(default_cwd=self.active_project_path, parent=self)
        dlg.request_submitted.connect(self._analyze_manual_input)
        dlg.exec()

    def _analyze_manual_input(self, raw_input: str, custom_cwd: str) -> None:
        normalized = RequestParser.parse(raw_input, default_cwd=custom_cwd or self.active_project_path)
        analysis = self.analyzer.analyze(normalized, self.active_profile)
        self._on_request_received_threadsafe(normalized, analysis)

    def _on_policy_changed(self, new_policy: PolicyConfig) -> None:
        self.policy = new_policy
        save_policy(self.policy)
        self.analyzer.update_policy(self.policy)

    def _on_settings_updated(self, new_settings: AppSettings) -> None:
        self.settings = new_settings
        save_settings(self.settings)

    def _update_metrics(self) -> None:
        self.metrics_label.setText(
            f"Analyzed: {self.stat_analyzed} | Auto-Approved: {self.stat_auto_approved} | Blocked: {self.stat_blocked}"
        )

    def closeEvent(self, event) -> None:
        """Shuts down IPC server when window closes."""
        if self.ipc_server:
            self.ipc_server.stop()
        super().closeEvent(event)
