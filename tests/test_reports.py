import os
from datetime import date
from decimal import Decimal
import pytest
from PySide6.QtWidgets import QApplication
from app.services.master_service import MasterService
from app.services.sales_service import SalesService
from app.services.purchase_service import PurchaseService
from app.services.payment_service import PaymentService
from app.services.balance_service import BalanceService
from app.ui.views.reports_view import ReportsView, ProviderFacingStatementTab, CustomerFacingStatementTab

# Ensure Qt runs offscreen for CI / headless testing
os.environ["QT_QPA_PLATFORM"] = "offscreen"

@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(["-platform", "offscreen"])
    return app

def test_reports_view_tabs_and_provider_statement(qapp):
    # 1. Create a provider with opening balance ₹25,000 as of 01/09/2026
    prov = MasterService.create_provider(
        name="Supreme Poultry Farm",
        phone="9988776655",
        opening_balance=25000,
        opening_balance_date=date(2026, 9, 1)
    )
    item = MasterService.get_all_items()[0]

    # Purchase on 05/09/2026: 400 KG @ ₹150 = ₹60,000 CASH with Voucher P-888
    pur = PurchaseService.create_purchase(
        transaction_date=date(2026, 9, 5),
        provider_id=prov.id,
        item_id=item.id,
        weight_kg=400,
        rate_per_kg=150,
        payment_type="CASH",
        voucher_number="P-888"
    )

    # Payment Made on 10/09/2026: ₹30,000 Bank transfer Ref BANK-456
    pymt = PaymentService.create_provider_payment(
        payment_date=date(2026, 9, 10),
        provider_id=prov.id,
        amount=30000,
        payment_mode="BANK",
        bank_reference="BANK-456"
    )

    # 2. Instantiate ReportsView
    reports_view = ReportsView()
    assert reports_view.tabs is not None
    assert isinstance(reports_view.cust_stmt_tab, CustomerFacingStatementTab)
    assert isinstance(reports_view.prov_stmt_tab, ProviderFacingStatementTab)

    prov_tab = reports_view.prov_stmt_tab

    # 3. Verify provider combo contains the new provider
    prov_idx = prov_tab.provider_combo.findData(prov.id)
    assert prov_idx >= 0
    prov_tab.provider_combo.setCurrentIndex(prov_idx)

    # Set date range: 01/09/2026 to 30/09/2026
    prov_tab.date_picker.set_date_range(date(2026, 9, 1), date(2026, 9, 30))
    prov_tab.generate_report()

    # 4. Verify Summary Card calculations
    summary_text = prov_tab.summary_card.text()
    assert "SUPREME POULTRY FARM" in summary_text
    assert "Opening Balance: ₹25,000.00" in summary_text
    assert "Total Weight: 400.000 KG" in summary_text
    assert "Total Purchases: ₹60,000.00" in summary_text
    assert "Total Payments Made: ₹30,000.00" in summary_text
    assert "Closing / Payable Balance: ₹55,000.00" in summary_text

    # 5. Verify Table Rows (7 columns: Date, Description, Weight, Rate, Purchase Amount, Amount Paid, Balance)
    assert prov_tab.table.columnCount() == 7
    assert prov_tab.table.rowCount() == 3

    # Row 0: Opening Balance
    assert prov_tab.table.item(0, 0).text() == "01/09/2026"
    assert prov_tab.table.item(0, 1).text() == "OPENING BALANCE"
    assert prov_tab.table.item(0, 2).text() == "-"
    assert prov_tab.table.item(0, 3).text() == "-"
    assert prov_tab.table.item(0, 4).text() == "-"
    assert prov_tab.table.item(0, 5).text() == "-"
    assert prov_tab.table.item(0, 6).text() == "₹25,000.00"

    # Row 1: Purchase (Purchase Amount = ₹60,000, Amount Paid = '-', Balance = ₹85,000)
    assert prov_tab.table.item(1, 0).text() == "05/09/2026"
    assert "Purchase" in prov_tab.table.item(1, 1).text()
    assert "P-888" in prov_tab.table.item(1, 1).text()
    assert prov_tab.table.item(1, 2).text() == "400.000 KG"
    assert prov_tab.table.item(1, 3).text() == "₹150.00"
    assert prov_tab.table.item(1, 4).text() == "₹60,000.00"
    assert prov_tab.table.item(1, 5).text() == "-"
    assert prov_tab.table.item(1, 6).text() == "₹85,000.00"

    # Row 2: Payment Made (Purchase Amount = '-', Amount Paid = ₹30,000, Balance = ₹55,000)
    assert prov_tab.table.item(2, 0).text() == "10/09/2026"
    assert "Payment Made" in prov_tab.table.item(2, 1).text()
    assert "BANK-456" in prov_tab.table.item(2, 1).text()
    assert prov_tab.table.item(2, 2).text() == "-"
    assert prov_tab.table.item(2, 3).text() == "-"
    assert prov_tab.table.item(2, 4).text() == "-"
    assert prov_tab.table.item(2, 5).text() == "₹30,000.00"
    assert prov_tab.table.item(2, 6).text() == "₹55,000.00"

    # 6. Verify refresh_data() preserves selection and runs without errors
    reports_view.refresh_data()
    assert prov_tab.provider_combo.currentData() == prov.id
    assert prov_tab.table.rowCount() == 3


