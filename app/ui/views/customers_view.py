from datetime import date
from decimal import Decimal
from typing import Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QDialog, QFormLayout, QDoubleSpinBox, QDateEdit,
    QMessageBox, QTextEdit
)
from PySide6.QtCore import Qt, QDate, Signal
from app.services.master_service import MasterService
from app.services.balance_service import BalanceService
from app.services.statement_print_service import StatementPrintService
from app.ui.components.date_range_picker import DateRangePicker
from app.ui.components.table_utils import enable_table_copy_and_tooltips, create_table_item
from app.ui.views.customer_rate_adjustments_dialog import CustomerRateAdjustmentsDialog
from app.utils.decimal_utils import format_currency

class CustomerDialog(QDialog):
    """
    Dialog for Adding or Editing Customer Master record including Opening Balance & Date.
    """
    def __init__(self, customer=None, parent=None):
        super().__init__(parent)
        self.customer = customer
        self.setWindowTitle("Edit Customer" if customer else "Add New Customer")
        self.resize(450, 350)

        layout = QFormLayout(self)

        self.name_edit = QLineEdit(customer.name if customer else "")
        self.phone_edit = QLineEdit(customer.phone if customer and customer.phone else "")
        self.address_edit = QLineEdit(customer.address if customer and customer.address else "")
        
        op_val = float(customer.opening_balance.amount) if customer and customer.opening_balance else 0.0
        self.op_balance_spin = QDoubleSpinBox()
        self.op_balance_spin.setRange(-9999999.00, 9999999.00)
        self.op_balance_spin.setDecimals(2)
        self.op_balance_spin.setPrefix("₹ ")
        self.op_balance_spin.setValue(op_val)

        op_d = customer.opening_balance.as_of_date if customer and customer.opening_balance else date.today()
        self.op_date_edit = QDateEdit(QDate(op_d.year, op_d.month, op_d.day))
        self.op_date_edit.setCalendarPopup(True)
        self.op_date_edit.setDisplayFormat("dd/MM/yyyy")

        self.notes_edit = QTextEdit(customer.notes if customer and customer.notes else "")
        self.notes_edit.setMaximumHeight(70)

        layout.addRow("Customer Name*:", self.name_edit)
        layout.addRow("Phone Number:", self.phone_edit)
        layout.addRow("Address:", self.address_edit)
        layout.addRow("Opening Balance:", self.op_balance_spin)
        layout.addRow("Opening Balance Date:", self.op_date_edit)
        layout.addRow("Notes:", self.notes_edit)

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
        q_d = self.op_date_edit.date()
        return {
            "name": self.name_edit.text().strip(),
            "phone": self.phone_edit.text().strip() or None,
            "address": self.address_edit.text().strip() or None,
            "opening_balance": self.op_balance_spin.value(),
            "opening_balance_date": date(q_d.year(), q_d.month(), q_d.day()),
            "notes": self.notes_edit.toPlainText().strip() or None
        }

