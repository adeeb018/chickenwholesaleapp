from datetime import date
from decimal import Decimal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTabWidget, QComboBox, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QFrame
)
from PySide6.QtCore import Qt
from app.services.master_service import MasterService
from app.services.balance_service import BalanceService
from app.services.report_service import ReportService
from app.services.weight_loss_service import WeightLossService
from app.ui.components.date_range_picker import DateRangePicker
from app.utils.decimal_utils import format_currency, format_weight

class CustomerFacingStatementTab(QWidget):
    """
    Customer Statement Tab - Customer Facing.
    CRITICAL RULE: MUST NOT show Box Weight! Uses only Net Weight, Rate, and Amount.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        filter_layout = QHBoxLayout()
        self.customer_combo = QComboBox()
        self.date_picker = DateRangePicker()
        self.date_picker.date_range_changed.connect(self.generate_report)
        self.customer_combo.currentIndexChanged.connect(self.generate_report)

        filter_layout.addWidget(QLabel("Customer:"))
        filter_layout.addWidget(self.customer_combo)
        filter_layout.addWidget(self.date_picker)
        filter_layout.addStretch()

        layout.addLayout(filter_layout)

        self.summary_card = QLabel()
        self.summary_card.setStyleSheet("font-size: 14px; font-weight: bold; background-color: #f0fdf4; padding: 12px; border-radius: 6px; border: 1px solid #bbf7d0;")
        layout.addWidget(self.summary_card)

        # Customer Statement Table - Strictly HIDES Box Weight!
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels([
            "Date", "Item / Description", "Net Weight (KG)", "Rate (₹/KG)", "Amount (₹)"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table)

        self.load_customers()

    def load_customers(self):
        self.customer_combo.clear()
        for c in MasterService.get_all_customers():
            self.customer_combo.addItem(c.name, c.id)

    def generate_report(self):
        c_id = self.customer_combo.currentData()
        if not c_id:
            return

        start_d, end_d = self.date_picker.get_date_range()
        stmt = BalanceService.get_customer_statement(c_id, start_d, end_d)
        if not stmt:
            return

        self.summary_card.setText(
            f"CUSTOMER STATEMENT — {stmt.customer_name.upper()}\n"
            f"Period: {start_d.strftime('%d/%m/%Y')} to {end_d.strftime('%d/%m/%Y')} | "
            f"Opening Balance: {format_currency(stmt.period_opening_balance)}\n"
            f"Total Net Weight: {format_weight(stmt.total_net_weight_kg)} | "
            f"Total Sales: {format_currency(stmt.total_sales_amount)} | "
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
        self.table.setItem(r, 4, QTableWidgetItem(format_currency(stmt.period_opening_balance)))

        for entry in stmt.ledger_entries[1:]:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(entry.entry_date.strftime("%d/%m/%Y")))
            self.table.setItem(r, 1, QTableWidgetItem(entry.description))
            
            if entry.net_weight_kg:
                self.table.setItem(r, 2, QTableWidgetItem(format_weight(entry.net_weight_kg)))
            else:
                self.table.setItem(r, 2, QTableWidgetItem("-"))

            if entry.rate_per_kg:
                self.table.setItem(r, 3, QTableWidgetItem(format_currency(entry.rate_per_kg)))
            else:
                self.table.setItem(r, 3, QTableWidgetItem("-"))

            val = entry.debit if entry.debit > 0 else (Decimal("-1") * entry.credit)
            self.table.setItem(r, 4, QTableWidgetItem(format_currency(val)))

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

        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels([
            "Date", "Customer", "Item", "Gross Weight (KG)", "Box Weight (KG)", "Net Weight (KG)", "Rate (₹/KG)", "Discount (₹)", "Final Amount (₹)"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table)

    def generate_report(self):
        start_d, end_d = self.date_picker.get_date_range()
        summary = ReportService.get_sales_summary(start_d, end_d)

        self.summary_label.setText(
            f"INTERNAL SALES REPORT ({start_d.strftime('%d/%m/%Y')} - {end_d.strftime('%d/%m/%Y')}) | "
            f"Gross: {format_weight(summary['total_gross_weight_kg'])} | "
            f"Box: {format_weight(summary['total_box_weight_kg'])} | "
            f"Net: {format_weight(summary['total_net_weight_kg'])} | "
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
            self.table.setItem(r, 3, QTableWidgetItem(format_weight(s.gross_weight_kg)))
            self.table.setItem(r, 4, QTableWidgetItem(format_weight(s.box_weight_kg)))
            self.table.setItem(r, 5, QTableWidgetItem(format_weight(s.net_weight_kg)))
            self.table.setItem(r, 6, QTableWidgetItem(format_currency(s.rate_per_kg)))
            disc_val = getattr(s, "discount_amount", Decimal("0.00"))
            self.table.setItem(r, 7, QTableWidgetItem(format_currency(disc_val)))
            self.table.setItem(r, 8, QTableWidgetItem(format_currency(s.total_amount)))

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

        tabs = QTabWidget()
        self.cust_stmt_tab = CustomerFacingStatementTab()
        self.internal_sales_tab = InternalSalesReportTab()
        self.weight_loss_tab = WeightLossReportTab()

        tabs.addTab(self.cust_stmt_tab, "Customer Statement (Client-Facing)")
        tabs.addTab(self.internal_sales_tab, "Internal Sales Summary")
        tabs.addTab(self.weight_loss_tab, "Weight Loss Analysis")

        layout.addWidget(tabs)