def test_customer_statement_columns_with_discount_and_payment(qapp):
    # 1. Create customer with opening balance ₹50,000
    cust = MasterService.create_customer(
        name="Grand Royal Hotel",
        phone="9811223344",
        opening_balance=50000,
        opening_balance_date=date(2026, 9, 1)
    )
    item = MasterService.get_all_items()[0]

    # Sale 1 (02/09/2026): Gross=100 KG, Box=0, Net=100 KG @ ₹200 = ₹20,000, Discount=₹1,000 -> Total = ₹19,000
    sale1 = SalesService.create_sale(
        transaction_date=date(2026, 9, 2),
        customer_id=cust.id,
        item_id=item.id,
        gross_weight_kg=100,
        box_weight_kg=0,
        rate_per_kg=200,
        discount_amount=1000
    )
    assert sale1.total_amount == Decimal("19000.00")

    # Sale 2 (05/09/2026): Gross=50 KG, Box=0, Net=50 KG @ ₹180 = ₹9,000, No discount
    sale2 = SalesService.create_sale(
        transaction_date=date(2026, 9, 5),
        customer_id=cust.id,
        item_id=item.id,
        gross_weight_kg=50,
        box_weight_kg=0,
        rate_per_kg=180,
        discount_amount=0
    )
    assert sale2.total_amount == Decimal("9000.00")

    # Payment (08/09/2026): ₹25,000 Cash Voucher RC-999
    pymt = PaymentService.create_customer_payment(
        payment_date=date(2026, 9, 8),
        customer_id=cust.id,
        amount=25000,
        payment_mode="CASH",
        voucher_number="RC-999"
    )

    # 2. Instantiate and inspect Customer Statement tab
    reports_view = ReportsView()
    cust_tab = reports_view.cust_stmt_tab

    c_idx = cust_tab.customer_combo.findData(cust.id)
    assert c_idx >= 0
    cust_tab.customer_combo.setCurrentIndex(c_idx)

    cust_tab.date_picker.set_date_range(date(2026, 9, 1), date(2026, 9, 30))
    cust_tab.generate_report()

    # 3. Verify Summary Card
    # Opening: 50,000, Sales: 28,000, Discount: 1,000, Payments: 25,000, Closing: 50,000 + 28,000 - 25,000 = 53,000
    card_text = cust_tab.summary_card.text()
    assert "GRAND ROYAL HOTEL" in card_text
    assert "Opening Balance: ₹50,000.00" in card_text
    assert "Total Sales: ₹28,000.00" in card_text
    assert "Total Discount: ₹1,000.00" in card_text
    assert "Total Payments Received: ₹25,000.00" in card_text
    assert "Closing / Outstanding Balance: ₹53,000.00" in card_text

    # 4. Verify Table structure (8 columns: Date, Description, Net Weight, Rate, Sale Amount, Discount, Amount Received, Balance)
    assert cust_tab.table.columnCount() == 8
    assert cust_tab.table.rowCount() == 4

    # Row 0: Opening Balance
    assert cust_tab.table.item(0, 0).text() == "01/09/2026"
    assert cust_tab.table.item(0, 1).text() == "OPENING BALANCE"
    assert cust_tab.table.item(0, 2).text() == "-"
    assert cust_tab.table.item(0, 3).text() == "-"
    assert cust_tab.table.item(0, 4).text() == "-"
    assert cust_tab.table.item(0, 5).text() == "-"
    assert cust_tab.table.item(0, 6).text() == "-"
    assert cust_tab.table.item(0, 7).text() == "₹50,000.00"

    # Row 1: Sale 1 (Gross Sale: ₹20,000, Discount: ₹1,000, Received: '-', Balance: ₹69,000)
    assert cust_tab.table.item(1, 0).text() == "02/09/2026"
    assert "Sale" in cust_tab.table.item(1, 1).text()
    assert cust_tab.table.item(1, 2).text() == "100.000 KG"
    assert cust_tab.table.item(1, 3).text() == "₹200.00"
    assert cust_tab.table.item(1, 4).text() == "₹20,000.00"
    assert cust_tab.table.item(1, 5).text() == "₹1,000.00"
    assert cust_tab.table.item(1, 6).text() == "-"
    assert cust_tab.table.item(1, 7).text() == "₹69,000.00"

    # Row 2: Sale 2 (Sale Amount: ₹9,000, Discount: '-', Received: '-', Balance: ₹78,000)
    assert cust_tab.table.item(2, 0).text() == "05/09/2026"
    assert "Sale" in cust_tab.table.item(2, 1).text()
    assert cust_tab.table.item(2, 2).text() == "50.000 KG"
    assert cust_tab.table.item(2, 3).text() == "₹180.00"
    assert cust_tab.table.item(2, 4).text() == "₹9,000.00"
    assert cust_tab.table.item(2, 5).text() == "-"
    assert cust_tab.table.item(2, 6).text() == "-"
    assert cust_tab.table.item(2, 7).text() == "₹78,000.00"

    # Row 3: Payment (Sale Amount: '-', Discount: '-', Received: ₹25,000, Balance: ₹53,000)
    assert cust_tab.table.item(3, 0).text() == "08/09/2026"
    assert "Payment Received" in cust_tab.table.item(3, 1).text()
    assert cust_tab.table.item(3, 2).text() == "-"
    assert cust_tab.table.item(3, 3).text() == "-"
    assert cust_tab.table.item(3, 4).text() == "-"
    assert cust_tab.table.item(3, 5).text() == "-"
    assert cust_tab.table.item(3, 6).text() == "₹25,000.00"
    assert cust_tab.table.item(3, 7).text() == "₹53,000.00"

