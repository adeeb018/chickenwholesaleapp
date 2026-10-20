from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton, QFileDialog,
    QMessageBox, QDoubleSpinBox, QDialog, QLineEdit, QCheckBox, QFormLayout,
    QScrollArea, QInputDialog
)
from PySide6.QtCore import Qt, Signal, QUrl
from PySide6.QtGui import QDesktopServices
from app.config.settings import get_db_path
from app.services.backup_service import BackupService
from app.services.setting_service import SettingService
from app.database.audit_logger import AuditLogger
from app.ui.components.audit_log_dialog import AuditLogDialog
from app.utils.decimal_utils import format_currency

class ClearAllDataDialog(QDialog):
    """
    Password-protected confirmation dialog to permanently wipe database transactions.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Authorize Database Data Clearance")
        self.resize(520, 380)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(20, 20, 20, 20)

        warn_box = QFrame()
        warn_box.setStyleSheet("""
            QFrame {
                background-color: #fef2f2;
                border: 2px solid #ef4444;
                border-radius: 8px;
                padding: 12px;
            }
        """)
        wb_layout = QVBoxLayout(warn_box)
        w_title = QLabel("⚠️ PERMANENT DATA CLEARANCE")
        w_title.setStyleSheet("font-size: 15px; font-weight: bold; color: #b91c1c;")
        wb_layout.addWidget(w_title)

        w_desc = QLabel(
            "This operation will permanently delete all business transactions, purchases, sales, "
            "customer returns, customer payments, provider payments, batch inventory, and physical stock reconciliations.\n\n"
            "An automated safety backup of your current database will be saved before deletion."
        )
        w_desc.setWordWrap(True)
        w_desc.setStyleSheet("color: #7f1d1d; font-size: 12px; line-height: 1.4;")
        wb_layout.addWidget(w_desc)
        layout.addWidget(warn_box)

        # Options
        self.include_masters_check = QCheckBox("Also delete all Customers & Providers (Full Complete Reset)")
        self.include_masters_check.setStyleSheet("font-weight: 600; color: #991b1b; padding: 4px;")
        layout.addWidget(self.include_masters_check)

        # Form fields for verification
        form = QFormLayout()
        form.setSpacing(10)

        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.password_edit.setPlaceholderText("Enter Admin Password")
        form.addRow("Admin Password:", self.password_edit)

        self.confirm_text_edit = QLineEdit()
        self.confirm_text_edit.setPlaceholderText("Type CLEAR in capital letters")
        form.addRow("Type 'CLEAR' to confirm:", self.confirm_text_edit)

        layout.addLayout(form)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setProperty("class", "secondaryBtn")
        cancel_btn.clicked.connect(self.reject)

        self.delete_btn = QPushButton("🗑️ Permanently Delete Data")
        self.delete_btn.setProperty("class", "dangerBtn")
        self.delete_btn.setStyleSheet("padding: 8px 16px; font-weight: bold;")
        self.delete_btn.clicked.connect(self._on_confirm_delete)

        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(self.delete_btn)
        layout.addLayout(btn_row)

    def _on_confirm_delete(self):
        pwd = self.password_edit.text()
        if not pwd:
            QMessageBox.warning(self, "Password Required", "Please enter your admin password.")
            self.password_edit.setFocus()
            return

        if not SettingService.verify_admin_password(pwd):
            QMessageBox.critical(self, "Authorization Failed", "Incorrect admin password. Data clearance cancelled.")
            self.password_edit.clear()
            self.password_edit.setFocus()
            return

        conf_txt = self.confirm_text_edit.text().strip()
        if conf_txt != "CLEAR":
            QMessageBox.warning(
                self,
                "Confirmation Mismatch",
                "Please type 'CLEAR' in capital letters in the confirmation field to authorize permanent deletion."
            )
            self.confirm_text_edit.setFocus()
            return

        inc_masters = self.include_masters_check.isChecked()
        success, msg = SettingService.clear_all_data(include_masters=inc_masters)
        if success:
            QMessageBox.information(
                self,
                "Data Cleared Successfully",
                f"All business data has been cleared from the database.\n\n{msg}"
            )
            self.accept()
        else:
            QMessageBox.critical(self, "Error Clearing Data", msg)


class SettingsView(QWidget):
    """
    Application Settings, Admin Security, Data Management & Database Backup/Restore View.
    """
    data_cleared = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)

        # Scroll area for clean responsive layout
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        main_layout.addWidget(scroll)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(16)
        scroll.setWidget(content)

        header = QLabel("⚙️ Application Settings & Administration")
        header.setStyleSheet("font-size: 20px; font-weight: bold; color: #0f172a;")
        layout.addWidget(header)

        # 1. Database Information Frame
        info_frame = QFrame()
        info_frame.setProperty("class", "cardFrame")
        info_box = QVBoxLayout(info_frame)
        
        info_box.addWidget(QLabel("<b>Local Database File Location:</b>"))
        self.db_path_label = QLabel(str(get_db_path()))
        self.db_path_label.setStyleSheet("font-family: monospace; background-color: #f1f5f9; padding: 8px; border-radius: 4px;")
        info_box.addWidget(self.db_path_label)

        layout.addWidget(info_frame)

        # 2. Default Pricing Settings Frame
        pricing_frame = QFrame()
        pricing_frame.setProperty("class", "cardFrame")
        pricing_box = QVBoxLayout(pricing_frame)
        pricing_box.setSpacing(10)

        pricing_box.addWidget(QLabel("<b>🐔 Daily Benchmark Chicken Selling Rate:</b>"))
        pricing_box.addWidget(QLabel("Default market selling rate (₹/KG) that automatically pre-fills on new customer sales."))

        rate_row = QHBoxLayout()
        self.settings_rate_spin = QDoubleSpinBox()
        self.settings_rate_spin.setRange(0.00, 99999.00)
        self.settings_rate_spin.setDecimals(2)
        self.settings_rate_spin.setPrefix("₹ ")
        self.settings_rate_spin.setSuffix(" / KG")
        self.settings_rate_spin.setStyleSheet("""
            QDoubleSpinBox {
                font-size: 14px;
                font-weight: bold;
                color: #1e3a8a;
                background-color: #ffffff;
                border: 2px solid #93c5fd;
                border-radius: 6px;
                padding: 6px 10px;
                min-width: 140px;
            }
        """)

        save_rate_btn = QPushButton("Save Rate")
        save_rate_btn.setProperty("class", "primaryBtn")
        save_rate_btn.clicked.connect(self._save_pricing_rate)

        rate_row.addWidget(self.settings_rate_spin)
        rate_row.addWidget(save_rate_btn)
        rate_row.addStretch()

        pricing_box.addLayout(rate_row)
        layout.addWidget(pricing_frame)

        # 3. Backup & Restore Frame
        backup_frame = QFrame()
        backup_frame.setProperty("class", "cardFrame")
        backup_box = QVBoxLayout(backup_frame)
        backup_box.setSpacing(12)

        backup_box.addWidget(QLabel("<b>💾 Database Backup & Data Protection:</b>"))
        backup_box.addWidget(QLabel("Create standard offline backups of your shop's database to protect against system hardware failure or data loss."))

        btn_layout = QHBoxLayout()
        backup_btn = QPushButton("Create Database Backup...")
        backup_btn.setProperty("class", "primaryBtn")
        backup_btn.clicked.connect(self._create_backup)

        restore_btn = QPushButton("Restore Database from File...")
        restore_btn.setProperty("class", "secondaryBtn")
        restore_btn.clicked.connect(self._restore_backup)

        btn_layout.addWidget(backup_btn)
        btn_layout.addWidget(restore_btn)
        btn_layout.addStretch()

        backup_box.addLayout(btn_layout)
        layout.addWidget(backup_frame)

        # 4. Admin Security & Password Protection Frame
        self.security_frame = QFrame()
        self.security_frame.setProperty("class", "cardFrame")
        self.security_layout = QVBoxLayout(self.security_frame)
        self.security_layout.setSpacing(12)

        # Sub-frame A: First-run Setup Password (shown only if password NOT yet created)
        self.create_pwd_box = QWidget()
        create_box_l = QVBoxLayout(self.create_pwd_box)
        create_box_l.setContentsMargins(0, 0, 0, 0)
        create_box_l.setSpacing(10)

        create_title = QLabel("<b>🔒 Set Admin Protection Password</b>")
        create_title.setStyleSheet("font-size: 15px; color: #0f172a;")
        create_box_l.addWidget(create_title)

        create_note = QLabel(
            "⚠️ No admin password is currently set. Create a strong admin password to protect administrative "
            "operations like clearing database records and modifying critical settings."
        )
        create_note.setStyleSheet("color: #b45309; font-size: 13px; background-color: #fefce8; padding: 10px; border-radius: 6px; border: 1px solid #fef08a;")
        create_note.setWordWrap(True)
        create_box_l.addWidget(create_note)

        create_form = QFormLayout()
        create_form.setSpacing(8)

        self.new_admin_pwd = QLineEdit()
        self.new_admin_pwd.setEchoMode(QLineEdit.Password)
        self.new_admin_pwd.setPlaceholderText("Enter strong password (min 8 characters, letters & numbers)")
        create_form.addRow("New Password:", self.new_admin_pwd)

        self.confirm_admin_pwd = QLineEdit()
        self.confirm_admin_pwd.setEchoMode(QLineEdit.Password)
        self.confirm_admin_pwd.setPlaceholderText("Confirm new password")
        create_form.addRow("Confirm Password:", self.confirm_admin_pwd)

        create_box_l.addLayout(create_form)

        create_help = QLabel("Password must be at least 8 characters long and contain both letters and numbers.")
        create_help.setStyleSheet("color: #64748b; font-size: 11px;")
        create_box_l.addWidget(create_help)

        create_btn_row = QHBoxLayout()
        self.show_create_pwd_check = QCheckBox("Show password text")
        self.show_create_pwd_check.toggled.connect(self._toggle_show_create_pwd)
        create_btn_row.addWidget(self.show_create_pwd_check)
        create_btn_row.addStretch()

        save_admin_pwd_btn = QPushButton("🔒 Save Admin Password")
        save_admin_pwd_btn.setProperty("class", "primaryBtn")
        save_admin_pwd_btn.clicked.connect(self._save_new_admin_password)
        create_btn_row.addWidget(save_admin_pwd_btn)
        create_box_l.addLayout(create_btn_row)

        self.security_layout.addWidget(self.create_pwd_box)

        # Sub-frame B: Change Password (visible only when admin password already exists)
        self.change_pwd_box = QWidget()
        change_box_l = QVBoxLayout(self.change_pwd_box)
        change_box_l.setContentsMargins(0, 0, 0, 0)
        change_box_l.setSpacing(10)

        change_hdr_row = QHBoxLayout()
        change_title = QLabel("<b>🔑 Change Admin Password</b>")
        change_title.setStyleSheet("font-size: 15px; color: #0f172a;")
        change_status = QLabel("✅ Admin Password Active")
        change_status.setStyleSheet("color: #15803d; font-size: 12px; font-weight: bold; background: #dcfce7; padding: 3px 8px; border-radius: 4px;")
        change_hdr_row.addWidget(change_title)
        change_hdr_row.addStretch()
        change_hdr_row.addWidget(change_status)
        change_box_l.addLayout(change_hdr_row)

        change_form = QFormLayout()
        change_form.setSpacing(8)

        self.curr_admin_pwd = QLineEdit()
        self.curr_admin_pwd.setEchoMode(QLineEdit.Password)
        self.curr_admin_pwd.setPlaceholderText("Enter current password")
        change_form.addRow("Current Password:", self.curr_admin_pwd)

        self.update_admin_pwd = QLineEdit()
        self.update_admin_pwd.setEchoMode(QLineEdit.Password)
        self.update_admin_pwd.setPlaceholderText("Enter new password (min 8 chars, letters & numbers)")
        change_form.addRow("New Password:", self.update_admin_pwd)

        self.update_confirm_pwd = QLineEdit()
        self.update_confirm_pwd.setEchoMode(QLineEdit.Password)
        self.update_confirm_pwd.setPlaceholderText("Confirm new password")
        change_form.addRow("Confirm New Password:", self.update_confirm_pwd)

        change_box_l.addLayout(change_form)

        change_btn_row = QHBoxLayout()
        self.show_change_pwd_check = QCheckBox("Show password text")
        self.show_change_pwd_check.toggled.connect(self._toggle_show_change_pwd)
        change_btn_row.addWidget(self.show_change_pwd_check)
        change_btn_row.addStretch()

        update_pwd_btn = QPushButton("🔑 Update Password")
        update_pwd_btn.setProperty("class", "primaryBtn")
        update_pwd_btn.clicked.connect(self._update_admin_password)
        change_btn_row.addWidget(update_pwd_btn)
        change_box_l.addLayout(change_btn_row)

        self.security_layout.addWidget(self.change_pwd_box)
        layout.addWidget(self.security_frame)

        # 5. Database Audit Logs Section
        audit_frame = QFrame()
        audit_frame.setStyleSheet("""
            QFrame {
                background-color: #f8fafc;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                padding: 14px;
            }
        """)
        audit_box = QVBoxLayout(audit_frame)
        audit_box.setSpacing(10)

        audit_title = QLabel("📋 Database Audit Logs & Activity Trail")
        audit_title.setStyleSheet("font-size: 15px; font-weight: bold; color: #0f172a;")
        audit_box.addWidget(audit_title)

        audit_desc = QLabel(
            "All operations on the database (INSERT, UPDATE, SOFT_DELETE, DELETE) are automatically recorded "
            "with precise timestamps, entity models, and changed details. Protected by Admin Password."
        )
        audit_desc.setWordWrap(True)
        audit_desc.setStyleSheet("color: #475569; font-size: 13px;")
        audit_box.addWidget(audit_desc)

        audit_btn_row = QHBoxLayout()
        view_logs_btn = QPushButton("🔐 View Database Audit Logs")
        view_logs_btn.setProperty("class", "primaryBtn")
        view_logs_btn.setStyleSheet("padding: 8px 16px; font-weight: bold;")
        view_logs_btn.clicked.connect(self._open_audit_logs)

        open_log_file_btn = QPushButton("📂 Open Log File")
        open_log_file_btn.setProperty("class", "secondaryBtn")
        open_log_file_btn.setStyleSheet("padding: 8px 16px;")
        open_log_file_btn.clicked.connect(self._open_audit_log_file)

        audit_btn_row.addWidget(view_logs_btn)
        audit_btn_row.addWidget(open_log_file_btn)
        audit_btn_row.addStretch()
        audit_box.addLayout(audit_btn_row)

        layout.addWidget(audit_frame)

        # 6. Danger Zone — Clear All Data Frame
        danger_frame = QFrame()
        danger_frame.setStyleSheet("""
            QFrame {
                background-color: #fff1f2;
                border: 2px solid #fecaca;
                border-radius: 8px;
                padding: 14px;
            }
        """)
        danger_box = QVBoxLayout(danger_frame)
        danger_box.setSpacing(10)

        danger_title = QLabel("⚠️ Danger Zone: Clear All Data")
        danger_title.setStyleSheet("font-size: 15px; font-weight: bold; color: #b91c1c;")
        danger_box.addWidget(danger_title)

        danger_desc = QLabel(
            "Permanently delete all business transaction records, purchases, sales, customer returns, "
            "payments, batch inventory, and daily stock reconciliations. Requires admin password authorization.\n"
            "An automatic safety backup copy will be saved before clearing."
        )
        danger_desc.setWordWrap(True)
        danger_desc.setStyleSheet("color: #7f1d1d; font-size: 13px;")
        danger_box.addWidget(danger_desc)

        danger_btn_row = QHBoxLayout()
        clear_data_btn = QPushButton("🗑️ Clear All Data...")
        clear_data_btn.setProperty("class", "dangerBtn")
        clear_data_btn.setStyleSheet("padding: 8px 16px; font-weight: bold;")
        clear_data_btn.clicked.connect(self._open_clear_data_dialog)

        danger_btn_row.addWidget(clear_data_btn)
        danger_btn_row.addStretch()
        danger_box.addLayout(danger_btn_row)

        layout.addWidget(danger_frame)
        layout.addStretch()

        self.refresh_data()

    def _toggle_show_create_pwd(self, checked: bool):
        mode = QLineEdit.Normal if checked else QLineEdit.Password
        self.new_admin_pwd.setEchoMode(mode)
        self.confirm_admin_pwd.setEchoMode(mode)

    def _toggle_show_change_pwd(self, checked: bool):
        mode = QLineEdit.Normal if checked else QLineEdit.Password
        self.curr_admin_pwd.setEchoMode(mode)
        self.update_admin_pwd.setEchoMode(mode)
        self.update_confirm_pwd.setEchoMode(mode)

    def _save_new_admin_password(self):
        p1 = self.new_admin_pwd.text()
        p2 = self.confirm_admin_pwd.text()

        if p1 != p2:
            QMessageBox.warning(self, "Password Mismatch", "Passwords do not match. Please re-enter.")
            return

        success, msg = SettingService.set_admin_password(p1)
        if success:
            QMessageBox.information(
                self,
                "Password Saved",
                "Admin protection password has been successfully created and secured."
            )
            self.new_admin_pwd.clear()
            self.confirm_admin_pwd.clear()
            self._update_password_ui()
        else:
            QMessageBox.warning(self, "Invalid Password", msg)

    def _update_admin_password(self):
        curr = self.curr_admin_pwd.text()
        p_new = self.update_admin_pwd.text()
        p_conf = self.update_confirm_pwd.text()

        if not curr:
            QMessageBox.warning(self, "Validation Error", "Please enter your current password.")
            self.curr_admin_pwd.setFocus()
            return

        if p_new != p_conf:
            QMessageBox.warning(self, "Password Mismatch", "New passwords do not match. Please re-enter.")
            return

        success, msg = SettingService.change_admin_password(curr, p_new)
        if success:
            QMessageBox.information(
                self,
                "Password Updated",
                "Admin protection password has been successfully updated."
            )
            self.curr_admin_pwd.clear()
            self.update_admin_pwd.clear()
            self.update_confirm_pwd.clear()
            self._update_password_ui()
        else:
            QMessageBox.warning(self, "Update Failed", msg)

    def _open_clear_data_dialog(self):
        if not SettingService.is_admin_password_set():
            QMessageBox.warning(
                self,
                "Admin Password Required",
                "Please set an Admin Protection Password in the section above before clearing data."
            )
            self.new_admin_pwd.setFocus()
            return

        dlg = ClearAllDataDialog(parent=self)
        if dlg.exec() == QDialog.Accepted:
            self.refresh_data()
            self.data_cleared.emit()

    def _update_password_ui(self):
        is_set = SettingService.is_admin_password_set()
        self.create_pwd_box.setVisible(not is_set)
        self.change_pwd_box.setVisible(is_set)

    def _create_backup(self):
        default_name = f"chicken_wholesale_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Database Backup", default_name, "SQLite Database (*.db)"
        )
        if file_path:
            success, msg = BackupService.backup_database(file_path)
            if success:
                QMessageBox.information(self, "Backup Successful", msg)
            else:
                QMessageBox.critical(self, "Backup Error", msg)

    def _restore_backup(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Backup File to Restore", "", "SQLite Database (*.db)"
        )
        if file_path:
            reply = QMessageBox.warning(
                self, "Confirm Database Restore",
                "RESTORE WARNING:\n\nRestoring will overwrite your current active database with the contents of the backup file.\n"
                "A automatic safety copy of your current database will be saved first.\n\n"
                "Do you want to proceed with restore?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                success, msg = BackupService.restore_database(file_path)
                if success:
                    QMessageBox.information(self, "Restore Successful", msg)
                    self.refresh_data()
                    self.data_cleared.emit()
                else:
                    QMessageBox.critical(self, "Restore Error", msg)

    def refresh_data(self):
        """Loads current settings values into form fields and updates UI state."""
        current_rate = SettingService.get_main_chicken_rate()
        self.settings_rate_spin.setValue(float(current_rate))
        self._update_password_ui()

    def on_view_activated(self):
        self.refresh_data()

    def _save_pricing_rate(self):
        val = self.settings_rate_spin.value()
        try:
            saved_rate = SettingService.set_main_chicken_rate(val)
            QMessageBox.information(
                self,
                "Settings Saved",
                f"Main chicken selling rate successfully updated to {format_currency(saved_rate)} / KG."
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save chicken rate: {str(e)}")

    def _open_audit_logs(self):
        if SettingService.is_admin_password_set():
            pwd, ok = QInputDialog.getText(
                self, "Admin Password Required",
                "Enter Admin Password to view database audit logs:",
                QLineEdit.Password
            )
            if not ok:
                return
            if not SettingService.verify_admin_password(pwd):
                QMessageBox.critical(self, "Access Denied", "Incorrect admin password. Cannot view audit logs.")
                return

        dlg = AuditLogDialog(parent=self)
        dlg.exec()

    def _open_audit_log_file(self):
        if SettingService.is_admin_password_set():
            pwd, ok = QInputDialog.getText(
                self, "Admin Password Required",
                "Enter Admin Password to open database audit log file:",
                QLineEdit.Password
            )
            if not ok:
                return
            if not SettingService.verify_admin_password(pwd):
                QMessageBox.critical(self, "Access Denied", "Incorrect admin password.")
                return

        log_path = AuditLogger.get_log_file_path()
        if not log_path.exists():
            QMessageBox.information(self, "No Log File", "No database operations have been logged yet.")
            return

        try:
            url = QUrl.fromLocalFile(str(log_path.resolve()))
            QDesktopServices.openUrl(url)
        except Exception as e:
            QMessageBox.warning(self, "Could Not Open File", f"Unable to open log file automatically: {e}")
