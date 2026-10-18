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

def test_purchase_boxes_and_net_weight_calculation():
    provider = MasterService.create_provider(name="Provider Boxes Test")
    item = MasterService.get_all_items()[0]

    # Gross = 500 KG, Box Weight = 25 KG (20 boxes) -> Net Weight = 475 KG @ ₹150 = ₹71,250
    pur = PurchaseService.create_purchase(
        transaction_date=date(2026, 9, 21),
        provider_id=provider.id,
        item_id=item.id,
        gross_weight_kg=500,
        box_weight_kg=25,
        box_count=20,
        rate_per_kg=150,
        payment_type="BANK"
    )
    assert pur.box_count == 20
    assert pur.gross_weight_kg == Decimal("500.000")
    assert pur.box_weight_kg == Decimal("25.000")
    assert pur.net_weight_kg == Decimal("475.000")
    assert pur.weight_kg == Decimal("475.000")
    assert pur.total_amount == Decimal("71250.00")

    # Verify statement closing balance
    stmt = BalanceService.get_provider_statement(provider.id, date(2026, 9, 1), date(2026, 9, 30))
    assert stmt.total_purchase_weight_kg == Decimal("475.000")
    assert stmt.closing_balance == Decimal("71250.00")

    # Reject Box weight > Gross weight
    with pytest.raises(ValueError, match="Box weight cannot be greater than gross weight"):
        PurchaseService.create_purchase(
            transaction_date=date(2026, 9, 21),
            provider_id=provider.id,
            item_id=item.id,
            gross_weight_kg=50,
            box_weight_kg=60,
            box_count=5,
            rate_per_kg=150,
            payment_type="BANK"
        )

    # Reject Box count < 0
    with pytest.raises(ValueError, match="Box count cannot be negative"):
        PurchaseService.create_purchase(
            transaction_date=date(2026, 9, 21),
            provider_id=provider.id,
            item_id=item.id,
            gross_weight_kg=100,
            box_weight_kg=5,
            box_count=-1,
            rate_per_kg=150,
            payment_type="BANK"
        )

    # Update purchase with new box count and weights
    updated_pur = PurchaseService.update_purchase(
        purchase_id=pur.id,
        transaction_date=date(2026, 9, 21),
        provider_id=provider.id,
        item_id=item.id,
        gross_weight_kg=600,
        box_weight_kg=30,
        box_count=25,
        rate_per_kg=150,
        payment_type="BANK"
    )
    assert updated_pur.box_count == 25
    assert updated_pur.gross_weight_kg == Decimal("600.000")
    assert updated_pur.box_weight_kg == Decimal("30.000")
    assert updated_pur.net_weight_kg == Decimal("570.000")
    assert updated_pur.total_amount == Decimal("85500.00")

def test_purchases_view_ui_and_edit_dialog(qapp, monkeypatch):
    from app.ui.views.purchases_view import PurchasesView, EditPurchaseDialog
    from PySide6.QtWidgets import QMessageBox

    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: QMessageBox.Ok)
    monkeypatch.setattr(QMessageBox, "warning", lambda *args, **kwargs: QMessageBox.Ok)

    prov = MasterService.create_provider(name="Poultry Farm UI")
    item = MasterService.get_all_items()[0]

    view = PurchasesView()
    view.load_combos()
    view.provider_combo.setCurrentIndex(view.provider_combo.findData(prov.id))
    view.item_combo.setCurrentIndex(view.item_combo.findData(item.id))

    # Enter 18 boxes, 450 KG gross, 20 KG box weight, ₹150 rate
    view.box_count_spin.setValue(18)
    view.gross_spin.setValue(450.0)
    view.box_spin.setValue(20.0)
    view.rate_spin.setValue(150.0)
    view.pay_type_combo.setCurrentText("BANK")

    # Verify live net weight and amount calculation
    view._calculate_net_and_amount()
    assert view.net_edit.text() == "430.000 KG"
    assert "64,500.00" in view.amount_edit.text()

    # Save purchase
    view._save_purchase()

    # Verify form reset
    assert view.box_count_spin.value() == 0
    assert view.gross_spin.value() == 0.0
    assert view.box_spin.value() == 0.0

    # Verify history table contains Boxes, Gross, Box Wt, Net
    assert view.table.rowCount() >= 1
    row = 0
    assert view.table.item(row, 4).text() == "18"
    assert "450.000" in view.table.item(row, 5).text()
    assert "20.000" in view.table.item(row, 6).text()
    assert "430.000" in view.table.item(row, 7).text()
    assert "150.00" in view.table.item(row, 8).text()
    assert "64,500.00" in view.table.item(row, 9).text()

    # Test EditPurchaseDialog
    saved_pur = PurchaseService.get_purchases()[0]
    dlg = EditPurchaseDialog(saved_pur)
    assert dlg.box_count_spin.value() == 18
    assert dlg.gross_spin.value() == 450.0
    assert dlg.box_spin.value() == 20.0
    assert "430.000" in dlg.net_label.text()

    # Change box count and box weight
    dlg.box_count_spin.setValue(20)
    dlg.box_spin.setValue(25.0)
    dlg._recalc()
    assert "425.000" in dlg.net_label.text()
    assert "63,750.00" in dlg.total_label.text()

    data = dlg.get_data()
    assert data["box_count"] == 20
    assert data["gross_weight_kg"] == 450.0
    assert data["box_weight_kg"] == 25.0


