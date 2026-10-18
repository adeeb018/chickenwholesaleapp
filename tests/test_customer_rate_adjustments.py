import pytest
from datetime import date, timedelta
from decimal import Decimal
from PySide6.QtCore import Qt
from app.services.master_service import MasterService
from app.services.setting_service import SettingService
from app.services.sales_service import SalesService
from app.services.customer_rate_adjustment_service import CustomerRateAdjustmentService
from app.ui.views.sales_view import SalesView
from app.ui.views.customers_view import CustomersView
from app.ui.views.customer_rate_adjustments_dialog import (
    CustomerRateAdjustmentsDialog, AddRateAdjustmentDialog
)

def test_customer_rate_adjustment_service_crud_and_matching():
    # 1. Setup customer and set main chicken rate = 185.00
    cust = MasterService.create_customer(name="VIP Restaurant", phone="9988771122")
    SettingService.set_main_chicken_rate(185.00)

    # Reject invalid date range
    with pytest.raises(ValueError, match="Start date cannot be after end date"):
        CustomerRateAdjustmentService.create_adjustment(
            customer_id=cust.id,
            adjustment_per_kg=-5.00,
            start_date=date(2026, 10, 20),
            end_date=date(2026, 10, 10)
        )

    # Reject non-existent customer
    with pytest.raises(ValueError, match="does not exist"):
        CustomerRateAdjustmentService.create_adjustment(
            customer_id=99999,
            adjustment_per_kg=-5.00,
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 31)
        )

    # 2. Create an adjustment: -₹5.00/KG for October, but WEEKENDS ONLY (SAT, SUN)
    adj = CustomerRateAdjustmentService.create_adjustment(
        customer_id=cust.id,
        adjustment_per_kg=-5.00,
        start_date=date(2026, 10, 1),
        end_date=date(2026, 10, 31),
        days_of_week=["SAT", "SUN"],
        notes="Weekend Special Discount"
    )
    assert adj.id is not None
    assert adj.adjustment_per_kg == Decimal("-5.00")
    assert adj.days_of_week == "SAT,SUN"

    # 3. Test matching on Sunday (e.g. 18/10/2026 is Sunday)
    sunday_date = date(2026, 10, 18)
    assert sunday_date.weekday() == 6  # Sunday
    matched = CustomerRateAdjustmentService.get_adjustment_for_customer(cust.id, sunday_date)
    assert matched is not None
    assert matched.id == adj.id

    eff_rate, matched_adj, main_rate = CustomerRateAdjustmentService.get_effective_rate_for_customer(cust.id, sunday_date)
    assert main_rate == Decimal("185.00")
    assert matched_adj is not None
    assert eff_rate == Decimal("180.00")  # 185 - 5 = 180

    # 4. Test matching on Monday (e.g. 19/10/2026 is Monday) -> Should NOT match (weekend only)
    monday_date = date(2026, 10, 19)
    assert monday_date.weekday() == 0  # Monday
    matched_mon = CustomerRateAdjustmentService.get_adjustment_for_customer(cust.id, monday_date)
    assert matched_mon is None

    eff_rate_mon, matched_adj_mon, main_rate_mon = CustomerRateAdjustmentService.get_effective_rate_for_customer(cust.id, monday_date)
    assert matched_adj_mon is None
    assert eff_rate_mon == Decimal("185.00")  # Standard Main Rate

    # 5. Test matching outside date range (e.g. November) -> Should NOT match
    nov_date = date(2026, 11, 1)
    assert CustomerRateAdjustmentService.get_adjustment_for_customer(cust.id, nov_date) is None

    # 6. Delete adjustment
    success = CustomerRateAdjustmentService.delete_adjustment(adj.id)
    assert success is True
    # Verify no longer active
    assert CustomerRateAdjustmentService.get_adjustment_for_customer(cust.id, sunday_date) is None


def test_customer_rate_adjustments_bulk_clear():
    cust = MasterService.create_customer(name="Bulk Clear Customer")
    CustomerRateAdjustmentService.create_adjustment(
        customer_id=cust.id,
        adjustment_per_kg=-3.00,
        start_date=date(2026, 10, 1),
        end_date=date(2026, 10, 15)
    )
    CustomerRateAdjustmentService.create_adjustment(
        customer_id=cust.id,
        adjustment_per_kg=-4.00,
        start_date=date(2026, 10, 16),
        end_date=date(2026, 10, 31)
    )
    assert len(CustomerRateAdjustmentService.get_adjustments(customer_id=cust.id, active_only=True)) == 2

    # Clear all for this customer
    deleted_count = CustomerRateAdjustmentService.delete_adjustments_for_customer(cust.id)
    assert deleted_count == 2
    assert len(CustomerRateAdjustmentService.get_adjustments(customer_id=cust.id, active_only=True)) == 0