def test_statement_print_service_and_buttons(qapp, tmp_path):
    from app.services.statement_print_service import StatementPrintService
    from app.ui.views.customers_view import CustomerLedgerDialog
    from app.ui.views.providers_view import ProviderLedgerDialog

    # 1. Setup sample customer and provider statements
    cust = MasterService.create_customer(name="Print Test Customer", phone="9900112233")
    prov = MasterService.create_provider(name="Print Test Provider", phone="9900112244")
    item = MasterService.get_all_items()[0]

    SalesService.create_sale(
        transaction_date=date(2026, 9, 2),
        customer_id=cust.id,
        item_id=item.id,
        gross_weight_kg=100,
        box_weight_kg=0,
        rate_per_kg=200,
        discount_amount=500
    )
    PurchaseService.create_purchase(
        transaction_date=date(2026, 9, 3),
        provider_id=prov.id,
        item_id=item.id,
        weight_kg=200,
        rate_per_kg=150,
        payment_type="BANK"
    )

    cust_stmt = BalanceService.get_customer_statement(cust.id, date(2026, 9, 1), date(2026, 9, 30))
    prov_stmt = BalanceService.get_provider_statement(prov.id, date(2026, 9, 1), date(2026, 9, 30))

    # 2. Test Customer HTML generation
    cust_html = StatementPrintService.generate_customer_statement_html(cust_stmt)
    assert "CUSTOMER STATEMENT" in cust_html
    assert "PRINT TEST CUSTOMER" in cust_html
    assert "Sale (Broiler - 100.000 KG" in cust_html
    assert "₹19,500.00" in cust_html

    # 3. Test Provider HTML generation
    prov_html = StatementPrintService.generate_provider_statement_html(prov_stmt)
    assert "PROVIDER ACCOUNT STATEMENT" in prov_html
    assert "PRINT TEST PROVIDER" in prov_html
    assert "Purchase (Broiler - 200.000 KG" in prov_html
    assert "₹30,000.00" in prov_html

    # 4. Test PDF rendering to disk
    pdf_path = str(tmp_path / "test_statement.pdf")
    from PySide6.QtPrintSupport import QPrinter
    from PySide6.QtGui import QTextDocument

    printer = QPrinter(QPrinter.HighResolution)
    printer.setOutputFormat(QPrinter.PdfFormat)
    printer.setOutputFileName(pdf_path)

    doc = QTextDocument()
    doc.setHtml(cust_html)
    doc.print_(printer)

    assert os.path.exists(pdf_path)
    assert os.path.getsize(pdf_path) > 1000

    # 5. Verify UI buttons exist and are wired on Report Hub tabs and dialogs
    reports_view = ReportsView()
    assert reports_view.cust_stmt_tab.print_btn.text() == "🖨️ Print Statement"
    assert reports_view.cust_stmt_tab.pdf_btn.text() == "📄 Save PDF"
    assert reports_view.prov_stmt_tab.print_btn.text() == "🖨️ Print Statement"
    assert reports_view.prov_stmt_tab.pdf_btn.text() == "📄 Save PDF"

    cust_dlg = CustomerLedgerDialog(cust.id)
    assert cust_dlg.print_btn.text() == "🖨️ Print Statement"
    assert cust_dlg.pdf_btn.text() == "📄 Save PDF"

    prov_dlg = ProviderLedgerDialog(prov.id)
    assert prov_dlg.print_btn.text() == "🖨️ Print Statement"
    assert prov_dlg.pdf_btn.text() == "📄 Save PDF"

