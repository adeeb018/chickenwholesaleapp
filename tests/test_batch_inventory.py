import pytest
from datetime import date
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database.base import Base
from app.database.connection import _migrate_schema
from app.database.models import (
    Customer, Provider, Item, Purchase, Sale, PurchaseBatch,
    SaleBatchAllocation, InventoryMovement, DailyStockReconciliation,
    CustomerReturn, CustomerReturnLine
)
from app.services.master_service import MasterService
from app.services.purchase_service import PurchaseService
from app.services.sales_service import SalesService
from app.services.inventory_service import InventoryService
from app.services.reconciliation_service import ReconciliationService
from app.services.customer_return_service import CustomerReturnService
from app.services.balance_service import BalanceService

def test_1_multiple_purchases():
    provider = MasterService.create_provider(name="Provider A")
    item = MasterService.get_all_items()[0]

    # Purchase 1: 500 kg
    pur1 = PurchaseService.create_purchase(
        transaction_date=date(2026, 10, 19),
        provider_id=provider.id,
        item_id=item.id,
        weight_kg=500,
        rate_per_kg=150,
        payment_type="BANK",
        bank_reference="REF1",
        batch_number="Batch A"
    )

    # Purchase 2: 400 kg
    pur2 = PurchaseService.create_purchase(
        transaction_date=date(2026, 10, 19),
        provider_id=provider.id,
        item_id=item.id,
        weight_kg=400,
        rate_per_kg=150,
        payment_type="BANK",
        bank_reference="REF2",
        batch_number="Batch B"
    )

    batches = InventoryService.get_batches()
    assert len(batches) == 2
    batch_a = next(b for b in batches if b.batch_number == "Batch A")
    batch_b = next(b for b in batches if b.batch_number == "Batch B")

    assert batch_a.net_weight_kg == Decimal("500.000")
    assert batch_a.current_stock_kg == Decimal("500.000")
    assert batch_b.net_weight_kg == Decimal("400.000")
    assert batch_b.current_stock_kg == Decimal("400.000")

def test_2_sales_from_different_batches():
    provider = MasterService.create_provider(name="Provider A")
    customer = MasterService.create_customer(name="Customer 1")
    item = MasterService.get_all_items()[0]

    pur1 = PurchaseService.create_purchase(
        transaction_date=date(2026, 10, 19),
        provider_id=provider.id,
        item_id=item.id,
        weight_kg=500,
        rate_per_kg=150,
        payment_type="BANK",
        batch_number="Batch A"
    )
    pur2 = PurchaseService.create_purchase(
        transaction_date=date(2026, 10, 19),
        provider_id=provider.id,
        item_id=item.id,
        weight_kg=400,
        rate_per_kg=150,
        payment_type="BANK",
        batch_number="Batch B"
    )

    batch_a = pur1.batch
    batch_b = pur2.batch

    # Sell 100 kg from Batch A
    SalesService.create_sale(
        transaction_date=date(2026, 10, 19),
        customer_id=customer.id,
        item_id=item.id,
        gross_weight_kg=100,
        box_weight_kg=0,
        rate_per_kg=200,
        batch_id=batch_a.id
    )

    # Sell 150 kg from Batch B
    SalesService.create_sale(
        transaction_date=date(2026, 10, 19),
        customer_id=customer.id,
        item_id=item.id,
        gross_weight_kg=150,
        box_weight_kg=0,
        rate_per_kg=200,
        batch_id=batch_b.id
    )

    batch_a_reloaded = InventoryService.get_batch_by_id(batch_a.id)
    batch_b_reloaded = InventoryService.get_batch_by_id(batch_b.id)

    assert batch_a_reloaded.current_stock_kg == Decimal("400.000")
    assert batch_b_reloaded.current_stock_kg == Decimal("250.000")

def test_3_daily_reconciliation():
    provider = MasterService.create_provider(name="Provider A")
    customer = MasterService.create_customer(name="Customer 1")
    item = MasterService.get_all_items()[0]
    mon = date(2026, 10, 19)

    # Purchase 500 kg
    pur = PurchaseService.create_purchase(
        transaction_date=mon,
        provider_id=provider.id,
        item_id=item.id,
        weight_kg=500,
        rate_per_kg=150,
        payment_type="BANK",
        batch_number="Batch A"
    )
    batch_a = pur.batch

    # Sales 450 kg
    SalesService.create_sale(
        transaction_date=mon,
        customer_id=customer.id,
        item_id=item.id,
        gross_weight_kg=450,
        box_weight_kg=0,
        rate_per_kg=200,
        batch_id=batch_a.id
    )

    # Calculated closing stock before reconciliation: 50 kg
    sheet = ReconciliationService.get_reconciliation_sheet(mon)
    batch_row = next(r for r in sheet if r["batch"].id == batch_a.id)
    assert batch_row["opening_stock"] == Decimal("0.000")
    assert batch_row["stock_additions"] == Decimal("500.000")
    assert batch_row["sales"] == Decimal("450.000")
    assert batch_row["calculated_closing"] == Decimal("50.000")

    # Reconcile with actual 47 kg -> difference -3 kg
    recon = ReconciliationService.reconcile_batch(
        batch_id=batch_a.id,
        business_date=mon,
        actual_closing_stock=47,
        reason="Natural weight loss"
    )
    assert recon.difference_kg == Decimal("-3.000")
    assert recon.actual_closing_kg == Decimal("47.000")

    batch_reloaded = InventoryService.get_batch_by_id(batch_a.id)
    assert batch_reloaded.current_stock_kg == Decimal("47.000")

