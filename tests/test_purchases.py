import pytest
from datetime import date
from decimal import Decimal
from app.services.master_service import MasterService
from app.services.purchase_service import PurchaseService
from app.services.balance_service import BalanceService

def test_purchase_creation_and_voucher_rule():
    provider = MasterService.create_provider(name="Provider A")
    item = MasterService.get_all_items()[0]

    # Purchase 500 KG @ ₹150 = ₹75,000 CASH payment with voucher P-501
    pur1 = PurchaseService.create_purchase(
        transaction_date=date(2026, 9, 20),
        provider_id=provider.id,
        item_id=item.id,
        weight_kg=500,
        rate_per_kg=150,
        payment_type="CASH",
        voucher_number="P-501"
    )
    assert pur1.weight_kg == Decimal("500.000")
    assert pur1.total_amount == Decimal("75000.00")
    assert pur1.voucher_number == "P-501"

    # Reject CASH purchase without voucher number
    with pytest.raises(ValueError, match="Voucher number is required for CASH"):
        PurchaseService.create_purchase(
            transaction_date=date(2026, 9, 20),
            provider_id=provider.id,
            item_id=item.id,
            weight_kg=300,
            rate_per_kg=150,
            payment_type="CASH",
            voucher_number=""
        )

    # BANK purchase does not require voucher number
    pur2 = PurchaseService.create_purchase(
        transaction_date=date(2026, 9, 20),
        provider_id=provider.id,
        item_id=item.id,
        weight_kg=300,
        rate_per_kg=150,
        payment_type="BANK",
        bank_reference="NFT1001"
    )
    assert pur2.total_amount == Decimal("45000.00")
    assert pur2.bank_reference == "NFT1001"

def test_purchase_update_and_ledger_recalculation():
    provider = MasterService.create_provider(name="Provider Edit Test")
    item = MasterService.get_all_items()[0]

    # Initial purchase: 100 KG @ ₹150 = ₹15,000
    pur = PurchaseService.create_purchase(
        transaction_date=date(2026, 9, 20),
        provider_id=provider.id,
        item_id=item.id,
        weight_kg=100,
        rate_per_kg=150,
        payment_type="BANK"
    )
    assert pur.total_amount == Decimal("15000.00")

    # Verify provider ledger closing balance (₹15,000)
    stmt_before = BalanceService.get_provider_statement(provider.id, date(2026, 9, 1), date(2026, 9, 30))
    assert stmt_before.closing_balance == Decimal("15000.00")

    # Edit past purchase: Change weight to 200 KG @ ₹160 = ₹32,000
    updated_pur = PurchaseService.update_purchase(
        purchase_id=pur.id,
        transaction_date=date(2026, 9, 20),
        provider_id=provider.id,
        item_id=item.id,
        weight_kg=200,
        rate_per_kg=160,
        payment_type="BANK"
    )
    assert updated_pur.weight_kg == Decimal("200.000")
    assert updated_pur.total_amount == Decimal("32000.00")

    # Verify provider ledger statement dynamically recalculated to ₹32,000
    stmt_after = BalanceService.get_provider_statement(provider.id, date(2026, 9, 1), date(2026, 9, 30))
    assert stmt_after.closing_balance == Decimal("32000.00")