class CustomerLedgerDialog(QDialog):
    """
    Customer Statement / Ledger Viewer Dialog with period selection.
    """
    def __init__(self, customer_id: int, parent=None):
        super().__init__(parent)
        self.customer_id = customer_id
        self.current_stmt = None
        self.setWindowTitle("Customer Statement & Ledger")
        self.resize(850, 500)

        layout = QVBoxLayout(self)

        top_layout = QHBoxLayout()
        self.date_picker = DateRangePicker()
        self.date_picker.date_range_changed.connect(self.refresh_ledger)
        top_layout.addWidget(self.date_picker)
        top_layout.addStretch()

        self.print_btn = QPushButton("🖨️ Print Statement")
        self.print_btn.setProperty("class", "secondaryBtn")
        self.print_btn.clicked.connect(self._on_print)
        top_layout.addWidget(self.print_btn)

        self.pdf_btn = QPushButton("📄 Save PDF")
        self.pdf_btn.setProperty("class", "secondaryBtn")
        self.pdf_btn.clicked.connect(self._on_export_pdf)
        top_layout.addWidget(self.pdf_btn)

        layout.addLayout(top_layout)

        self.summary_label = QLabel()
        self.summary_label.setStyleSheet("font-size: 14px; font-weight: bold; background-color: #f8fafc; padding: 10px; border-radius: 6px;")
        layout.addWidget(self.summary_label)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels([
            "Date", "Description", "Debit (Sale)", "Credit (Payment)", "Balance"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table)

        self.refresh_ledger()

    def refresh_ledger(self):
        start_d, end_d = self.date_picker.get_date_range()
        stmt = BalanceService.get_customer_statement(self.customer_id, start_d, end_d)
        if not stmt:
            self.current_stmt = None
            return

        self.current_stmt = stmt

        self.summary_label.setText(
            f"Customer: {stmt.customer_name} | Period Opening: {format_currency(stmt.period_opening_balance)} | "
            f"Sales: {format_currency(stmt.total_sales_amount)} ({stmt.total_net_weight_kg:.3f} KG) | "
            f"Payments: {format_currency(stmt.total_payments)} | Closing Balance: {format_currency(stmt.closing_balance)}"
        )

        self.table.setRowCount(0)
        for entry in stmt.ledger_entries:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(entry.entry_date.strftime("%d/%m/%Y")))
            self.table.setItem(r, 1, QTableWidgetItem(entry.description))
            self.table.setItem(r, 2, QTableWidgetItem(format_currency(entry.debit) if entry.debit > 0 else "-"))
            self.table.setItem(r, 3, QTableWidgetItem(format_currency(entry.credit) if entry.credit > 0 else "-"))
            self.table.setItem(r, 4, QTableWidgetItem(format_currency(entry.running_balance)))

    def _on_print(self):
        if not self.current_stmt:
            return
        StatementPrintService.print_statement(self.current_stmt, parent=self, is_provider=False)

    def _on_export_pdf(self):
        if not self.current_stmt:
            return
        StatementPrintService.export_pdf(self.current_stmt, parent=self, is_provider=False)