def test_4_carry_forward():
    provider = MasterService.create_provider(name="Provider A")
    customer = MasterService.create_customer(name="Customer 1")
    item = MasterService.get_all_items()[0]
    mon = date(2026, 10, 19)
    tue = date(2026, 10, 20)

    # Monday: Purchase 500 kg, Sale 450 kg, Reconciled at 47 kg
    pur = PurchaseService.create_purchase(
        transaction_date=mon,
        provider_id=provider.id,
        item_id=item.id,
        weight_kg=500,
        rate_per_kg=150,
        payment_type="BANK",
        batch_number="Batch A"
    )
    batch_a = pur.batch

    SalesService.create_sale(
        transaction_date=mon,
        customer_id=customer.id,
        item_id=item.id,
        gross_weight_kg=450,
        box_weight_kg=0,
        rate_per_kg=200,
        batch_id=batch_a.id
    )
    ReconciliationService.reconcile_batch(
        batch_id=batch_a.id,
        business_date=mon,
        actual_closing_stock=47,
        reason="Natural weight loss"
    )

    # Tuesday: Opening stock must be 47 kg
    tue_sheet = ReconciliationService.get_reconciliation_sheet(tue)
    batch_row = next(r for r in tue_sheet if r["batch"].id == batch_a.id)
    assert batch_row["opening_stock"] == Decimal("47.000")

    # Tuesday sales: 10 kg
    SalesService.create_sale(
        transaction_date=tue,
        customer_id=customer.id,
        item_id=item.id,
        gross_weight_kg=10,
        box_weight_kg=0,
        rate_per_kg=200,
        batch_id=batch_a.id
    )

    # Expected remaining stock before Tuesday reconciliation: 37 kg
    tue_sheet_after_sale = ReconciliationService.get_reconciliation_sheet(tue)
    row_after = next(r for r in tue_sheet_after_sale if r["batch"].id == batch_a.id)
    assert row_after["opening_stock"] == Decimal("47.000")
    assert row_after["sales"] == Decimal("10.000")
    assert row_after["calculated_closing"] == Decimal("37.000")

    batch_reloaded = InventoryService.get_batch_by_id(batch_a.id)
    assert batch_reloaded.current_stock_kg == Decimal("37.000")

def test_5_multiple_days_of_reconciliation():
    provider = MasterService.create_provider(name="Provider A")
    customer = MasterService.create_customer(name="Customer 1")
    item = MasterService.get_all_items()[0]
    mon = date(2026, 10, 19)
    tue = date(2026, 10, 20)
    wed = date(2026, 10, 21)

    # Monday purchase 500, sale 450, reconciled 47
    pur = PurchaseService.create_purchase(
        transaction_date=mon,
        provider_id=provider.id,
        item_id=item.id,
        weight_kg=500,
        rate_per_kg=150,
        payment_type="BANK",
        batch_number="Batch A"
    )
    batch_a = pur.batch
    SalesService.create_sale(
        transaction_date=mon,
        customer_id=customer.id,
        item_id=item.id,
        gross_weight_kg=450,
        box_weight_kg=0,
        rate_per_kg=200,
        batch_id=batch_a.id
    )
    ReconciliationService.reconcile_batch(batch_a.id, mon, actual_closing_stock=47)

    # Tuesday sales: 20 kg -> calculated closing 47 - 20 = 27 kg
    SalesService.create_sale(
        transaction_date=tue,
        customer_id=customer.id,
        item_id=item.id,
        gross_weight_kg=20,
        box_weight_kg=0,
        rate_per_kg=200,
        batch_id=batch_a.id
    )
    # Tuesday actual closing stock: 25 kg
    ReconciliationService.reconcile_batch(batch_a.id, tue, actual_closing_stock=25)

    # Wednesday opening stock must be 25 kg
    wed_sheet = ReconciliationService.get_reconciliation_sheet(wed)
    wed_row = next(r for r in wed_sheet if r["batch"].id == batch_a.id)
    assert wed_row["opening_stock"] == Decimal("25.000")
    assert wed_row["calculated_closing"] == Decimal("25.000")

def test_6_stock_gain():
    provider = MasterService.create_provider(name="Provider A")
    item = MasterService.get_all_items()[0]
    d = date(2026, 10, 19)

    pur = PurchaseService.create_purchase(
        transaction_date=d,
        provider_id=provider.id,
        item_id=item.id,
        weight_kg=100,
        rate_per_kg=150,
        payment_type="BANK",
        batch_number="Batch A"
    )
    batch_a = pur.batch

    # Expected closing: 100 kg. Actual closing: 102 kg.
    recon = ReconciliationService.reconcile_batch(
        batch_id=batch_a.id,
        business_date=d,
        actual_closing_stock=102,
        reason="Weighing scale calibration difference"
    )
    assert recon.difference_kg == Decimal("2.000")

    batch_reloaded = InventoryService.get_batch_by_id(batch_a.id)
    assert batch_reloaded.current_stock_kg == Decimal("102.000")

