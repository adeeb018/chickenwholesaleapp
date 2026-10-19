from datetime import date
from decimal import Decimal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTabWidget, QComboBox, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QFrame, QMessageBox, QLineEdit, QGridLayout
)
from PySide6.QtGui import QColor
from PySide6.QtCore import Qt
from app.services.master_service import MasterService
from app.services.balance_service import BalanceService
from app.services.report_service import ReportService
from app.services.weight_loss_service import WeightLossService
from app.services.statement_print_service import StatementPrintService
from app.services.inventory_service import InventoryService
from app.services.customer_return_service import CustomerReturnService
from app.ui.views.batches_view import BatchHistoryDialog
from app.ui.components.date_range_picker import DateRangePicker
from app.ui.components.stat_card import StatCard
from app.ui.components.table_utils import enable_table_copy_and_tooltips, create_table_item
from app.utils.decimal_utils import format_currency, format_weight, round_weight, round_money, to_decimal

class CustomerFacingStatementTab(QWidget):
    """
    Customer Statement Tab - Customer Facing.
    CRITICAL RULE: MUST NOT show Box Weight! Uses only Net Weight, Rate, and Amount.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_stmt = None
        layout = QVBoxLayout(self)

        filter_layout = QHBoxLayout()
        self.customer_combo = QComboBox()
        self.customer_combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.customer_combo.setMinimumContentsLength(12)
        self.date_picker = DateRangePicker()
        self.date_picker.date_range_changed.connect(self.generate_report)
        self.customer_combo.currentIndexChanged.connect(self.generate_report)

        self.print_btn = QPushButton("🖨️ Print Statement")
        self.print_btn.setProperty("class", "secondaryBtn")
        self.print_btn.clicked.connect(self._on_print)

        self.pdf_btn = QPushButton("📄 Save PDF")
        self.pdf_btn.setProperty("class", "secondaryBtn")
        self.pdf_btn.clicked.connect(self._on_export_pdf)

        filter_layout.addWidget(QLabel("Customer:"))
        filter_layout.addWidget(self.customer_combo)
        filter_layout.addWidget(self.date_picker)
        filter_layout.addStretch()
        filter_layout.addWidget(self.print_btn)
        filter_layout.addWidget(self.pdf_btn)

        layout.addLayout(filter_layout)

        self.summary_card = QLabel()
        self.summary_card.setWordWrap(True)
        self.summary_card.setStyleSheet("font-size: 14px; font-weight: bold; background-color: #f0fdf4; padding: 12px; border-radius: 6px; border: 1px solid #bbf7d0;")
        layout.addWidget(self.summary_card)

        # Customer Statement Table - Strictly HIDES Box Weight!
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.table.setHorizontalHeaderLabels([
            "Date", "Item / Description", "Net Weight (KG)", "Rate (₹/KG)", "Sale Amount (₹)", "Discount (₹)", "Amount Received (₹)", "Balance (₹)"
        ])
        header = self.table.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setMinimumSectionSize(100)
        header.setStretchLastSection(False)
        self.table.verticalHeader().setDefaultSectionSize(48)
        self.table.verticalHeader().setVisible(False)
        enable_table_copy_and_tooltips(self.table)
        layout.addWidget(self.table)

        self.load_customers()

    def load_customers(self):
        current_id = self.customer_combo.currentData()
        self.customer_combo.blockSignals(True)
        self.customer_combo.clear()
        for c in MasterService.get_all_customers():
            self.customer_combo.addItem(c.name, c.id)
        if current_id is not None:
            idx = self.customer_combo.findData(current_id)
            if idx >= 0:
                self.customer_combo.setCurrentIndex(idx)
        self.customer_combo.blockSignals(False)
        self.generate_report()

    def generate_report(self):
        c_id = self.customer_combo.currentData()
        if not c_id:
            self.current_stmt = None
            self.summary_card.setText("No customer selected.")
            self.table.setRowCount(0)
            return

        start_d, end_d = self.date_picker.get_date_range()
        stmt = BalanceService.get_customer_statement(c_id, start_d, end_d)
        if not stmt:
            self.current_stmt = None
            self.summary_card.setText("Customer statement could not be loaded.")
            self.table.setRowCount(0)
            return

        self.current_stmt = stmt

        total_discount = sum(
            (entry.discount_amount for entry in stmt.ledger_entries if entry.discount_amount),
            Decimal("0.00")
        )
        disc_str = f" | Total Discount: {format_currency(total_discount)}" if total_discount > 0 else ""

        self.summary_card.setText(
            f"CUSTOMER STATEMENT — {stmt.customer_name.upper()}\n"
            f"Period: {start_d.strftime('%d/%m/%Y')} to {end_d.strftime('%d/%m/%Y')} | "
            f"Opening Balance: {format_currency(stmt.period_opening_balance)}\n"
            f"Total Net Weight: {format_weight(stmt.total_net_weight_kg)} | "
            f"Total Sales: {format_currency(stmt.total_sales_amount)}{disc_str} | "
            f"Total Payments Received: {format_currency(stmt.total_payments)}\n"
            f"Closing / Outstanding Balance: {format_currency(stmt.closing_balance)}"
        )

        self.table.setRowCount(0)

        # Add Opening Balance Row
        r = self.table.rowCount()
        self.table.insertRow(r)
        self.table.setItem(r, 0, create_table_item(start_d.strftime("%d/%m/%Y"), alignment=Qt.AlignCenter))
        self.table.setItem(r, 1, create_table_item("OPENING BALANCE", bold=True))
        self.table.setItem(r, 2, create_table_item("-", alignment=Qt.AlignCenter))
        self.table.setItem(r, 3, create_table_item("-", alignment=Qt.AlignCenter))
        self.table.setItem(r, 4, create_table_item("-", alignment=Qt.AlignCenter))
        self.table.setItem(r, 5, create_table_item("-", alignment=Qt.AlignCenter))
        self.table.setItem(r, 6, create_table_item("-", alignment=Qt.AlignCenter))
        self.table.setItem(r, 7, create_table_item(format_currency(stmt.period_opening_balance), alignment=Qt.AlignRight | Qt.AlignVCenter, bold=True))

        for entry in stmt.ledger_entries[1:]:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, create_table_item(entry.entry_date.strftime("%d/%m/%Y"), alignment=Qt.AlignCenter))
            self.table.setItem(r, 1, create_table_item(entry.description))
            
            # Net Weight
            if entry.net_weight_kg:
                self.table.setItem(r, 2, create_table_item(format_weight(entry.net_weight_kg), alignment=Qt.AlignRight | Qt.AlignVCenter))
            else:
                self.table.setItem(r, 2, create_table_item("-", alignment=Qt.AlignCenter))

            # Rate
            if entry.rate_per_kg:
                self.table.setItem(r, 3, create_table_item(format_currency(entry.rate_per_kg), alignment=Qt.AlignRight | Qt.AlignVCenter))
            else:
                self.table.setItem(r, 3, create_table_item("-", alignment=Qt.AlignCenter))

            # Sale Amount (Occurred), Discount, Amount Received
            if entry.transaction_type == "SALE" or entry.debit > 0:
                disc = entry.discount_amount or Decimal("0.00")
                if entry.net_weight_kg and entry.rate_per_kg:
                    gross_sale = entry.net_weight_kg * entry.rate_per_kg
                else:
                    gross_sale = entry.debit + disc

                self.table.setItem(r, 4, create_table_item(format_currency(gross_sale), alignment=Qt.AlignRight | Qt.AlignVCenter))
                self.table.setItem(r, 5, create_table_item(format_currency(disc) if disc > 0 else "-", alignment=Qt.AlignRight | Qt.AlignVCenter))
                self.table.setItem(r, 6, create_table_item("-", alignment=Qt.AlignCenter))
            elif entry.transaction_type == "PAYMENT_RECEIVED" or entry.credit > 0:
                self.table.setItem(r, 4, create_table_item("-", alignment=Qt.AlignCenter))
                self.table.setItem(r, 5, create_table_item("-", alignment=Qt.AlignCenter))
                self.table.setItem(r, 6, create_table_item(format_currency(entry.credit), alignment=Qt.AlignRight | Qt.AlignVCenter))
            else:
                self.table.setItem(r, 4, create_table_item("-", alignment=Qt.AlignCenter))
                self.table.setItem(r, 5, create_table_item("-", alignment=Qt.AlignCenter))
                self.table.setItem(r, 6, create_table_item("-", alignment=Qt.AlignCenter))

            # Running Balance
            self.table.setItem(r, 7, create_table_item(format_currency(entry.running_balance), alignment=Qt.AlignRight | Qt.AlignVCenter, bold=True))

    def _on_print(self):
        if not self.current_stmt:
            QMessageBox.warning(self, "No Statement", "Please select a customer to print statement.")
            return
        StatementPrintService.print_statement(self.current_stmt, parent=self, is_provider=False)

    def _on_export_pdf(self):
        if not self.current_stmt:
            QMessageBox.warning(self, "No Statement", "Please select a customer to export statement.")
            return
        StatementPrintService.export_pdf(self.current_stmt, parent=self, is_provider=False)

class ProviderFacingStatementTab(QWidget):
    """
    Provider Statement Tab - Supplier / Provider Facing.
    Displays transactions with the provider: Purchases (Weight in KG, Rate, Purchase Amount)
    and Payments Made (Amount Paid), with Opening Balance and Running Balance.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_stmt = None
        layout = QVBoxLayout(self)

        filter_layout = QHBoxLayout()
        self.provider_combo = QComboBox()
        self.provider_combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.provider_combo.setMinimumContentsLength(12)
        self.date_picker = DateRangePicker()
        self.date_picker.date_range_changed.connect(self.generate_report)
        self.provider_combo.currentIndexChanged.connect(self.generate_report)

        self.print_btn = QPushButton("🖨️ Print Statement")
        self.print_btn.setProperty("class", "secondaryBtn")
        self.print_btn.clicked.connect(self._on_print)

        self.pdf_btn = QPushButton("📄 Save PDF")
        self.pdf_btn.setProperty("class", "secondaryBtn")
        self.pdf_btn.clicked.connect(self._on_export_pdf)

        filter_layout.addWidget(QLabel("Provider:"))
        filter_layout.addWidget(self.provider_combo)
        filter_layout.addWidget(self.date_picker)
        filter_layout.addStretch()
        filter_layout.addWidget(self.print_btn)
        filter_layout.addWidget(self.pdf_btn)

        layout.addLayout(filter_layout)

        self.summary_card = QLabel()
        self.summary_card.setWordWrap(True)
        self.summary_card.setStyleSheet("font-size: 14px; font-weight: bold; background-color: #eff6ff; padding: 12px; border-radius: 6px; border: 1px solid #bfdbfe;")
        layout.addWidget(self.summary_card)

        # Provider Statement Table
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.table.setHorizontalHeaderLabels([
            "Date", "Item / Description", "Weight (KG)", "Rate (₹/KG)", "Purchase Amount (₹)", "Amount Paid (₹)", "Balance (₹)"
        ])
        header = self.table.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setMinimumSectionSize(100)
        header.setStretchLastSection(False)
        self.table.verticalHeader().setDefaultSectionSize(48)
        self.table.verticalHeader().setVisible(False)
        enable_table_copy_and_tooltips(self.table)
        layout.addWidget(self.table)

        self.load_providers()

    def load_providers(self):
        current_id = self.provider_combo.currentData()
        self.provider_combo.blockSignals(True)
        self.provider_combo.clear()
        for p in MasterService.get_all_providers():
            self.provider_combo.addItem(p.name, p.id)
        if current_id is not None:
            idx = self.provider_combo.findData(current_id)
            if idx >= 0:
                self.provider_combo.setCurrentIndex(idx)
        self.provider_combo.blockSignals(False)
        self.generate_report()

    def generate_report(self):
        p_id = self.provider_combo.currentData()
        if not p_id:
            self.current_stmt = None
            self.summary_card.setText("No provider selected.")
            self.table.setRowCount(0)
            return

        start_d, end_d = self.date_picker.get_date_range()
        stmt = BalanceService.get_provider_statement(p_id, start_d, end_d)
        if not stmt:
            self.current_stmt = None
            self.summary_card.setText("Provider statement could not be loaded.")
            self.table.setRowCount(0)
            return

        self.current_stmt = stmt

        self.summary_card.setText(
            f"PROVIDER STATEMENT — {stmt.provider_name.upper()}\n"
            f"Period: {start_d.strftime('%d/%m/%Y')} to {end_d.strftime('%d/%m/%Y')} | "
            f"Opening Balance: {format_currency(stmt.period_opening_balance)}\n"
            f"Total Weight: {format_weight(stmt.total_purchase_weight_kg)} | "
            f"Total Purchases: {format_currency(stmt.total_purchases_amount)} | "
            f"Total Payments Made: {format_currency(stmt.total_payments)}\n"
            f"Closing / Payable Balance: {format_currency(stmt.closing_balance)}"
        )

        self.table.setRowCount(0)

        # Add Opening Balance Row
        r = self.table.rowCount()
        self.table.insertRow(r)
        self.table.setItem(r, 0, create_table_item(start_d.strftime("%d/%m/%Y"), alignment=Qt.AlignCenter))
        self.table.setItem(r, 1, create_table_item("OPENING BALANCE", bold=True))
        self.table.setItem(r, 2, create_table_item("-", alignment=Qt.AlignCenter))
        self.table.setItem(r, 3, create_table_item("-", alignment=Qt.AlignCenter))
        self.table.setItem(r, 4, create_table_item("-", alignment=Qt.AlignCenter))
        self.table.setItem(r, 5, create_table_item("-", alignment=Qt.AlignCenter))
        self.table.setItem(r, 6, create_table_item(format_currency(stmt.period_opening_balance), alignment=Qt.AlignRight | Qt.AlignVCenter, bold=True))

        for entry in stmt.ledger_entries[1:]:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, create_table_item(entry.entry_date.strftime("%d/%m/%Y"), alignment=Qt.AlignCenter))
            self.table.setItem(r, 1, create_table_item(entry.description))
            
            # Weight
            if entry.net_weight_kg:
                self.table.setItem(r, 2, create_table_item(format_weight(entry.net_weight_kg), alignment=Qt.AlignRight | Qt.AlignVCenter))
            else:
                self.table.setItem(r, 2, create_table_item("-", alignment=Qt.AlignCenter))

            # Rate
            if entry.rate_per_kg:
                self.table.setItem(r, 3, create_table_item(format_currency(entry.rate_per_kg), alignment=Qt.AlignRight | Qt.AlignVCenter))
            else:
                self.table.setItem(r, 3, create_table_item("-", alignment=Qt.AlignCenter))

            # Purchase Amount (Occurred), Amount Paid
            if entry.transaction_type == "PURCHASE" or entry.credit > 0:
                self.table.setItem(r, 4, create_table_item(format_currency(entry.credit), alignment=Qt.AlignRight | Qt.AlignVCenter))
                self.table.setItem(r, 5, create_table_item("-", alignment=Qt.AlignCenter))
            elif entry.transaction_type == "PAYMENT_MADE" or entry.debit > 0:
                self.table.setItem(r, 4, create_table_item("-", alignment=Qt.AlignCenter))
                self.table.setItem(r, 5, create_table_item(format_currency(entry.debit), alignment=Qt.AlignRight | Qt.AlignVCenter))
            else:
                self.table.setItem(r, 4, create_table_item("-", alignment=Qt.AlignCenter))
                self.table.setItem(r, 5, create_table_item("-", alignment=Qt.AlignCenter))

            # Running Balance
            self.table.setItem(r, 6, create_table_item(format_currency(entry.running_balance), alignment=Qt.AlignRight | Qt.AlignVCenter, bold=True))

    def _on_print(self):
        if not self.current_stmt:
            QMessageBox.warning(self, "No Statement", "Please select a provider to print statement.")
            return
        StatementPrintService.print_statement(self.current_stmt, parent=self, is_provider=True)

    def _on_export_pdf(self):
        if not self.current_stmt:
            QMessageBox.warning(self, "No Statement", "Please select a provider to export statement.")
            return
        StatementPrintService.export_pdf(self.current_stmt, parent=self, is_provider=True)

