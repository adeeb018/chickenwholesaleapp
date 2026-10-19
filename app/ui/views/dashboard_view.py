from datetime import date
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QFrame, QTableWidget,
    QTableWidgetItem, QHeaderView, QDoubleSpinBox, QPushButton, QMessageBox
)
from PySide6.QtCore import Qt
from app.ui.components.date_range_picker import DateRangePicker
from app.ui.components.stat_card import StatCard
from app.ui.components.table_utils import enable_table_copy_and_tooltips, create_table_item
from app.services.report_service import ReportService
from app.services.weight_loss_service import WeightLossService
from app.services.balance_service import BalanceService
from app.services.setting_service import SettingService
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

        # Main Chicken Rate Benchmark Control Banner
        rate_frame = QFrame()
        rate_frame.setProperty("class", "cardFrame")
        rate_frame.setStyleSheet("""
            QFrame.cardFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #ffffff, stop:1 #f8fafc);
                border: 1.5px solid #cbd5e1;
                border-left: 6px solid #2563eb;
                border-radius: 8px;
                padding: 10px 16px;
            }
        """)
        rate_layout = QHBoxLayout(rate_frame)
        rate_layout.setContentsMargins(5, 5, 5, 5)
        rate_layout.setSpacing(15)

        rate_info_box = QVBoxLayout()
        rate_info_box.setSpacing(2)
        rate_title = QLabel("🐔 <b>Market Rate (Daily Benchmark)</b>")
        rate_title.setStyleSheet("font-size: 15px; color: #0f172a;")
        rate_subtitle = QLabel("Set today's market rate (₹/KG). Auto pre-filled as default on customer sales.")
        rate_subtitle.setStyleSheet("font-size: 12px; color: #64748b;")
        rate_subtitle.setWordWrap(True)
        rate_info_box.addWidget(rate_title)
        rate_info_box.addWidget(rate_subtitle)

        rate_layout.addLayout(rate_info_box, 1)

        self.main_rate_spin = QDoubleSpinBox()
        self.main_rate_spin.setRange(0.00, 99999.00)
        self.main_rate_spin.setDecimals(2)
        self.main_rate_spin.setPrefix("₹ ")
        self.main_rate_spin.setSuffix(" / KG")
        self.main_rate_spin.setStyleSheet("""
            QDoubleSpinBox {
                font-size: 15px;
                font-weight: bold;
                color: #1e3a8a;
                background-color: #ffffff;
                border: 2px solid #93c5fd;
                border-radius: 6px;
                padding: 6px 10px;
                min-width: 140px;
            }
            QDoubleSpinBox:focus {
                border: 2px solid #2563eb;
            }
        """)

        save_rate_btn = QPushButton("💾 Set Market Rate")
        save_rate_btn.setProperty("class", "primaryBtn")
        save_rate_btn.clicked.connect(self._save_main_rate)

        self.rate_status_badge = QLabel("Active: ₹ 0.00 / KG")
        self.rate_status_badge.setStyleSheet("""
            color: #047857;
            background-color: #d1fae5;
            border: 1px solid #6ee7b7;
            border-radius: 12px;
            padding: 5px 12px;
            font-size: 12px;
            font-weight: bold;
        """)

        rate_controls = QHBoxLayout()
        rate_controls.setSpacing(8)
        rate_controls.addWidget(self.main_rate_spin)
        rate_controls.addWidget(save_rate_btn)
        rate_controls.addWidget(self.rate_status_badge)
        rate_layout.addLayout(rate_controls)

        layout.addWidget(rate_frame)

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
        self.prov_table.verticalHeader().setDefaultSectionSize(42)
        self.prov_table.verticalHeader().setVisible(False)
        enable_table_copy_and_tooltips(self.prov_table)
        prov_box.addWidget(self.prov_table)

        # Customer Breakdown Frame
        cust_frame = QFrame()
        cust_frame.setProperty("class", "cardFrame")
        cust_box = QVBoxLayout(cust_frame)
        cust_box.addWidget(QLabel("<b>Top Sales by Customer</b>"))
        self.cust_table = QTableWidget(0, 3)
        self.cust_table.setHorizontalHeaderLabels(["Customer", "Net Weight (KG)", "Amount"])
        self.cust_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.cust_table.verticalHeader().setDefaultSectionSize(42)
        self.cust_table.verticalHeader().setVisible(False)
        enable_table_copy_and_tooltips(self.cust_table)
        cust_box.addWidget(self.cust_table)

        tables_layout.addWidget(prov_frame)
        tables_layout.addWidget(cust_frame)

        layout.addLayout(tables_layout, 1)

        # Initial refresh
        self.refresh_data()

    def refresh_data(self):
        # 0. Refresh Main Chicken Rate
        current_rate = SettingService.get_main_chicken_rate()
        self.main_rate_spin.setValue(float(current_rate))
        self.rate_status_badge.setText(f"Active: {format_currency(current_rate)} / KG")

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
        loss_pct_str = f"{wl_summary.weight_loss_percentage:.2f}%"
        self.card_weight_loss.set_data(
            value=f"{format_weight(wl_summary.weight_loss_kg)} ({loss_pct_str})",
            subtitle=f"In-Stock: {format_weight(wl_summary.total_remaining_stock_kg)} | Pur: {format_weight(wl_summary.total_purchased_kg)}"
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
            self.prov_table.setItem(r, 0, create_table_item(p_name, bold=True))
            self.prov_table.setItem(r, 1, create_table_item(format_weight(data["weight_kg"]), alignment=Qt.AlignRight | Qt.AlignVCenter))
            self.prov_table.setItem(r, 2, create_table_item(format_currency(data["amount"]), alignment=Qt.AlignRight | Qt.AlignVCenter, bold=True))

        self.cust_table.setRowCount(0)
        for c_name, data in list(sales_summary["customer_breakdown"].items())[:5]:
            r = self.cust_table.rowCount()
            self.cust_table.insertRow(r)
            self.cust_table.setItem(r, 0, create_table_item(c_name, bold=True))
            self.cust_table.setItem(r, 1, create_table_item(format_weight(data["net_weight_kg"]), alignment=Qt.AlignRight | Qt.AlignVCenter))
            self.cust_table.setItem(r, 2, create_table_item(format_currency(data["amount"]), alignment=Qt.AlignRight | Qt.AlignVCenter, bold=True))

    def _save_main_rate(self):
        val = self.main_rate_spin.value()
        try:
            saved_rate = SettingService.set_main_chicken_rate(val)
            self.rate_status_badge.setText(f"Active: {format_currency(saved_rate)} / KG")
            QMessageBox.information(
                self,
                "Market Rate Updated",
                f"Market chicken selling rate successfully updated to {format_currency(saved_rate)} / KG.\n\n"
                "This rate will now auto-fill by default when recording customer sales."
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save main chicken rate: {str(e)}")
