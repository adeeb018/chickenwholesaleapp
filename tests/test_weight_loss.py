from datetime import date
from decimal import Decimal
from app.services.master_service import MasterService
from app.services.purchase_service import PurchaseService
from app.services.sales_service import SalesService
from app.services.inventory_service import InventoryService
from app.services.reconciliation_service import ReconciliationService
from app.services.customer_return_service import CustomerReturnService
from app.services.weight_loss_service import WeightLossService

def test_weight_loss_calculation():
    prov = MasterService.create_provider(name="Poultry Farm A")
    cust = MasterService.create_customer(name="Hotel Royal")
    item = MasterService.get_all_items()[0]

    # 1. Purchased = 10,000 KG
    pur = PurchaseService.create_purchase(
        transaction_date=date(2026, 9, 20),
        provider_id=prov.id,
        item_id=item.id,
        weight_kg=10000,
        rate_per_kg=150,
        payment_type="BANK",
        batch_number="BATCH-WL-001"
    )

    batches = InventoryService.get_batches()
    batch = next(b for b in batches if b.batch_number == "BATCH-WL-001")
    assert batch.current_stock_kg == Decimal("10000.000")

    # 2. Sold: Gross=10,000, Box=500 -> Net=9,500 KG
    sale = SalesService.create_sale(
        transaction_date=date(2026, 9, 20),
        customer_id=cust.id,
        item_id=item.id,
        gross_weight_kg=10000,
        box_weight_kg=500,
        rate_per_kg=180,
        batch_id=batch.id
    )

    # 3. Before reconciliation or closing:
    # 500 KG unsold chicken is still sitting in crates/stock, so it is NOT lost.
    wl1 = WeightLossService.get_weight_loss_summary(date(2026, 9, 1), date(2026, 9, 30))
    assert wl1.total_purchased_kg == Decimal("10000.000")
    assert wl1.total_sales_net_kg == Decimal("9500.000")
    assert wl1.total_remaining_stock_kg == Decimal("500.000")
    assert wl1.weight_loss_kg == Decimal("0.000")
    assert wl1.weight_loss_percentage == Decimal("0.00")
    assert len(wl1.batch_details) >= 1
    b_detail1 = next(b for b in wl1.batch_details if b.batch_id == batch.id)
    assert b_detail1.remaining_stock_kg == Decimal("500.000")
    assert b_detail1.weight_loss_kg == Decimal("0.000")

    # 4. Daily physical reconciliation:
    # Physical stock count reveals actual stock is 480 KG (20 KG physical shrinkage/loss).
    recon = ReconciliationService.reconcile_batch(
        batch_id=batch.id,
        business_date=date(2026, 9, 20),
        actual_closing_stock=Decimal("480.000"),
        reason="Daily evening physical weighment shrinkage",
        notes="Normal shrinkage"
    )
    assert recon.difference_kg == Decimal("-20.000")

    wl2 = WeightLossService.get_weight_loss_summary(date(2026, 9, 1), date(2026, 9, 30))
    assert wl2.total_remaining_stock_kg == Decimal("480.000")
    assert wl2.total_reconciled_loss_kg == Decimal("20.000")
    assert wl2.weight_loss_kg == Decimal("20.000")
    assert wl2.weight_loss_percentage == Decimal("0.20")  # 20 / 10000 * 100

    b_detail2 = next(b for b in wl2.batch_details if b.batch_id == batch.id)
    assert b_detail2.reconciled_loss_kg == Decimal("20.000")
    assert b_detail2.remaining_stock_kg == Decimal("480.000")
    assert b_detail2.weight_loss_kg == Decimal("20.000")
    assert b_detail2.weight_loss_percentage == Decimal("0.20")

    # 5. Customer Return:
    # Customer returns 30 KG net chicken eligible for resale.
    CustomerReturnService.create_customer_return(
        customer_id=cust.id,
        original_sale_id=sale.id,
        return_date=date(2026, 9, 21),
        lines_data=[{
            "batch_id": batch.id,
            "sale_batch_allocation_id": sale.allocations[0].id if sale.allocations else None,
            "returned_gross_weight_kg": Decimal("30.000"),
            "returned_box_weight_kg": Decimal("0.000"),
            "resale_eligible": True,
            "financial_credit_amount": Decimal("5400.00"),
            "return_reason": "Excess quantity returned"
        }]
    )

    wl3 = WeightLossService.get_weight_loss_summary(date(2026, 9, 1), date(2026, 9, 30))
    assert wl3.total_returns_net_kg == Decimal("30.000")
    # Remaining stock increases by 30 KG (from 480 to 510)
    assert wl3.total_remaining_stock_kg == Decimal("510.000")
    # Loss remains 20 KG: 10000 - (9500 - 30 + 510) = 10000 - 9980 = 20 KG
    assert wl3.weight_loss_kg == Decimal("20.000")

    # 6. Mark batch as completely finished (CLOSED):
    # Finish the remaining 510 KG (e.g. written off / discarded)
    InventoryService.finish_batch(
        batch_id=batch.id,
        business_date=date(2026, 9, 22),
        reason="Stock finished / written off",
        notes="Final batch closing"
    )

    wl4 = WeightLossService.get_weight_loss_summary(date(2026, 9, 1), date(2026, 9, 30))
    assert wl4.total_remaining_stock_kg == Decimal("0.000")
    # Total lost = 10000 - (9500 - 30 + 0) = 530 KG (20 KG recon loss + 510 KG closure adjustment)
    assert wl4.weight_loss_kg == Decimal("530.000")
    assert wl4.weight_loss_percentage == Decimal("5.30")

    b_detail4 = next(b for b in wl4.batch_details if b.batch_id == batch.id)
    assert b_detail4.status == "CLOSED"
    assert b_detail4.remaining_stock_kg == Decimal("0.000")
    assert b_detail4.weight_loss_kg == Decimal("530.000")
    assert b_detail4.weight_loss_percentage == Decimal("5.30")
