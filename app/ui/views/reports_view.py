from datetime import date
from decimal import Decimal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTabWidget, QComboBox, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QFrame, QMessageBox
)
from PySide6.QtCore import Qt
from app.services.master_service import MasterService
from app.services.balance_service import BalanceService
from app.services.report_service import ReportService
from app.services.weight_loss_service import WeightLossService
from app.services.statement_print_service import StatementPrintService
from app.ui.components.date_range_picker import DateRangePicker
from app.utils.decimal_utils import format_currency, format_weight, round_weight, to_decimal

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
        self.summary_card.setStyleSheet("font-size: 14px; font-weight: bold; background-color: #f0fdf4; padding: 12px; border-radius: 6px; border: 1px solid #bbf7d0;")
        layout.addWidget(self.summary_card)

        # Customer Statement Table - Strictly HIDES Box Weight!
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels([
            "Date", "Item / Description", "Net Weight (KG)", "Rate (₹/KG)", "Sale Amount (₹)", "Discount (₹)", "Amount Received (₹)", "Balance (₹)"
        ])
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.table.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setMinimumSectionSize(90)
        self.table.horizontalHeader().setStretchLastSection(False)
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
        self.table.setItem(r, 0, QTableWidgetItem(start_d.strftime("%d/%m/%Y")))
        self.table.setItem(r, 1, QTableWidgetItem("OPENING BALANCE"))
        self.table.setItem(r, 2, QTableWidgetItem("-"))
        self.table.setItem(r, 3, QTableWidgetItem("-"))
        self.table.setItem(r, 4, QTableWidgetItem("-"))
        self.table.setItem(r, 5, QTableWidgetItem("-"))
        self.table.setItem(r, 6, QTableWidgetItem("-"))
        self.table.setItem(r, 7, QTableWidgetItem(format_currency(stmt.period_opening_balance)))

        for entry in stmt.ledger_entries[1:]:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(entry.entry_date.strftime("%d/%m/%Y")))
            self.table.setItem(r, 1, QTableWidgetItem(entry.description))
            
            # Net Weight
            if entry.net_weight_kg:
                self.table.setItem(r, 2, QTableWidgetItem(format_weight(entry.net_weight_kg)))
            else:
                self.table.setItem(r, 2, QTableWidgetItem("-"))

            # Rate
            if entry.rate_per_kg:
                self.table.setItem(r, 3, QTableWidgetItem(format_currency(entry.rate_per_kg)))
            else:
                self.table.setItem(r, 3, QTableWidgetItem("-"))

            # Sale Amount (Occurred), Discount, Amount Received
            if entry.transaction_type == "SALE" or entry.debit > 0:
                disc = entry.discount_amount or Decimal("0.00")
                if entry.net_weight_kg and entry.rate_per_kg:
                    gross_sale = entry.net_weight_kg * entry.rate_per_kg
                else:
                    gross_sale = entry.debit + disc

                self.table.setItem(r, 4, QTableWidgetItem(format_currency(gross_sale)))
                self.table.setItem(r, 5, QTableWidgetItem(format_currency(disc) if disc > 0 else "-"))
                self.table.setItem(r, 6, QTableWidgetItem("-"))
            elif entry.transaction_type == "PAYMENT_RECEIVED" or entry.credit > 0:
                self.table.setItem(r, 4, QTableWidgetItem("-"))
                self.table.setItem(r, 5, QTableWidgetItem("-"))
                self.table.setItem(r, 6, QTableWidgetItem(format_currency(entry.credit)))
            else:
                self.table.setItem(r, 4, QTableWidgetItem("-"))
                self.table.setItem(r, 5, QTableWidgetItem("-"))
                self.table.setItem(r, 6, QTableWidgetItem("-"))

            # Running Balance
            self.table.setItem(r, 7, QTableWidgetItem(format_currency(entry.running_balance)))

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
        self.summary_card.setStyleSheet("font-size: 14px; font-weight: bold; background-color: #eff6ff; padding: 12px; border-radius: 6px; border: 1px solid #bfdbfe;")
        layout.addWidget(self.summary_card)

        # Provider Statement Table
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels([
            "Date", "Item / Description", "Weight (KG)", "Rate (₹/KG)", "Purchase Amount (₹)", "Amount Paid (₹)", "Balance (₹)"
        ])
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.table.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setMinimumSectionSize(90)
        self.table.horizontalHeader().setStretchLastSection(False)
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
        self.table.setItem(r, 0, QTableWidgetItem(start_d.strftime("%d/%m/%Y")))
        self.table.setItem(r, 1, QTableWidgetItem("OPENING BALANCE"))
        self.table.setItem(r, 2, QTableWidgetItem("-"))
        self.table.setItem(r, 3, QTableWidgetItem("-"))
        self.table.setItem(r, 4, QTableWidgetItem("-"))
        self.table.setItem(r, 5, QTableWidgetItem("-"))
        self.table.setItem(r, 6, QTableWidgetItem(format_currency(stmt.period_opening_balance)))

        for entry in stmt.ledger_entries[1:]:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(entry.entry_date.strftime("%d/%m/%Y")))
            self.table.setItem(r, 1, QTableWidgetItem(entry.description))
            
            # Weight
            if entry.net_weight_kg:
                self.table.setItem(r, 2, QTableWidgetItem(format_weight(entry.net_weight_kg)))
            else:
                self.table.setItem(r, 2, QTableWidgetItem("-"))

            # Rate
            if entry.rate_per_kg:
                self.table.setItem(r, 3, QTableWidgetItem(format_currency(entry.rate_per_kg)))
            else:
                self.table.setItem(r, 3, QTableWidgetItem("-"))

            # Purchase Amount (Occurred), Amount Paid
            if entry.transaction_type == "PURCHASE" or entry.credit > 0:
                self.table.setItem(r, 4, QTableWidgetItem(format_currency(entry.credit)))
                self.table.setItem(r, 5, QTableWidgetItem("-"))
            elif entry.transaction_type == "PAYMENT_MADE" or entry.debit > 0:
                self.table.setItem(r, 4, QTableWidgetItem("-"))
                self.table.setItem(r, 5, QTableWidgetItem(format_currency(entry.debit)))
            else:
                self.table.setItem(r, 4, QTableWidgetItem("-"))
                self.table.setItem(r, 5, QTableWidgetItem("-"))

            # Running Balance
            self.table.setItem(r, 6, QTableWidgetItem(format_currency(entry.running_balance)))

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
        top_layout.addStretch()
        layout.addLayout(top_layout)

        self.summary_label = QLabel()
        self.summary_label.setStyleSheet("font-size: 13px; font-weight: bold; background-color: #f1f5f9; padding: 10px; border-radius: 6px;")
        layout.addWidget(self.summary_label)

        self.table = QTableWidget(0, 11)
        self.table.setHorizontalHeaderLabels([
            "Date", "Customer", "Item", "Boxes", "Gross Weight (KG)", "Box Weight (KG)", "Net Weight (KG)", "Avg Wt/Box (KG)", "Rate (₹/KG)", "Discount (₹)", "Final Amount (₹)"
        ])
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.table.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setMinimumSectionSize(85)
        self.table.horizontalHeader().setStretchLastSection(False)
        layout.addWidget(self.table)

    def generate_report(self):
        start_d, end_d = self.date_picker.get_date_range()
        summary = ReportService.get_sales_summary(start_d, end_d)

        tot_boxes = summary.get("total_boxes_count", 0)
        avg_box_str = format_weight(summary.get("avg_weight_per_box_kg", Decimal("0.000"))) if tot_boxes > 0 else "-"

        self.summary_label.setText(
            f"INTERNAL SALES REPORT ({start_d.strftime('%d/%m/%Y')} - {end_d.strftime('%d/%m/%Y')}) | "
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
            self.table.setItem(r, 0, QTableWidgetItem(s.transaction_date.strftime("%d/%m/%Y")))
            self.table.setItem(r, 1, QTableWidgetItem(s.customer.name if s.customer else ""))
            self.table.setItem(r, 2, QTableWidgetItem(s.item.name if s.item else ""))
            boxes = int(getattr(s, "box_count", 0) or 0)
            self.table.setItem(r, 3, QTableWidgetItem(str(boxes)))
            self.table.setItem(r, 4, QTableWidgetItem(format_weight(s.gross_weight_kg)))
            self.table.setItem(r, 5, QTableWidgetItem(format_weight(s.box_weight_kg)))
            self.table.setItem(r, 6, QTableWidgetItem(format_weight(s.net_weight_kg)))
            
            # Avg Weight per Box = Net Weight / Number of Boxes (for cross verification)
            net_val = to_decimal(s.net_weight_kg)
            if boxes > 0:
                avg_val = round_weight(net_val / boxes)
                avg_str = format_weight(avg_val)
            else:
                avg_str = "-"
            self.table.setItem(r, 7, QTableWidgetItem(avg_str))

            self.table.setItem(r, 8, QTableWidgetItem(format_currency(s.rate_per_kg)))
            disc_val = getattr(s, "discount_amount", Decimal("0.00"))
            self.table.setItem(r, 9, QTableWidgetItem(format_currency(disc_val)))
            self.table.setItem(r, 10, QTableWidgetItem(format_currency(s.total_amount)))

class WeightLossReportTab(QWidget):
    """
    Weight Loss Analysis Report Tab.
    Computes Purchased Weight vs Sold Net Weight and calculates Loss KG and Loss %.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        top_layout = QHBoxLayout()
        self.date_picker = DateRangePicker()
        self.date_picker.date_range_changed.connect(self.generate_report)
        top_layout.addWidget(self.date_picker)
        top_layout.addStretch()
        layout.addLayout(top_layout)

        self.card = QLabel()
        self.card.setStyleSheet("font-size: 15px; font-weight: bold; background-color: #fef2f2; padding: 15px; border-radius: 8px; border: 1px solid #fecaca;")
        layout.addWidget(self.card)

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Metric / Parameter", "Value"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table)

    def generate_report(self):
        start_d, end_d = self.date_picker.get_date_range()
        wl = WeightLossService.get_weight_loss_summary(start_d, end_d)

        self.card.setText(
            f"WEIGHT LOSS ANALYSIS REPORT\n"
            f"Period: {start_d.strftime('%d/%m/%Y')} to {end_d.strftime('%d/%m/%Y')}\n\n"
            f"Purchased Weight: {format_weight(wl.total_purchased_kg)}\n"
            f"Sold Net Weight: {format_weight(wl.total_sales_net_kg)}\n"
            f"WEIGHT LOSS: {format_weight(wl.weight_loss_kg)} ({wl.weight_loss_percentage:.2f}%)"
        )

        metrics = [
            ("Total Purchased Weight (KG)", format_weight(wl.total_purchased_kg)),
            ("Total Sales Gross Weight (KG)", format_weight(wl.total_sales_gross_kg)),
            ("Total Sales Box Weight (KG)", format_weight(wl.total_sales_box_kg)),
            ("Total Sales Net Weight (KG)", format_weight(wl.total_sales_net_kg)),
            ("Actual Chicken Weight Loss (KG)", format_weight(wl.weight_loss_kg)),
            ("Weight Loss Percentage (%)", f"{wl.weight_loss_percentage:.2f} %")
        ]

        self.table.setRowCount(0)
        for m, v in metrics:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(m))
            self.table.setItem(r, 1, QTableWidgetItem(v))

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

        self.tabs.addTab(self.cust_stmt_tab, "Customer Statement (Client-Facing)")
        self.tabs.addTab(self.prov_stmt_tab, "Provider Statement (Supplier-Facing)")
        self.tabs.addTab(self.internal_sales_tab, "Internal Sales Summary")
        self.tabs.addTab(self.weight_loss_tab, "Weight Loss Analysis")

        layout.addWidget(self.tabs)

    def refresh_data(self):
        self.cust_stmt_tab.load_customers()
        self.prov_stmt_tab.load_providers()
        self.internal_sales_tab.generate_report()
        self.weight_loss_tab.generate_report()