# Friendly aliases
CustomerStatementTab = CustomerFacingStatementTab
ProviderStatementTab = ProviderFacingStatementTab

class InternalSalesReportTab(QWidget):
    """
    Internal Sales Report Tab for Shop Calculations & Weight Loss Analysis.
    Shows Gross Weight, Box Weight, Net Weight, Rate, Amount.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        top_layout = QHBoxLayout()
        self.date_picker = DateRangePicker()
        self.date_picker.date_range_changed.connect(self.generate_report)
        top_layout.addWidget(self.date_picker)

        top_layout.addWidget(QLabel("Customer:"))
        self.customer_combo = QComboBox()
        self.customer_combo.setMinimumWidth(180)
        self.load_customers()
        self.customer_combo.currentIndexChanged.connect(self.generate_report)
        top_layout.addWidget(self.customer_combo)

        top_layout.addStretch()
        layout.addLayout(top_layout)

        self.summary_label = QLabel()
        self.summary_label.setStyleSheet("font-size: 13px; font-weight: bold; background-color: #f1f5f9; padding: 10px; border-radius: 6px;")
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)

        self.table = QTableWidget(0, 11)
        self.table.setHorizontalHeaderLabels([
            "Date", "Customer", "Item", "Gross Weight (KG)", "Box Weight (KG)", "Net Weight (KG)", "Boxes", "Avg Wt/Box (KG)", "Rate (₹/KG)", "Discount (₹)", "Final Amount (₹)"
        ])
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        header = self.table.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setMinimumSectionSize(95)
        header.setStretchLastSection(False)
        self.table.verticalHeader().setDefaultSectionSize(48)
        self.table.verticalHeader().setVisible(False)
        enable_table_copy_and_tooltips(self.table)
        layout.addWidget(self.table)

        self.generate_report()

    def load_customers(self):
        prev_id = self.customer_combo.currentData() if hasattr(self, "customer_combo") else None
        self.customer_combo.blockSignals(True)
        self.customer_combo.clear()
        self.customer_combo.addItem("All", None)
        for c in MasterService.get_all_customers():
            self.customer_combo.addItem(c.name, c.id)

        if prev_id is not None:
            idx = self.customer_combo.findData(prev_id)
            if idx >= 0:
                self.customer_combo.setCurrentIndex(idx)
        else:
            self.customer_combo.setCurrentIndex(0)
        self.customer_combo.blockSignals(False)

    def generate_report(self):
        start_d, end_d = self.date_picker.get_date_range()
        cust_id = self.customer_combo.currentData() if hasattr(self, "customer_combo") else None
        summary = ReportService.get_sales_summary(start_d, end_d, customer_id=cust_id)

        tot_boxes = summary.get("total_boxes_count", 0)
        avg_box_str = format_weight(summary.get("avg_weight_per_box_kg", Decimal("0.000"))) if tot_boxes > 0 else "-"

        cust_title = f" - {self.customer_combo.currentText()}" if cust_id else ""

        self.summary_label.setText(
            f"INTERNAL SALES REPORT{cust_title} ({start_d.strftime('%d/%m/%Y')} - {end_d.strftime('%d/%m/%Y')}) | "
            f"Boxes: {tot_boxes} | "
            f"Gross: {format_weight(summary['total_gross_weight_kg'])} | "
            f"Box: {format_weight(summary['total_box_weight_kg'])} | "
            f"Net: {format_weight(summary['total_net_weight_kg'])} | "
            f"Avg Wt/Box: {avg_box_str} | "
            f"Discounts: {format_currency(summary['total_discount_amount'])} | "
            f"Final Sales: {format_currency(summary['total_amount'])}"
        )

        self.table.setRowCount(0)
        for s in summary["records"]:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, create_table_item(s.transaction_date.strftime("%d/%m/%Y"), alignment=Qt.AlignCenter))
            self.table.setItem(r, 1, create_table_item(s.customer.name if s.customer else ""))
            self.table.setItem(r, 2, create_table_item(s.item.name if s.item else ""))
            self.table.setItem(r, 3, create_table_item(format_weight(s.gross_weight_kg), alignment=Qt.AlignRight | Qt.AlignVCenter))
            self.table.setItem(r, 4, create_table_item(format_weight(s.box_weight_kg), alignment=Qt.AlignRight | Qt.AlignVCenter))
            self.table.setItem(r, 5, create_table_item(format_weight(s.net_weight_kg), alignment=Qt.AlignRight | Qt.AlignVCenter, bold=True))
            boxes = int(getattr(s, "box_count", 0) or 0)
            self.table.setItem(r, 6, create_table_item(str(boxes), alignment=Qt.AlignCenter))
            
            # Avg Weight per Box = Net Weight / Number of Boxes (for cross verification)
            net_val = to_decimal(s.net_weight_kg)
            if boxes > 0:
                avg_val = round_weight(net_val / boxes)
                avg_str = format_weight(avg_val)
            else:
                avg_str = "-"
            self.table.setItem(r, 7, create_table_item(avg_str, alignment=Qt.AlignRight | Qt.AlignVCenter))

            self.table.setItem(r, 8, create_table_item(format_currency(s.rate_per_kg), alignment=Qt.AlignRight | Qt.AlignVCenter))
            disc_val = getattr(s, "discount_amount", Decimal("0.00"))
            self.table.setItem(r, 9, create_table_item(format_currency(disc_val), alignment=Qt.AlignRight | Qt.AlignVCenter))
            self.table.setItem(r, 10, create_table_item(format_currency(s.total_amount), alignment=Qt.AlignRight | Qt.AlignVCenter, bold=True))

class WeightLossReportTab(QWidget):
    """
    Weight Loss Analysis Report Tab.
    Computes Batch-wise & Period-wide Weight Loss, accounting for:
    - Purchased Net Intake
    - Sold Net Weight
    - Customer Returns restocked
    - Remaining unsold stock currently in crates/inventory
    - Physical daily stock reconciliation discrepancies (shrinkage vs overage)
    - Batch completion/closure zeroing adjustments
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_summary = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # 1. Top Filters Row
        filter_layout = QHBoxLayout()
        self.date_picker = DateRangePicker()
        self.date_picker.date_range_changed.connect(self.generate_report)
        filter_layout.addWidget(self.date_picker)

        filter_layout.addWidget(QLabel("Status:"))
        self.status_combo = QComboBox()
        self.status_combo.addItems(["ALL", "ACTIVE", "DEPLETED", "CLOSED"])
        self.status_combo.currentIndexChanged.connect(self._apply_filters)
        filter_layout.addWidget(self.status_combo)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Filter by Batch #, Provider, Item...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self._apply_filters)
        filter_layout.addWidget(self.search_input)

        filter_layout.addStretch()

        self.refresh_btn = QPushButton("🔄 Refresh")
        self.refresh_btn.setProperty("class", "secondaryBtn")
        self.refresh_btn.clicked.connect(self.generate_report)
        filter_layout.addWidget(self.refresh_btn)

        layout.addLayout(filter_layout)

        # 2. KPI Summary Cards Grid (2 rows x 3 columns)
        cards_grid = QGridLayout()
        cards_grid.setSpacing(10)
        self.card_intake = StatCard("Total Intake (Purchased)", accent_color="#2563eb")
        self.card_sales = StatCard("Total Sold Net", accent_color="#059669")
        self.card_returns = StatCard("Customer Returns", accent_color="#d97706")
        self.card_stock = StatCard("Unsold In-Stock", accent_color="#7c3aed")
        self.card_recon = StatCard("Reconciliation Discrepancy", accent_color="#0891b2")
        self.card_loss = StatCard("Net Weight Loss", accent_color="#dc2626")

        cards_grid.addWidget(self.card_intake, 0, 0)
        cards_grid.addWidget(self.card_sales, 0, 1)
        cards_grid.addWidget(self.card_returns, 0, 2)
        cards_grid.addWidget(self.card_stock, 1, 0)
        cards_grid.addWidget(self.card_recon, 1, 1)
        cards_grid.addWidget(self.card_loss, 1, 2)
        layout.addLayout(cards_grid)

        # 3. Batch-Wise Weight Loss Breakdown Table
        self.table = QTableWidget(0, 14)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.table.setHorizontalHeaderLabels([
            "Batch #", "Date", "Provider", "Item", "Intake Net (KG)",
            "Sold Net (KG)", "Returns (KG)", "In-Stock (KG)", "Recon Loss (KG)",
            "Recon Gain (KG)", "Net Loss (KG)", "Loss %", "Status", "Actions"
        ])
        header = self.table.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setMinimumSectionSize(95)
        header.setStretchLastSection(False)
        header.setSectionResizeMode(13, QHeaderView.Fixed)
        self.table.setColumnWidth(13, 110)
        self.table.verticalHeader().setDefaultSectionSize(48)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        enable_table_copy_and_tooltips(self.table)
        layout.addWidget(self.table, 1)

    def generate_report(self):
        start_d, end_d = self.date_picker.get_date_range()
        self.current_summary = WeightLossService.get_weight_loss_summary(start_d, end_d)
        wl = self.current_summary

        # Update KPI Cards
        self.card_intake.set_data(
            value=format_weight(wl.total_purchased_kg),
            subtitle="Gross intake minus provider crates"
        )
        self.card_sales.set_data(
            value=format_weight(wl.total_sales_net_kg),
            subtitle=f"Gross: {format_weight(wl.total_sales_gross_kg)} | Box: {format_weight(wl.total_sales_box_kg)}"
        )
        self.card_returns.set_data(
            value=format_weight(wl.total_returns_net_kg),
            subtitle="Restocked from customer returns"
        )
        self.card_stock.set_data(
            value=format_weight(wl.total_remaining_stock_kg),
            subtitle="Unsold chicken sitting in active batches"
        )

        recon_net = wl.total_reconciled_gain_kg - wl.total_reconciled_loss_kg
        recon_sub = f"Loss: {format_weight(wl.total_reconciled_loss_kg)} | Gain: {format_weight(wl.total_reconciled_gain_kg)}"
        recon_str = f"+{format_weight(recon_net)}" if recon_net > 0 else format_weight(recon_net)
        self.card_recon.set_data(
            value=recon_str,
            subtitle=recon_sub
        )

        self.card_loss.set_data(
            value=f"{format_weight(wl.weight_loss_kg)}",
            subtitle=f"Loss Rate: {wl.weight_loss_percentage:.2f}% of intake"
        )

        self._apply_filters()

    def _apply_filters(self):
        if not self.current_summary:
            return

        status_filter = self.status_combo.currentText()
        search_query = self.search_input.text().strip().lower()

        filtered_batches = []
        for b in (self.current_summary.batch_details or []):
            if status_filter != "ALL" and b.status != status_filter:
                continue
            if search_query:
                combined = f"{b.batch_number} {b.provider_name} {b.item_name} {b.status}".lower()
                if search_query not in combined:
                    continue
            filtered_batches.append(b)

        self._populate_table(filtered_batches)

    def _populate_table(self, batches):
        self.table.setRowCount(0)

        tot_intake = Decimal("0.000")
        tot_sold = Decimal("0.000")
        tot_returns = Decimal("0.000")
        tot_stock = Decimal("0.000")
        tot_recon_loss = Decimal("0.000")
        tot_recon_gain = Decimal("0.000")
        tot_loss = Decimal("0.000")

        for b in batches:
            tot_intake += b.intake_net_kg
            tot_sold += b.sold_net_kg
            tot_returns += b.returned_net_kg
            tot_stock += b.remaining_stock_kg
            tot_recon_loss += b.reconciled_loss_kg
            tot_recon_gain += b.reconciled_gain_kg
            tot_loss += b.weight_loss_kg

            r = self.table.rowCount()
            self.table.insertRow(r)

            # 0: Batch #
            self.table.setItem(r, 0, create_table_item(b.batch_number, bold=True))

            # 1: Date
            self.table.setItem(r, 1, create_table_item(b.purchase_date.strftime("%d/%m/%Y") if b.purchase_date else "-", alignment=Qt.AlignCenter))

            # 2: Provider
            self.table.setItem(r, 2, create_table_item(b.provider_name or "Direct"))

            # 3: Item
            self.table.setItem(r, 3, create_table_item(b.item_name or "Chicken"))

            # 4: Intake Net (KG)
            self.table.setItem(r, 4, create_table_item(format_weight(b.intake_net_kg), alignment=Qt.AlignRight | Qt.AlignVCenter))

            # 5: Sold Net (KG)
            self.table.setItem(r, 5, create_table_item(format_weight(b.sold_net_kg), alignment=Qt.AlignRight | Qt.AlignVCenter))

            # 6: Returns (KG)
            self.table.setItem(r, 6, create_table_item(format_weight(b.returned_net_kg), alignment=Qt.AlignRight | Qt.AlignVCenter))

            # 7: In-Stock (KG)
            stock_color = QColor("#4338ca") if b.remaining_stock_kg > 0 else None
            self.table.setItem(r, 7, create_table_item(
                format_weight(b.remaining_stock_kg),
                alignment=Qt.AlignRight | Qt.AlignVCenter,
                bold=(b.remaining_stock_kg > 0),
                color=stock_color
            ))

            # 8: Recon Loss (KG)
            rl_color = QColor("#b91c1c") if b.reconciled_loss_kg > 0 else None
            self.table.setItem(r, 8, create_table_item(
                format_weight(b.reconciled_loss_kg),
                alignment=Qt.AlignRight | Qt.AlignVCenter,
                color=rl_color
            ))

            # 9: Recon Gain (KG)
            rg_color = QColor("#15803d") if b.reconciled_gain_kg > 0 else None
            self.table.setItem(r, 9, create_table_item(
                format_weight(b.reconciled_gain_kg),
                alignment=Qt.AlignRight | Qt.AlignVCenter,
                color=rg_color
            ))

            # 10: Weight Loss (KG)
            loss_str = format_weight(b.weight_loss_kg)
            if b.weight_loss_kg > 0:
                loss_color = QColor("#dc2626")
            elif b.weight_loss_kg < 0:
                loss_color = QColor("#16a34a")
            else:
                loss_color = QColor("#64748b")
            self.table.setItem(r, 10, create_table_item(
                loss_str,
                alignment=Qt.AlignRight | Qt.AlignVCenter,
                bold=True,
                color=loss_color
            ))

            # 11: Loss %
            pct_str = f"{b.weight_loss_percentage:.2f}%"
            self.table.setItem(r, 11, create_table_item(
                pct_str,
                alignment=Qt.AlignRight | Qt.AlignVCenter,
                color=loss_color
            ))

            # 12: Status
            if b.status == "ACTIVE":
                stat_color = QColor("#16a34a")
            elif b.status == "DEPLETED":
                stat_color = QColor("#d97706")
            else:
                stat_color = QColor("#64748b")
            self.table.setItem(r, 12, create_table_item(
                b.status,
                alignment=Qt.AlignCenter,
                color=stat_color
            ))

            # 13: Actions
            act_widget = QWidget()
            act_box = QHBoxLayout(act_widget)
            act_box.setContentsMargins(6, 0, 6, 0)
            act_box.setAlignment(Qt.AlignCenter)

            hist_btn = QPushButton("📜 History")
            hist_btn.setProperty("class", "actionDark")
            hist_btn.setToolTip("View full movement history and audit trail for this batch")
            hist_btn.clicked.connect(lambda _, bid=b.batch_id: self._show_history(bid))
            act_box.addWidget(hist_btn)
            self.table.setCellWidget(r, 13, act_widget)

        # Totals Summary Row (if any batches)
        if batches:
            r = self.table.rowCount()
            self.table.insertRow(r)
            f_bold = self.font()
            f_bold.setBold(True)
            tot_lbl = QTableWidgetItem("TOTALS")
            tot_lbl.setFont(f_bold)
            self.table.setItem(r, 0, tot_lbl)
            for c in (1, 2, 3, 12, 13):
                self.table.setItem(r, c, QTableWidgetItem(""))

            cols_vals = [
                (4, tot_intake),
                (5, tot_sold),
                (6, tot_returns),
                (7, tot_stock),
                (8, tot_recon_loss),
                (9, tot_recon_gain),
                (10, tot_loss),
            ]
            for col_idx, val in cols_vals:
                it = QTableWidgetItem(format_weight(val))
                it.setFont(f_bold)
                it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                if col_idx == 10:
                    if val > 0:
                        it.setForeground(QColor("#dc2626"))
                    elif val < 0:
                        it.setForeground(QColor("#16a34a"))
                self.table.setItem(r, col_idx, it)

            tot_pct = ((tot_loss / tot_intake) * Decimal("100")) if tot_intake > 0 else Decimal("0.00")
            pct_item = QTableWidgetItem(f"{tot_pct:.2f}%")
            pct_item.setFont(f_bold)
            pct_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            if tot_loss > 0:
                pct_item.setForeground(QColor("#dc2626"))
            elif tot_loss < 0:
                pct_item.setForeground(QColor("#16a34a"))
            self.table.setItem(r, 11, pct_item)

            for col_idx in range(14):
                cell = self.table.item(r, col_idx)
                if cell:
                    cell.setBackground(QColor("#f1f5f9"))

    def _show_history(self, batch_id: int):
        dlg = BatchHistoryDialog(batch_id, self)
        dlg.exec()

