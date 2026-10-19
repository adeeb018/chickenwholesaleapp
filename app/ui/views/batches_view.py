from datetime import date
from decimal import Decimal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QFrame, QMessageBox,
    QDialog, QFormLayout, QLineEdit, QTextEdit, QDoubleSpinBox, QGroupBox
)
from PySide6.QtCore import Qt
from app.services.inventory_service import InventoryService
from app.services.master_service import MasterService
from app.utils.decimal_utils import format_weight, format_currency, to_decimal

class FinishBatchDialog(QDialog):
    """Dialog for explicitly marking a batch as completely finished (CLOSED)."""
    def __init__(self, batch, parent=None):
        super().__init__(parent)
        self.batch = batch
        self.setWindowTitle(f"Finish Batch - {batch.batch_number}")
        self.resize(500, 380)

        layout = QVBoxLayout(self)

        info_box = QGroupBox("Batch Verification Details")
        info_layout = QFormLayout(info_box)

        info_layout.addRow("Batch Number:", QLabel(f"<b>{batch.batch_number}</b>"))
        info_layout.addRow("Purchase Date:", QLabel(batch.purchase_date.strftime("%d/%m/%Y")))
        info_layout.addRow("Chicken Item:", QLabel(batch.item.name if batch.item else ""))
        info_layout.addRow("Purchased Net Weight:", QLabel(format_weight(batch.net_weight_kg)))
        
        hist = InventoryService.get_batch_history(batch.id)
        info_layout.addRow("Total Sold Weight:", QLabel(format_weight(hist.get("total_sold", Decimal("0.000")))))
        info_layout.addRow("Customer Returns:", QLabel(format_weight(hist.get("total_returned", Decimal("0.000")))))
        
        stock_label = QLabel(format_weight(batch.current_stock_kg))
        stock_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #b91c1c;" if batch.current_stock_kg > 0 else "color: #15803d; font-weight: bold;")
        info_layout.addRow("Current Stock Balance:", stock_label)

        layout.addWidget(info_box)

        self.reason_edit = QLineEdit()
        self.reason_edit.setPlaceholderText("e.g. Natural shrinkage, damaged chicken discarded")
        self.notes_edit = QTextEdit()
        self.notes_edit.setMaximumHeight(50)
        self.notes_edit.setPlaceholderText("Optional notes")

        if batch.current_stock_kg > 0:
            warn = QLabel(
                f"⚠️ <b>Notice:</b> This batch has <b>{format_weight(batch.current_stock_kg)}</b> remaining stock.<br>"
                "To finish this batch, an explicit stock adjustment will be recorded to account for the remaining chicken."
            )
            warn.setStyleSheet("color: #b45309; background-color: #fffbeb; padding: 8px; border-radius: 4px; border: 1px solid #fde68a;")
            layout.addWidget(warn)

            adj_box = QGroupBox("Final Zeroing Adjustment")
            adj_layout = QFormLayout(adj_box)
            adj_layout.addRow("Adjustment Reason (Required):", self.reason_edit)
            adj_layout.addRow("Notes:", self.notes_edit)
            layout.addWidget(adj_box)

        confirm_lbl = QLabel("<b>Have you confirmed that no chicken remains from this batch?</b>")
        confirm_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(confirm_lbl)

        btn_layout = QHBoxLayout()
        confirm_btn = QPushButton("Confirm Batch Completion")
        confirm_btn.setProperty("class", "primaryBtn")
        confirm_btn.clicked.connect(self._confirm)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setProperty("class", "secondaryBtn")
        cancel_btn.clicked.connect(self.reject)

        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(confirm_btn)
        layout.addLayout(btn_layout)

    def _confirm(self):
        if self.batch.current_stock_kg > 0:
            reason = self.reason_edit.text().strip()
            if not reason:
                QMessageBox.warning(self, "Validation Error", "Please provide a reason to account for the remaining stock.")
                return
        else:
            reason = None

        try:
            InventoryService.finish_batch(
                batch_id=self.batch.id,
                business_date=date.today(),
                reason=reason,
                notes=self.notes_edit.toPlainText().strip()
            )
            QMessageBox.information(self, "Success", f"Batch '{self.batch.batch_number}' has been marked as CLOSED.")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

