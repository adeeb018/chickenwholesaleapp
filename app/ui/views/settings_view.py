from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton, QFileDialog,
    QMessageBox, QDoubleSpinBox
)
from PySide6.QtCore import Qt
from app.config.settings import get_db_path
from app.services.backup_service import BackupService
from app.services.setting_service import SettingService
from app.utils.decimal_utils import format_currency

class SettingsView(QWidget):
    """
    Application Settings & Database Backup/Restore View.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        header = QLabel("Application Settings & Backup")
        header.setStyleSheet("font-size: 20px; font-weight: bold; color: #0f172a;")
        layout.addWidget(header)

        # Database Information Frame
        info_frame = QFrame()
        info_frame.setProperty("class", "cardFrame")
        info_box = QVBoxLayout(info_frame)
        
        info_box.addWidget(QLabel("<b>Local Database File Location:</b>"))
        self.db_path_label = QLabel(str(get_db_path()))
        self.db_path_label.setStyleSheet("font-family: monospace; background-color: #f1f5f9; padding: 8px; border-radius: 4px;")
        info_box.addWidget(self.db_path_label)

        layout.addWidget(info_frame)

        # Default Pricing Settings Frame
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

        # Backup & Restore Frame
        backup_frame = QFrame()
        backup_frame.setProperty("class", "cardFrame")
        backup_box = QVBoxLayout(backup_frame)
        backup_box.setSpacing(12)

        backup_box.addWidget(QLabel("<b>Database Backup & Data Protection:</b>"))
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
        layout.addStretch()

        self.refresh_data()

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
                else:
                    QMessageBox.critical(self, "Restore Error", msg)

    def refresh_data(self):
        """Loads current settings values into form fields."""
        current_rate = SettingService.get_main_chicken_rate()
        self.settings_rate_spin.setValue(float(current_rate))

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