def test_sales_view_auto_fill_with_rate_adjustment_and_live_edit(qapp):
    SettingService.set_main_chicken_rate(190.00)

    # Customer 1 has -₹10.00 discount on all days of this week
    today = date.today()
    c1 = MasterService.create_customer(name="Discounted Customer 1")
    c2 = MasterService.create_customer(name="Regular Customer 2")
    item = MasterService.get_all_items()[0]

    CustomerRateAdjustmentService.create_adjustment(
        customer_id=c1.id,
        adjustment_per_kg=-10.00,
        start_date=today - timedelta(days=2),
        end_date=today + timedelta(days=5),
        days_of_week=None,  # all days
        notes="Wholesale Loyalty Discount"
    )

    sales_view = SalesView()

    # 1. Select Customer 1: Default rate must auto-fill with 190 - 10 = 180.00
    idx1 = sales_view.customer_combo.findData(c1.id)
    sales_view.customer_combo.setCurrentIndex(idx1)
    sales_view._on_customer_or_date_changed()

    assert sales_view.rate_spin.value() == 180.00
    assert "Special Party Discount" in sales_view.adj_info_label.text()
    assert "-₹10.00/KG" in sales_view.adj_info_label.text()
    assert "180.00" in sales_view.adj_info_label.text()

    # 2. Select Customer 2: Default rate must auto-fill with benchmark 190.00 (no adjustment)
    idx2 = sales_view.customer_combo.findData(c2.id)
    sales_view.customer_combo.setCurrentIndex(idx2)
    sales_view._on_customer_or_date_changed()

    assert sales_view.rate_spin.value() == 190.00
    assert "Standard Benchmark Rate" in sales_view.adj_info_label.text()

    # 3. Switch back to Customer 1
    sales_view.customer_combo.setCurrentIndex(idx1)
    sales_view._on_customer_or_date_changed()
    assert sales_view.rate_spin.value() == 180.00

    # 4. User enters weights: Gross=100 KG, Box=10 KG -> Net=90 KG
    sales_view.gross_spin.setValue(100.0)
    sales_view.box_spin.setValue(10.0)
    sales_view._calculate_net_and_amount()
    # 90 * 180 = 16,200.00
    assert "16,200.00" in sales_view.amount_edit.text()

    # 5. User custom edits rate for this customer to 175.00 while sale is happening
    sales_view.rate_spin.setValue(175.00)
    sales_view._calculate_net_and_amount()
    # 90 * 175 = 15,750.00
    assert "15,750.00" in sales_view.amount_edit.text()

    # 6. Save sale
    sales_view._save_sale()

    # Verify sale saved with the custom rate
    sales = SalesService.get_sales()
    saved_sale = [s for s in sales if s.customer_id == c1.id][-1]
    assert saved_sale.rate_per_kg == Decimal("175.00")
    assert saved_sale.total_amount == Decimal("15750.00")

    # 7. Form automatically resets and re-evaluates customer's default adjusted rate (180.00)
    assert sales_view.gross_spin.value() == 0.0
    assert sales_view.rate_spin.value() == 180.00


