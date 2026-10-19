from datetime import date
from decimal import Decimal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QFrame, QComboBox,
    QDoubleSpinBox, QLineEdit, QDateEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox
)
from PySide6.QtCore import Qt, QDate
from app.services.master_service import MasterService
from app.services.payment_service import PaymentService
from app.ui.components.date_range_picker import DateRangePicker
from app.utils.decimal_utils import format_currency

class CustomerPaymentsView(QWidget):
    """
    Customer Payments Entry View enforcing mandatory voucher numbers for CASH payments.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        header = QLabel("Customer Payments (Receipts)")
        header.setStyleSheet("font-size: 20px; font-weight: bold; color: #0f172a;")
        layout.addWidget(header)

        # Payment Entry Form
        form_frame = QFrame()
        form_frame.setProperty("class", "cardFrame")
        form_layout = QGridLayout(form_frame)
        form_layout.setSpacing(10)

        self.date_edit = QDateEdit(QDate.currentDate())
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("dd/MM/yyyy")

        self.customer_combo = QComboBox()

        self.amount_spin = QDoubleSpinBox()
        self.amount_spin.setRange(0.01, 9999999.00)
        self.amount_spin.setDecimals(2)
        self.amount_spin.setPrefix("₹ ")

        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["CASH", "BANK"])

        self.voucher_edit = QLineEdit()
        self.voucher_edit.setPlaceholderText("Customer Receipt Voucher # (Required for CASH)")

        self.ref_edit = QLineEdit()
        self.ref_edit.setPlaceholderText("Bank Ref (Optional for BANK)")

        self.notes_edit = QLineEdit()
        self.notes_edit.setPlaceholderText("Notes/Remarks")

        save_btn = QPushButton("Record Customer Payment")
        save_btn.setProperty("class", "primaryBtn")
        save_btn.clicked.connect(self._save_payment)

        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)

        form_layout.addWidget(QLabel("Date:", self), 0, 0)
        form_layout.addWidget(self.date_edit, 0, 1)
        form_layout.addWidget(QLabel("Customer:", self), 0, 2)
        form_layout.addWidget(self.customer_combo, 0, 3)
        form_layout.addWidget(QLabel("Amount:", self), 0, 4)
        form_layout.addWidget(self.amount_spin, 0, 5)

        form_layout.addWidget(QLabel("Payment Mode:", self), 1, 0)
        form_layout.addWidget(self.mode_combo, 1, 1)
        form_layout.addWidget(QLabel("Voucher #:", self), 1, 2)
        form_layout.addWidget(self.voucher_edit, 1, 3)
        form_layout.addWidget(QLabel("Bank Ref:", self), 1, 4)
        form_layout.addWidget(self.ref_edit, 1, 5)

        form_layout.addWidget(QLabel("Notes:", self), 2, 0)
        form_layout.addWidget(self.notes_edit, 2, 1, 1, 3)
        form_layout.addWidget(save_btn, 2, 5)

        layout.addWidget(form_frame)

        # Filters and History Table
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

        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels([
            "ID", "Date", "Customer", "Mode", "Voucher #", "Bank Ref", "Amount", "Actions"
        ])
        header = self.table.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(7, QHeaderView.Fixed)
        self.table.setColumnWidth(7, 120)
        self.table.verticalHeader().setDefaultSectionSize(42)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table, 1)

        self._on_mode_changed()
        self.load_combos()
        self.refresh_table()

    def load_combos(self):
        self.customer_combo.clear()
        for c in MasterService.get_all_customers():
            self.customer_combo.addItem(c.name, c.id)

    def _on_mode_changed(self):
        mode = self.mode_combo.currentText()
        if mode == "CASH":
            self.voucher_edit.setEnabled(True)
            self.ref_edit.setEnabled(False)
            self.voucher_edit.setPlaceholderText("Customer Voucher # (REQUIRED)")
        else:
            self.voucher_edit.setEnabled(False)
            self.ref_edit.setEnabled(True)
            self.voucher_edit.setPlaceholderText("Voucher # (Not Required)")

    def _save_payment(self):
        c_id = self.customer_combo.currentData()
        if not c_id:
            QMessageBox.warning(self, "Validation Error", "Please select a customer.")
            return

        amt = self.amount_spin.value()
        if amt <= 0:
            QMessageBox.warning(self, "Validation Error", "Amount must be greater than 0.")
            return

        mode = self.mode_combo.currentText()
        voucher = self.voucher_edit.text().strip()
        ref = self.ref_edit.text().strip()

        if mode == "CASH" and not voucher:
            QMessageBox.warning(self, "Validation Error", "Voucher number is MANDATORY for CASH payments.")
            return

        q_date = self.date_edit.date()
        p_date = date(q_date.year(), q_date.month(), q_date.day())

        try:
            PaymentService.create_customer_payment(
                payment_date=p_date,
                customer_id=c_id,
                amount=amt,
                payment_mode=mode,
                voucher_number=voucher,
                bank_reference=ref,
                notes=self.notes_edit.text()
            )
            QMessageBox.information(self, "Success", "Customer payment recorded successfully!")
            self.amount_spin.setValue(0.0)
            self.voucher_edit.clear()
            self.ref_edit.clear()
            self.notes_edit.clear()
            self.refresh_table()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to record payment: {str(e)}")

    def refresh_table(self):
        start_d, end_d = self.date_picker.get_date_range()
        payments = PaymentService.get_customer_payments(start_date=start_d, end_date=end_d)

        self.table.setRowCount(0)
        for p in payments:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(str(p.id)))
            self.table.setItem(r, 1, QTableWidgetItem(p.payment_date.strftime("%d/%m/%Y")))
            self.table.setItem(r, 2, QTableWidgetItem(p.customer.name if p.customer else ""))
            self.table.setItem(r, 3, QTableWidgetItem(p.payment_mode))
            self.table.setItem(r, 4, QTableWidgetItem(p.voucher_number or "-"))
            self.table.setItem(r, 5, QTableWidgetItem(p.bank_reference or "-"))
            self.table.setItem(r, 6, QTableWidgetItem(format_currency(p.amount)))

            action_widget = QWidget()
            act_box = QHBoxLayout(action_widget)
            act_box.setContentsMargins(6, 2, 6, 2)
            act_box.setAlignment(Qt.AlignCenter)

            del_btn = QPushButton("🗑️ Delete")
            del_btn.setProperty("class", "actionDelete")
            del_btn.setToolTip("Delete this customer payment")
            del_btn.clicked.connect(lambda _, pid=p.id: self._delete_payment_by_id(pid))
            act_box.addWidget(del_btn)

            self.table.setCellWidget(r, 7, action_widget)

    def _delete_payment_by_id(self, p_id: int):
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Are you sure you want to delete customer payment #{p_id}?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            PaymentService.soft_delete_customer_payment(p_id)
            self.refresh_table()

    def _delete_selected(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Selection Required", "Please select a row to delete.")
            return

        p_id = int(self.table.item(row, 0).text())
        self._delete_payment_by_id(p_id)
