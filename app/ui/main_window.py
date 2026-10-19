from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QStackedWidget,
    QLabel, QFrame, QScrollArea
)
from PySide6.QtCore import Qt
from app.ui.styles.theme import MAIN_QSS
from app.ui.components.voucher_search_dialog import VoucherSearchDialog
from app.ui.views.dashboard_view import DashboardView
from app.ui.views.purchases_view import PurchasesView
from app.ui.views.sales_view import SalesView
from app.ui.views.customer_returns_view import CustomerReturnsView
from app.ui.views.customer_payments_view import CustomerPaymentsView
from app.ui.views.provider_payments_view import ProviderPaymentsView
from app.ui.views.batches_view import BatchesView
from app.ui.views.reconciliation_view import ReconciliationView
from app.ui.views.customers_view import CustomersView
from app.ui.views.providers_view import ProvidersView
from app.ui.views.items_view import ItemsView
from app.ui.views.reports_view import ReportsView
from app.ui.views.settings_view import SettingsView

class MainWindow(QMainWindow):
    """
    Main Application Window with sidebar navigation and stacked views.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Chicken Wholesale Shop Management")
        self.resize(1280, 800)
        self.setStyleSheet(MAIN_QSS)

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Sidebar Widget
        sidebar = QFrame()
        sidebar.setObjectName("sidebarWidget")
        sidebar.setFixedWidth(250)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(2)

        header = QLabel("🐔 CHICKEN WHOLESALE")
        header.setObjectName("sidebarHeader")
        sidebar_layout.addWidget(header)

        # Sidebar Navigation Items
        self.nav_buttons = []

        def add_category(title):
            cat = QLabel(title)
            cat.setObjectName("sidebarCategory")
            sidebar_layout.addWidget(cat)

        def add_nav(title, index):
            btn = QPushButton(title)
            btn.setProperty("class", "sidebarBtn")
            btn.setCheckable(True)
            btn.clicked.connect(lambda: self._switch_view(index))
            sidebar_layout.addWidget(btn)
            self.nav_buttons.append(btn)
            return btn

        add_category("Overview")
        add_nav("📊 Dashboard", 0)

        add_category("Transactions")
        add_nav("🛒 Purchases", 1)
        add_nav("🏷️ Sales", 2)
        add_nav("🔁 Customer Returns", 3)
        add_nav("💵 Customer Payments", 4)
        add_nav("💳 Provider Payments", 5)

        add_category("Inventory & Stock")
        add_nav("📦 Batches & Stock", 6)
        add_nav("⚖️ Daily Reconciliation", 7)

        add_category("Masters")
        add_nav("👥 Customers", 8)
        add_nav("🏭 Providers", 9)
        add_nav("🍗 Chicken Types", 10)

        add_category("Analytics & Settings")
        add_nav("📈 Reports Hub", 11)
        add_nav("⚙️ Settings & Backup", 12)

        sidebar_layout.addStretch()

        main_layout.addWidget(sidebar)

        # Right Panel Container (Header Bar + Stacked Content)
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        # Top Header Bar
        top_bar = QFrame()
        top_bar.setObjectName("topHeaderBar")
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(20, 10, 20, 10)

        self.title_label = QLabel("Dashboard")
        self.title_label.setObjectName("headerTitle")

        voucher_btn = QPushButton("🔍 Search Voucher #")
        voucher_btn.setProperty("class", "secondaryBtn")
        voucher_btn.clicked.connect(self._open_voucher_search)

        top_layout.addWidget(self.title_label)
        top_layout.addStretch()
        top_layout.addWidget(voucher_btn)

        right_layout.addWidget(top_bar)

        # Stacked Views in Scroll Area
        self.stacked = QStackedWidget()
        
        self.dashboard_view = DashboardView()
        self.purchases_view = PurchasesView()
        self.sales_view = SalesView()
        self.returns_view = CustomerReturnsView()
        self.customer_payments_view = CustomerPaymentsView()
        self.provider_payments_view = ProviderPaymentsView()
        self.batches_view = BatchesView()
        self.reconciliation_view = ReconciliationView()
        self.customers_view = CustomersView()
        self.providers_view = ProvidersView()
        self.items_view = ItemsView()
        self.reports_view = ReportsView()
        self.settings_view = SettingsView()

        self.stacked.addWidget(self.dashboard_view)          # 0
        self.stacked.addWidget(self.purchases_view)          # 1
        self.stacked.addWidget(self.sales_view)              # 2
        self.stacked.addWidget(self.returns_view)            # 3
        self.stacked.addWidget(self.customer_payments_view)  # 4
        self.stacked.addWidget(self.provider_payments_view)  # 5
        self.stacked.addWidget(self.batches_view)            # 6
        self.stacked.addWidget(self.reconciliation_view)     # 7
        self.stacked.addWidget(self.customers_view)          # 8
        self.stacked.addWidget(self.providers_view)          # 9
        self.stacked.addWidget(self.items_view)              # 10
        self.stacked.addWidget(self.reports_view)            # 11
        self.stacked.addWidget(self.settings_view)           # 12

        right_layout.addWidget(self.stacked, 1)
        main_layout.addWidget(right_panel, 1)

        self._switch_view(0)

    def _switch_view(self, index: int):
        self.stacked.setCurrentIndex(index)
        for i, btn in enumerate(self.nav_buttons):
            btn.setChecked(i == index)
        
        titles = [
            "Dashboard", "Purchases", "Sales", "Customer Returns",
            "Customer Payments", "Provider Payments", "Batches & Stock Management",
            "Daily Physical Stock Reconciliation", "Customer Master", "Provider Master",
            "Chicken Types / Items", "Reports Hub", "Settings & Backup"
        ]
        if index < len(titles):
            self.title_label.setText(titles[index])

        # Auto refresh active view when navigated
        current_widget = self.stacked.currentWidget()
        if hasattr(current_widget, "on_view_activated"):
            current_widget.on_view_activated()
        elif hasattr(current_widget, "refresh_data"):
            current_widget.refresh_data()
        elif hasattr(current_widget, "refresh_table"):
            current_widget.refresh_table()
        elif hasattr(current_widget, "load_combos"):
            current_widget.load_combos()

    def _open_voucher_search(self):
        dlg = VoucherSearchDialog(parent=self)
        dlg.exec()
