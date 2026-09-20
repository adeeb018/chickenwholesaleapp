from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QLabel, QMessageBox
)
from PySide6.QtCore import Qt
from app.services.payment_service import PaymentService
from app.utils.decimal_utils import format_currency

class VoucherSearchDialog(QDialog):
    """
    Global modal dialog to search voucher numbers across Customer and Provider payment domains.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Global Voucher Search")
        self.resize(700, 400)

        layout = QVBoxLayout(self)

        search_layout = QHBoxLayout()
        self.voucher_input = QLineEdit()
        self.voucher_input.setPlaceholderText("Enter voucher number (e.g., P-501, C-1025)...")
        search_btn = QPushButton("Search")
        search_btn.setProperty("class", "primaryBtn")
        search_btn.clicked.connect(self._do_search)
        self.voucher_input.returnPressed.connect(self._do_search)

        search_layout.addWidget(QLabel("Voucher #:"))
        search_layout.addWidget(self.voucher_input)
        search_layout.addWidget(search_btn)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels([
            "Domain / Type", "Date", "Entity (Customer/Provider)", "Payment Mode", "Voucher #", "Amount"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        layout.addLayout(search_layout)
        layout.addWidget(self.table)

    def _do_search(self):
        v_num = self.voucher_input.text().strip()
        if not v_num:
            QMessageBox.warning(self, "Validation Error", "Please enter a voucher number to search.")
            return

        cust_payments, prov_payments = PaymentService.search_voucher(v_num)

        self.table.setRowCount(0)

        for cp in cust_payments:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem("CUSTOMER PAYMENT"))
            self.table.setItem(row, 1, QTableWidgetItem(cp.payment_date.strftime("%d/%m/%Y")))
            self.table.setItem(row, 2, QTableWidgetItem(cp.customer.name if cp.customer else "Unknown"))
            self.table.setItem(row, 3, QTableWidgetItem(cp.payment_mode))
            self.table.setItem(row, 4, QTableWidgetItem(cp.voucher_number or "N/A"))
            self.table.setItem(row, 5, QTableWidgetItem(format_currency(cp.amount)))

        for pp in prov_payments:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem("PROVIDER PAYMENT"))
            self.table.setItem(row, 1, QTableWidgetItem(pp.payment_date.strftime("%d/%m/%Y")))
            self.table.setItem(row, 2, QTableWidgetItem(pp.provider.name if pp.provider else "Unknown"))
            self.table.setItem(row, 3, QTableWidgetItem(pp.payment_mode))
            self.table.setItem(row, 4, QTableWidgetItem(pp.voucher_number or "N/A"))
            self.table.setItem(row, 5, QTableWidgetItem(format_currency(pp.amount)))

        if len(cust_payments) == 0 and len(prov_payments) == 0:
            QMessageBox.information(self, "No Results", f"No transactions found with voucher number '{v_num}'.")
