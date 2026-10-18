from datetime import date
from decimal import Decimal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QFrame, QComboBox,
    QDoubleSpinBox, QSpinBox, QLineEdit, QDateEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QDialog, QFormLayout, QTextEdit
)
from PySide6.QtCore import Qt, QDate
from app.services.master_service import MasterService
from app.services.purchase_service import PurchaseService
from app.ui.components.date_range_picker import DateRangePicker
from app.utils.decimal_utils import format_currency, format_weight, to_decimal

class EditPurchaseDialog(QDialog):
    """
    Dialog for Editing an Existing Purchase record (modifying past purchase details).
    Supports boxes count, gross weight, box weight, and net weight.
    """
    def __init__(self, purchase, parent=None):
        super().__init__(parent)
        self.purchase = purchase
        self.setWindowTitle(f"Edit Purchase #{purchase.id}")
        self.resize(500, 460)

        layout = QFormLayout(self)

        q_date = QDate(purchase.transaction_date.year, purchase.transaction_date.month, purchase.transaction_date.day)
        self.date_edit = QDateEdit(q_date)
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("dd/MM/yyyy")

        self.provider_combo = QComboBox()
        for p in MasterService.get_all_providers():
            self.provider_combo.addItem(p.name, p.id)
        idx_p = self.provider_combo.findData(purchase.provider_id)
        if idx_p >= 0:
            self.provider_combo.setCurrentIndex(idx_p)

        self.item_combo = QComboBox()
        for i in MasterService.get_all_items():
            self.item_combo.addItem(i.name, i.id)
        idx_i = self.item_combo.findData(purchase.item_id)
        if idx_i >= 0:
            self.item_combo.setCurrentIndex(idx_i)

        self.box_count_spin = QSpinBox()
        self.box_count_spin.setRange(0, 99999)
        self.box_count_spin.setValue(int(getattr(purchase, "box_count", 0) or 0))

        gross_val = float(getattr(purchase, "gross_weight_kg", purchase.weight_kg) or purchase.weight_kg)
        self.gross_spin = QDoubleSpinBox()
        self.gross_spin.setRange(0.001, 999999.000)
        self.gross_spin.setDecimals(3)
        self.gross_spin.setSuffix(" KG")
        self.gross_spin.setValue(gross_val)

        box_val = float(getattr(purchase, "box_weight_kg", 0.000) or 0.000)
        self.box_spin = QDoubleSpinBox()
        self.box_spin.setRange(0.000, 999999.000)
        self.box_spin.setDecimals(3)
        self.box_spin.setSuffix(" KG")
        self.box_spin.setValue(box_val)

        self.net_label = QLabel("0.000 KG")
        self.net_label.setStyleSheet("font-weight: bold; color: #0369a1;")

        self.rate_spin = QDoubleSpinBox()
        self.rate_spin.setRange(0.00, 999999.00)
        self.rate_spin.setDecimals(2)
        self.rate_spin.setPrefix("₹ ")
        self.rate_spin.setValue(float(purchase.rate_per_kg))

        self.total_label = QLabel("₹0.00")
        self.total_label.setStyleSheet("font-weight: bold; font-size: 15px; color: #15803d;")

        self.pay_type_combo = QComboBox()
        self.pay_type_combo.addItems(["CASH", "BANK"])
        idx_pay = self.pay_type_combo.findText(purchase.payment_type)
        if idx_pay >= 0:
            self.pay_type_combo.setCurrentIndex(idx_pay)

        self.voucher_edit = QLineEdit(purchase.voucher_number if purchase.voucher_number else "")
        self.ref_edit = QLineEdit(purchase.bank_reference if purchase.bank_reference else "")

        self.notes_edit = QTextEdit(purchase.notes if purchase.notes else "")
        self.notes_edit.setMaximumHeight(60)

        # Connect signals for auto calculation & mode toggle
        self.gross_spin.valueChanged.connect(self._recalc)
        self.box_spin.valueChanged.connect(self._recalc)
        self.rate_spin.valueChanged.connect(self._recalc)
        self.pay_type_combo.currentIndexChanged.connect(self._on_pay_type_changed)

        layout.addRow("Transaction Date:", self.date_edit)
        layout.addRow("Provider:", self.provider_combo)
        layout.addRow("Chicken Item:", self.item_combo)
        layout.addRow("Number of Boxes:", self.box_count_spin)
        layout.addRow("Gross Weight (KG):", self.gross_spin)
        layout.addRow("Box Weight (KG):", self.box_spin)
        layout.addRow("Net Weight (AUTO):", self.net_label)
        layout.addRow("Rate (₹/KG):", self.rate_spin)
        layout.addRow("Total Amount (AUTO):", self.total_label)
        layout.addRow("Payment Type:", self.pay_type_combo)
        layout.addRow("Voucher #:", self.voucher_edit)
        layout.addRow("Bank Reference:", self.ref_edit)
        layout.addRow("Notes:", self.notes_edit)

        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Update Purchase")
        save_btn.setProperty("class", "primaryBtn")
        save_btn.clicked.connect(self._validate_and_accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setProperty("class", "secondaryBtn")
        cancel_btn.clicked.connect(self.reject)

        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(save_btn)

        layout.addRow(btn_layout)
        self._on_pay_type_changed()
        self._recalc()

    def _on_pay_type_changed(self):
        pay_type = self.pay_type_combo.currentText()
        if pay_type == "CASH":
            self.voucher_edit.setEnabled(True)
            self.ref_edit.setEnabled(False)
            self.voucher_edit.setPlaceholderText("Voucher # (REQUIRED)")
        else:
            self.voucher_edit.setEnabled(False)
            self.ref_edit.setEnabled(True)
            self.voucher_edit.setPlaceholderText("Voucher # (Not Required)")

    def _recalc(self):
        gross = Decimal(str(self.gross_spin.value()))
        box = Decimal(str(self.box_spin.value()))
        if box > gross:
            self.net_label.setText("INVALID (Box > Gross)")
            self.total_label.setText("₹0.00")
            return
        net = gross - box
        self.net_label.setText(format_weight(net))
        rate = Decimal(str(self.rate_spin.value()))
        total = net * rate
        self.total_label.setText(format_currency(total))

    def _validate_and_accept(self):
        pay_type = self.pay_type_combo.currentText()
        voucher = self.voucher_edit.text().strip()
        if pay_type == "CASH" and not voucher:
            QMessageBox.warning(self, "Validation Error", "Voucher number is MANDATORY for CASH payments.")
            return
        if self.gross_spin.value() <= 0:
            QMessageBox.warning(self, "Validation Error", "Gross weight must be greater than 0.")
            return
        if self.box_spin.value() > self.gross_spin.value():
            QMessageBox.warning(self, "Validation Error", "Box weight CANNOT be greater than gross weight.")
            return
        self.accept()

    def get_data(self):
        qd = self.date_edit.date()
        return {
            "transaction_date": date(qd.year(), qd.month(), qd.day()),
            "provider_id": self.provider_combo.currentData(),
            "item_id": self.item_combo.currentData(),
            "box_count": self.box_count_spin.value(),
            "gross_weight_kg": self.gross_spin.value(),
            "box_weight_kg": self.box_spin.value(),
            "rate_per_kg": self.rate_spin.value(),
            "payment_type": self.pay_type_combo.currentText(),
            "voucher_number": self.voucher_edit.text().strip() or None,
            "bank_reference": self.ref_edit.text().strip() or None,
            "notes": self.notes_edit.toPlainText().strip() or None
        }

class PurchasesView(QWidget):
    """
    Purchase Management View for fast chicken purchase data entry and editing past purchases.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        header = QLabel("Purchase Management")
        header.setStyleSheet("font-size: 20px; font-weight: bold; color: #0f172a;")
        layout.addWidget(header)

        # Fast Entry Form Frame
        form_frame = QFrame()
        form_frame.setProperty("class", "cardFrame")
        form_layout = QGridLayout(form_frame)
        form_layout.setSpacing(10)

        self.date_edit = QDateEdit(QDate.currentDate())
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("dd/MM/yyyy")

        self.provider_combo = QComboBox()
        self.item_combo = QComboBox()

        self.box_count_spin = QSpinBox()
        self.box_count_spin.setRange(0, 99999)
        self.box_count_spin.setValue(0)

        self.gross_spin = QDoubleSpinBox()
        self.gross_spin.setRange(0.000, 999999.000)
        self.gross_spin.setDecimals(3)
        self.gross_spin.setSuffix(" KG")

        self.box_spin = QDoubleSpinBox()
        self.box_spin.setRange(0.000, 999999.000)
        self.box_spin.setDecimals(3)
        self.box_spin.setSuffix(" KG")

        self.net_edit = QLineEdit("0.000 KG")
        self.net_edit.setReadOnly(True)
        self.net_edit.setStyleSheet("font-weight: bold; color: #0369a1; background-color: #f0f9ff;")

        self.rate_spin = QDoubleSpinBox()
        self.rate_spin.setRange(0.00, 999999.00)
        self.rate_spin.setDecimals(2)
        self.rate_spin.setPrefix("₹ ")

        self.amount_edit = QLineEdit("₹0.00")
        self.amount_edit.setReadOnly(True)
        self.amount_edit.setStyleSheet("font-weight: bold; color: #15803d; background-color: #f0fdf4;")

        self.pay_type_combo = QComboBox()
        self.pay_type_combo.addItems(["CASH", "BANK"])

        self.voucher_edit = QLineEdit()
        self.voucher_edit.setPlaceholderText("Voucher # (Required for CASH)")

        self.ref_edit = QLineEdit()
        self.ref_edit.setPlaceholderText("Bank Ref (Optional for BANK)")

        self.notes_edit = QLineEdit()
        self.notes_edit.setPlaceholderText("Notes/Remarks")

        save_btn = QPushButton("Save Purchase")
        save_btn.setProperty("class", "primaryBtn")
        save_btn.clicked.connect(self._save_purchase)

        # Live calculation
        self.gross_spin.valueChanged.connect(self._calculate_net_and_amount)
        self.box_spin.valueChanged.connect(self._calculate_net_and_amount)
        self.rate_spin.valueChanged.connect(self._calculate_net_and_amount)
        self.pay_type_combo.currentIndexChanged.connect(self._on_pay_type_changed)

        form_layout.addWidget(QLabel("Date:", self), 0, 0)
        form_layout.addWidget(self.date_edit, 0, 1)
        form_layout.addWidget(QLabel("Provider:", self), 0, 2)
        form_layout.addWidget(self.provider_combo, 0, 3)
        form_layout.addWidget(QLabel("Item / Chicken:", self), 0, 4)
        form_layout.addWidget(self.item_combo, 0, 5)

        form_layout.addWidget(QLabel("No. of Boxes:", self), 1, 0)
        form_layout.addWidget(self.box_count_spin, 1, 1)
        form_layout.addWidget(QLabel("Gross Weight (KG):", self), 1, 2)
        form_layout.addWidget(self.gross_spin, 1, 3)
        form_layout.addWidget(QLabel("Box Weight (KG):", self), 1, 4)
        form_layout.addWidget(self.box_spin, 1, 5)

        form_layout.addWidget(QLabel("<b>Net Weight (AUTO):</b>", self), 2, 0)
        form_layout.addWidget(self.net_edit, 2, 1)
        form_layout.addWidget(QLabel("Rate (₹/KG):", self), 2, 2)
        form_layout.addWidget(self.rate_spin, 2, 3)
        form_layout.addWidget(QLabel("<b>Total Amount:</b>", self), 2, 4)
        form_layout.addWidget(self.amount_edit, 2, 5)

        form_layout.addWidget(QLabel("Payment Type:", self), 3, 0)
        form_layout.addWidget(self.pay_type_combo, 3, 1)
        form_layout.addWidget(QLabel("Voucher #:", self), 3, 2)
        form_layout.addWidget(self.voucher_edit, 3, 3)
        form_layout.addWidget(QLabel("Bank Ref:", self), 3, 4)
        form_layout.addWidget(self.ref_edit, 3, 5)

        form_layout.addWidget(QLabel("Notes:", self), 4, 0)
        form_layout.addWidget(self.notes_edit, 4, 1, 1, 4)
        form_layout.addWidget(save_btn, 4, 5)

        layout.addWidget(form_frame)

        # Filter & Search Bar
        filter_layout = QHBoxLayout()
        self.date_picker = DateRangePicker()
        self.date_picker.date_range_changed.connect(self.refresh_table)

        filter_layout.addWidget(self.date_picker)
        filter_layout.addStretch()

        delete_btn = QPushButton("Delete Selected")
        delete_btn.setProperty("class", "dangerBtn")
        delete_btn.clicked.connect(self._delete_selected)
        filter_layout.addWidget(delete_btn)

        layout.addLayout(filter_layout)

        # Transactions Table
        self.table = QTableWidget(0, 13)
        self.table.setHorizontalHeaderLabels([
            "ID", "Date", "Provider", "Item", "Boxes", "Gross (KG)", "Box (KG)", "Net (KG)", "Rate (₹/KG)", "Amount", "Pay Type", "Voucher / Ref", "Actions"
        ])
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.table.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setMinimumSectionSize(75)
        self.table.horizontalHeader().setStretchLastSection(False)
        layout.addWidget(self.table)

        self._on_pay_type_changed()
        self.load_combos()
        self.refresh_table()

    def load_combos(self):
        self.provider_combo.clear()
        for p in MasterService.get_all_providers():
            self.provider_combo.addItem(p.name, p.id)

        self.item_combo.clear()
        for i in MasterService.get_all_items():
            self.item_combo.addItem(i.name, i.id)

    def _on_pay_type_changed(self):
        pay_type = self.pay_type_combo.currentText()
        if pay_type == "CASH":
            self.voucher_edit.setEnabled(True)
            self.ref_edit.setEnabled(False)
            self.voucher_edit.setPlaceholderText("Voucher # (REQUIRED)")
        else:
            self.voucher_edit.setEnabled(False)
            self.ref_edit.setEnabled(True)
            self.voucher_edit.setPlaceholderText("Voucher # (Not Required)")

    def _calculate_net_and_amount(self):
        gross = Decimal(str(self.gross_spin.value()))
        box = Decimal(str(self.box_spin.value()))
        if box > gross:
            self.net_edit.setText("INVALID (Box > Gross)")
            self.amount_edit.setText("₹0.00")
            return
        net = gross - box
        self.net_edit.setText(format_weight(net))
        rate = Decimal(str(self.rate_spin.value()))
        amt = net * rate
        self.amount_edit.setText(format_currency(amt))

    def _save_purchase(self):
        p_id = self.provider_combo.currentData()
        i_id = self.item_combo.currentData()
        if not p_id or not i_id:
            QMessageBox.warning(self, "Validation Error", "Please select a provider and chicken item.")
            return

        gross = self.gross_spin.value()
        box = self.box_spin.value()
        box_count = self.box_count_spin.value()
        rate = self.rate_spin.value()

        if gross <= 0:
            QMessageBox.warning(self, "Validation Error", "Gross weight must be greater than 0.")
            return
        if box > gross:
            QMessageBox.warning(self, "Validation Error", "Box weight CANNOT be greater than gross weight.")
            return

        pay_type = self.pay_type_combo.currentText()
        voucher = self.voucher_edit.text().strip()
        ref = self.ref_edit.text().strip()

        if pay_type == "CASH" and not voucher:
            QMessageBox.warning(self, "Validation Error", "Voucher number is MANDATORY for CASH payments.")
            return

        q_date = self.date_edit.date()
        t_date = date(q_date.year(), q_date.month(), q_date.day())

        try:
            PurchaseService.create_purchase(
                transaction_date=t_date,
                provider_id=p_id,
                item_id=i_id,
                gross_weight_kg=gross,
                box_weight_kg=box,
                box_count=box_count,
                rate_per_kg=rate,
                payment_type=pay_type,
                voucher_number=voucher,
                bank_reference=ref,
                notes=self.notes_edit.text()
            )
            QMessageBox.information(self, "Success", "Purchase transaction saved successfully!")
            self.box_count_spin.setValue(0)
            self.gross_spin.setValue(0.0)
            self.box_spin.setValue(0.0)
            self.rate_spin.setValue(0.0)
            self.voucher_edit.clear()
            self.ref_edit.clear()
            self.notes_edit.clear()
            self.refresh_table()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save purchase: {str(e)}")

    def refresh_table(self):
        start_d, end_d = self.date_picker.get_date_range()
        purchases = PurchaseService.get_purchases(start_date=start_d, end_date=end_d)

        self.table.setRowCount(0)
        for p in purchases:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(str(p.id)))
            self.table.setItem(r, 1, QTableWidgetItem(p.transaction_date.strftime("%d/%m/%Y")))
            self.table.setItem(r, 2, QTableWidgetItem(p.provider.name if p.provider else ""))
            self.table.setItem(r, 3, QTableWidgetItem(p.item.name if p.item else ""))
            self.table.setItem(r, 4, QTableWidgetItem(str(getattr(p, "box_count", 0) or 0)))
            self.table.setItem(r, 5, QTableWidgetItem(format_weight(getattr(p, "gross_weight_kg", p.weight_kg))))
            self.table.setItem(r, 6, QTableWidgetItem(format_weight(getattr(p, "box_weight_kg", Decimal("0.000")))))
            self.table.setItem(r, 7, QTableWidgetItem(format_weight(getattr(p, "net_weight_kg", p.weight_kg))))
            self.table.setItem(r, 8, QTableWidgetItem(format_currency(p.rate_per_kg)))
            self.table.setItem(r, 9, QTableWidgetItem(format_currency(p.total_amount)))
            self.table.setItem(r, 10, QTableWidgetItem(p.payment_type))
            self.table.setItem(r, 11, QTableWidgetItem(p.voucher_number or p.bank_reference or "-"))

            # Actions column with Edit button
            action_widget = QWidget()
            act_box = QHBoxLayout(action_widget)
            act_box.setContentsMargins(0, 0, 0, 0)
            act_box.setSpacing(4)

            edit_btn = QPushButton("Edit")
            edit_btn.setProperty("class", "secondaryBtn")
            edit_btn.clicked.connect(lambda _, pur_obj=p: self._edit_purchase(pur_obj))

            act_box.addWidget(edit_btn)
            self.table.setCellWidget(r, 12, action_widget)

    def _edit_purchase(self, purchase):
        dlg = EditPurchaseDialog(purchase=purchase, parent=self)
        if dlg.exec() == QDialog.Accepted:
            data = dlg.get_data()
            try:
                PurchaseService.update_purchase(purchase_id=purchase.id, **data)
                QMessageBox.information(self, "Success", f"Purchase #{purchase.id} updated successfully!")
                self.refresh_table()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to update purchase: {str(e)}")

    def _delete_selected(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Selection Required", "Please select a row to delete.")
            return

        pur_id = int(self.table.item(row, 0).text())
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Are you sure you want to delete purchase record #{pur_id}?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            PurchaseService.soft_delete_purchase(pur_id)
            self.refresh_table()
