import os
from datetime import date
from decimal import Decimal
import pytest
from PySide6.QtWidgets import QApplication
from app.services.master_service import MasterService
from app.services.sales_service import SalesService
from app.services.purchase_service import PurchaseService
from app.services.payment_service import PaymentService
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
