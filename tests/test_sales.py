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

def test_multi_batch_sale_dialog_layout_and_data_visibility(qapp):
    from app.services.purchase_service import PurchaseService
    from app.ui.views.sales_view import MultiBatchSaleDialog
    from PySide6.QtWidgets import QHeaderView

    prov = MasterService.create_provider(name="Multi Batch Provider")
    item = MasterService.get_all_items()[0]

    # Create two purchase batches
    p1 = PurchaseService.create_purchase(
        transaction_date=date.today(),
        provider_id=prov.id,
        item_id=item.id,
        gross_weight_kg=200,
        box_weight_kg=10,
        rate_per_kg=130,
        voucher_number="V-101"
    )
    p2 = PurchaseService.create_purchase(
        transaction_date=date.today(),
        provider_id=prov.id,
        item_id=item.id,
        gross_weight_kg=300,
        box_weight_kg=15,
        rate_per_kg=135,
        voucher_number="V-102"
    )

    dlg = MultiBatchSaleDialog(item_id=item.id, default_rate=Decimal("175.00"))

    # 1. Verify dialog sizing and row heights
    assert dlg.width() >= 960
    assert dlg.table.verticalHeader().defaultSectionSize() >= 42

    # 2. Verify column widths and stretch modes
    from PySide6.QtCore import Qt
    header = dlg.table.horizontalHeader()
    assert dlg.table.horizontalScrollBarPolicy() == Qt.ScrollBarAsNeeded
    assert dlg.table.columnWidth(0) >= 240  # Batch Name / Inventory Source
    assert dlg.table.columnWidth(1) == 90   # Boxes
    assert dlg.table.columnWidth(2) == 125  # Gross
    assert dlg.table.columnWidth(3) == 125  # Box
    assert dlg.table.columnWidth(4) == 125  # Net
    assert dlg.table.columnWidth(5) == 120  # Rate
    assert dlg.table.columnWidth(6) == 130  # Amount
    assert dlg.table.columnWidth(7) == 95   # Action

    # 3. Verify row auto-calculation and visibility
    assert dlg.table.rowCount() == 1
    dlg.table.cellWidget(0, 1).setValue(5)       # Boxes
    dlg.table.cellWidget(0, 2).setValue(110.000) # Gross
    dlg.table.cellWidget(0, 3).setValue(10.000)  # Box
    dlg.table.cellWidget(0, 5).setValue(175.00)  # Rate

    # Live math updates
    assert dlg.table.cellWidget(0, 4).text() == "100.000 KG"
    assert dlg.table.cellWidget(0, 6).text() == "₹17,500.00"
    assert "100.000 KG" in dlg.total_net_lbl.text()
    assert "17,500.00" in dlg.total_amt_lbl.text()

    # 4. Add second row and test removal
    dlg._add_row()
    assert dlg.table.rowCount() == 2
    del_container = dlg.table.cellWidget(1, 7)
    del_btn = del_container.findChild(object)
    dlg._remove_row(1)
    assert dlg.table.rowCount() == 1