def test_dialogs_and_customer_view_buttons(qapp):
    cust = MasterService.create_customer(name="Dialog Test Customer")
    
    # 1. Add Rate Adjustment Dialog presets
    add_dlg = AddRateAdjustmentDialog(preselected_customer_id=cust.id)
    assert add_dlg.get_selected_customer_ids() == [cust.id]
    
    # Test preset buttons
    add_dlg._preset_today()
    assert add_dlg.start_date_edit.date() == add_dlg.end_date_edit.date()
    
    add_dlg._preset_this_month()
    assert add_dlg.start_date_edit.date().day() == 1

    add_dlg._select_weekends()
    assert add_dlg.day_checkboxes["SAT"].isChecked()
    assert add_dlg.day_checkboxes["SUN"].isChecked()
    assert not add_dlg.day_checkboxes["MON"].isChecked()

    add_dlg.adj_spin.setValue(-7.50)
    add_dlg.notes_edit.setText("Weekend Promo")
    add_dlg._on_save()

    # 2. Verify adjustment saved
    adjs = CustomerRateAdjustmentService.get_adjustments(customer_id=cust.id)
    assert len(adjs) == 1
    assert adjs[0].adjustment_per_kg == Decimal("-7.50")
    assert adjs[0].days_of_week == "SAT,SUN"

    # 3. Manager Dialog
    mgr_dlg = CustomerRateAdjustmentsDialog(preselected_customer_id=cust.id)
    assert mgr_dlg.table.rowCount() == 1
    assert "-₹7.50/KG" in mgr_dlg.table.item(0, 2).text()
    assert "SAT,SUN" in mgr_dlg.table.item(0, 4).text()
    assert "Weekend Promo" in mgr_dlg.table.item(0, 5).text()

    # 4. CustomersView has Rate Adjustments button
    cv = CustomersView()
    assert hasattr(cv, "_open_rate_adjustments")


def test_multiple_customer_rate_adjustment_in_one_go(qapp):
    SettingService.set_main_chicken_rate(180.00)

    # 1. Create 3 distinct customers
    p1 = MasterService.create_customer(name="Multi Party 1", phone="9111111111")
    p2 = MasterService.create_customer(name="Multi Party 2", phone="9222222222")
    p3 = MasterService.create_customer(name="Multi Party 3", phone="9333333333")

    today = date.today()

    # 2. Open AddRateAdjustmentDialog
    dlg = AddRateAdjustmentDialog()
    assert len(dlg.get_selected_customer_ids()) == 0

    # Test Select All and Clear All
    dlg._select_all_customers()
    assert len(dlg.get_selected_customer_ids()) >= 3

    dlg._clear_all_customers()
    assert len(dlg.get_selected_customer_ids()) == 0

    # Test Search / Filtering
    dlg._filter_customer_list("Multi Party 1")
    # Item for Party 1 should be visible, others hidden
    visible_count = sum(1 for i in range(dlg.customer_list.count()) if not dlg.customer_list.item(i).isHidden())
    assert visible_count == 1

    # Reset search
    dlg._filter_customer_list("")

    # Select p1 and p2 specifically
    for i in range(dlg.customer_list.count()):
        item = dlg.customer_list.item(i)
        if item.data(Qt.UserRole) in [p1.id, p2.id]:
            item.setCheckState(Qt.Checked)
        else:
            item.setCheckState(Qt.Unchecked)

    selected_ids = dlg.get_selected_customer_ids()
    assert set(selected_ids) == {p1.id, p2.id}
    assert "2 /" in dlg.cust_count_badge.text()

    # 3. Apply -₹8.00/KG for this week to both customers in one go
    dlg._preset_this_week()
    dlg.adj_spin.setValue(-8.00)
    dlg.notes_edit.setText("Multi-party Group Offer")
    dlg._on_save()

    # 4. Verify both p1 and p2 got the adjustment applied, but p3 did not
    p1_adjs = CustomerRateAdjustmentService.get_adjustments(customer_id=p1.id)
    p2_adjs = CustomerRateAdjustmentService.get_adjustments(customer_id=p2.id)
    p3_adjs = CustomerRateAdjustmentService.get_adjustments(customer_id=p3.id)

    assert len(p1_adjs) == 1
    assert p1_adjs[0].adjustment_per_kg == Decimal("-8.00")
    assert p1_adjs[0].notes == "Multi-party Group Offer"

    assert len(p2_adjs) == 1
    assert p2_adjs[0].adjustment_per_kg == Decimal("-8.00")
    assert p2_adjs[0].notes == "Multi-party Group Offer"

    assert len(p3_adjs) == 0

    # 5. Verify effective rates in SalesView
    eff1, _, _ = CustomerRateAdjustmentService.get_effective_rate_for_customer(p1.id, today)
    eff2, _, _ = CustomerRateAdjustmentService.get_effective_rate_for_customer(p2.id, today)
    eff3, _, _ = CustomerRateAdjustmentService.get_effective_rate_for_customer(p3.id, today)

    assert eff1 == Decimal("172.00")  # 180 - 8 = 172
    assert eff2 == Decimal("172.00")  # 180 - 8 = 172
    assert eff3 == Decimal("180.00")  # Standard benchmark rate

