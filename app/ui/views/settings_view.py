from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton, QFileDialog,
    QMessageBox
)
from PySide6.QtCore import Qt
from app.config.settings import get_db_path
from app.services.backup_service import BackupService

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
