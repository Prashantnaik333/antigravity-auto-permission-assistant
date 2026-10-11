"""Application entry helpers for AAPA desktop interface."""

from __future__ import annotations

import sys
from typing import Optional
from PySide6.QtWidgets import QApplication

from aapa.audit_logger import setup_application_logging
from aapa.ui.dashboard import AAPADashboard


def launch_gui(project_path: Optional[str] = None) -> int:
    """Launches the PySide6 AAPA desktop dashboard."""
    setup_application_logging()

    # Pass commandline arguments to QApplication
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)

    app.setApplicationName("Antigravity Auto Permission Assistant")
    app.setOrganizationName("Google Antigravity Community")

    window = AAPADashboard(project_path=project_path)
    window.show()

    return app.exec()