def test_7_resellable_customer_return():
    provider = MasterService.create_provider(name="Provider A")
    customer = MasterService.create_customer(name="Customer 1")
    item = MasterService.get_all_items()[0]
    d = date(2026, 10, 19)

    pur = PurchaseService.create_purchase(
        transaction_date=d,
        provider_id=provider.id,
        item_id=item.id,
        weight_kg=120,
        rate_per_kg=150,
        payment_type="BANK",
        batch_number="Batch A"
    )
    batch_a = pur.batch

    # Sale of 20 kg from Batch A -> Batch A has 100 kg remaining
    sale = SalesService.create_sale(
        transaction_date=d,
        customer_id=customer.id,
        item_id=item.id,
        gross_weight_kg=20,
        box_weight_kg=0,
        rate_per_kg=200,
        batch_id=batch_a.id
    )
    assert InventoryService.get_batch_by_id(batch_a.id).current_stock_kg == Decimal("100.000")

    # Customer returns 5 kg accepted for resale
    ret = CustomerReturnService.create_customer_return(
        customer_id=customer.id,
        original_sale_id=sale.id,
        return_date=d,
        lines_data=[{
            "sale_batch_allocation_id": sale.allocations[0].id,
            "returned_gross_weight_kg": 5,
            "returned_box_weight_kg": 0,
            "resale_eligible": True,
            "reason": "Excess quantity returned"
        }]
    )
    assert ret.total_returned_weight_kg == Decimal("5.000")
    assert ret.financial_credit_amount == Decimal("1000.00")  # 5 kg * ₹200

    batch_reloaded = InventoryService.get_batch_by_id(batch_a.id)
    assert batch_reloaded.current_stock_kg == Decimal("105.000")

    # Customer statement reflects credit
    stmt = BalanceService.get_customer_statement(customer.id, d, d)
    assert stmt.total_sales_amount == Decimal("4000.00")
    assert stmt.total_returns_amount == Decimal("1000.00")
    assert stmt.closing_balance == Decimal("3000.00")

def test_8_unsellable_customer_return():
    provider = MasterService.create_provider(name="Provider A")
    customer = MasterService.create_customer(name="Customer 1")
    item = MasterService.get_all_items()[0]
    d = date(2026, 10, 19)

    pur = PurchaseService.create_purchase(
        transaction_date=d,
        provider_id=provider.id,
        item_id=item.id,
        weight_kg=120,
        rate_per_kg=150,
        payment_type="BANK",
        batch_number="Batch A"
    )
    batch_a = pur.batch

    sale = SalesService.create_sale(
        transaction_date=d,
        customer_id=customer.id,
        item_id=item.id,
        gross_weight_kg=20,
        box_weight_kg=0,
        rate_per_kg=200,
        batch_id=batch_a.id
    )
    assert InventoryService.get_batch_by_id(batch_a.id).current_stock_kg == Decimal("100.000")

    # Customer returns 5 kg unsellable (spoiled)
    ret = CustomerReturnService.create_customer_return(
        customer_id=customer.id,
        original_sale_id=sale.id,
        return_date=d,
        lines_data=[{
            "sale_batch_allocation_id": sale.allocations[0].id,
            "returned_gross_weight_kg": 5,
            "returned_box_weight_kg": 0,
            "resale_eligible": False,
            "reason": "Damaged/Spoiled"
        }]
    )
    assert ret.total_returned_weight_kg == Decimal("5.000")
    # Stock remains 100 kg
    assert InventoryService.get_batch_by_id(batch_a.id).current_stock_kg == Decimal("100.000")

    # Financial credit is still given
    stmt = BalanceService.get_customer_statement(customer.id, d, d)
    assert stmt.closing_balance == Decimal("3000.00")

def test_9_partial_customer_returns():
    provider = MasterService.create_provider(name="Provider A")
    customer = MasterService.create_customer(name="Customer 1")
    item = MasterService.get_all_items()[0]
    d = date(2026, 10, 19)

    pur = PurchaseService.create_purchase(
        transaction_date=d,
        provider_id=provider.id,
        item_id=item.id,
        weight_kg=50,
        rate_per_kg=150,
        payment_type="BANK",
        batch_number="Batch A"
    )
    sale = SalesService.create_sale(
        transaction_date=d,
        customer_id=customer.id,
        item_id=item.id,
        gross_weight_kg=20,
        box_weight_kg=0,
        rate_per_kg=200,
        batch_id=pur.batch.id
    )
    alloc_id = sale.allocations[0].id

    # First return: 3 kg
    ret1 = CustomerReturnService.create_customer_return(
        customer_id=customer.id,
        original_sale_id=sale.id,
        return_date=d,
        lines_data=[{"sale_batch_allocation_id": alloc_id, "returned_gross_weight_kg": 3}]
    )
    assert ret1.total_returned_weight_kg == Decimal("3.000")

    # Second return: 2 kg
    ret2 = CustomerReturnService.create_customer_return(
        customer_id=customer.id,
        original_sale_id=sale.id,
        return_date=d,
        lines_data=[{"sale_batch_allocation_id": alloc_id, "returned_gross_weight_kg": 2}]
    )
    assert ret2.total_returned_weight_kg == Decimal("2.000")

    # Attempting to return more than remaining 15 kg (e.g. 16 kg) must fail
    with pytest.raises(ValueError, match="exceeds returnable limit"):
        CustomerReturnService.create_customer_return(
            customer_id=customer.id,
            original_sale_id=sale.id,
            return_date=d,
            lines_data=[{"sale_batch_allocation_id": alloc_id, "returned_gross_weight_kg": 16}]
        )

def test_10_return_against_a_depleted_batch():
    provider = MasterService.create_provider(name="Provider A")
    customer = MasterService.create_customer(name="Customer 1")
    item = MasterService.get_all_items()[0]
    d = date(2026, 10, 19)

    pur = PurchaseService.create_purchase(
        transaction_date=d,
        provider_id=provider.id,
        item_id=item.id,
        weight_kg=20,
        rate_per_kg=150,
        payment_type="BANK",
        batch_number="Batch A"
    )
    sale = SalesService.create_sale(
        transaction_date=d,
        customer_id=customer.id,
        item_id=item.id,
        gross_weight_kg=20,
        box_weight_kg=0,
        rate_per_kg=200,
        batch_id=pur.batch.id
    )

    batch = InventoryService.get_batch_by_id(pur.batch.id)
    assert batch.current_stock_kg == Decimal("0.000")
    assert batch.status == "DEPLETED"

    # Depleted batch receives 3 kg return accepted for resale
    CustomerReturnService.create_customer_return(
        customer_id=customer.id,
        original_sale_id=sale.id,
        return_date=d,
        lines_data=[{
            "sale_batch_allocation_id": sale.allocations[0].id,
            "returned_gross_weight_kg": 3,
            "resale_eligible": True
        }]
    )

    batch_reloaded = InventoryService.get_batch_by_id(pur.batch.id)
    assert batch_reloaded.current_stock_kg == Decimal("3.000")
    assert batch_reloaded.status == "ACTIVE"

