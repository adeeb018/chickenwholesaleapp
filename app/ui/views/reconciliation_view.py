from datetime import date
from decimal import Decimal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QFrame, QMessageBox,
    QDialog, QFormLayout, QLineEdit, QTextEdit, QDoubleSpinBox, QDateEdit,
    QComboBox, QGridLayout
)
from PySide6.QtCore import Qt, QDate
from app.services.reconciliation_service import ReconciliationService
from app.services.inventory_service import InventoryService
from app.utils.decimal_utils import format_weight, round_weight, to_decimal

class ReconcileBatchDialog(QDialog):
    """Dialog for entering physically weighed closing stock for a batch."""
    def __init__(self, batch_val=None, business_date: date = None, parent=None, is_correction=False, batch_id: int = None):
        super().__init__(parent)
        if business_date is None:
            business_date = date.today()
        if batch_val is None and batch_id is not None:
            batch_val = ReconciliationService.get_batch_reconciliation(batch_id, business_date)
        elif isinstance(batch_val, int):
            batch_id = batch_val
            batch_val = ReconciliationService.get_batch_reconciliation(batch_id, business_date)

        self.batch_val = batch_val
        self.business_date = business_date
        self.is_correction = is_correction
        self.batch = batch_val["batch"]

        title = f"Correct Reconciliation - {self.batch.batch_number}" if is_correction else f"Reconcile Stock - {self.batch.batch_number}"
        self.setWindowTitle(title)
        self.resize(520, 440)

        layout = QFormLayout(self)

        layout.addRow("Business Date:", QLabel(f"<b>{business_date.strftime('%d/%m/%Y')}</b>"))
        layout.addRow("Batch Number:", QLabel(f"<b>{self.batch.batch_number}</b>"))
        layout.addRow("Chicken Item:", QLabel(self.batch.item.name if self.batch.item else ""))
        layout.addRow("Opening Stock:", QLabel(format_weight(batch_val["opening_stock"])))
        layout.addRow("Stock Additions:", QLabel(format_weight(batch_val["stock_additions"])))
        layout.addRow("Today's Sales:", QLabel(format_weight(batch_val["sales"])))
        layout.addRow("Today's Returns:", QLabel(format_weight(batch_val["returns"])))
        
        calc_lbl = QLabel(format_weight(batch_val["calculated_closing"]))
        calc_lbl.setStyleSheet("font-size: 14px; font-weight: bold; color: #0369a1;")
        layout.addRow("<b>Calculated Expected Closing:</b>", calc_lbl)

        # Actual weight spinbox
        self.actual_spin = QDoubleSpinBox()
        self.actual_spin.setRange(0.000, 999999.000)
        self.actual_spin.setDecimals(3)
        self.actual_spin.setSuffix(" KG")
        initial_actual = float(batch_val["actual_closing"] if batch_val["actual_closing"] is not None else batch_val["calculated_closing"])
        self.actual_spin.setValue(initial_actual)
        layout.addRow("<b>Actual Physically Measured Weight:</b>", self.actual_spin)

        # Difference label
        self.diff_label = QLabel()
        self.diff_lbl = self.diff_label
        self.diff_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        layout.addRow("Discrepancy (Actual - Calc):", self.diff_label)

        # Reason presets
        self.reason_combo = QComboBox()
        self.reason_combo.setEditable(True)
        self.reason_combo.addItems([
            "Natural weight loss",
            "Weighing difference",
            "Damaged chicken",
            "Physical moisture shrinkage",
            "Other discrepancy"
        ])
        if batch_val.get("reason"):
            self.reason_combo.setCurrentText(batch_val["reason"])
        layout.addRow("Reason:", self.reason_combo)

        self.notes_edit = QTextEdit()
        self.notes_edit.setMaximumHeight(50)
        if batch_val.get("notes"):
            self.notes_edit.setText(batch_val["notes"])
        layout.addRow("Notes / Remarks:", self.notes_edit)

        self.actual_spin.valueChanged.connect(self._recalc_diff)
        self._recalc_diff()

        btn_box = QHBoxLayout()
        submit_btn = QPushButton("Save Reconciliation")
        submit_btn.setProperty("class", "primaryBtn")
        submit_btn.clicked.connect(self._submit)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setProperty("class", "secondaryBtn")
        cancel_btn.clicked.connect(self.reject)

        btn_box.addStretch()
        btn_box.addWidget(cancel_btn)
        btn_box.addWidget(submit_btn)
        layout.addRow(btn_box)

    def _recalc(self):
        self._recalc_diff()

    def _recalc_diff(self):
        actual = Decimal(str(self.actual_spin.value()))
        calc = self.batch_val["calculated_closing"]
        diff = round_weight(actual - calc)

        if diff < 0:
            self.diff_label.setText(f"{format_weight(diff)} (Stock Loss)")
            self.diff_label.setStyleSheet("color: #b91c1c; font-weight: bold;")
        elif diff > 0:
            self.diff_label.setText(f"+{format_weight(diff)} (Stock Gain)")
            self.diff_label.setStyleSheet("color: #15803d; font-weight: bold;")
        else:
            self.diff_label.setText("0.000 KG (Exact Match)")
            self.diff_label.setStyleSheet("color: #0369a1; font-weight: bold;")

    def _submit(self):
        actual = round_weight(self.actual_spin.value())
        if actual < 0:
            QMessageBox.warning(self, "Validation Error", "Actual closing stock cannot be negative.")
            return

        reason = self.reason_combo.currentText().strip()
        notes = self.notes_edit.toPlainText().strip()

        try:
            if self.is_correction:
                recon_id = self.batch_val["active_recon"].id
                ReconciliationService.correct_reconciliation(
                    reconciliation_id=recon_id,
                    new_actual_closing_stock=actual,
                    reason=reason or "Correction",
                    notes=notes
                )
                QMessageBox.information(self, "Success", "Reconciliation corrected successfully!")
            else:
                ReconciliationService.reconcile_batch(
                    batch_id=self.batch.id,
                    business_date=self.business_date,
                    actual_closing_stock=actual,
                    reason=reason,
                    notes=notes
                )
                QMessageBox.information(self, "Success", f"Batch '{self.batch.batch_number}' reconciled successfully!")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

