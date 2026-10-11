"""Project profile and boundary management tab for AAPA desktop UI."""

from __future__ import annotations

from typing import Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from aapa.project_context import ProjectProfile


class ProjectProfileWidget(QWidget):
    """Visualizes project characteristics, frameworks, tests, and boundaries."""

    project_selected = Signal(str)
    rescan_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.current_profile: Optional[ProjectProfile] = None
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        # 1. Project Selection Bar
        selector_layout = QHBoxLayout()
        selector_layout.addWidget(QLabel("Active Project Path:"))
        self.path_edit = QLineEdit()
        self.path_edit.setReadOnly(True)
        self.browse_btn = QPushButton("Browse Folder...")
        self.browse_btn.clicked.connect(self._on_browse)
        self.rescan_btn = QPushButton("Rescan Context")
        self.rescan_btn.setObjectName("btn-secondary")
        self.rescan_btn.clicked.connect(lambda: self.rescan_requested.emit())

        selector_layout.addWidget(self.path_edit)
        selector_layout.addWidget(self.browse_btn)
        selector_layout.addWidget(self.rescan_btn)
        layout.addLayout(selector_layout)

        # 2. Splitter for Profile Details & Discovered Files
        splitter = QSplitter(Qt.Horizontal)

        # Left: Metadata card
        meta_group = QGroupBox("Project Metadata & Tools")
        meta_layout = QVBoxLayout(meta_group)

        self.name_label = QLabel("Project Name: None")
        self.name_label.setFont(QFont("Segoe UI", 11, QFont.Bold))
        meta_layout.addWidget(self.name_label)

        self.purpose_label = QLabel("Purpose: None")
        self.purpose_label.setWordWrap(True)
        meta_layout.addWidget(self.purpose_label)

        self.lang_label = QLabel("Detected Languages: None")
        meta_layout.addWidget(self.lang_label)

        self.tools_label = QLabel("Package Managers: None")
        meta_layout.addWidget(self.tools_label)

        self.tests_label = QLabel("Approved Test Runners: None")
        self.tests_label.setStyleSheet("color: #68d391; font-weight: bold;")
        meta_layout.addWidget(self.tests_label)

        self.summary_box = QPlainTextEdit()
        self.summary_box.setReadOnly(True)
        self.summary_box.setFont(QFont("Consolas", 10))
        meta_layout.addWidget(self.summary_box)

        splitter.addWidget(meta_group)

        # Right: Discovered Files & Warnings
        files_group = QGroupBox("Context Files & Security Boundaries")
        files_layout = QVBoxLayout(files_group)

        files_layout.addWidget(QLabel("Permitted Files Read:"))
        self.files_list = QListWidget()
        files_layout.addWidget(self.files_list)

        files_layout.addWidget(QLabel("Excluded Sensitive Files / Security Warnings:"))
        self.warnings_list = QListWidget()
        self.warnings_list.setStyleSheet("color: #fc8181;")
        files_layout.addWidget(self.warnings_list)

        splitter.addWidget(files_group)
        layout.addWidget(splitter)

    def set_profile(self, profile: ProjectProfile) -> None:
        """Updates UI with scanned profile data."""
        self.current_profile = profile
        self.path_edit.setText(profile.project_path)
        self.name_label.setText(f"Project Name: {profile.project_name}")
        self.purpose_label.setText(f"Purpose: {profile.purpose}")
        self.lang_label.setText(f"Detected Languages: {', '.join(profile.languages) or 'None'}")
        self.tools_label.setText(f"Package Managers: {', '.join(profile.package_managers) or 'None'}")
        self.tests_label.setText(f"Approved Test Runners: {', '.join(profile.test_commands) or 'None'}")
        self.summary_box.setPlainText(profile.to_markdown_summary())

        self.files_list.clear()
        for f in profile.read_files:
            self.files_list.addItem(f"✓ {f}")

        self.warnings_list.clear()
        for ignored in profile.ignored_files:
            self.warnings_list.addItem(f"🔒 Excluded: {ignored}")
        for warn in profile.security_warnings:
            self.warnings_list.addItem(f"⚠️ {warn}")
        for inj in profile.detected_injections:
            self.warnings_list.addItem(f"🚨 INJECTION: {inj}")

    def _on_browse(self) -> None:
        """Opens folder dialog."""
        folder = QFileDialog.getExistingDirectory(self, "Select Project Folder")
        if folder:
            self.project_selected.emit(folder)