def test_11_explicit_batch_completion():
    provider = MasterService.create_provider(name="Provider A")
    customer = MasterService.create_customer(name="Customer 1")
    item = MasterService.get_all_items()[0]
    d = date(2026, 10, 19)

    pur = PurchaseService.create_purchase(
        transaction_date=d,
        provider_id=provider.id,
        item_id=item.id,
        weight_kg=20,
        rate_per_kg=150,
        payment_type="BANK",
        batch_number="Batch A"
    )
    # Sell all 20 kg
    SalesService.create_sale(
        transaction_date=d,
        customer_id=customer.id,
        item_id=item.id,
        gross_weight_kg=20,
        box_weight_kg=0,
        rate_per_kg=200,
        batch_id=pur.batch.id
    )

    # Uncle confirms batch completion
    closed_batch = InventoryService.finish_batch(pur.batch.id, d, notes="Completed")
    assert closed_batch.status == "CLOSED"
    assert closed_batch.closed_at is not None

    # Ordinary sales rejected from closed batch
    with pytest.raises(ValueError, match="CLOSED"):
        SalesService.create_sale(
            transaction_date=d,
            customer_id=customer.id,
            item_id=item.id,
            gross_weight_kg=5,
            box_weight_kg=0,
            rate_per_kg=200,
            batch_id=pur.batch.id
        )

    # History remains accessible
    hist = InventoryService.get_batch_history(pur.batch.id)
    assert hist["status"] == "CLOSED"
    assert len(hist["movements"]) >= 2  # Purchase and Sale

def test_12_completion_with_unexplained_remaining_stock():
    provider = MasterService.create_provider(name="Provider A")
    item = MasterService.get_all_items()[0]
    d = date(2026, 10, 19)

    pur = PurchaseService.create_purchase(
        transaction_date=d,
        provider_id=provider.id,
        item_id=item.id,
        weight_kg=2,
        rate_per_kg=150,
        payment_type="BANK",
        batch_number="Batch A"
    )

    # Attempting to finish batch without reason/adjustment fails
    with pytest.raises(ValueError, match="remaining stock"):
        InventoryService.finish_batch(pur.batch.id, d, reason="")

    # Closing with explicit adjustment reason succeeds
    closed = InventoryService.finish_batch(
        pur.batch.id,
        d,
        reason="Chicken physically dried up/discarded",
        notes="Final physical verification done"
    )
    assert closed.status == "CLOSED"
    assert closed.current_stock_kg == Decimal("0.000")

def test_13_daily_reconciliation_does_not_close_a_batch():
    provider = MasterService.create_provider(name="Provider A")
    customer = MasterService.create_customer(name="Customer 1")
    item = MasterService.get_all_items()[0]
    mon = date(2026, 10, 19)
    tue = date(2026, 10, 20)

    pur = PurchaseService.create_purchase(
        transaction_date=mon,
        provider_id=provider.id,
        item_id=item.id,
        weight_kg=500,
        rate_per_kg=150,
        payment_type="BANK",
        batch_number="Batch A"
    )
    SalesService.create_sale(
        transaction_date=mon,
        customer_id=customer.id,
        item_id=item.id,
        gross_weight_kg=450,
        box_weight_kg=0,
        rate_per_kg=200,
        batch_id=pur.batch.id
    )

    # Reconcile Monday at 47 kg
    ReconciliationService.reconcile_batch(pur.batch.id, mon, actual_closing_stock=47)

    batch = InventoryService.get_batch_by_id(pur.batch.id)
    assert batch.current_stock_kg == Decimal("47.000")
    assert batch.status == "ACTIVE"  # NOT CLOSED!

    # Tuesday opening stock is 47 kg
    sheet = ReconciliationService.get_reconciliation_sheet(tue)
    row = next(r for r in sheet if r["batch"].id == pur.batch.id)
    assert row["opening_stock"] == Decimal("47.000")

def test_14_negative_stock_prevention():
    provider = MasterService.create_provider(name="Provider A")
    customer = MasterService.create_customer(name="Customer 1")
    item = MasterService.get_all_items()[0]
    d = date(2026, 10, 19)

    pur = PurchaseService.create_purchase(
        transaction_date=d,
        provider_id=provider.id,
        item_id=item.id,
        weight_kg=10,
        rate_per_kg=150,
        payment_type="BANK",
        batch_number="Batch A"
    )

    # Attempting to sell 12 kg from 10 kg batch must fail
    with pytest.raises(ValueError, match="Insufficient stock"):
        SalesService.create_sale(
            transaction_date=d,
            customer_id=customer.id,
            item_id=item.id,
            gross_weight_kg=12,
            box_weight_kg=0,
            rate_per_kg=200,
            batch_id=pur.batch.id
        )

    # Stock remains 10 kg
    batch = InventoryService.get_batch_by_id(pur.batch.id)
    assert batch.current_stock_kg == Decimal("10.000")