class BatchHistoryDialog(QDialog):
    """Dialog showing chronological inventory ledger and audit trail for a batch."""
    def __init__(self, batch_id: int, parent=None):
        super().__init__(parent)
        self.batch_id = batch_id
        hist = InventoryService.get_batch_history(batch_id)
        batch = hist.get("batch")
        self.setWindowTitle(f"Batch History - {batch.batch_number if batch else ''}")
        self.resize(750, 500)

        layout = QVBoxLayout(self)

        # Summary Metrics Frame
        summary = QFrame()
        summary.setStyleSheet("background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 10px;")
        s_layout = QHBoxLayout(summary)
        s_layout.addWidget(QLabel(f"<b>Batch:</b> {batch.batch_number}"))
        s_layout.addWidget(QLabel(f"<b>Purchased:</b> {format_weight(hist.get('total_purchased', 0))}"))
        s_layout.addWidget(QLabel(f"<b>Sold:</b> {format_weight(hist.get('total_sold', 0))}"))
        s_layout.addWidget(QLabel(f"<b>Returns:</b> {format_weight(hist.get('total_returned', 0))}"))
        s_layout.addWidget(QLabel(f"<b>Current Stock:</b> {format_weight(hist.get('current_stock', 0))}"))
        s_layout.addWidget(QLabel(f"<b>Status:</b> {batch.status}"))
        layout.addWidget(summary)

        # Transactions Table
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Date", "Movement Type", "Quantity Change", "Reference", "Reason", "Notes"])
        self.table.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        running = Decimal("0.000")
        for m in hist.get("movements", []):
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(m.business_date.strftime("%d/%m/%Y")))
            
            type_item = QTableWidgetItem(m.movement_type)
            if m.movement_type in ("PURCHASE", "STOCK_GAIN", "CUSTOMER_RETURN"):
                type_item.setForeground(Qt.darkGreen)
            else:
                type_item.setForeground(Qt.darkRed)
            self.table.setItem(r, 1, type_item)

            qty_str = f"+{format_weight(m.quantity_kg)}" if m.quantity_kg > 0 else format_weight(m.quantity_kg)
            qty_item = QTableWidgetItem(qty_str)
            qty_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(r, 2, qty_item)

            self.table.setItem(r, 3, QTableWidgetItem(f"{m.reference_type or ''} #{m.reference_id or ''}".strip()))
            self.table.setItem(r, 4, QTableWidgetItem(m.reason or ""))
            self.table.setItem(r, 5, QTableWidgetItem(m.notes or ""))

        layout.addWidget(self.table)

        close_btn = QPushButton("Close")
        close_btn.setProperty("class", "secondaryBtn")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, 0, Qt.AlignRight)

