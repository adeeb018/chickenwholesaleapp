from datetime import date
from decimal import Decimal
from app.services.master_service import MasterService
from app.services.sales_service import SalesService
from app.services.payment_service import PaymentService
from app.services.balance_service import BalanceService

def test_customer_ledger_and_balance_calculation():
    # 1. Create customer with opening balance ₹50,000 as of 01/09/2026
    cust = MasterService.create_customer(
        name="ABC Hotel",
        opening_balance=50000,
        opening_balance_date=date(2026, 9, 1)
    )
    items = MasterService.get_all_items()
    item_broiler = items[0]

    # Day 1 (02/09/2026): Gross=100, Box=5 -> Net=95 KG, Rate=₹180 -> Amount=₹17,100
    sale1 = SalesService.create_sale(
        transaction_date=date(2026, 9, 2),
        customer_id=cust.id,
        item_id=item_broiler.id,
        gross_weight_kg=100,
        box_weight_kg=5,
        rate_per_kg=180
    )
    assert sale1.net_weight_kg == Decimal("95.000")
    assert sale1.total_amount == Decimal("17100.00")

    # Day 2 (03/09/2026): Payment received ₹20,000 Cash (Voucher C-1025)
    pymt1 = PaymentService.create_customer_payment(
        payment_date=date(2026, 9, 3),
        customer_id=cust.id,
        amount=20000,
        payment_mode="CASH",
        voucher_number="C-1025"
    )
    assert pymt1.amount == Decimal("20000.00")

    # Day 3 (05/09/2026): Gross=200, Box=10 -> Net=190 KG, Rate=₹185 -> Amount=₹35,150
    sale2 = SalesService.create_sale(
        transaction_date=date(2026, 9, 5),
        customer_id=cust.id,
        item_id=item_broiler.id,
        gross_weight_kg=200,
        box_weight_kg=10,
        rate_per_kg=185
    )
    assert sale2.net_weight_kg == Decimal("190.000")
    assert sale2.total_amount == Decimal("35150.00")

    # Verify statement for full month
    stmt = BalanceService.get_customer_statement(cust.id, date(2026, 9, 1), date(2026, 9, 30))
    assert stmt.period_opening_balance == Decimal("50000.00")
    assert stmt.total_net_weight_kg == Decimal("285.000")
    assert stmt.total_sales_amount == Decimal("52250.00")  # 17100 + 35150
    assert stmt.total_payments == Decimal("20000.00")
    # Closing = 50000 + 52250 - 20000 = 82250
    assert stmt.closing_balance == Decimal("82250.00")

def test_period_opening_balance_calculation():
    """Verify that opening balance for a selected period includes all prior transactions."""
    cust = MasterService.create_customer(
        name="Hotel XYZ",
        opening_balance=50000,
        opening_balance_date=date(2026, 9, 1)
    )
    items = MasterService.get_all_items()
    item_broiler = items[0]

    # Sale before period (02/09): ₹20,000
    SalesService.create_sale(
        transaction_date=date(2026, 9, 2),
        customer_id=cust.id,
        item_id=item_broiler.id,
        gross_weight_kg=100,
        box_weight_kg=0,
        rate_per_kg=200
    )
    # Payment before period (05/09): ₹15,000
    PaymentService.create_customer_payment(
        payment_date=date(2026, 9, 5),
        customer_id=cust.id,
        amount=15000,
        payment_mode="BANK",
        bank_reference="TXN123"
    )

    # When viewing statement for period 10/09/2026 to 20/09/2026:
    # Opening balance should be 50,000 + 20,000 - 15,000 = 55,000
    stmt = BalanceService.get_customer_statement(cust.id, date(2026, 9, 10), date(2026, 9, 20))
    assert stmt.period_opening_balance == Decimal("55000.00")