def test_internal_sales_report_average_box_weight_and_horizontal_scroll(qapp):
    from app.ui.views.reports_view import InternalSalesReportTab
    from app.services.report_service import ReportService
    from app.utils.date_utils import DateRangePreset, get_date_range_for_preset
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QHeaderView

    # Verify This Year preset in date_utils
    today = date.today()
    start_yr, end_yr = get_date_range_for_preset(DateRangePreset.THIS_YEAR, today)
    assert start_yr == date(today.year, 1, 1)
    assert end_yr == date(today.year, 12, 31)

    # Create customers and sales with boxes
    cust1 = MasterService.create_customer(
        name="Avg Box Customer 1",
        phone="9876501234",
        opening_balance=0
    )
    cust2 = MasterService.create_customer(
        name="Avg Box Customer 2",
        phone="9876501235",
        opening_balance=0
    )
    item = MasterService.get_all_items()[0]

    # Sale 1 with 5 boxes: Gross 150 KG, Box wt 20 KG -> Net 130 KG
    # Avg per box = 130 / 5 = 26.000 KG
    sale1 = SalesService.create_sale(
        transaction_date=date(2026, 9, 15),
        customer_id=cust1.id,
        item_id=item.id,
        gross_weight_kg=150,
        box_weight_kg=20,
        rate_per_kg=100,
        box_count=5
    )

    # Sale 2 with 2 boxes: Gross 60 KG, Box wt 10 KG -> Net 50 KG
    # Avg per box = 50 / 2 = 25.000 KG
    sale2 = SalesService.create_sale(
        transaction_date=date(2026, 9, 15),
        customer_id=cust2.id,
        item_id=item.id,
        gross_weight_kg=60,
        box_weight_kg=10,
        rate_per_kg=110,
        box_count=2
    )

    tab = InternalSalesReportTab()
    # Check table column configuration and horizontal scrollable setup
    assert tab.table.columnCount() == 11
    assert tab.table.horizontalScrollBarPolicy() == Qt.ScrollBarAsNeeded
    assert tab.table.horizontalHeader().defaultAlignment() == (Qt.AlignLeft | Qt.AlignVCenter)
    assert tab.table.horizontalHeader().stretchLastSection() is False

    # Check header order: Net Weight -> Boxes -> Avg Wt/Box
    headers = [tab.table.horizontalHeaderItem(c).text() for c in range(tab.table.columnCount())]
    assert headers[3] == "Gross Weight (KG)"
    assert headers[4] == "Box Weight (KG)"
    assert headers[5] == "Net Weight (KG)"
    assert headers[6] == "Boxes"
    assert headers[7] == "Avg Wt/Box (KG)"

    # Verify "This Year" is present in the DateRangePicker presets
    preset_items = [tab.date_picker.preset_combo.itemText(i) for i in range(tab.date_picker.preset_combo.count())]
    assert "This Year" in preset_items

    # Verify customer filter exists with "All" as first option
    assert tab.customer_combo.count() >= 3
    assert tab.customer_combo.itemText(0) == "All"
    assert tab.customer_combo.itemData(0) is None

    # Generate report for that date with "All" customers
    tab.date_picker.set_date_range(date(2026, 9, 15), date(2026, 9, 15))
    tab.customer_combo.setCurrentIndex(0)
    tab.generate_report()

    # Verify summary banner contains total boxes (5 + 2 = 7) and combined Avg Wt/Box (180 / 7 = 25.714)
    assert "Boxes: 7" in tab.summary_label.text()
    assert "Avg Wt/Box: 25.714 KG" in tab.summary_label.text()

    # Verify both rows are present
    rows_c1 = [r for r in range(tab.table.rowCount()) if tab.table.item(r, 1).text() == "Avg Box Customer 1"]
    rows_c2 = [r for r in range(tab.table.rowCount()) if tab.table.item(r, 1).text() == "Avg Box Customer 2"]
    assert len(rows_c1) == 1
    assert len(rows_c2) == 1

    r1 = rows_c1[0]
    assert tab.table.item(r1, 3).text() == "150.000 KG" # Gross
    assert tab.table.item(r1, 4).text() == "20.000 KG"  # Box Wt
    assert tab.table.item(r1, 5).text() == "130.000 KG" # Net Wt
    assert tab.table.item(r1, 6).text() == "5"          # Boxes
    assert tab.table.item(r1, 7).text() == "26.000 KG"  # Avg Wt / Box

    # Filter by specific customer (cust2)
    idx2 = tab.customer_combo.findData(cust2.id)
    assert idx2 >= 0
    tab.customer_combo.setCurrentIndex(idx2)

    # Now only cust2 should be in the table
    assert tab.table.rowCount() == 1
    assert tab.table.item(0, 1).text() == "Avg Box Customer 2"
    assert tab.table.item(0, 5).text() == "50.000 KG"
    assert tab.table.item(0, 6).text() == "2"
    assert tab.table.item(0, 7).text() == "25.000 KG"
    assert "Avg Box Customer 2" in tab.summary_label.text()
    assert "Boxes: 2" in tab.summary_label.text()
    assert "Avg Wt/Box: 25.000 KG" in tab.summary_label.text()

def test_screen_responsiveness_and_table_filling(qapp):
    from app.ui.main_window import MainWindow
    from PySide6.QtWidgets import QHeaderView, QScrollArea

    window = MainWindow()
    # 1. Verify MainWindow has scroll area wrapping stacked widget so right side is never cut off
    assert isinstance(window.scroll_area, QScrollArea)
    assert window.scroll_area.widget() == window.stacked

    # 2. Verify MainWindow can shrink cleanly on 1280 or smaller resolutions
    assert window.minimumSizeHint().width() <= 1000

    # 3. Verify Customer and Provider Statement tables have Stretch resize mode to fill page without gaps
    cust_table = window.reports_view.cust_stmt_tab.table
    prov_table = window.reports_view.prov_stmt_tab.table
    assert cust_table.horizontalHeader().sectionResizeMode(0) == QHeaderView.Stretch
    assert prov_table.horizontalHeader().sectionResizeMode(0) == QHeaderView.Stretch

    # 4. Verify Internal Sales table preserves horizontal scrollable setup with left alignment
    int_table = window.reports_view.internal_sales_tab.table
    assert int_table.horizontalHeader().sectionResizeMode(0) == QHeaderView.ResizeToContents
    assert int_table.horizontalHeader().stretchLastSection() is False