class BatchStockReportTab(QWidget):
    """
    Batch Inventory & Stock Report Tab.
    Provides batch-wise stock visibility, sold quantities, returns, reconciliation discrepancies, and sellable stock.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        top_layout = QHBoxLayout()
        self.date_picker = DateRangePicker()
        self.date_picker.date_range_changed.connect(self.generate_report)
        top_layout.addWidget(self.date_picker)

        top_layout.addWidget(QLabel("Status:"))
        self.status_combo = QComboBox()
        self.status_combo.addItems(["ALL", "ACTIVE", "DEPLETED", "CLOSED"])
        self.status_combo.currentIndexChanged.connect(self.generate_report)
        top_layout.addWidget(self.status_combo)

        top_layout.addStretch()
        layout.addLayout(top_layout)

        self.summary_card = QLabel()
        self.summary_card.setStyleSheet(
            "font-size: 13px; font-weight: bold; background-color: #f0f9ff; "
            "padding: 12px; border-radius: 6px; border: 1px solid #bae6fd; color: #0369a1;"
        )
        layout.addWidget(self.summary_card)

        self.table = QTableWidget(0, 10)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.table.setHorizontalHeaderLabels([
            "Batch #", "Item", "Status", "Purchased Date", "Purchased (KG)",
            "Sold (KG)", "Returns (KG)", "Loss / Gain (KG)", "Current Stock (KG)", "Actions"
        ])
        header = self.table.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setMinimumSectionSize(95)
        header.setStretchLastSection(False)
        header.setSectionResizeMode(9, QHeaderView.Fixed)
        self.table.setColumnWidth(9, 130)
        self.table.verticalHeader().setDefaultSectionSize(48)
        self.table.verticalHeader().setVisible(False)
        enable_table_copy_and_tooltips(self.table)
        layout.addWidget(self.table, 1)

    def generate_report(self):
        start_d, end_d = self.date_picker.get_date_range()
        status_filter = self.status_combo.currentText()
        if status_filter == "ALL":
            status_filter = None

        batches = InventoryService.get_batches(status=status_filter, start_date=start_d, end_date=end_d)

        tot_purchased = Decimal("0.000")
        tot_sold = Decimal("0.000")
        tot_returned = Decimal("0.000")
        tot_adj = Decimal("0.000")
        tot_stock = Decimal("0.000")

        self.table.setRowCount(0)
        for b in batches:
            hist = InventoryService.get_batch_history(b.id)
            purchased_wt = hist.get("total_purchased", b.net_weight_kg)
            sold_wt = hist.get("total_sold", Decimal("0.000"))
            ret_wt = hist.get("total_returned", Decimal("0.000"))
            loss_wt = hist.get("total_loss", Decimal("0.000"))
            gain_wt = hist.get("total_gain", Decimal("0.000"))
            adj_wt = gain_wt - loss_wt
            stock_wt = b.current_stock_kg

            tot_purchased += purchased_wt
            tot_sold += sold_wt
            tot_returned += ret_wt
            tot_adj += adj_wt
            tot_stock += stock_wt

            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, create_table_item(b.batch_number, bold=True))
            self.table.setItem(r, 1, create_table_item(b.item.name if b.item else ""))

            if b.status == "ACTIVE":
                stat_col = Qt.darkGreen
            elif b.status == "DEPLETED":
                stat_col = Qt.darkYellow
            else:
                stat_col = Qt.gray
            self.table.setItem(r, 2, create_table_item(b.status, alignment=Qt.AlignCenter, color=stat_col))

            self.table.setItem(r, 3, create_table_item(b.purchase_date.strftime("%d/%m/%Y"), alignment=Qt.AlignCenter))
            self.table.setItem(r, 4, create_table_item(format_weight(purchased_wt), alignment=Qt.AlignRight | Qt.AlignVCenter))
            self.table.setItem(r, 5, create_table_item(format_weight(sold_wt), alignment=Qt.AlignRight | Qt.AlignVCenter))
            self.table.setItem(r, 6, create_table_item(format_weight(ret_wt), alignment=Qt.AlignRight | Qt.AlignVCenter))

            adj_str = f"+{format_weight(adj_wt)}" if adj_wt > 0 else format_weight(adj_wt)
            adj_col = Qt.red if adj_wt < 0 else (Qt.darkGreen if adj_wt > 0 else None)
            self.table.setItem(r, 7, create_table_item(adj_str, alignment=Qt.AlignRight | Qt.AlignVCenter, color=adj_col))

            self.table.setItem(r, 8, create_table_item(format_weight(stock_wt), alignment=Qt.AlignRight | Qt.AlignVCenter, bold=True))

            act_widget = QWidget()
            act_box = QHBoxLayout(act_widget)
            act_box.setContentsMargins(6, 0, 6, 0)
            act_box.setAlignment(Qt.AlignCenter)

            act_btn = QPushButton("📜 History")
            act_btn.setProperty("class", "actionDark")
            act_btn.setToolTip("View full movement history and audit trail for this batch")
            act_btn.clicked.connect(lambda _, b_id=b.id: self._show_history(b_id))
            act_box.addWidget(act_btn)
            self.table.setCellWidget(r, 9, act_widget)

        self.summary_card.setText(
            f"BATCH INVENTORY SUMMARY | Total Batches: {len(batches)} | "
            f"Purchased: {format_weight(tot_purchased)} | "
            f"Sold: {format_weight(tot_sold)} | "
            f"Returns: {format_weight(tot_returned)} | "
            f"Net Adj (Loss/Gain): {format_weight(tot_adj)} | "
            f"Available Sellable Stock: {format_weight(tot_stock)}"
        )

    def _show_history(self, batch_id: int):
        dlg = BatchHistoryDialog(batch_id=batch_id, parent=self)
        dlg.exec()


class CustomerReturnsReportTab(QWidget):
    """
    Customer Returns Report Tab.
    Provides complete visibility into returned quantities, resale vs unsellable, and financial credits.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        top_layout = QHBoxLayout()
        self.date_picker = DateRangePicker()
        self.date_picker.date_range_changed.connect(self.generate_report)
        top_layout.addWidget(self.date_picker)

        top_layout.addWidget(QLabel("Customer:"))
        self.cust_combo = QComboBox()
        self.cust_combo.setMinimumWidth(160)
        self.load_customers()
        self.cust_combo.currentIndexChanged.connect(self.generate_report)
        top_layout.addWidget(self.cust_combo)

        top_layout.addStretch()
        layout.addLayout(top_layout)

        self.summary_card = QLabel()
        self.summary_card.setStyleSheet(
            "font-size: 13px; font-weight: bold; background-color: #fefce8; "
            "padding: 12px; border-radius: 6px; border: 1px solid #fef08a; color: #854d0e;"
        )
        layout.addWidget(self.summary_card)

        self.table = QTableWidget(0, 11)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.table.setHorizontalHeaderLabels([
            "Return #", "Date", "Customer", "Sale #", "Batch",
            "Gross (KG)", "Box (KG)", "Net (KG)", "Resale?", "Reason", "Credit Amount (₹)"
        ])
        header = self.table.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setMinimumSectionSize(95)
        header.setStretchLastSection(False)
        self.table.verticalHeader().setDefaultSectionSize(48)
        self.table.verticalHeader().setVisible(False)
        enable_table_copy_and_tooltips(self.table)
        layout.addWidget(self.table)

    def load_customers(self):
        self.cust_combo.blockSignals(True)
        self.cust_combo.clear()
        self.cust_combo.addItem("All Customers", None)
        for c in MasterService.get_all_customers():
            self.cust_combo.addItem(c.name, c.id)
        self.cust_combo.blockSignals(False)

    def generate_report(self):
        start_d, end_d = self.date_picker.get_date_range()
        c_id = self.cust_combo.currentData()

        returns = CustomerReturnService.get_returns(start_date=start_d, end_date=end_d, customer_id=c_id)

        tot_gross = Decimal("0.000")
        tot_box = Decimal("0.000")
        tot_net = Decimal("0.000")
        tot_resale = Decimal("0.000")
        tot_unsellable = Decimal("0.000")
        tot_credit = Decimal("0.00")

        self.table.setRowCount(0)
        for cr in returns:
            for line in cr.lines:
                tot_gross += line.returned_gross_weight_kg
                tot_box += line.returned_box_weight_kg
                tot_net += line.returned_net_weight_kg
                if line.resale_eligible:
                    tot_resale += line.returned_net_weight_kg
                else:
                    tot_unsellable += line.returned_net_weight_kg
                tot_credit += line.financial_amount

                r = self.table.rowCount()
                self.table.insertRow(r)
                self.table.setItem(r, 0, create_table_item(cr.return_number, bold=True))
                self.table.setItem(r, 1, create_table_item(cr.return_date.strftime("%d/%m/%Y"), alignment=Qt.AlignCenter))
                self.table.setItem(r, 2, create_table_item(cr.customer.name if cr.customer else ""))
                self.table.setItem(r, 3, create_table_item(f"#{cr.original_sale_id}" if cr.original_sale_id else "-", alignment=Qt.AlignCenter))
                self.table.setItem(r, 4, create_table_item(line.batch.batch_number if line.batch else "-"))
                self.table.setItem(r, 5, create_table_item(format_weight(line.returned_gross_weight_kg), alignment=Qt.AlignRight | Qt.AlignVCenter))
                self.table.setItem(r, 6, create_table_item(format_weight(line.returned_box_weight_kg), alignment=Qt.AlignRight | Qt.AlignVCenter))
                self.table.setItem(r, 7, create_table_item(format_weight(line.returned_net_weight_kg), alignment=Qt.AlignRight | Qt.AlignVCenter, bold=True))

                resale_str = "✅ Resellable" if line.resale_eligible else "❌ Unsellable"
                resale_col = Qt.darkGreen if line.resale_eligible else Qt.red
                self.table.setItem(r, 8, create_table_item(resale_str, alignment=Qt.AlignCenter, color=resale_col))

                self.table.setItem(r, 9, create_table_item(line.reason or "-"))
                self.table.setItem(r, 10, create_table_item(format_currency(line.financial_amount), alignment=Qt.AlignRight | Qt.AlignVCenter))

        self.summary_card.setText(
            f"CUSTOMER RETURNS SUMMARY | Total Records: {len(returns)} | "
            f"Returned Net Weight: {format_weight(tot_net)} | "
            f"Resellable: {format_weight(tot_resale)} | "
            f"Unsellable / Damaged: {format_weight(tot_unsellable)} | "
            f"Total Customer Credits: {format_currency(tot_credit)}"
        )


