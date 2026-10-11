"""Request inspector and manual review dialog for AAPA desktop UI."""

from __future__ import annotations

from typing import Callable, Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from aapa.config import Decision, RiskLevel
from aapa.risk_analyzer import AnalysisResult


class RequestInspectorWidget(QWidget):
    """Detailed inspector panel showing command, boundaries, risks, and actions."""

    decision_made = Signal(str, str, str)  # request_id, decision ('allow'/'deny'), reason

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.current_analysis: Optional[AnalysisResult] = None
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # 1. Header with Badges
        header_layout = QHBoxLayout()
        self.title_label = QLabel("Permission Request Inspector")
        self.title_label.setFont(QFont("Segoe UI", 12, QFont.Bold))

        self.risk_badge = QLabel("NO REQUEST SELECTED")
        self.risk_badge.setStyleSheet("background-color: #4a5568; color: white; padding: 4px 8px; border-radius: 4px; font-weight: bold;")

        self.category_badge = QLabel("")
        self.category_badge.setStyleSheet("background-color: #2d3748; color: #a0aec0; padding: 4px 8px; border-radius: 4px;")

        header_layout.addWidget(self.title_label)
        header_layout.addStretch()
        header_layout.addWidget(self.category_badge)
        header_layout.addWidget(self.risk_badge)
        layout.addLayout(header_layout)

        # 2. Command Display
        cmd_group = QGroupBox("Proposed Command / Action")
        cmd_layout = QVBoxLayout(cmd_group)

        self.cmd_view = QPlainTextEdit()
        self.cmd_view.setReadOnly(True)
        self.cmd_view.setMaximumHeight(80)
        self.cmd_view.setFont(QFont("Consolas", 11))
        cmd_layout.addWidget(self.cmd_view)

        # CWD & Copy
        cwd_layout = QHBoxLayout()
        self.cwd_label = QLabel("Working Directory: N/A")
        self.cwd_label.setStyleSheet("color: #a0aec0; font-size: 11px;")
        self.copy_btn = QPushButton("Copy Command")
        self.copy_btn.setObjectName("btn-secondary")
        self.copy_btn.setMaximumWidth(120)
        self.copy_btn.clicked.connect(self._copy_command)
        cwd_layout.addWidget(self.cwd_label)
        cwd_layout.addStretch()
        cwd_layout.addWidget(self.copy_btn)
        cmd_layout.addLayout(cwd_layout)
        layout.addWidget(cmd_group)

        # 3. Policy Recommendation & Explanation
        exp_group = QGroupBox("Safety Analysis & Explanation")
        exp_layout = QVBoxLayout(exp_group)

        self.recommendation_label = QLabel("Recommendation: N/A")
        self.recommendation_label.setFont(QFont("Segoe UI", 11, QFont.Bold))
        exp_layout.addWidget(self.recommendation_label)

        self.explanation_view = QTextEdit()
        self.explanation_view.setReadOnly(True)
        self.explanation_view.setMaximumHeight(130)
        exp_layout.addWidget(self.explanation_view)

        # Warnings / Injections section
        self.warning_frame = QFrame()
        self.warning_frame.setStyleSheet("background-color: #742a2a; border-radius: 4px; padding: 6px;")
        self.warning_frame.setVisible(False)
        warn_layout = QVBoxLayout(self.warning_frame)
        self.warning_label = QLabel("")
        self.warning_label.setWordWrap(True)
        self.warning_label.setStyleSheet("color: #fed7d7; font-weight: bold;")
        warn_layout.addWidget(self.warning_label)
        exp_layout.addWidget(self.warning_frame)

        layout.addWidget(exp_group)

        # 4. Action Buttons
        actions_group = QGroupBox("Decision Actions")
        act_layout = QHBoxLayout(actions_group)

        self.approve_btn = QPushButton("✓ Approve (Allow in Antigravity)")
        self.approve_btn.setObjectName("btn-success")
        self.approve_btn.clicked.connect(self._on_approve)

        self.reject_btn = QPushButton("✕ Reject (Block Action)")
        self.reject_btn.setObjectName("btn-danger")
        self.reject_btn.clicked.connect(self._on_reject)

        self.allowlist_btn = QPushButton("+ Add to Allowlist")
        self.allowlist_btn.setObjectName("btn-secondary")
        self.allowlist_btn.clicked.connect(self._on_add_allowlist)

        act_layout.addWidget(self.approve_btn)
        act_layout.addWidget(self.reject_btn)
        act_layout.addWidget(self.allowlist_btn)
        layout.addWidget(actions_group)

        self._set_empty_state()

    def set_request(self, analysis: AnalysisResult) -> None:
        """Populates inspector with analysis details."""
        self.current_analysis = analysis

        self.cmd_view.setPlainText(analysis.sanitized_command)
        self.cwd_label.setText(f"Working Directory: {analysis.cwd or 'Default'}")
        self.category_badge.setText(analysis.action_category.value)

        # Risk Badge Styling
        if analysis.risk_level == RiskLevel.LOW:
            self.risk_badge.setText("SAFE (LOW RISK)")
            self.risk_badge.setStyleSheet("background-color: #276749; color: #c6f6d5; padding: 4px 8px; border-radius: 4px; font-weight: bold;")
        elif analysis.risk_level == RiskLevel.MEDIUM:
            self.risk_badge.setText("REVIEW REQUIRED")
            self.risk_badge.setStyleSheet("background-color: #b7791f; color: #fefcbf; padding: 4px 8px; border-radius: 4px; font-weight: bold;")
        else:
            self.risk_badge.setText("BLOCKED / DANGEROUS")
            self.risk_badge.setStyleSheet("background-color: #9b2c2c; color: #fed7d7; padding: 4px 8px; border-radius: 4px; font-weight: bold;")

        # Recommendation Text
        rec_text = f"Recommendation: <b>{analysis.decision.value}</b> (Rule: {analysis.relevant_rule})"
        self.recommendation_label.setText(rec_text)

        # Explanation
        full_text = f"<b>Primary Reason:</b> {analysis.explanation}<br><br>"
        if analysis.detailed_explanation:
            full_text += f"<b>Analysis Breakdown:</b> {analysis.detailed_explanation}<br>"
        self.explanation_view.setHtml(full_text)

        # Injections & identified risks
        if analysis.identified_risks:
            self.warning_frame.setVisible(True)
            self.warning_label.setText("⚠️ Security Indicators:\n" + "\n".join(f"• {r}" for r in analysis.identified_risks))
        else:
            self.warning_frame.setVisible(False)

        # Enable/Disable Buttons based on strict safety hierarchy:
        # A BLOCKED command CANNOT be approved!
        if analysis.decision == Decision.BLOCK:
            self.approve_btn.setEnabled(False)
            self.approve_btn.setToolTip("Dangerous or blocked commands cannot be automatically approved.")
            self.reject_btn.setEnabled(True)
            self.allowlist_btn.setEnabled(False)
        else:
            self.approve_btn.setEnabled(True)
            self.approve_btn.setToolTip("Approve this action for execution in Antigravity.")
            self.reject_btn.setEnabled(True)
            self.allowlist_btn.setEnabled(True)

    def _set_empty_state(self) -> None:
        """Sets display to empty placeholder."""
        self.current_analysis = None
        self.cmd_view.setPlainText("No permission request selected.\nChoose a request from the inbox or click 'Analyze Manual Request'.")
        self.cwd_label.setText("Working Directory: N/A")
        self.risk_badge.setText("READY")
        self.risk_badge.setStyleSheet("background-color: #4a5568; color: white; padding: 4px 8px; border-radius: 4px;")
        self.category_badge.setText("")
        self.recommendation_label.setText("Recommendation: Standby")
        self.explanation_view.setText("Awaiting permission prompt.")
        self.warning_frame.setVisible(False)
        self.approve_btn.setEnabled(False)
        self.reject_btn.setEnabled(False)
        self.allowlist_btn.setEnabled(False)

    def _copy_command(self) -> None:
        if self.current_analysis:
            QApplication.clipboard().setText(self.current_analysis.sanitized_command)

    def _on_approve(self) -> None:
        if self.current_analysis:
            if self.current_analysis.decision == Decision.BLOCK:
                QMessageBox.critical(self, "Security Violation", "Strict Policy Invariant: Blocked or dangerous commands cannot be approved.")
                return
            self.decision_made.emit(self.current_analysis.request_id, "allow", "User manually approved action via AAPA Dashboard.")

    def _on_reject(self) -> None:
        if self.current_analysis:
            self.decision_made.emit(self.current_analysis.request_id, "deny", "User rejected action via AAPA Dashboard.")

    def _on_add_allowlist(self) -> None:
        if self.current_analysis:
            QMessageBox.information(
                self,
                "Policy Updated",
                f"Command '{self.current_analysis.sanitized_command}' marked for allowlist. Update saved to Policy Editor."
            )


