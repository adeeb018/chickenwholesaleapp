"""
Modern Professional PySide6 QSS Theme Tokens and Styling.
Provides 100% consistent high-contrast rendering across macOS/Windows Light and Dark OS modes.
"""

MAIN_QSS = """
/* Base Window & Global Reset */
QMainWindow, QDialog, QMessageBox {
    background-color: #f4f6f9;
    color: #0f172a;
}

QWidget {
    font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
    font-size: 13px;
    color: #0f172a;
}

/* Sidebar Styling */
#sidebarWidget {
    background-color: #1e293b;
    min-width: 220px;
    max-width: 220px;
}

#sidebarHeader {
    color: #ffffff;
    font-size: 16px;
    font-weight: bold;
    padding: 18px 15px;
    border-bottom: 1px solid #334155;
}

#sidebarCategory {
    color: #94a3b8;
    font-size: 11px;
    font-weight: bold;
    text-transform: uppercase;
    padding: 12px 15px 4px 15px;
}

QPushButton.sidebarBtn {
    background-color: transparent;
    color: #cbd5e1;
    border: none;
    text-align: left;
    padding: 10px 18px;
    font-size: 13px;
    border-radius: 6px;
    margin: 2px 8px;
}

QPushButton.sidebarBtn:hover {
    background-color: #334155;
    color: #ffffff;
}

QPushButton.sidebarBtn:checked {
    background-color: #2563eb;
    color: #ffffff;
    font-weight: bold;
}

/* Top Header Bar */
#topHeaderBar {
    background-color: #ffffff;
    border-bottom: 1px solid #e2e8f0;
    padding: 10px 20px;
}

#headerTitle {
    font-size: 18px;
    font-weight: bold;
    color: #0f172a;
}

/* Cards & Containers */
QFrame.cardFrame {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 15px;
}

/* Form Controls */
QLineEdit, QDoubleSpinBox, QDateEdit, QComboBox, QTextEdit, QSpinBox {
    background-color: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 13px;
    color: #0f172a;
    selection-background-color: #2563eb;
    selection-color: #ffffff;
}

QLineEdit:focus, QDoubleSpinBox:focus, QDateEdit:focus, QComboBox:focus, QTextEdit:focus, QSpinBox:focus {
    border: 2px solid #2563eb;
}

QLineEdit[readOnly="true"], QDoubleSpinBox[readOnly="true"] {
    background-color: #f1f5f9;
    color: #475569;
}

QLabel {
    color: #334155;
}

QLabel.formLabel {
    font-weight: 600;
    color: #1e293b;
}

/* ComboBox Dropdown List */
QComboBox {
    padding-right: 20px;
}

QComboBox QAbstractItemView {
    background-color: #ffffff;
    color: #0f172a;
    border: 1px solid #cbd5e1;
    selection-background-color: #2563eb;
    selection-color: #ffffff;
    padding: 4px;
    outline: none;
}

/* Buttons */
QPushButton.primaryBtn {
    background-color: #2563eb;
    color: #ffffff;
    font-weight: bold;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
}

QPushButton.primaryBtn:hover {
    background-color: #1d4ed8;
}

QPushButton.secondaryBtn {
    background-color: #e2e8f0;
    color: #1e293b;
    font-weight: 600;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
}

QPushButton.secondaryBtn:hover {
    background-color: #cbd5e1;
}

QPushButton.dangerBtn {
    background-color: #ef4444;
    color: #ffffff;
    font-weight: bold;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
}

QPushButton.dangerBtn:hover {
    background-color: #dc2626;
}

/* Table Widget */
QTableWidget, QTableView {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    gridline-color: #f1f5f9;
    font-size: 13px;
    color: #0f172a;
    selection-background-color: #2563eb;
    selection-color: #ffffff;
}

QTableWidget::item:selected, QTableView::item:selected {
    background-color: #2563eb;
    color: #ffffff;
    font-weight: 500;
}

QTableWidget::item:hover, QTableView::item:hover {
    background-color: #f8fafc;
}

QHeaderView::section {
    background-color: #f8fafc;
    color: #334155;
    font-weight: bold;
    border: none;
    border-bottom: 2px solid #cbd5e1;
    border-right: 1px solid #e2e8f0;
    padding: 8px 10px;
}

QTableWidget::item {
    padding: 6px 10px;
    border-bottom: 1px solid #f1f5f9;
}

/* Calendar Widget (Date Picker Popup) */
QCalendarWidget QWidget {
    background-color: #ffffff;
    color: #0f172a;
}

QCalendarWidget QWidget#qt_calendar_navigationbar {
    background-color: #1e293b;
    color: #ffffff;
}

QCalendarWidget QToolButton {
    color: #ffffff;
    background-color: transparent;
    border: none;
    border-radius: 4px;
    font-weight: bold;
    padding: 4px;
}

QCalendarWidget QToolButton:hover {
    background-color: #334155;
}

QCalendarWidget QSpinBox {
    background-color: #334155;
    color: #ffffff;
    border-radius: 4px;
}

QCalendarWidget QTableView {
    background-color: #ffffff;
    color: #0f172a;
    selection-background-color: #2563eb;
    selection-color: #ffffff;
    alternate-background-color: #f8fafc;
}

QCalendarWidget QMenu {
    background-color: #1e293b;
    color: #ffffff;
}

/* Tab Bar Styling */
QTabWidget::pane {
    border: 1px solid #e2e8f0;
    background-color: #ffffff;
    border-radius: 6px;
}

QTabBar::tab {
    background-color: #f1f5f9;
    color: #475569;
    border: 1px solid #cbd5e1;
    padding: 8px 16px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 2px;
}

QTabBar::tab:selected {
    background-color: #ffffff;
    color: #2563eb;
    font-weight: bold;
    border-bottom: 2px solid #2563eb;
}

QTabBar::tab:hover:!selected {
    background-color: #e2e8f0;
    color: #1e293b;
}

/* Scrollbars */
QScrollBar:vertical {
    border: none;
    background: #f1f5f9;
    width: 8px;
    border-radius: 4px;
}

QScrollBar::handle:vertical {
    background: #cbd5e1;
    min-height: 20px;
    border-radius: 4px;
}

QScrollBar::handle:vertical:hover {
    background: #94a3b8;
}

QScrollBar:horizontal {
    border: none;
    background: #f1f5f9;
    height: 8px;
    border-radius: 4px;
}

QScrollBar::handle:horizontal {
    background: #cbd5e1;
    min-width: 20px;
    border-radius: 4px;
}

QScrollBar::handle:horizontal:hover {
    background: #94a3b8;
}
"""