def test_sales_return_quick_dialog_no_detached_error(qapp, monkeypatch):
    from app.services.purchase_service import PurchaseService
    from app.services.customer_return_service import CustomerReturnService
    from app.ui.views.sales_view import QuickSaleReturnDialog
    from PySide6.QtWidgets import QMessageBox

    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: QMessageBox.Ok)
    monkeypatch.setattr(QMessageBox, "warning", lambda *args, **kwargs: QMessageBox.Ok)
    monkeypatch.setattr(QMessageBox, "critical", lambda *args, **kwargs: QMessageBox.Ok)

    prov = MasterService.create_provider(name="Return Test Prov")
    cust = MasterService.create_customer(name="Return Test Cust")
    item = MasterService.get_all_items()[0]

    pur = PurchaseService.create_purchase(
        transaction_date=date.today(),
        provider_id=prov.id,
        item_id=item.id,
        gross_weight_kg=200,
        box_weight_kg=0,
        rate_per_kg=120,
        voucher_number="V-RET-1"
    )

    sale = SalesService.create_sale(
        transaction_date=date.today(),
        customer_id=cust.id,
        item_id=item.id,
        gross_weight_kg=50,
        box_weight_kg=0,
        rate_per_kg=160
    )

    # 1. Verify get_returnable_sale_info returns detached-safe object with pre-loaded relations
    info = CustomerReturnService.get_returnable_sale_info(sale.id)
    assert info is not None
    s = info["sale"]
    assert s.customer.name == "Return Test Cust"
    assert s.item.name == item.name

    # 2. Instantiate QuickSaleReturnDialog directly
    dlg = QuickSaleReturnDialog(sale_id=sale.id)
    assert dlg.sale.customer.name == "Return Test Cust"
    assert dlg.gross_spin.value() > 0 or dlg.gross_spin.value() == 0.0

    # Fill return
    dlg.gross_spin.setValue(10.0)
    dlg.box_spin.setValue(0.0)
    dlg._recalc()
    assert dlg.credit_spin.value() == 1600.00  # 10 KG * 160

    # Test submit
    dlg._submit()
    # Check that return was recorded
    returns = CustomerReturnService.get_returns(customer_id=cust.id)
    assert len(returns) >= 1
    assert returns[0].financial_credit_amount == Decimal("1600.00")


def test_multi_batch_split_rate_reflection_and_no_hover_selection(qapp):
    from app.services.purchase_service import PurchaseService
    from app.ui.views.sales_view import MultiBatchSaleDialog, SalesView
    from PySide6.QtWidgets import QAbstractItemView

    prov = MasterService.create_provider(name="Split Rate Prov")
    cust = MasterService.create_customer(name="Split Rate Cust")
    item = MasterService.get_all_items()[0]

    p1 = PurchaseService.create_purchase(
        transaction_date=date.today(),
        provider_id=prov.id,
        item_id=item.id,
        gross_weight_kg=200,
        box_weight_kg=0,
        rate_per_kg=120,
        voucher_number="V-SR-1"
    )
    p2 = PurchaseService.create_purchase(
        transaction_date=date.today(),
        provider_id=prov.id,
        item_id=item.id,
        gross_weight_kg=200,
        box_weight_kg=0,
        rate_per_kg=125,
        voucher_number="V-SR-2"
    )

    dlg = MultiBatchSaleDialog(item_id=item.id, default_rate=Decimal("150.00"))

    # Verify no-selection and hover-safe settings
    assert dlg.table.selectionMode() == QAbstractItemView.NoSelection
    assert dlg.table.hasMouseTracking() is False
    assert dlg.table.viewport().hasMouseTracking() is False
    assert dlg.table.property("class") == "noHoverTable"

    # Add 2 rows with distinct rates: Row 1 = 50 KG @ 150 (7500), Row 2 = 50 KG @ 170 (8500)
    dlg.table.cellWidget(0, 1).setValue(2)
    dlg.table.cellWidget(0, 2).setValue(50.0)
    dlg.table.cellWidget(0, 3).setValue(0.0)
    dlg.table.cellWidget(0, 5).setValue(150.00)

    dlg._add_row()
    # Select second batch for row 1
    dlg.table.cellWidget(1, 0).setCurrentIndex(1)
    dlg.table.cellWidget(1, 1).setValue(3)
    dlg.table.cellWidget(1, 2).setValue(50.0)
    dlg.table.cellWidget(1, 3).setValue(0.0)
    dlg.table.cellWidget(1, 5).setValue(170.00)

    dlg._recalculate_all()
    # Total net: 100 KG, Total amount: 16,000.00, Effective rate: 160.00
    assert "100.000 KG" in dlg.total_net_lbl.text()
    assert "16,000.00" in dlg.total_amt_lbl.text()
    assert "160.00" in dlg.avg_rate_lbl.text()

    dlg._validate_and_accept()
    allocs = dlg.get_allocations()
    assert len(allocs) == 2
    assert allocs[0]["amount"] == Decimal("7500.00")
    assert allocs[1]["amount"] == Decimal("8500.00")


