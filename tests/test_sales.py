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

def test_main_chicken_rate_and_sales_view_integration(qapp):
    from app.services.setting_service import SettingService
    from app.ui.views.dashboard_view import DashboardView
    from app.ui.views.sales_view import SalesView

    # 1. Initially default main chicken rate is 0.00
    assert SettingService.get_main_chicken_rate() == Decimal("0.00")

    # Reject negative rate
    with pytest.raises(ValueError, match="cannot be negative"):
        SettingService.set_main_chicken_rate(-10)

    # 2. Set main chicken rate on Dashboard (e.g. ₹185.50 / KG)
    dashboard = DashboardView()
    dashboard.main_rate_spin.setValue(185.50)
    dashboard._save_main_rate()

    assert SettingService.get_main_chicken_rate() == Decimal("185.50")
    assert "₹185.50" in dashboard.rate_status_badge.text()

    # 3. Create a Customer
    cust = MasterService.create_customer(name="Market Buyer")

    # 4. Open SalesView - rate_spin should automatically reflect default main chicken rate (185.50)
    sales_view = SalesView()
    assert sales_view.rate_spin.value() == 185.50

    # 5. User enters weights: Gross=100 KG, Box=10 KG -> Net=90 KG
    sales_view.gross_spin.setValue(100.0)
    sales_view.box_spin.setValue(10.0)
    sales_view._calculate_net_and_amount()

    assert sales_view.net_edit.text() == "90.000 KG"
    # Net 90 * 185.50 = 16,695.00
    assert "16,695.00" in sales_view.amount_edit.text()

    # 6. Customer requests special rate while sale is happening: Edit rate from 185.50 to 180.00
    sales_view.rate_spin.setValue(180.00)
    sales_view._calculate_net_and_amount()
    # Net 90 * 180.00 = 16,200.00
    assert "16,200.00" in sales_view.amount_edit.text()

    # 7. Save this sale
    sales_view._save_sale()

    # Verify sale was saved with the custom customer rate (180.00)
    sales = SalesService.get_sales()
    assert len(sales) == 1
    assert sales[0].rate_per_kg == Decimal("180.00")
    assert sales[0].total_amount == Decimal("16200.00")

    # 8. Verify global main rate is still 185.50
    assert SettingService.get_main_chicken_rate() == Decimal("185.50")

    # 9. Verify sales form automatically reset with the default main rate (185.50) for the NEXT customer!
    assert sales_view.gross_spin.value() == 0.0
    assert sales_view.box_spin.value() == 0.0
    assert sales_view.rate_spin.value() == 185.50

    # 10. Test Reset Button functionality: if user edits rate and clicks reset, it reverts to main rate
    sales_view.rate_spin.setValue(195.00)
    assert sales_view.rate_spin.value() == 195.00
    sales_view.apply_default_rate(force=True)
    assert sales_view.rate_spin.value() == 185.50

def test_sales_box_count():
    cust = MasterService.create_customer(name="Box Count Customer")
    item = MasterService.get_all_items()[0]

    # Sale with 10 boxes, Gross 120 KG, Box weight 10 KG -> Net 110 KG @ ₹160
    sale = SalesService.create_sale(
        transaction_date=date(2026, 9, 23),
        customer_id=cust.id,
        item_id=item.id,
        gross_weight_kg=120,
        box_weight_kg=10,
        box_count=10,
        rate_per_kg=160
    )
    assert sale.box_count == 10
    assert sale.net_weight_kg == Decimal("110.000")
    assert sale.total_amount == Decimal("17600.00")

    # Update box count
    updated = SalesService.update_sale(
        sale_id=sale.id,
        transaction_date=date(2026, 9, 23),
        customer_id=cust.id,
        item_id=item.id,
        gross_weight_kg=120,
        box_weight_kg=10,
        box_count=12,
        rate_per_kg=160
    )
    assert updated.box_count == 12

    # Negative box count validation
    with pytest.raises(ValueError, match="Box count cannot be negative"):
        SalesService.create_sale(
            transaction_date=date(2026, 9, 23),
            customer_id=cust.id,
            item_id=item.id,
            gross_weight_kg=100,
            box_weight_kg=5,
            box_count=-3,
            rate_per_kg=160
        )

def test_sales_view_boxes_ui_and_edit_dialog(qapp, monkeypatch):
    from app.ui.views.sales_view import SalesView, EditSaleDialog
    from PySide6.QtWidgets import QMessageBox

    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: QMessageBox.Ok)
    monkeypatch.setattr(QMessageBox, "warning", lambda *args, **kwargs: QMessageBox.Ok)

    cust = MasterService.create_customer(name="Boxes Customer UI")
    item = MasterService.get_all_items()[0]

    view = SalesView()
    view.load_combos()
    view.customer_combo.setCurrentIndex(view.customer_combo.findData(cust.id))
    view.item_combo.setCurrentIndex(view.item_combo.findData(item.id))

    # Enter 8 boxes, 160 KG gross, 10 KG box weight, ₹170 rate
    view.box_count_spin.setValue(8)
    view.gross_spin.setValue(160.0)
    view.box_spin.setValue(10.0)
    view.rate_spin.setValue(170.0)

    # Live calculate
    view._calculate_net_and_amount()
    assert view.net_edit.text() == "150.000 KG"

    # Save sale
    view._save_sale()

    # Form reset
    assert view.box_count_spin.value() == 0
    assert view.gross_spin.value() == 0.0

    # History table check
    assert view.table.rowCount() >= 1
    row = 0
    assert view.table.item(row, 4).text() == "8"
    assert "160.000" in view.table.item(row, 5).text()
    assert "10.000" in view.table.item(row, 6).text()
    assert "150.000" in view.table.item(row, 7).text()

    # EditSaleDialog check
    saved_sale = SalesService.get_sales(customer_id=cust.id)[0]
    dlg = EditSaleDialog(saved_sale)
    assert dlg.box_count_spin.value() == 8
    dlg.box_count_spin.setValue(10)
    data = dlg.get_data()
    assert data["box_count"] == 10



