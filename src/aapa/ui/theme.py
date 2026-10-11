"""UI Theme and CSS styling for AAPA PySide6 desktop interface."""

DARK_STYLESHEET = """
QMainWindow, QDialog {
    background-color: #12141a;
    color: #e2e8f0;
    font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
}

QWidget {
    color: #e2e8f0;
    font-size: 13px;
}

QTabWidget::pane {
    border: 1px solid #2d3748;
    background-color: #1a202c;
    border-radius: 6px;
}

QTabBar::tab {
    background: #171923;
    color: #a0aec0;
    padding: 8px 16px;
    margin-right: 2px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    font-weight: 500;
}

QTabBar::tab:selected {
    background: #1a202c;
    color: #63b3ed;
    border-bottom: 2px solid #3182ce;
}

QPushButton {
    background-color: #2b6cb0;
    color: #ffffff;
    border: none;
    padding: 7px 14px;
    border-radius: 4px;
    font-weight: 600;
}

QPushButton:hover {
    background-color: #3182ce;
}

QPushButton:pressed {
    background-color: #2c5282;
}

QPushButton:disabled {
    background-color: #4a5568;
    color: #a0aec0;
}

QPushButton#btn-danger {
    background-color: #e53e3e;
}
QPushButton#btn-danger:hover {
    background-color: #f56565;
}

QPushButton#btn-success {
    background-color: #38a169;
}
QPushButton#btn-success:hover {
    background-color: #48bb78;
}

QPushButton#btn-secondary {
    background-color: #4a5568;
}
QPushButton#btn-secondary:hover {
    background-color: #718096;
}

QLineEdit, QTextEdit, QPlainTextEdit {
    background-color: #0d1117;
    border: 1px solid #2d3748;
    border-radius: 4px;
    padding: 6px 10px;
    color: #f7fafc;
    font-family: 'Consolas', 'Courier New', monospace;
}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {
    border: 1px solid #63b3ed;
}

QListWidget, QTableWidget {
    background-color: #1a202c;
    border: 1px solid #2d3748;
    border-radius: 6px;
    padding: 4px;
    alternate-background-color: #171923;
}

QListWidget::item {
    padding: 8px;
    border-radius: 4px;
    margin-bottom: 3px;
}

QListWidget::item:selected {
    background-color: #2b6cb0;
    color: white;
}

QHeaderView::section {
    background-color: #171923;
    color: #cbd5e0;
    padding: 6px;
    border: 1px solid #2d3748;
    font-weight: bold;
}

QGroupBox {
    border: 1px solid #2d3748;
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 14px;
    font-weight: 600;
    color: #cbd5e0;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
}

QCheckBox {
    spacing: 8px;
    font-size: 13px;
}

QScrollBar:vertical {
    border: none;
    background: #171923;
    width: 10px;
    border-radius: 5px;
}

QScrollBar::handle:vertical {
    background: #4a5568;
    border-radius: 5px;
}
"""