def test_15_one_sale_with_multiple_batches():
    provider = MasterService.create_provider(name="Provider A")
    customer = MasterService.create_customer(name="Customer 1")
    item = MasterService.get_all_items()[0]
    d = date(2026, 10, 19)

    pur_a = PurchaseService.create_purchase(
        transaction_date=d,
        provider_id=provider.id,
        item_id=item.id,
        weight_kg=50,
        rate_per_kg=150,
        payment_type="BANK",
        batch_number="Batch A"
    )
    pur_c = PurchaseService.create_purchase(
        transaction_date=d,
        provider_id=provider.id,
        item_id=item.id,
        weight_kg=100,
        rate_per_kg=150,
        payment_type="BANK",
        batch_number="Batch C"
    )

    # One customer sale of 100 kg: 30 kg from Batch A, 70 kg from Batch C
    sale = SalesService.create_sale(
        transaction_date=d,
        customer_id=customer.id,
        item_id=item.id,
        gross_weight_kg=100,
        box_weight_kg=0,
        rate_per_kg=220,
        allocations=[
            {"batch_id": pur_a.batch.id, "net_weight_kg": 30, "rate_per_kg": 220},
            {"batch_id": pur_c.batch.id, "net_weight_kg": 70, "rate_per_kg": 220}
        ]
    )

    assert sale.net_weight_kg == Decimal("100.000")
    assert sale.total_amount == Decimal("22000.00")
    assert len(sale.allocations) == 2

    batch_a = InventoryService.get_batch_by_id(pur_a.batch.id)
    batch_c = InventoryService.get_batch_by_id(pur_c.batch.id)

    assert batch_a.current_stock_kg == Decimal("20.000")  # 50 - 30
    assert batch_c.current_stock_kg == Decimal("30.000")  # 100 - 70

def test_16_duplicate_submissions():
    provider = MasterService.create_provider(name="Provider A")
    item = MasterService.get_all_items()[0]
    d = date(2026, 10, 19)

    pur = PurchaseService.create_purchase(
        transaction_date=d,
        provider_id=provider.id,
        item_id=item.id,
        weight_kg=50,
        rate_per_kg=150,
        payment_type="BANK",
        batch_number="Batch A"
    )

    # Reconcile on date d
    ReconciliationService.reconcile_batch(pur.batch.id, d, actual_closing_stock=48)

    # Duplicate reconciliation submission on same batch and date must be rejected
    with pytest.raises(ValueError, match="already reconciled"):
        ReconciliationService.reconcile_batch(pur.batch.id, d, actual_closing_stock=48)

def test_17_closed_batch_return():
    provider = MasterService.create_provider(name="Provider A")
    customer = MasterService.create_customer(name="Customer 1")
    item = MasterService.get_all_items()[0]
    d = date(2026, 10, 19)

    pur = PurchaseService.create_purchase(
        transaction_date=d,
        provider_id=provider.id,
        item_id=item.id,
        weight_kg=20,
        rate_per_kg=150,
        payment_type="BANK",
        batch_number="Batch A"
    )
    sale = SalesService.create_sale(
        transaction_date=d,
        customer_id=customer.id,
        item_id=item.id,
        gross_weight_kg=20,
        box_weight_kg=0,
        rate_per_kg=200,
        batch_id=pur.batch.id
    )

    # Close the batch
    InventoryService.finish_batch(pur.batch.id, d, notes="Sold out")
    closed_batch = InventoryService.get_batch_by_id(pur.batch.id)
    assert closed_batch.status == "CLOSED"

    # Attempting to return into a closed batch without reopening must fail
    with pytest.raises(ValueError, match="is CLOSED"):
        CustomerReturnService.create_customer_return(
            customer_id=customer.id,
            original_sale_id=sale.id,
            return_date=d,
            lines_data=[{
                "sale_batch_allocation_id": sale.allocations[0].id,
                "returned_gross_weight_kg": 2,
                "resale_eligible": True
            }],
            reopen_if_closed=False
        )

    # Returning with reopen_if_closed=True reopens batch and restores stock
    ret = CustomerReturnService.create_customer_return(
        customer_id=customer.id,
        original_sale_id=sale.id,
        return_date=d,
        lines_data=[{
            "sale_batch_allocation_id": sale.allocations[0].id,
            "returned_gross_weight_kg": 2,
            "resale_eligible": True
        }],
        reopen_if_closed=True
    )

    batch_after = InventoryService.get_batch_by_id(pur.batch.id)
    assert batch_after.status == "ACTIVE"
    assert batch_after.current_stock_kg == Decimal("2.000")
    assert ret.total_returned_weight_kg == Decimal("2.000")

def test_18_reconciliation_correction():
    provider = MasterService.create_provider(name="Provider A")
    item = MasterService.get_all_items()[0]
    d = date(2026, 10, 19)

    pur = PurchaseService.create_purchase(
        transaction_date=d,
        provider_id=provider.id,
        item_id=item.id,
        weight_kg=100,
        rate_per_kg=150,
        payment_type="BANK",
        batch_number="Batch A"
    )
    # First reconciliation: actual closing entered as 90 kg (loss 10 kg)
    recon = ReconciliationService.reconcile_batch(pur.batch.id, d, actual_closing_stock=90)
    assert InventoryService.get_batch_by_id(pur.batch.id).current_stock_kg == Decimal("90.000")

    # Correction: actual closing was actually 95 kg (loss was only 5 kg)
    corrected = ReconciliationService.correct_reconciliation(
        reconciliation_id=recon.id,
        new_actual_closing_stock=95,
        reason="Scale re-calibrated; initial weighing was inaccurate"
    )
    assert corrected.version == 2
    assert corrected.actual_closing_kg == Decimal("95.000")
    assert corrected.difference_kg == Decimal("-5.000")

    # Old reconciliation is preserved and marked corrected
    from app.database.connection import get_session
    with get_session() as session:
        recon_reloaded = session.query(DailyStockReconciliation).filter_by(id=recon.id).first()
        assert recon_reloaded.is_active is False
        assert recon_reloaded.status == "CORRECTED"

    # Effective balance is now 95 kg
    assert InventoryService.get_batch_by_id(pur.batch.id).current_stock_kg == Decimal("95.000")