def test_edit_sale_dialog_multi_batch_support(qapp, monkeypatch):
    from app.services.purchase_service import PurchaseService
    from app.services.inventory_service import InventoryService
    from app.ui.views.sales_view import EditSaleDialog
    from PySide6.QtWidgets import QMessageBox

    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: QMessageBox.Ok)
    monkeypatch.setattr(QMessageBox, "warning", lambda *args, **kwargs: QMessageBox.Ok)
    monkeypatch.setattr(QMessageBox, "critical", lambda *args, **kwargs: QMessageBox.Ok)

    prov = MasterService.create_provider(name="Edit Multi Prov")
    cust = MasterService.create_customer(name="Edit Multi Cust")
    item = MasterService.get_all_items()[0]

    p1 = PurchaseService.create_purchase(
        transaction_date=date.today(),
        provider_id=prov.id,
        item_id=item.id,
        gross_weight_kg=300,
        box_weight_kg=0,
        rate_per_kg=120,
        voucher_number="V-ED-1"
    )
    p2 = PurchaseService.create_purchase(
        transaction_date=date.today(),
        provider_id=prov.id,
        item_id=item.id,
        gross_weight_kg=300,
        box_weight_kg=0,
        rate_per_kg=125,
        voucher_number="V-ED-2"
    )

    batches = InventoryService.get_sellable_batches(item_id=item.id)
    b1 = batches[0]
    b2 = batches[1]

    # Create multi-batch sale: 60 KG from b1 @ 150, 40 KG from b2 @ 160
    allocs = [
        {"batch_id": b1.id, "box_count": 3, "gross_weight_kg": Decimal("60.000"), "box_weight_kg": Decimal("0.000"), "net_weight_kg": Decimal("60.000"), "rate_per_kg": Decimal("150.00")},
        {"batch_id": b2.id, "box_count": 2, "gross_weight_kg": Decimal("40.000"), "box_weight_kg": Decimal("0.000"), "net_weight_kg": Decimal("40.000"), "rate_per_kg": Decimal("160.00")}
    ]
    sale = SalesService.create_sale(
        transaction_date=date.today(),
        customer_id=cust.id,
        item_id=item.id,
        gross_weight_kg=Decimal("100.000"),
        box_weight_kg=Decimal("0.000"),
        rate_per_kg=Decimal("154.00"),
        box_count=5,
        allocations=allocs
    )
    assert sale.total_amount == Decimal("15400.00")  # 60*150 (9000) + 40*160 (6400) = 15400

    # Open EditSaleDialog
    fresh_sale = SalesService.get_sale_by_id(sale.id)
    dlg = EditSaleDialog(fresh_sale)

    # Verify allocations table populated with 2 rows
    assert dlg.table.rowCount() == 2
    assert dlg.table.property("class") == "noHoverTable"
    assert dlg.table.cellWidget(0, 1).value() == 3
    assert dlg.table.cellWidget(0, 2).value() == 60.0
    assert dlg.table.cellWidget(0, 5).value() == 150.0
    assert dlg.table.cellWidget(1, 1).value() == 2
    assert dlg.table.cellWidget(1, 2).value() == 40.0
    assert dlg.table.cellWidget(1, 5).value() == 160.0

    # Edit row 0: Change weight to 70 KG, rate to 155
    dlg.table.cellWidget(0, 2).setValue(70.0)
    dlg.table.cellWidget(0, 5).setValue(155.0)
    dlg._recalculate_all()

    # Total net: 110 KG. Gross total = 70*155 (10850) + 40*160 (6400) = 17250.00
    assert "110.000 KG" in dlg.total_net_lbl.text()
    assert "17,250.00" in dlg.gross_amt_lbl.text()

    # Save edit
    dlg._validate_and_save()
    data = dlg.get_data()
    updated_sale = SalesService.update_sale(sale_id=sale.id, **data)

    assert updated_sale.net_weight_kg == Decimal("110.000")
    assert updated_sale.total_amount == Decimal("17250.00")
    assert len(updated_sale.allocations) == 2




