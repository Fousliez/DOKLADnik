APP_STYLESHEET = """
QMainWindow, QWidget {
    font-size: 13px;
}

QLineEdit, QComboBox, QDateEdit, QSpinBox, QDoubleSpinBox, QTextEdit {
    padding: 5px;
}

QPushButton {
    padding: 6px 10px;
}

QTableView, QTableWidget {
    gridline-color: #d7d7d7;
    alternate-background-color: #f6f6f6;
}

QHeaderView::section {
    padding: 6px;
    font-weight: 600;
}

QGroupBox {
    font-weight: 600;
    margin-top: 8px;
    padding-top: 8px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 8px;
    padding: 0 4px;
}

QTabBar::tab {
    padding: 8px 14px;
}
"""