class ReportsView(QWidget):
    """
    Main Reports View container with tabs.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        header = QLabel("Reports Hub")
        header.setStyleSheet("font-size: 20px; font-weight: bold; color: #0f172a;")
        layout.addWidget(header)

        self.tabs = QTabWidget()
        self.cust_stmt_tab = CustomerFacingStatementTab()
        self.prov_stmt_tab = ProviderFacingStatementTab()
        self.internal_sales_tab = InternalSalesReportTab()
        self.weight_loss_tab = WeightLossReportTab()
        self.batch_stock_tab = BatchStockReportTab()
        self.returns_tab = CustomerReturnsReportTab()

        self.tabs.addTab(self.cust_stmt_tab, "Customer Statement (Client-Facing)")
        self.tabs.addTab(self.prov_stmt_tab, "Provider Statement (Supplier-Facing)")
        self.tabs.addTab(self.internal_sales_tab, "Internal Sales Summary")
        self.tabs.addTab(self.weight_loss_tab, "Weight Loss Analysis")
        self.tabs.addTab(self.batch_stock_tab, "Batch Inventory & Stock")
        self.tabs.addTab(self.returns_tab, "Customer Returns Report")

        layout.addWidget(self.tabs)

    def refresh_data(self):
        self.cust_stmt_tab.load_customers()
        self.prov_stmt_tab.load_providers()
        self.internal_sales_tab.load_customers()
        self.internal_sales_tab.generate_report()
        self.weight_loss_tab.generate_report()
        self.batch_stock_tab.generate_report()
        self.returns_tab.load_customers()
        self.returns_tab.generate_report()