class BatchesView(QWidget):
    """
    Batch Inventory Overview and Batch Lifecycle Management Screen.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        header = QLabel("📦 Batch-Wise Inventory Management")
        header.setStyleSheet("font-size: 20px; font-weight: bold; color: #0f172a;")
        layout.addWidget(header)

        # Filter Bar
        filter_layout = QHBoxLayout()

        self.status_combo = QComboBox()
        self.status_combo.addItems(["ALL STATUSES", "ACTIVE", "DEPLETED", "CLOSED"])
        self.status_combo.currentIndexChanged.connect(self.refresh_table)

        self.item_combo = QComboBox()
        self.item_combo.addItem("ALL CHICKEN TYPES", None)
        for itm in MasterService.get_all_items():
            self.item_combo.addItem(itm.name, itm.id)
        self.item_combo.currentIndexChanged.connect(self.refresh_table)

        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.setProperty("class", "secondaryBtn")
        refresh_btn.clicked.connect(self.refresh_table)

        filter_layout.addWidget(QLabel("Filter Status:"))
        filter_layout.addWidget(self.status_combo)
        filter_layout.addWidget(QLabel("Chicken Type:"))
        filter_layout.addWidget(self.item_combo)
        filter_layout.addWidget(refresh_btn)
        filter_layout.addStretch()

        layout.addLayout(filter_layout)

        # Batches Table
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels([
            "Batch Number", "Purchase Date", "Chicken Item", "Purchased Net (KG)",
            "Available Stock (KG)", "Status", "Closure Notes", "Actions"
        ])
        header = self.table.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.Stretch)
        header.setSectionResizeMode(7, QHeaderView.Fixed)
        self.table.setColumnWidth(7, 220)
        self.table.verticalHeader().setDefaultSectionSize(42)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table, 1)

        self.refresh_table()

    def on_view_activated(self):
        self.refresh_table()

    def refresh_table(self):
        status_text = self.status_combo.currentText()
        status_filter = None if status_text == "ALL STATUSES" else status_text
        item_id = self.item_combo.currentData()

        batches = InventoryService.get_batches(status=status_filter, item_id=item_id, include_closed=True)
        self.table.setRowCount(0)

        for b in batches:
            r = self.table.rowCount()
            self.table.insertRow(r)

            self.table.setItem(r, 0, QTableWidgetItem(b.batch_number))
            self.table.setItem(r, 1, QTableWidgetItem(b.purchase_date.strftime("%d/%m/%Y")))
            self.table.setItem(r, 2, QTableWidgetItem(b.item.name if b.item else ""))
            self.table.setItem(r, 3, QTableWidgetItem(format_weight(b.net_weight_kg)))
            
            stock_item = QTableWidgetItem(format_weight(b.current_stock_kg))
            if b.current_stock_kg > 0:
                stock_item.setForeground(Qt.darkGreen)
            else:
                stock_item.setForeground(Qt.gray)
            self.table.setItem(r, 4, stock_item)

            # Status badge
            status_item = QTableWidgetItem(b.status)
            if b.status == "ACTIVE":
                status_item.setForeground(Qt.darkGreen)
            elif b.status == "DEPLETED":
                status_item.setForeground(Qt.darkYellow)
            else:
                status_item.setForeground(Qt.gray)
            self.table.setItem(r, 5, status_item)

            self.table.setItem(r, 6, QTableWidgetItem(b.closed_notes or ""))

            # Action buttons
            action_widget = QWidget()
            action_layout = QHBoxLayout(action_widget)
            action_layout.setContentsMargins(6, 2, 6, 2)
            action_layout.setSpacing(8)
            action_layout.setAlignment(Qt.AlignCenter)

            hist_btn = QPushButton("📜 History")
            hist_btn.setProperty("class", "actionDark")
            hist_btn.setToolTip("View full movement history and audit trail for this batch")
            hist_btn.clicked.connect(lambda _, bid=b.id: self._open_history(bid))
            action_layout.addWidget(hist_btn)

            if b.status != "CLOSED":
                finish_btn = QPushButton("🏁 Finish")
                finish_btn.setProperty("class", "actionFinish")
                finish_btn.setToolTip("Mark this batch as completely finished/closed")
                finish_btn.clicked.connect(lambda _, batch_obj=b: self._open_finish_batch(batch_obj))
                action_layout.addWidget(finish_btn)
            else:
                reopen_btn = QPushButton("🔓 Reopen")
                reopen_btn.setProperty("class", "actionReturn")
                reopen_btn.setToolTip("Reopen this closed batch")
                reopen_btn.clicked.connect(lambda _, bid=b.id: self._reopen_batch(bid))
                action_layout.addWidget(reopen_btn)

            self.table.setCellWidget(r, 7, action_widget)

    def _open_history(self, batch_id: int):
        dlg = BatchHistoryDialog(batch_id, self)
        dlg.exec()

    def _open_finish_batch(self, batch):
        dlg = FinishBatchDialog(batch, self)
        if dlg.exec() == QDialog.Accepted:
            self.refresh_table()

    def _reopen_batch(self, batch_id: int):
        reply = QMessageBox.question(
            self,
            "Reopen Batch",
            "Are you sure you want to reopen this closed batch?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            try:
                InventoryService.reopen_batch(batch_id, reason="User requested reopening from Batch Overview")
                QMessageBox.information(self, "Success", "Batch has been reopened.")
                self.refresh_table()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))
