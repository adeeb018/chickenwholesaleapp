from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QDialog, QFormLayout, QMessageBox, QCheckBox
)
from PySide6.QtCore import Qt
from app.services.master_service import MasterService

class ItemDialog(QDialog):
    """
    Dialog for Adding or Editing Chicken Type / Item.
    """
    def __init__(self, item=None, parent=None):
        super().__init__(parent)
        self.item = item
        self.setWindowTitle("Edit Chicken Type" if item else "Add New Chicken Type")
        self.resize(400, 200)

        layout = QFormLayout(self)

        self.name_edit = QLineEdit(item.name if item else "")
        self.code_edit = QLineEdit(item.code if item and item.code else "")
        self.active_check = QCheckBox("Active Item")
        self.active_check.setChecked(item.is_active if item else True)

        layout.addRow("Chicken Type Name*:", self.name_edit)
        layout.addRow("Item Code:", self.code_edit)
        layout.addRow("Status:", self.active_check)

        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.setProperty("class", "primaryBtn")
        save_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setProperty("class", "secondaryBtn")
        cancel_btn.clicked.connect(self.reject)

        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(save_btn)

        layout.addRow(btn_layout)

    def get_data(self):
        return {
            "name": self.name_edit.text().strip(),
            "code": self.code_edit.text().strip() or None,
            "is_active": self.active_check.isChecked()
        }

class ItemsView(QWidget):
    """
    Chicken Type Management Screen.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        header_layout = QHBoxLayout()
        header = QLabel("Chicken Type / Item Management")
        header.setStyleSheet("font-size: 20px; font-weight: bold; color: #0f172a;")
        
        add_btn = QPushButton("+ Add Chicken Type")
        add_btn.setProperty("class", "primaryBtn")
        add_btn.clicked.connect(self._add_item)

        header_layout.addWidget(header)
        header_layout.addStretch()
        header_layout.addWidget(add_btn)
        layout.addLayout(header_layout)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels([
            "ID", "Name", "Code", "Status", "Actions"
        ])
        header = self.table.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(4, QHeaderView.Fixed)
        self.table.setColumnWidth(4, 120)
        self.table.verticalHeader().setDefaultSectionSize(42)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table, 1)

        self.refresh_table()

    def refresh_table(self):
        items = MasterService.get_all_items(include_inactive=True)

        self.table.setRowCount(0)
        for i in items:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(str(i.id)))
            self.table.setItem(r, 1, QTableWidgetItem(i.name))
            self.table.setItem(r, 2, QTableWidgetItem(i.code or "-"))
            self.table.setItem(r, 3, QTableWidgetItem("Active" if i.is_active else "Inactive"))

            action_widget = QWidget()
            act_box = QHBoxLayout(action_widget)
            act_box.setContentsMargins(6, 2, 6, 2)
            act_box.setAlignment(Qt.AlignCenter)

            edit_btn = QPushButton("✏️ Edit")
            edit_btn.setProperty("class", "actionEdit")
            edit_btn.setToolTip("Edit chicken type name or code")
            edit_btn.clicked.connect(lambda _, item=i: self._edit_item(item))

            act_box.addWidget(edit_btn)
            self.table.setCellWidget(r, 4, action_widget)

    def _add_item(self):
        dlg = ItemDialog(parent=self)
        if dlg.exec() == QDialog.Accepted:
            data = dlg.get_data()
            if not data["name"]:
                QMessageBox.warning(self, "Validation Error", "Item name is required.")
                return
            MasterService.create_item(name=data["name"], code=data["code"])
            self.refresh_table()

    def _edit_item(self, item):
        dlg = ItemDialog(item=item, parent=self)
        if dlg.exec() == QDialog.Accepted:
            data = dlg.get_data()
            if not data["name"]:
                QMessageBox.warning(self, "Validation Error", "Item name is required.")
                return
            MasterService.update_item(item_id=item.id, **data)
            self.refresh_table()
