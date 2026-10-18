from datetime import date
from decimal import Decimal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QDialog, QFormLayout, QDoubleSpinBox, QDateEdit,
    QMessageBox, QTextEdit
)
from PySide6.QtCore import Qt, QDate
from app.services.master_service import MasterService
from app.services.balance_service import BalanceService
from app.services.statement_print_service import StatementPrintService
from app.ui.components.date_range_picker import DateRangePicker
from app.utils.decimal_utils import format_currency

class ProviderDialog(QDialog):
    """
    Dialog for Adding or Editing Provider Master record.
    """
    def __init__(self, provider=None, parent=None):
        super().__init__(parent)
        self.provider = provider
        self.setWindowTitle("Edit Provider" if provider else "Add New Provider")
        self.resize(450, 350)

        layout = QFormLayout(self)

        self.name_edit = QLineEdit(provider.name if provider else "")
        self.phone_edit = QLineEdit(provider.phone if provider and provider.phone else "")
        self.address_edit = QLineEdit(provider.address if provider and provider.address else "")
        
        op_val = float(provider.opening_balance.amount) if provider and provider.opening_balance else 0.0
        self.op_balance_spin = QDoubleSpinBox()
        self.op_balance_spin.setRange(-9999999.00, 9999999.00)
        self.op_balance_spin.setDecimals(2)
        self.op_balance_spin.setPrefix("₹ ")
        self.op_balance_spin.setValue(op_val)

        op_d = provider.opening_balance.as_of_date if provider and provider.opening_balance else date.today()
        self.op_date_edit = QDateEdit(QDate(op_d.year, op_d.month, op_d.day))
        self.op_date_edit.setCalendarPopup(True)
        self.op_date_edit.setDisplayFormat("dd/MM/yyyy")

        self.notes_edit = QTextEdit(provider.notes if provider and provider.notes else "")
        self.notes_edit.setMaximumHeight(70)

        layout.addRow("Provider Name*:", self.name_edit)
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

class ProviderLedgerDialog(QDialog):
    """
    Provider Statement / Ledger Viewer Dialog.
    """
    def __init__(self, provider_id: int, parent=None):
        super().__init__(parent)
        self.provider_id = provider_id
        self.current_stmt = None
        self.setWindowTitle("Provider Statement & Ledger")
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
            "Date", "Description", "Debit (Payment)", "Credit (Purchase)", "Balance"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table)

        self.refresh_ledger()

    def refresh_ledger(self):
        start_d, end_d = self.date_picker.get_date_range()
        stmt = BalanceService.get_provider_statement(self.provider_id, start_d, end_d)
        if not stmt:
            self.current_stmt = None
            return

        self.current_stmt = stmt

        self.summary_label.setText(
            f"Provider: {stmt.provider_name} | Period Opening: {format_currency(stmt.period_opening_balance)} | "
            f"Purchases: {format_currency(stmt.total_purchases_amount)} ({stmt.total_purchase_weight_kg:.3f} KG) | "
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
        StatementPrintService.print_statement(self.current_stmt, parent=self, is_provider=True)

    def _on_export_pdf(self):
        if not self.current_stmt:
            return
        StatementPrintService.export_pdf(self.current_stmt, parent=self, is_provider=True)


class ProvidersView(QWidget):
    """
    Provider Master Screen with Add, Edit, Delete, and Ledger Statement views.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        header_layout = QHBoxLayout()
        header = QLabel("Provider Management")
        header.setStyleSheet("font-size: 20px; font-weight: bold; color: #0f172a;")
        
        add_btn = QPushButton("+ Add Provider")
        add_btn.setProperty("class", "primaryBtn")
        add_btn.clicked.connect(self._add_provider)

        header_layout.addWidget(header)
        header_layout.addStretch()
        header_layout.addWidget(add_btn)
        layout.addLayout(header_layout)

        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search provider name or phone...")
        self.search_input.textChanged.connect(self.refresh_table)
        search_layout.addWidget(self.search_input)
        layout.addLayout(search_layout)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels([
            "ID", "Provider Name", "Phone", "Opening Balance", "Current Payable", "Actions"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table)

        self.refresh_table()

    def refresh_table(self):
        query_str = self.search_input.text().strip()
        providers = MasterService.get_all_providers()
        if query_str:
            providers = [p for p in providers if query_str.lower() in p.name.lower() or (p.phone and query_str in p.phone)]

        self.table.setRowCount(0)
        today = date.today()

        for p in providers:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(str(p.id)))
            self.table.setItem(r, 1, QTableWidgetItem(p.name))
            self.table.setItem(r, 2, QTableWidgetItem(p.phone or "-"))
            
            op_amt = p.opening_balance.amount if p.opening_balance else Decimal("0.00")
            self.table.setItem(r, 3, QTableWidgetItem(format_currency(op_amt)))

            stmt = BalanceService.get_provider_statement(p.id, date(2000, 1, 1), today)
            curr_bal = stmt.closing_balance if stmt else Decimal("0.00")
            self.table.setItem(r, 4, QTableWidgetItem(format_currency(curr_bal)))

            # Actions cell with View Ledger, Edit, and Delete buttons
            action_widget = QWidget()
            act_box = QHBoxLayout(action_widget)
            act_box.setContentsMargins(0, 0, 0, 0)
            act_box.setSpacing(4)

            ledger_btn = QPushButton("Statement")
            ledger_btn.setProperty("class", "secondaryBtn")
            ledger_btn.clicked.connect(lambda _, pid=p.id: self._view_ledger(pid))

            edit_btn = QPushButton("Edit")
            edit_btn.setProperty("class", "secondaryBtn")
            edit_btn.clicked.connect(lambda _, prov=p: self._edit_provider(prov))

            delete_btn = QPushButton("Delete")
            delete_btn.setProperty("class", "dangerBtn")
            delete_btn.clicked.connect(lambda _, prov=p: self._delete_provider(prov))

            act_box.addWidget(ledger_btn)
            act_box.addWidget(edit_btn)
            act_box.addWidget(delete_btn)
            self.table.setCellWidget(r, 5, action_widget)

    def _add_provider(self):
        dlg = ProviderDialog(parent=self)
        if dlg.exec() == QDialog.Accepted:
            data = dlg.get_data()
            if not data["name"]:
                QMessageBox.warning(self, "Validation Error", "Provider name is required.")
                return
            MasterService.create_provider(**data)
            self.refresh_table()

    def _edit_provider(self, provider):
        dlg = ProviderDialog(provider=provider, parent=self)
        if dlg.exec() == QDialog.Accepted:
            data = dlg.get_data()
            if not data["name"]:
                QMessageBox.warning(self, "Validation Error", "Provider name is required.")
                return
            MasterService.update_provider(provider_id=provider.id, **data)
            self.refresh_table()

    def _delete_provider(self, provider):
        reply = QMessageBox.question(
            self, "Confirm Delete Provider",
            f"Are you sure you want to delete provider '{provider.name}'?\n\nFinancial transaction history will be safely preserved.",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            MasterService.soft_delete_provider(provider.id)
            self.refresh_table()

    def _view_ledger(self, provider_id: int):
        dlg = ProviderLedgerDialog(provider_id=provider_id, parent=self)
        dlg.exec()