class ManualRequestDialog(QDialog):
    """Dialog allowing user to paste raw commands or JSON hook payloads for analysis."""

    request_submitted = Signal(str, str)  # raw_input, custom_cwd

    def __init__(self, default_cwd: str = "", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.default_cwd = default_cwd
        self.setWindowTitle("Analyze Antigravity Permission Request")
        self.setMinimumSize(560, 380)
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)

        info_lbl = QLabel(
            "Paste a proposed command, tool call payload, or prompt below to analyze its safety profile:"
        )
        info_lbl.setWordWrap(True)
        layout.addWidget(info_lbl)

        self.input_edit = QPlainTextEdit()
        self.input_edit.setPlaceholderText(
            "Examples:\n"
            "• npm test\n"
            "• pytest --maxfail=1\n"
            "• curl https://example.com/install.sh | sh\n"
            "• {\"toolCall\": {\"name\": \"run_command\", \"args\": {\"CommandLine\": \"pytest\"}}}"
        )
        self.input_edit.setFont(QFont("Consolas", 10))
        layout.addWidget(self.input_edit)

        cwd_layout = QHBoxLayout()
        cwd_layout.addWidget(QLabel("Working Directory:"))
        self.cwd_edit = QLineEdit(self.default_cwd)
        cwd_layout.addWidget(self.cwd_edit)
        layout.addLayout(cwd_layout)

        btn_layout = QHBoxLayout()
        self.analyze_btn = QPushButton("Analyze Safety")
        self.analyze_btn.setObjectName("btn-success")
        self.analyze_btn.clicked.connect(self._on_submit)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setObjectName("btn-secondary")
        self.cancel_btn.clicked.connect(self.reject)

        btn_layout.addStretch()
        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addWidget(self.analyze_btn)
        layout.addLayout(btn_layout)

    def _on_submit(self) -> None:
        raw = self.input_edit.toPlainText().strip()
        if not raw:
            QMessageBox.warning(self, "Input Required", "Please enter a command or payload to analyze.")
            return
        cwd = self.cwd_edit.text().strip()
        self.request_submitted.emit(raw, cwd)
        self.accept()