def test_19_existing_database_migration():
    # Create an isolated temporary SQLite database simulating pre-existing database before batch tables
    engine = create_engine("sqlite:///:memory:", echo=False)
    
    # Create legacy tables manually (purchases and sales without batches)
    with engine.connect() as conn:
        conn.exec_driver_sql("""
            CREATE TABLE providers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(150) NOT NULL,
                phone VARCHAR(50), address VARCHAR(255), notes TEXT,
                is_active BOOLEAN NOT NULL DEFAULT 1, is_deleted BOOLEAN NOT NULL DEFAULT 0,
                deleted_at DATETIME, created_at DATETIME DEFAULT CURRENT_TIMESTAMP, updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.exec_driver_sql("""
            CREATE TABLE items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(100) NOT NULL, code VARCHAR(20),
                is_active BOOLEAN NOT NULL DEFAULT 1, is_deleted BOOLEAN NOT NULL DEFAULT 0,
                deleted_at DATETIME, created_at DATETIME DEFAULT CURRENT_TIMESTAMP, updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.exec_driver_sql("""
            CREATE TABLE purchases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                transaction_date DATE NOT NULL, provider_id INTEGER NOT NULL, item_id INTEGER NOT NULL,
                box_count INTEGER NOT NULL DEFAULT 0, gross_weight_kg DECIMAL(12,3) NOT NULL DEFAULT 0,
                box_weight_kg DECIMAL(12,3) NOT NULL DEFAULT 0, net_weight_kg DECIMAL(12,3) NOT NULL DEFAULT 0,
                weight_kg DECIMAL(12,3) NOT NULL, rate_per_kg DECIMAL(12,2) NOT NULL, total_amount DECIMAL(12,2) NOT NULL,
                payment_type VARCHAR(20) NOT NULL, voucher_number VARCHAR(50), bank_reference VARCHAR(100), notes TEXT,
                is_deleted BOOLEAN NOT NULL DEFAULT 0, deleted_at DATETIME, created_at DATETIME DEFAULT CURRENT_TIMESTAMP, updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.exec_driver_sql("""
            CREATE TABLE sales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                transaction_date DATE NOT NULL, customer_id INTEGER NOT NULL, item_id INTEGER NOT NULL,
                box_count INTEGER NOT NULL DEFAULT 0, gross_weight_kg DECIMAL(12,3) NOT NULL,
                box_weight_kg DECIMAL(12,3) NOT NULL DEFAULT 0, net_weight_kg DECIMAL(12,3) NOT NULL,
                rate_per_kg DECIMAL(12,2) NOT NULL, discount_amount DECIMAL(12,2) NOT NULL DEFAULT 0,
                total_amount DECIMAL(12,2) NOT NULL, notes TEXT,
                is_deleted BOOLEAN NOT NULL DEFAULT 0, deleted_at DATETIME, created_at DATETIME DEFAULT CURRENT_TIMESTAMP, updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """)
        # Insert pre-existing purchase and sale
        conn.exec_driver_sql("INSERT INTO providers (name) VALUES ('Legacy Provider');")
        conn.exec_driver_sql("INSERT INTO items (name) VALUES ('Broiler');")
        conn.exec_driver_sql("""
            INSERT INTO purchases (transaction_date, provider_id, item_id, weight_kg, gross_weight_kg, net_weight_kg, rate_per_kg, total_amount, payment_type)
            VALUES ('2026-10-18', 1, 1, 300.0, 300.0, 300.0, 140.0, 42000.0, 'BANK');
        """)
        conn.exec_driver_sql("""
            INSERT INTO sales (transaction_date, customer_id, item_id, gross_weight_kg, net_weight_kg, rate_per_kg, total_amount)
            VALUES ('2026-10-18', 1, 1, 50.0, 50.0, 180.0, 9000.0);
        """)
        conn.commit()

    # Run create_all and _migrate_schema
    Base.metadata.create_all(bind=engine)
    _migrate_schema(engine)

    # Check migrated batch
    with engine.connect() as conn:
        batches = conn.exec_driver_sql("SELECT id, batch_number, purchase_id, net_weight_kg, current_stock_kg FROM purchase_batches;").fetchall()
        assert len(batches) == 1
        b_id, b_num, p_id, net, cur_stock = batches[0]
        assert b_num == "Batch P1"
        assert p_id == 1
        assert Decimal(str(net)) == Decimal("300.0")

        # Initial PURCHASE movement created
        movements = conn.exec_driver_sql("SELECT movement_type, quantity_kg FROM inventory_movements WHERE batch_id = ?;", (b_id,)).fetchall()
        assert len(movements) == 1
        assert movements[0][0] == "PURCHASE"

        # Sale remains untouched without arbitrary allocations
        allocations = conn.exec_driver_sql("SELECT id FROM sale_batch_allocations;").fetchall()
        assert len(allocations) == 0  # No arbitrary allocations invented

def test_20_batches_view_ui(qapp, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    from app.ui.views.batches_view import BatchesView, FinishBatchDialog, BatchHistoryDialog

    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: QMessageBox.Ok)
    monkeypatch.setattr(QMessageBox, "warning", lambda *args, **kwargs: QMessageBox.Ok)

    provider = MasterService.create_provider(name="Batch UI Provider")
    item = MasterService.get_all_items()[0]
    pur = PurchaseService.create_purchase(
        transaction_date=date(2026, 10, 19),
        provider_id=provider.id,
        item_id=item.id,
        weight_kg=200,
        rate_per_kg=150,
        payment_type="BANK",
        batch_number="Batch UI-1"
    )

    view = BatchesView()
    view.refresh_table()
    assert view.table.rowCount() >= 1

    batch = InventoryService.get_batches()[0]
    dlg_hist = BatchHistoryDialog(batch_id=batch.id)
    assert dlg_hist.table.rowCount() >= 1

    # Test FinishBatchDialog
    dlg_finish = FinishBatchDialog(batch=batch)
    # Remaining stock requires reason
    dlg_finish.reason_edit.setText("End of day zeroing")
    dlg_finish._confirm()
    reloaded_b = InventoryService.get_batch_by_id(batch.id)
    assert reloaded_b.status == "CLOSED"
    assert reloaded_b.current_stock_kg == Decimal("0.000")

def test_21_reconciliation_view_ui(qapp, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    from app.ui.views.reconciliation_view import ReconciliationView, ReconcileBatchDialog

    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: QMessageBox.Ok)
    monkeypatch.setattr(QMessageBox, "warning", lambda *args, **kwargs: QMessageBox.Ok)

    provider = MasterService.create_provider(name="Recon UI Provider")
    item = MasterService.get_all_items()[0]
    pur = PurchaseService.create_purchase(
        transaction_date=date(2026, 10, 19),
        provider_id=provider.id,
        item_id=item.id,
        weight_kg=100,
        rate_per_kg=150,
        payment_type="BANK",
        batch_number="Batch Recon-UI"
    )

    view = ReconciliationView()
    view.refresh_sheet()
    assert view.table.rowCount() >= 1

    batches = InventoryService.get_batches()
    b = next(x for x in batches if x.batch_number == "Batch Recon-UI")

    dlg = ReconcileBatchDialog(batch_id=b.id, business_date=date(2026, 10, 19))
    dlg.actual_spin.setValue(98.0)
    dlg._recalc()
    assert "-2.000 KG" in dlg.diff_lbl.text()
    dlg.reason_combo.setCurrentText("Natural weight loss (shrinkage)")
    dlg._submit()

    updated_b = InventoryService.get_batch_by_id(b.id)
    assert updated_b.current_stock_kg == Decimal("98.000")

def test_22_customer_returns_view_ui(qapp, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    from app.ui.views.customer_returns_view import CustomerReturnsView

    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: QMessageBox.Ok)
    monkeypatch.setattr(QMessageBox, "warning", lambda *args, **kwargs: QMessageBox.Ok)

    provider = MasterService.create_provider(name="Return UI Provider")
    cust = MasterService.create_customer(name="Return UI Customer")
    item = MasterService.get_all_items()[0]

    pur = PurchaseService.create_purchase(
        transaction_date=date(2026, 10, 19),
        provider_id=provider.id,
        item_id=item.id,
        weight_kg=300,
        rate_per_kg=150,
        payment_type="BANK",
        batch_number="Batch Ret-UI"
    )

    batches = InventoryService.get_batches()
    b = next(x for x in batches if x.batch_number == "Batch Ret-UI")

    sale = SalesService.create_sale(
        transaction_date=date(2026, 10, 19),
        customer_id=cust.id,
        item_id=item.id,
        gross_weight_kg=50,
        box_weight_kg=0,
        rate_per_kg=180,
        batch_id=b.id
    )

    view = CustomerReturnsView()
    view.load_combos()
    view.customer_combo.setCurrentIndex(view.customer_combo.findData(cust.id))
    view.sale_combo.setCurrentIndex(view.sale_combo.findData(sale.id))

    view.gross_spin.setValue(5.0)
    view.box_spin.setValue(0.0)
    view._recalc_net_and_amount()
    assert "5.000 KG" in view.net_label.text()

    view.resale_check.setChecked(True)
    view._save_return()

    view.refresh_table()
    assert view.table.rowCount() >= 1

    updated_b = InventoryService.get_batch_by_id(b.id)
    assert updated_b.current_stock_kg == Decimal("255.000")

def test_23_reports_view_batch_and_returns_tabs(qapp):
    from app.ui.views.reports_view import ReportsView

    # Seed provider, customer, item, purchase, sale, and customer return
    provider = MasterService.create_provider(name="Reports Provider")
    cust = MasterService.create_customer(name="Reports Customer")
    item = MasterService.get_all_items()[0]

    pur = PurchaseService.create_purchase(
        transaction_date=date(2026, 10, 19),
        provider_id=provider.id,
        item_id=item.id,
        weight_kg=500,
        rate_per_kg=150,
        payment_type="BANK",
        batch_number="Batch Report-1"
    )

    batches = InventoryService.get_batches()
    b = next(x for x in batches if x.batch_number == "Batch Report-1")

    sale = SalesService.create_sale(
        transaction_date=date(2026, 10, 19),
        customer_id=cust.id,
        item_id=item.id,
        gross_weight_kg=100,
        box_weight_kg=0,
        rate_per_kg=180,
        batch_id=b.id
    )

    CustomerReturnService.create_customer_return(
        customer_id=cust.id,
        original_sale_id=sale.id,
        return_date=date(2026, 10, 19),
        lines_data=[{
            "batch_id": b.id,
            "sale_batch_allocation_id": sale.allocations[0].id if sale.allocations else None,
            "returned_gross_weight_kg": Decimal("5.000"),
            "returned_box_weight_kg": Decimal("0.000"),
            "resale_eligible": True,
            "financial_credit_amount": Decimal("900.00"),
            "return_reason": "Quality check"
        }]
    )

    reports = ReportsView()
    reports.refresh_data()

    assert reports.batch_stock_tab.table.rowCount() >= 1
    assert "BATCH INVENTORY SUMMARY" in reports.batch_stock_tab.summary_card.text()

    assert reports.returns_tab.table.rowCount() >= 1
    assert "CUSTOMER RETURNS SUMMARY" in reports.returns_tab.summary_card.text()

def test_24_main_window_navigation(qapp):
    from app.ui.main_window import MainWindow

    window = MainWindow()
    assert window.stacked.count() == 13

    # Switch to Batches
    window._switch_view(6)
    assert window.title_label.text() == "Batches & Stock Management"
    assert window.stacked.currentIndex() == 6

    # Switch to Daily Reconciliation
    window._switch_view(7)
    assert window.title_label.text() == "Daily Physical Stock Reconciliation"
    assert window.stacked.currentIndex() == 7

    # Switch to Customer Returns
    window._switch_view(3)
    assert window.title_label.text() == "Customer Returns"
    assert window.stacked.currentIndex() == 3

def test_25_reconciliation_and_reports_horizontal_scrolling(qapp):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QHeaderView
    from app.ui.views.reconciliation_view import ReconciliationView
    from app.ui.views.reports_view import ReportsView
    from app.ui.views.batches_view import BatchesView

    # 1. Daily Reconciliation Table: horizontal scrollbar enabled & batch number completely visible
    recon = ReconciliationView()
    assert recon.table.horizontalScrollBarPolicy() == Qt.ScrollBarAsNeeded
    assert recon.table.horizontalHeader().sectionResizeMode(0) == QHeaderView.ResizeToContents
    assert recon.table.horizontalHeader().minimumSectionSize() >= 90
    assert recon.table.horizontalHeader().stretchLastSection() is False

    # 2. Reports Hub Tables: all 6 tables must be horizontally scrollable
    rep = ReportsView()
    tabs = [
        rep.cust_stmt_tab,
        rep.prov_stmt_tab,
        rep.internal_sales_tab,
        rep.weight_loss_tab,
        rep.batch_stock_tab,
        rep.returns_tab,
    ]
    for tab in tabs:
        assert tab.table.horizontalScrollBarPolicy() == Qt.ScrollBarAsNeeded
        assert tab.table.horizontalHeader().sectionResizeMode(0) == QHeaderView.ResizeToContents

    # 3. Batches View Table: horizontal scrollbar enabled
    batches = BatchesView()
    assert batches.table.horizontalScrollBarPolicy() == Qt.ScrollBarAsNeeded

def test_26_purchases_payments_returns_and_batch_name(qapp):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QHeaderView
    from app.ui.views.purchases_view import PurchasesView
    from app.ui.views.customer_returns_view import CustomerReturnsView
    from app.ui.views.customer_payments_view import CustomerPaymentsView
    from app.ui.views.provider_payments_view import ProviderPaymentsView
    from app.ui.views.sales_view import MultiBatchSaleDialog, SalesView
    from app.ui.views.reconciliation_view import ReconciliationView
    from app.ui.views.batches_view import BatchesView
    from app.ui.views.reports_view import ReportsView

    # Purchases Table
    pv = PurchasesView()
    assert pv.table.horizontalScrollBarPolicy() == Qt.ScrollBarAsNeeded
    assert pv.table.horizontalHeaderItem(11).text() == "Batch Name"
    assert pv.table.horizontalHeader().sectionResizeMode(11) == QHeaderView.ResizeToContents

    # Customer Returns Table
    crv = CustomerReturnsView()
    assert crv.table.horizontalScrollBarPolicy() == Qt.ScrollBarAsNeeded
    assert crv.table.horizontalHeaderItem(4).text() == "Batch Name"
    assert crv.table.horizontalHeader().sectionResizeMode(4) == QHeaderView.ResizeToContents

    # Customer Payments Table
    cpv = CustomerPaymentsView()
    assert cpv.table.horizontalScrollBarPolicy() == Qt.ScrollBarAsNeeded

    # Provider Payments Table
    ppv = ProviderPaymentsView()
    assert ppv.table.horizontalScrollBarPolicy() == Qt.ScrollBarAsNeeded

    # Multi Batch Split Table
    mbs = MultiBatchSaleDialog(item_id=1, default_rate=150)
    assert mbs.table.horizontalScrollBarPolicy() == Qt.ScrollBarAsNeeded
    assert "Batch Name" in mbs.table.horizontalHeaderItem(0).text()

    # Sales Table
    sv = SalesView()
    assert sv.table.horizontalScrollBarPolicy() == Qt.ScrollBarAsNeeded
    assert "Batch Name" in sv.table.horizontalHeaderItem(11).text()

    # Reconciliation Table
    rv = ReconciliationView()
    assert rv.table.horizontalHeaderItem(0).text() == "Batch Name"

    # Batches View Table
    bv = BatchesView()
    assert bv.table.horizontalHeaderItem(0).text() == "Batch Name"

    # Reports Hub
    rep = ReportsView()
    assert rep.weight_loss_tab.table.horizontalHeaderItem(0).text() == "Batch Name"
    assert rep.batch_stock_tab.table.horizontalHeaderItem(0).text() == "Batch Name"
    assert rep.returns_tab.table.horizontalHeaderItem(4).text() == "Batch Name"


