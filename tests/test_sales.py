import pytest
from datetime import date
from decimal import Decimal
from app.services.master_service import MasterService
from app.services.sales_service import SalesService
from app.services.balance_service import BalanceService

def test_sales_net_weight_and_box_weight_validation():
    cust = MasterService.create_customer(name="Test Customer")
    item = MasterService.get_all_items()[0]

    # Valid Sale: Gross=100, Box=5 -> Net=95, Rate=180 -> Amount=17100
    sale = SalesService.create_sale(
        transaction_date=date(2026, 9, 20),
        customer_id=cust.id,
        item_id=item.id,
        gross_weight_kg=100,
        box_weight_kg=5,
        rate_per_kg=180
    )
    assert sale.net_weight_kg == Decimal("95.000")
    assert sale.total_amount == Decimal("17100.00")

    # Reject Box weight > Gross weight
    with pytest.raises(ValueError, match="Box weight cannot be greater than gross weight"):
        SalesService.create_sale(
            transaction_date=date(2026, 9, 20),
            customer_id=cust.id,
            item_id=item.id,
            gross_weight_kg=10,
            box_weight_kg=12,
            rate_per_kg=180
        )

    # Reject Gross weight <= 0
    with pytest.raises(ValueError, match="Gross weight must be greater than 0"):
        SalesService.create_sale(
            transaction_date=date(2026, 9, 20),
            customer_id=cust.id,
            item_id=item.id,
            gross_weight_kg=0,
            box_weight_kg=0,
            rate_per_kg=180
        )

def test_sales_discount_and_retroactive_update():
    cust = MasterService.create_customer(name="Discount Customer")
    item = MasterService.get_all_items()[0]

    # 1. Sale with Discount at entry time: Gross=100, Box=5 -> Net=95, Rate=180, Discount=500 -> Amount=16,600
    sale1 = SalesService.create_sale(
        transaction_date=date(2026, 9, 20),
        customer_id=cust.id,
        item_id=item.id,
        gross_weight_kg=100,
        box_weight_kg=5,
        rate_per_kg=180,
        discount_amount=500
    )
    assert sale1.discount_amount == Decimal("500.00")
    assert sale1.total_amount == Decimal("16600.00")

    # 2. Sale without Discount initially: Gross=200, Box=10 -> Net=190, Rate=100 -> Amount=19,000
    sale2 = SalesService.create_sale(
        transaction_date=date(2026, 9, 21),
        customer_id=cust.id,
        item_id=item.id,
        gross_weight_kg=200,
        box_weight_kg=10,
        rate_per_kg=100,
        discount_amount=0
    )
    assert sale2.total_amount == Decimal("19000.00")

    # Verify customer balance prior to retroactive update (16600 + 19000 = 35600)
    stmt_before = BalanceService.get_customer_statement(cust.id, date(2026, 9, 1), date(2026, 9, 30))
    assert stmt_before.closing_balance == Decimal("35600.00")

    # 3. Retroactively apply a discount of ₹1,000 to sale2!
    updated_sale2 = SalesService.update_sale(
        sale_id=sale2.id,
        transaction_date=date(2026, 9, 21),
        customer_id=cust.id,
        item_id=item.id,
        gross_weight_kg=200,
        box_weight_kg=10,
        rate_per_kg=100,
        discount_amount=1000
    )
    assert updated_sale2.discount_amount == Decimal("1000.00")
    assert updated_sale2.total_amount == Decimal("18000.00")

    # Verify customer ledger automatically recalculates (16600 + 18000 = 34600)
    stmt_after = BalanceService.get_customer_statement(cust.id, date(2026, 9, 1), date(2026, 9, 30))
    assert stmt_after.closing_balance == Decimal("34600.00")

    # 4. Validation rule tests
    with pytest.raises(ValueError, match="Discount amount cannot be negative"):
        SalesService.create_sale(
            transaction_date=date(2026, 9, 22),
            customer_id=cust.id,
            item_id=item.id,
            gross_weight_kg=10,
            box_weight_kg=0,
            rate_per_kg=100,
            discount_amount=-50
        )

    with pytest.raises(ValueError, match="Discount amount cannot exceed gross sale amount"):
        SalesService.create_sale(
            transaction_date=date(2026, 9, 22),
            customer_id=cust.id,
            item_id=item.id,
            gross_weight_kg=10,
            box_weight_kg=0,
            rate_per_kg=100,
            discount_amount=1500  # Gross is 1000
        )
