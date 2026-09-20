from datetime import date
from decimal import Decimal
from app.services.master_service import MasterService
from app.services.purchase_service import PurchaseService
from app.services.sales_service import SalesService
from app.services.weight_loss_service import WeightLossService

def test_weight_loss_calculation():
    prov = MasterService.create_provider(name="Poultry Farm A")
    cust = MasterService.create_customer(name="Hotel Royal")
    item = MasterService.get_all_items()[0]

    # Purchased = 10,000 KG
    PurchaseService.create_purchase(
        transaction_date=date(2026, 9, 20),
        provider_id=prov.id,
        item_id=item.id,
        weight_kg=10000,
        rate_per_kg=150,
        payment_type="BANK"
    )

    # Sold: Gross=10,000, Box=500 -> Net=9,500 KG
    SalesService.create_sale(
        transaction_date=date(2026, 9, 20),
        customer_id=cust.id,
        item_id=item.id,
        gross_weight_kg=10000,
        box_weight_kg=500,
        rate_per_kg=180
    )

    # Summary
    wl = WeightLossService.get_weight_loss_summary(date(2026, 9, 1), date(2026, 9, 30))
    assert wl.total_purchased_kg == Decimal("10000.000")
    assert wl.total_sales_net_kg == Decimal("9500.000")
    assert wl.weight_loss_kg == Decimal("500.000")
    assert wl.weight_loss_percentage == Decimal("5.00")