class ReconciliationView(QWidget):
    """
    Daily Stock Reconciliation View.
    Allows entering end-of-day physical stock counts for batches and shows daily reconciliation summary.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        header = QLabel("⚖️ Daily Physical Stock Reconciliation")
        header.setStyleSheet("font-size: 20px; font-weight: bold; color: #0f172a;")
        layout.addWidget(header)

        # Date Bar & Controls
        ctrl_layout = QHBoxLayout()
        ctrl_layout.addWidget(QLabel("<b>Business Date:</b>"))

        self.date_edit = QDateEdit(QDate.currentDate())
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("dd/MM/yyyy")
        self.date_edit.dateChanged.connect(self.refresh_sheet)
        ctrl_layout.addWidget(self.date_edit)

        refresh_btn = QPushButton("🔄 Refresh Sheet")
        refresh_btn.setProperty("class", "secondaryBtn")
        refresh_btn.clicked.connect(self.refresh_sheet)
        ctrl_layout.addWidget(refresh_btn)

        ctrl_layout.addStretch()
        layout.addLayout(ctrl_layout)

        # Summary Metrics Frame
        self.summary_frame = QFrame()
        self.summary_frame.setStyleSheet("""
            QFrame {
                background-color: #f8fafc;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                padding: 12px;
            }
        """)
        self.summary_layout = QGridLayout(self.summary_frame)
        layout.addWidget(self.summary_frame)

        # Table
        self.table = QTableWidget(0, 11)
        self.table.setHorizontalHeaderLabels([
            "Batch Number", "Purchase Date", "Item", "Opening Stock", "Additions",
            "Sales", "Returns", "Expected Closing", "Actual Measured", "Difference", "Actions"
        ])
        self.table.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table)

        self.refresh_sheet()

    def on_view_activated(self):
        self.refresh_sheet()

    def get_selected_date(self) -> date:
        qd = self.date_edit.date()
        return date(qd.year(), qd.month(), qd.day())

    def refresh_sheet(self):
        b_date = self.get_selected_date()
        summary = ReconciliationService.get_daily_closing_summary(b_date)
        sheet = ReconciliationService.get_reconciliation_sheet(b_date)

        # Update summary widgets
        # Clear summary layout
        while self.summary_layout.count():
            item = self.summary_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        def add_metric(row, col, title, value, color="#0f172a"):
            w = QWidget()
            l = QVBoxLayout(w)
            l.setContentsMargins(5, 5, 5, 5)
            l.setSpacing(2)
            t_lbl = QLabel(title)
            t_lbl.setStyleSheet("font-size: 11px; color: #64748b; font-weight: 600;")
            v_lbl = QLabel(value)
            v_lbl.setStyleSheet(f"font-size: 15px; font-weight: bold; color: {color};")
            l.addWidget(t_lbl)
            l.addWidget(v_lbl)
            self.summary_layout.addWidget(w, row, col)

        add_metric(0, 0, "TOTAL BATCHES", str(summary["total_batches"]))
        add_metric(0, 1, "RECONCILED", f"{summary['reconciled_batches']} / {summary['total_batches']}", "#15803d")
        add_metric(0, 2, "AWAITING RECONCILIATION", str(summary["pending_batches"]), "#b45309" if summary["pending_batches"] > 0 else "#64748b")
        add_metric(0, 3, "EXPECTED CLOSING", format_weight(summary["total_expected_kg"]), "#0369a1")
        add_metric(0, 4, "ACTUAL CLOSING", format_weight(summary["total_actual_kg"]), "#0f172a")
        add_metric(0, 5, "TOTAL STOCK LOSS", format_weight(summary["total_loss_kg"]), "#b91c1c")
        add_metric(0, 6, "TOTAL STOCK GAIN", format_weight(summary["total_gain_kg"]), "#15803d")

        # Populate table
        self.table.setRowCount(0)
        for row in sheet:
            r = self.table.rowCount()
            self.table.insertRow(r)

            b = row["batch"]
            self.table.setItem(r, 0, QTableWidgetItem(b.batch_number))
            self.table.setItem(r, 1, QTableWidgetItem(b.purchase_date.strftime("%d/%m/%Y")))
            self.table.setItem(r, 2, QTableWidgetItem(b.item.name if b.item else ""))
            self.table.setItem(r, 3, QTableWidgetItem(format_weight(row["opening_stock"])))
            self.table.setItem(r, 4, QTableWidgetItem(format_weight(row["stock_additions"])))
            self.table.setItem(r, 5, QTableWidgetItem(format_weight(row["sales"])))
            self.table.setItem(r, 6, QTableWidgetItem(format_weight(row["returns"])))
            self.table.setItem(r, 7, QTableWidgetItem(format_weight(row["calculated_closing"])))

            actual_val = row["actual_closing"]
            diff_val = row["difference"]

            if actual_val is not None:
                self.table.setItem(r, 8, QTableWidgetItem(format_weight(actual_val)))
            else:
                pending_item = QTableWidgetItem("Awaiting Weighing")
                pending_item.setForeground(Qt.gray)
                self.table.setItem(r, 8, pending_item)

            if diff_val is not None:
                diff_str = f"+{format_weight(diff_val)}" if diff_val > 0 else format_weight(diff_val)
                diff_item = QTableWidgetItem(diff_str)
                if diff_val < 0:
                    diff_item.setForeground(Qt.darkRed)
                elif diff_val > 0:
                    diff_item.setForeground(Qt.darkGreen)
                self.table.setItem(r, 9, diff_item)
            else:
                self.table.setItem(r, 9, QTableWidgetItem("-"))

            # Action button
            action_btn = QPushButton("✏️ Correct" if row["is_reconciled"] else "⚖️ Reconcile")
            action_btn.setProperty("class", "secondaryBtn" if row["is_reconciled"] else "primaryBtn")
            action_btn.setStyleSheet("padding: 3px 8px; font-size: 11px;")
            action_btn.clicked.connect(lambda _, r_val=row: self._open_reconcile_dialog(r_val))
            self.table.setCellWidget(r, 10, action_btn)

    def _open_reconcile_dialog(self, batch_val):
        b_date = self.get_selected_date()
        is_corr = batch_val["is_reconciled"]
        dlg = ReconcileBatchDialog(batch_val, b_date, self, is_correction=is_corr)
        if dlg.exec() == QDialog.Accepted:
            self.refresh_sheet()
