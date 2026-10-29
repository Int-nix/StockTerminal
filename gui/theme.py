STYLESHEET = """
QMainWindow, QWidget {
    background-color: #0B1220;
    color: #F8FAFC;
    font-family: Segoe UI, Arial;
    font-size: 13px;
}

QFrame#Sidebar {
    background-color: #111827;
    border-right: 1px solid #293548;
}

QFrame#Card {
    background-color: #172235;
    border: 1px solid #293548;
    border-radius: 10px;
}

QLabel#Title {
    font-size: 25px;
    font-weight: bold;
}

QLabel#SectionTitle {
    font-size: 18px;
    font-weight: bold;
}

QLabel#Muted {
    color: #94A3B8;
}

QPushButton {
    background-color: #1E293B;
    color: white;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 10px;
}

QPushButton:hover {
    background-color: #334155;
}

QPushButton#Navigation {
    text-align: left;
    padding: 13px;
    border: none;
    background-color: transparent;
}

QPushButton#Navigation:hover {
    background-color: #1E293B;
}

QPushButton#Primary {
    background-color: #2563EB;
    border: none;
    font-weight: bold;
}

QPushButton#Primary:hover {
    background-color: #1D4ED8;
}

QLineEdit, QComboBox {
    background-color: #172235;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 10px;
    color: white;
}

QTableWidget {
    background-color: #172235;
    alternate-background-color: #1E293B;
    color: white;
    border: 1px solid #293548;
    gridline-color: #293548;
    selection-background-color: #2563EB;
}

QHeaderView::section {
    background-color: #1E293B;
    color: #CBD5E1;
    padding: 10px;
    border: none;
}
"""

# Additional shared styling for financial statement tabs and tooltips.
STYLESHEET += """
QToolTip {
    background-color: #1E293B;
    color: #F8FAFC;
    border: 1px solid #3B82F6;
    padding: 7px;
}

QTabWidget::pane {
    border: 1px solid #293548;
}

QTabBar::tab {
    background: #172235;
    padding: 10px 18px;
    color: #CBD5E1;
    border: 1px solid #293548;
}

QTabBar::tab:selected {
    background: #2563EB;
    color: white;
}
"""