class CustomersView(QWidget):
    """
    Customer Master Screen with Add, Edit, Delete, and Ledger Statement views.
    """
    customers_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        header_layout = QHBoxLayout()
        header = QLabel("Customer Management")
        header.setStyleSheet("font-size: 20px; font-weight: bold; color: #0f172a;")
        
        add_btn = QPushButton("+ Add Customer")
        add_btn.setProperty("class", "primaryBtn")
        add_btn.clicked.connect(self._add_customer)

        adj_btn = QPushButton("🏷️ Rate Adjustments")
        adj_btn.setProperty("class", "secondaryBtn")
        adj_btn.clicked.connect(lambda: self._open_rate_adjustments())

        header_layout.addWidget(header)
        header_layout.addStretch()
        header_layout.addWidget(adj_btn)
        header_layout.addWidget(add_btn)
        layout.addLayout(header_layout)

        # Search Bar
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search customer name or phone...")
        self.search_input.textChanged.connect(self.refresh_table)
        search_layout.addWidget(self.search_input)
        layout.addLayout(search_layout)

        # Customer List Table
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels([
            "ID", "Customer Name", "Phone", "Opening Balance", "Current Outstanding", "Actions"
        ])
        header = self.table.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(5, QHeaderView.Fixed)
        self.table.setColumnWidth(5, 380)
        self.table.verticalHeader().setDefaultSectionSize(48)
        self.table.verticalHeader().setVisible(False)
        enable_table_copy_and_tooltips(self.table)
        layout.addWidget(self.table, 1)

        self.refresh_table()

    def refresh_table(self):
        query_str = self.search_input.text().strip()
        customers = MasterService.get_all_customers()
        if query_str:
            customers = [c for c in customers if query_str.lower() in c.name.lower() or (c.phone and query_str in c.phone)]

        self.table.setRowCount(0)
        today = date.today()

        for c in customers:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, create_table_item(str(c.id), alignment=Qt.AlignCenter))
            self.table.setItem(r, 1, create_table_item(c.name, bold=True))
            self.table.setItem(r, 2, create_table_item(c.phone or "-", alignment=Qt.AlignCenter))
            
            op_amt = c.opening_balance.amount if c.opening_balance else Decimal("0.00")
            self.table.setItem(r, 3, create_table_item(format_currency(op_amt), alignment=Qt.AlignRight | Qt.AlignVCenter))

            stmt = BalanceService.get_customer_statement(c.id, date(2000, 1, 1), today)
            curr_bal = stmt.closing_balance if stmt else Decimal("0.00")
            self.table.setItem(r, 4, create_table_item(format_currency(curr_bal), alignment=Qt.AlignRight | Qt.AlignVCenter, bold=True))

            # Actions cell with View Ledger, Rate Adj, Edit, and Delete buttons
            action_widget = QWidget()
            act_box = QHBoxLayout(action_widget)
            act_box.setContentsMargins(4, 0, 4, 0)
            act_box.setSpacing(6)
            act_box.setAlignment(Qt.AlignCenter)

            ledger_btn = QPushButton("📄 Statement")
            ledger_btn.setProperty("class", "actionPrimary")
            ledger_btn.setToolTip("View full customer ledger and balance statement")
            ledger_btn.clicked.connect(lambda _, cid=c.id: self._view_ledger(cid))

            rate_adj_btn = QPushButton("📈 Rate Adj.")
            rate_adj_btn.setProperty("class", "actionDark")
            rate_adj_btn.setToolTip("Manage customized price adjustments for this customer")
            rate_adj_btn.clicked.connect(lambda _, cid=c.id: self._open_rate_adjustments(customer_id=cid))

            edit_btn = QPushButton("✏️ Edit")
            edit_btn.setProperty("class", "actionEdit")
            edit_btn.setToolTip("Edit customer details")
            edit_btn.clicked.connect(lambda _, cust=c: self._edit_customer(cust))

            delete_btn = QPushButton("🗑️ Delete")
            delete_btn.setProperty("class", "actionDelete")
            delete_btn.setToolTip("Delete this customer record")
            delete_btn.clicked.connect(lambda _, cust=c: self._delete_customer(cust))

            act_box.addWidget(ledger_btn)
            act_box.addWidget(rate_adj_btn)
            act_box.addWidget(edit_btn)
            act_box.addWidget(delete_btn)
            self.table.setCellWidget(r, 5, action_widget)

    def _open_rate_adjustments(self, customer_id: Optional[int] = None):
        dlg = CustomerRateAdjustmentsDialog(preselected_customer_id=customer_id, parent=self)
        dlg.exec()

    def _add_customer(self):
        dlg = CustomerDialog(parent=self)
        if dlg.exec() == QDialog.Accepted:
            data = dlg.get_data()
            if not data["name"]:
                QMessageBox.warning(self, "Validation Error", "Customer name is required.")
                return
            MasterService.create_customer(**data)
            self.refresh_table()
            self.customers_changed.emit()

    def _edit_customer(self, customer):
        dlg = CustomerDialog(customer=customer, parent=self)
        if dlg.exec() == QDialog.Accepted:
            data = dlg.get_data()
            if not data["name"]:
                QMessageBox.warning(self, "Validation Error", "Customer name is required.")
                return
            MasterService.update_customer(customer_id=customer.id, **data)
            self.refresh_table()
            self.customers_changed.emit()

    def _delete_customer(self, customer):
        reply = QMessageBox.question(
            self, "Confirm Delete Customer",
            f"Are you sure you want to delete customer '{customer.name}'?\n\nFinancial transaction history will be safely preserved.",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            MasterService.soft_delete_customer(customer.id)
            self.refresh_table()
            self.customers_changed.emit()

    def _view_ledger(self, customer_id: int):
        dlg = CustomerLedgerDialog(customer_id=customer_id, parent=self)
        dlg.exec()
