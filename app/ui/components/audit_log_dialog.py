import csv
import subprocess
import sys
from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QTabWidget, QPlainTextEdit,
    QFileDialog, QMessageBox, QFrame, QWidget
)
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QColor, QFont, QTextCursor
from app.database.audit_logger import AuditLogger
from app.ui.components.table_utils import enable_table_copy_and_tooltips, create_table_item

class AuditLogDialog(QDialog):
    """
    Password-protected Database Audit Log Viewer.
    Allows administrators to view, search, filter, and export all database operations.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Database Audit Logs & Activity Trail")
        self.resize(1050, 680)
        self.setMinimumSize(850, 500)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(18, 18, 18, 18)
        main_layout.setSpacing(12)

        # Header Banner
        header_frame = QFrame()
        header_frame.setStyleSheet("""
            QFrame {
                background-color: #f8fafc;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        h_layout = QHBoxLayout(header_frame)
        h_layout.setContentsMargins(8, 6, 8, 6)

        title_box = QVBoxLayout()
        title = QLabel("📋 Database Operations Audit Trail")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #0f172a;")
        sub = QLabel("Persistent audit trail tracking all INSERT, UPDATE, SOFT_DELETE, and DELETE operations.")
        sub.setStyleSheet("font-size: 11px; color: #64748b;")
        title_box.addWidget(title)
        title_box.addWidget(sub)
        h_layout.addLayout(title_box)
        h_layout.addStretch()

        self.file_size_lbl = QLabel("")
        self.file_size_lbl.setStyleSheet("font-size: 11px; color: #475569; font-weight: 500;")
        h_layout.addWidget(self.file_size_lbl)

        main_layout.addWidget(header_frame)

        # Controls & Filter Bar
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(10)

        # Search field
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("🔍 Search by keyword, table, ID, details...")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self._apply_filter)
        filter_layout.addWidget(self.search_edit, 2)

        # Action Filter
        self.action_combo = QComboBox()
        self.action_combo.addItems(["All Actions", "INSERT", "UPDATE", "SOFT_DELETE", "DELETE", "SYSTEM"])
        self.action_combo.currentIndexChanged.connect(self._apply_filter)
        filter_layout.addWidget(self.action_combo, 1)

        # Table Filter
        self.table_combo = QComboBox()
        self.table_combo.addItem("All Tables")
        self.table_combo.currentIndexChanged.connect(self._apply_filter)
        filter_layout.addWidget(self.table_combo, 1)

        # Refresh Button
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.setProperty("class", "secondaryBtn")
        refresh_btn.clicked.connect(self.reload_logs)
        filter_layout.addWidget(refresh_btn)

        # Export Button
        export_btn = QPushButton("💾 Export...")
        export_btn.setProperty("class", "secondaryBtn")
        export_btn.clicked.connect(self._export_logs)
        filter_layout.addWidget(export_btn)

        # Open External File Button
        open_file_btn = QPushButton("📂 Open File")
        open_file_btn.setProperty("class", "secondaryBtn")
        open_file_btn.clicked.connect(self._open_raw_file)
        filter_layout.addWidget(open_file_btn)

        main_layout.addLayout(filter_layout)

        # Tabs for Structured View vs Raw Log View
        self.tabs = QTabWidget()

        # Tab 1: Table View
        table_container = QWidget()
        tc_layout = QVBoxLayout(table_container)
        tc_layout.setContentsMargins(0, 0, 0, 0)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels([
            "Timestamp", "Action", "Table / Entity", "Record ID", "Operation Details"
        ])
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        header = self.table.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.Stretch)
        self.table.verticalHeader().setDefaultSectionSize(40)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        enable_table_copy_and_tooltips(self.table)
        tc_layout.addWidget(self.table)

        self.tabs.addTab(table_container, "📊 Structured Log Table")

        # Tab 2: Raw Log Console
        self.raw_text = QPlainTextEdit()
        self.raw_text.setReadOnly(True)
        self.raw_text.setFont(QFont("Monospace", 9))
        self.raw_text.setStyleSheet("""
            QPlainTextEdit {
                background-color: #0f172a;
                color: #f1f5f9;
                font-family: Menlo, Consolas, Monaco, "Courier New", monospace;
                padding: 10px;
                border-radius: 6px;
            }
        """)
        self.tabs.addTab(self.raw_text, "📝 Raw Log File")

        main_layout.addWidget(self.tabs, 1)

        # Bottom Status Bar
        bottom_layout = QHBoxLayout()
        self.status_lbl = QLabel("")
        self.status_lbl.setStyleSheet("font-size: 11px; color: #64748b;")
        bottom_layout.addWidget(self.status_lbl)
        bottom_layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.setProperty("class", "secondaryBtn")
        close_btn.clicked.connect(self.accept)
        bottom_layout.addWidget(close_btn)

        main_layout.addLayout(bottom_layout)

        self._all_records = []
        self._load_table_names()
        self.reload_logs()

    def _load_table_names(self):
        curr = self.table_combo.currentText()
        self.table_combo.blockSignals(True)
        self.table_combo.clear()
        self.table_combo.addItem("All Tables")
        distinct = AuditLogger.get_distinct_tables()
        for t in distinct:
            self.table_combo.addItem(t)
        idx = self.table_combo.findText(curr)
        if idx >= 0:
            self.table_combo.setCurrentIndex(idx)
        self.table_combo.blockSignals(False)

    def reload_logs(self):
        self._load_table_names()
        self._all_records = AuditLogger.read_logs(max_lines=5000)
        self._update_file_size()
        self._apply_filter()

        # Update raw tab
        log_path = AuditLogger.get_log_file_path()
        if log_path.exists():
            try:
                with AuditLogger._lock:
                    with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                        content = f.read()
                self.raw_text.setPlainText(content)
                self.raw_text.moveCursor(QTextCursor.End)
            except Exception as e:
                self.raw_text.setPlainText(f"Error reading log file: {str(e)}")
        else:
            self.raw_text.setPlainText("No audit log records recorded yet.")

    def _update_file_size(self):
        sz = AuditLogger.get_log_size_bytes()
        p = AuditLogger.get_log_file_path()
        sz_kb = sz / 1024.0
        self.file_size_lbl.setText(f"📁 {p.name} ({sz_kb:.1f} KB)")

    def _apply_filter(self):
        search_txt = self.search_edit.text().strip().lower()
        act_sel = self.action_combo.currentText()
        act_filter = None if act_sel == "All Actions" else act_sel.upper()
        tbl_sel = self.table_combo.currentText()
        tbl_filter = None if tbl_sel == "All Tables" else tbl_sel.lower()

        filtered = []
        for r in self._all_records:
            if act_filter and r["action"].upper() != act_filter:
                continue
            if tbl_filter and r["table"].lower() != tbl_filter:
                continue
            if search_txt:
                searchable = f"{r['timestamp']} {r['action']} {r['table']} {r['record_id']} {r['details']}".lower()
                if search_txt not in searchable:
                    continue
            filtered.append(r)

        self.table.setRowCount(0)
        for r in filtered:
            row_idx = self.table.rowCount()
            self.table.insertRow(row_idx)

            # Timestamp
            self.table.setItem(row_idx, 0, create_table_item(r["timestamp"], alignment=Qt.AlignCenter))

            # Action with color badge
            action_item = create_table_item(r["action"], alignment=Qt.AlignCenter, bold=True)
            act = r["action"].upper()
            if act == "INSERT":
                action_item.setForeground(QColor("#16a34a"))  # Green
            elif act == "UPDATE":
                action_item.setForeground(QColor("#2563eb"))  # Blue
            elif act == "SOFT_DELETE":
                action_item.setForeground(QColor("#d97706"))  # Amber
            elif act == "DELETE":
                action_item.setForeground(QColor("#dc2626"))  # Red
            elif act == "SYSTEM":
                action_item.setForeground(QColor("#9333ea"))  # Purple
            self.table.setItem(row_idx, 1, action_item)

            # Table
            self.table.setItem(row_idx, 2, create_table_item(r["table"], bold=True))

            # Record ID
            self.table.setItem(row_idx, 3, create_table_item(r["record_id"], alignment=Qt.AlignCenter))

            # Details
            self.table.setItem(row_idx, 4, create_table_item(r["details"]))

        self.status_lbl.setText(
            f"Showing {len(filtered)} of {len(self._all_records)} total audit entries | Path: {AuditLogger.get_log_file_path()}"
        )

    def _open_raw_file(self):
        log_path = AuditLogger.get_log_file_path()
        if not log_path.exists():
            QMessageBox.information(self, "No Log File", "No database operations have been logged yet.")
            return

        try:
            url = QUrl.fromLocalFile(str(log_path.resolve()))
            QDesktopServices.openUrl(url)
        except Exception as e:
            QMessageBox.warning(self, "Could Not Open File", f"Unable to open log file automatically: {e}")

    def _export_logs(self):
        if not self._all_records:
            QMessageBox.information(self, "No Records", "There are no audit logs to export.")
            return

        path, flt = QFileDialog.getSaveFileName(
            self, "Export Database Audit Logs", "database_audit_logs.csv",
            "CSV Files (*.csv);;Text Files (*.txt);;All Files (*)"
        )
        if not path:
            return

        try:
            if path.endswith(".csv"):
                with open(path, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(["Timestamp", "Action", "Table", "Record ID", "Details"])
                    for r in self._all_records:
                        writer.writerow([r["timestamp"], r["action"], r["table"], r["record_id"], r["details"]])
            else:
                with open(path, "w", encoding="utf-8") as f:
                    for r in self._all_records:
                        f.write(r["raw"] + "\n")

            QMessageBox.information(self, "Export Successful", f"Audit logs exported successfully to:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Failed", f"Failed to export audit logs: {e}")
