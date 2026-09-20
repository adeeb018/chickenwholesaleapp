from datetime import date
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QFrame, QTableWidget,
    QTableWidgetItem, QHeaderView
)
from PySide6.QtCore import Qt
from app.ui.components.date_range_picker import DateRangePicker
from app.ui.components.stat_card import StatCard
from app.services.report_service import ReportService
from app.services.weight_loss_service import WeightLossService
from app.services.balance_service import BalanceService
from app.utils.decimal_utils import format_currency, format_weight

class DashboardView(QWidget):
    """
    Executive Dashboard View showing KPI metric cards and date-filtered activity summaries.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Top Bar with Date Range Selector
        top_layout = QHBoxLayout()
        header = QLabel("Executive Dashboard")
        header.setStyleSheet("font-size: 20px; font-weight: bold; color: #0f172a;")
        
        self.date_picker = DateRangePicker()
        self.date_picker.date_range_changed.connect(self.refresh_data)

        top_layout.addWidget(header)
        top_layout.addStretch()
        top_layout.addWidget(self.date_picker)
        layout.addLayout(top_layout)

        # KPI Cards Grid
        grid = QGridLayout()
        grid.setSpacing(15)

        self.card_purchases = StatCard("Purchases", accent_color="#2563eb")
        self.card_sales = StatCard("Sales", accent_color="#059669")
        self.card_payments = StatCard("Payments Received", accent_color="#d97706")
        self.card_weight_loss = StatCard("Weight Loss", accent_color="#dc2626")
        self.card_receivables = StatCard("Total Receivables", accent_color="#7c3aed")
        self.card_payables = StatCard("Total Payables", accent_color="#db2777")

        grid.addWidget(self.card_purchases, 0, 0)
        grid.addWidget(self.card_sales, 0, 1)
        grid.addWidget(self.card_payments, 0, 2)
        grid.addWidget(self.card_weight_loss, 1, 0)
        grid.addWidget(self.card_receivables, 1, 1)
        grid.addWidget(self.card_payables, 1, 2)

        layout.addLayout(grid)

        # Summary Breakdown Tables
        tables_layout = QHBoxLayout()
        
        # Provider Breakdown Frame
        prov_frame = QFrame()
        prov_frame.setProperty("class", "cardFrame")
        prov_box = QVBoxLayout(prov_frame)
        prov_box.addWidget(QLabel("<b>Top Purchases by Provider</b>"))
        self.prov_table = QTableWidget(0, 3)
        self.prov_table.setHorizontalHeaderLabels(["Provider", "Weight (KG)", "Amount"])
        self.prov_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        prov_box.addWidget(self.prov_table)

        # Customer Breakdown Frame
        cust_frame = QFrame()
        cust_frame.setProperty("class", "cardFrame")
        cust_box = QVBoxLayout(cust_frame)
        cust_box.addWidget(QLabel("<b>Top Sales by Customer</b>"))
        self.cust_table = QTableWidget(0, 3)
        self.cust_table.setHorizontalHeaderLabels(["Customer", "Net Weight (KG)", "Amount"])
        self.cust_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        cust_box.addWidget(self.cust_table)

        tables_layout.addWidget(prov_frame)
        tables_layout.addWidget(cust_frame)

        layout.addLayout(tables_layout)

        # Initial refresh
        self.refresh_data()

    def refresh_data(self):
        start_d, end_d = self.date_picker.get_date_range()

        # 1. Purchases
        pur_summary = ReportService.get_purchase_summary(start_d, end_d)
        self.card_purchases.set_data(
            value=format_currency(pur_summary["total_amount"]),
            subtitle=f"{format_weight(pur_summary['total_weight_kg'])} | {pur_summary['provider_count']} Providers"
        )

        # 2. Sales
        sales_summary = ReportService.get_sales_summary(start_d, end_d)
        self.card_sales.set_data(
            value=format_currency(sales_summary["total_amount"]),
            subtitle=f"Net: {format_weight(sales_summary['total_net_weight_kg'])} (Box: {format_weight(sales_summary['total_box_weight_kg'])})"
        )

        # 3. Payments
        pymt_summary = ReportService.get_payment_summary(start_d, end_d)
        self.card_payments.set_data(
            value=format_currency(pymt_summary["customer_total"]),
            subtitle=f"Cash: {format_currency(pymt_summary['customer_cash'])} | Bank: {format_currency(pymt_summary['customer_bank'])}"
        )

        # 4. Weight Loss
        wl_summary = WeightLossService.get_weight_loss_summary(start_d, end_d)
        self.card_weight_loss.set_data(
            value=f"{format_weight(wl_summary.weight_loss_kg)}",
            subtitle=f"Loss: {wl_summary.weight_loss_percentage:.2f}% (Pur: {format_weight(wl_summary.total_purchased_kg)})"
        )

        # 5. Receivables & Payables
        receivables = BalanceService.get_total_receivables()
        payables = BalanceService.get_total_payables()

        self.card_receivables.set_data(
            value=format_currency(receivables),
            subtitle="Current total customer balance"
        )
        self.card_payables.set_data(
            value=format_currency(payables),
            subtitle="Current total provider balance"
        )

        # Populate tables
        self.prov_table.setRowCount(0)
        for p_name, data in list(pur_summary["provider_breakdown"].items())[:5]:
            r = self.prov_table.rowCount()
            self.prov_table.insertRow(r)
            self.prov_table.setItem(r, 0, QTableWidgetItem(p_name))
            self.prov_table.setItem(r, 1, QTableWidgetItem(format_weight(data["weight_kg"])))
            self.prov_table.setItem(r, 2, QTableWidgetItem(format_currency(data["amount"])))

        self.cust_table.setRowCount(0)
        for c_name, data in list(sales_summary["customer_breakdown"].items())[:5]:
            r = self.cust_table.rowCount()
            self.cust_table.insertRow(r)
            self.cust_table.setItem(r, 0, QTableWidgetItem(c_name))
            self.cust_table.setItem(r, 1, QTableWidgetItem(format_weight(data["net_weight_kg"])))
            self.cust_table.setItem(r, 2, QTableWidgetItem(format_currency(data["amount"])))
