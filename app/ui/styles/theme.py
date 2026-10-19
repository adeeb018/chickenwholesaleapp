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
    min-width: 250px;
    max-width: 250px;
}

#sidebarHeader {
    color: #ffffff;
    font-size: 15px;
    font-weight: bold;
    padding: 18px 16px;
    border-bottom: 1px solid #334155;
    letter-spacing: 0.5px;
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

/* Modern High-Visibility Action Buttons for Table Cells */
QPushButton.actionEdit, QPushButton[class="actionEdit"] {
    background-color: #dcfce7;
    color: #15803d;
    border: 1.5px solid #86efac;
    border-radius: 6px;
    padding: 2px 10px;
    font-size: 12px;
    font-weight: 700;
    min-height: 24px;
    max-height: 28px;
    margin: 0px;
}
QPushButton.actionEdit:hover, QPushButton[class="actionEdit"]:hover {
    background-color: #bbf7d0;
    border-color: #4ade80;
    color: #14532d;
}

QPushButton.actionDelete, QPushButton[class="actionDelete"] {
    background-color: #fee2e2;
    color: #b91c1c;
    border: 1.5px solid #fca5a5;
    border-radius: 6px;
    padding: 2px 10px;
    font-size: 12px;
    font-weight: 700;
    min-height: 24px;
    max-height: 28px;
    margin: 0px;
}
QPushButton.actionDelete:hover, QPushButton[class="actionDelete"]:hover {
    background-color: #fecaca;
    border-color: #f87171;
    color: #7f1d1d;
}

QPushButton.actionReturn, QPushButton[class="actionReturn"] {
    background-color: #fef3c7;
    color: #b45309;
    border: 1.5px solid #fcd34d;
    border-radius: 6px;
    padding: 2px 10px;
    font-size: 12px;
    font-weight: 700;
    min-height: 24px;
    max-height: 28px;
    margin: 0px;
}
QPushButton.actionReturn:hover, QPushButton[class="actionReturn"]:hover {
    background-color: #fde68a;
    border-color: #f59e0b;
    color: #78350f;
}

QPushButton.actionPrimary, QPushButton[class="actionPrimary"] {
    background-color: #dbeafe;
    color: #1d4ed8;
    border: 1.5px solid #93c5fd;
    border-radius: 6px;
    padding: 2px 10px;
    font-size: 12px;
    font-weight: 700;
    min-height: 24px;
    max-height: 28px;
    margin: 0px;
}
QPushButton.actionPrimary:hover, QPushButton[class="actionPrimary"]:hover {
    background-color: #bfdbfe;
    border-color: #60a5fa;
    color: #1e3a8a;
}

QPushButton.actionDark, QPushButton[class="actionDark"] {
    background-color: #f1f5f9;
    color: #1e293b;
    border: 1.5px solid #cbd5e1;
    border-radius: 6px;
    padding: 2px 10px;
    font-size: 12px;
    font-weight: 700;
    min-height: 24px;
    max-height: 28px;
    margin: 0px;
}
QPushButton.actionDark:hover, QPushButton[class="actionDark"]:hover {
    background-color: #e2e8f0;
    border-color: #94a3b8;
    color: #0f172a;
}

QPushButton.actionFinish, QPushButton[class="actionFinish"] {
    background-color: #f3e8ff;
    color: #7e22ce;
    border: 1.5px solid #d8b4fe;
    border-radius: 6px;
    padding: 2px 10px;
    font-size: 12px;
    font-weight: 700;
    min-height: 24px;
    max-height: 28px;
    margin: 0px;
}
QPushButton.actionFinish:hover, QPushButton[class="actionFinish"]:hover {
    background-color: #e9d5ff;
    border-color: #c084fc;
    color: #581c87;
}

/* Multi-Batch Allocation Source Dropdown */
QComboBox.batchSourceCombo, QComboBox[class="batchSourceCombo"] {
    font-size: 13px;
    font-weight: 600;
    color: #0f172a;
    background-color: #ffffff;
    border: 1.5px solid #cbd5e1;
    border-radius: 6px;
    padding: 4px 30px 4px 10px;
    min-height: 26px;
}
QComboBox.batchSourceCombo:hover, QComboBox[class="batchSourceCombo"]:hover {
    border-color: #2563eb;
    background-color: #f8fafc;
}
QComboBox.batchSourceCombo:focus, QComboBox[class="batchSourceCombo"]:focus {
    border: 2px solid #2563eb;
    background-color: #ffffff;
}
QComboBox.batchSourceCombo::drop-down, QComboBox[class="batchSourceCombo"]::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 26px;
    border-left: 1px solid #e2e8f0;
    border-top-right-radius: 5px;
    border-bottom-right-radius: 5px;
    background-color: #f1f5f9;
}
QComboBox.batchSourceCombo::drop-down:hover, QComboBox[class="batchSourceCombo"]::drop-down:hover {
    background-color: #e2e8f0;
}
QComboBox.batchSourceCombo::down-arrow, QComboBox[class="batchSourceCombo"]::down-arrow {
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #334155;
    width: 0;
    height: 0;
}
QComboBox.batchSourceCombo QAbstractItemView, QComboBox[class="batchSourceCombo"] QAbstractItemView {
    background-color: #ffffff;
    color: #0f172a;
    border: 1.5px solid #94a3b8;
    border-radius: 6px;
    selection-background-color: #2563eb;
    selection-color: #ffffff;
    padding: 4px;
    outline: none;
}
QComboBox.batchSourceCombo QAbstractItemView::item, QComboBox[class="batchSourceCombo"] QAbstractItemView::item {
    min-height: 30px;
    padding: 6px 12px;
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
    text-align: left;
    border: none;
    border-bottom: 2px solid #cbd5e1;
    border-right: 1px solid #e2e8f0;
    padding: 8px 12px;
}

QTableWidget::item {
    padding: 4px 8px;
    border-bottom: 1px solid #f1f5f9;
}

/* Scroll Area */
QScrollArea {
    border: none;
    background-color: transparent;
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
