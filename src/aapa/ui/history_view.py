"""Audit log and permission history view for AAPA desktop UI."""

from __future__ import annotations

import csv
from typing import Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from aapa.audit_logger import AuditLogger


class HistoryViewWidget(QWidget):
    """Searchable audit log viewer with export support."""

    def __init__(self, audit_logger: AuditLogger, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.audit_logger = audit_logger
        self._init_ui()
        self.refresh_logs()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        # 1. Filter bar
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Search Logs:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Filter by command, rule, or decision...")
        self.search_edit.textChanged.connect(self._apply_filter)
        filter_layout.addWidget(self.search_edit)

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setObjectName("btn-secondary")
        self.refresh_btn.clicked.connect(self.refresh_logs)
        filter_layout.addWidget(self.refresh_btn)

        self.export_btn = QPushButton("Export CSV...")
        self.export_btn.clicked.connect(self._export_csv)
        filter_layout.addWidget(self.export_btn)

        layout.addLayout(filter_layout)

        # 2. Table Widget
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Timestamp (UTC)", "Action / Command", "CWD", "Risk", "Decision", "Safety Rule"
        ])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.table)

    def refresh_logs(self) -> None:
        """Reloads records from audit log file."""
        entries = self.audit_logger.get_recent_entries(limit=250)
        self.entries = entries
        self._populate_table(entries)

    def _populate_table(self, records: list[dict]) -> None:
        self.table.setRowCount(len(records))
        for row, item in enumerate(records):
            ts = item.get("timestamp", "")[:19].replace("T", " ")
            action = item.get("action", "")
            cwd = item.get("cwd", "")
            risk = item.get("risk_level", "")
            decision = item.get("decision", "")
            rule = item.get("rule_name", "")

            self.table.setItem(row, 0, QTableWidgetItem(ts))
            self.table.setItem(row, 1, QTableWidgetItem(action))
            self.table.setItem(row, 2, QTableWidgetItem(cwd))
            
            risk_item = QTableWidgetItem(risk)
            if risk == "LOW":
                risk_item.setForeground(Qt.green)
            elif risk == "MEDIUM":
                risk_item.setForeground(Qt.yellow)
            else:
                risk_item.setForeground(Qt.red)
            self.table.setItem(row, 3, risk_item)

            dec_item = QTableWidgetItem(decision)
            self.table.setItem(row, 4, dec_item)
            self.table.setItem(row, 5, QTableWidgetItem(rule))

    def _apply_filter(self, query: str) -> None:
        q = query.strip().lower()
        if not q:
            self._populate_table(getattr(self, "entries", []))
            return
        filtered = [
            e for e in getattr(self, "entries", [])
            if q in e.get("action", "").lower()
            or q in e.get("rule_name", "").lower()
            or q in e.get("decision", "").lower()
        ]
        self._populate_table(filtered)

    def _export_csv(self) -> None:
        file_path, _ = QFileDialog.getSaveFileName(self, "Export Audit Log", "aapa_audit_log.csv", "CSV Files (*.csv)")
        if not file_path:
            return
        try:
            records = getattr(self, "entries", [])
            with open(file_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Timestamp", "Action", "CWD", "Risk", "Decision", "Rule", "Explanation"])
                for r in records:
                    writer.writerow([
                        r.get("timestamp", ""),
                        r.get("action", ""),
                        r.get("cwd", ""),
                        r.get("risk_level", ""),
                        r.get("decision", ""),
                        r.get("rule_name", ""),
                        r.get("explanation", ""),
                    ])
            QMessageBox.information(self, "Export Complete", f"Exported {len(records)} audit records to {file_path}")
        except Exception as exc:
            QMessageBox.critical(self, "Export Error", f"Failed to export CSV: {exc}")
