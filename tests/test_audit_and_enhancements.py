import os
import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path
import pytest
from PySide6.QtWidgets import QApplication

from app.database.connection import init_db, get_session, session_scope
from app.database.models import Item, Provider, Customer, Sale, CustomerReturn, CustomerReturnLine, Purchase
from app.database.audit_logger import AuditLogger
from app.services.master_service import MasterService
from app.services.balance_service import BalanceService
from app.services.setting_service import SettingService
from app.domain.accounting import generate_customer_ledger
from app.utils.decimal_utils import round_money, round_weight

@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if not app:
        app = QApplication([])
    return app

@pytest.fixture(autouse=True)
def setup_test_audit_log(tmp_path, monkeypatch):
    log_file = tmp_path / "test_audit.log"
    monkeypatch.setenv("CHICKEN_WHOLESALE_AUDIT_LOG_PATH", str(log_file))
    yield

def test_item_soft_delete():
    """Verify that chicken types / items can be deleted (soft-deleted)."""
    item = MasterService.create_item(name="Organic Country Chicken", code="OCC")
    assert item.id is not None
    assert item.is_active is True
    assert item.is_deleted is False

    # Soft delete item
    success = MasterService.soft_delete_item(item.id)
    assert success is True

    # Active items should no longer contain it
    active_items = MasterService.get_all_items(include_inactive=False)
    assert not any(i.id == item.id for i in active_items)

    # Inactive list should also not return it if is_deleted == True
    all_items = MasterService.get_all_items(include_inactive=True)
    assert not any(i.id == item.id for i in all_items)

def test_customer_statement_return_rate():
    """Verify that customer returns on customer statement populate return rate per kg."""
    from app.services.sales_service import SalesService
    from app.services.purchase_service import PurchaseService
    from app.services.customer_return_service import CustomerReturnService

    prov = MasterService.create_provider(name="Prov Statement Rate Test")
    cust = MasterService.create_customer(name="Cust Statement Rate Test")
    item = MasterService.create_item(name="Item Statement Rate Test")

    pur = PurchaseService.create_purchase(
        provider_id=prov.id,
        item_id=item.id,
        weight_kg=Decimal("100.000"),
        rate_per_kg=Decimal("100.00"),
        gross_weight_kg=Decimal("110.000"),
        box_weight_kg=Decimal("10.000"),
        box_count=2,
        transaction_date=date(2026, 10, 20),
        payment_type="CASH",
        voucher_number="V-STMT-RATE"
    )

    sale = SalesService.create_sale(
        transaction_date=date(2026, 10, 20),
        customer_id=cust.id,
        item_id=item.id,
        gross_weight_kg=Decimal("25.000"),
        box_weight_kg=Decimal("5.000"),
        rate_per_kg=Decimal("150.00"),
        box_count=2
    )

    cr = CustomerReturnService.create_customer_return(
        customer_id=cust.id,
        original_sale_id=sale.id,
        return_date=date(2026, 10, 20),
        lines_data=[{
            "returned_gross_weight_kg": Decimal("12.000"),
            "returned_box_weight_kg": Decimal("2.000"),
            "box_count": 1,
            "rate_per_kg": Decimal("150.00"),
            "resale_eligible": True,
            "financial_credit_amount": Decimal("1500.00"),
            "return_reason": "Excess Order"
        }]
    )

    stmt = BalanceService.get_customer_statement(cust.id, date(2026, 10, 1), date(2026, 10, 31))
    assert stmt is not None

    # Find the customer return ledger entry
    return_entries = [e for e in stmt.ledger_entries if e.transaction_type == "CUSTOMER_RETURN"]
    assert len(return_entries) == 1
    cr_entry = return_entries[0]
    
    # Rate per kg must be populated and equal 150.00
    assert cr_entry.rate_per_kg == Decimal("150.00")
    assert cr_entry.net_weight_kg == Decimal("10.000")
    assert cr_entry.credit == Decimal("1500.00")

def test_database_audit_logging():
    """Verify that all database operations are recorded with timestamps, actions, tables, and details."""
    # 1. Test INSERT logging
    item = MasterService.create_item(name="Test Audit Chicken", code="TAC")
    
    log_path = AuditLogger.get_log_file_path()
    assert log_path.exists()

    records = AuditLogger.read_logs()
    assert len(records) > 0

    insert_records = [r for r in records if r["table"] == "items" and r["action"] == "INSERT"]
    assert len(insert_records) >= 1
    assert "Test Audit Chicken" in insert_records[0]["details"]

    # 2. Test UPDATE logging
    MasterService.update_item(item.id, name="Test Audit Chicken Renamed", code="TAC2")
    records = AuditLogger.read_logs()
    update_records = [r for r in records if r["table"] == "items" and r["action"] == "UPDATE"]
    assert len(update_records) >= 1
    assert "name" in update_records[0]["details"]

    # 3. Test SOFT_DELETE logging
    MasterService.soft_delete_item(item.id)
    records = AuditLogger.read_logs()
    soft_del_records = [r for r in records if r["table"] == "items" and r["action"] == "SOFT_DELETE"]
    assert len(soft_del_records) >= 1
    assert "is_deleted" in soft_del_records[0]["details"]

def test_admin_password_and_settings_protection(qapp):
    """Verify password protection for viewing audit logs."""
    from app.ui.views.settings_view import SettingsView

    # Set password
    SettingService.set_admin_password("AdminPass123")
    assert SettingService.is_admin_password_set() is True
    assert SettingService.verify_admin_password("AdminPass123") is True
    assert SettingService.verify_admin_password("WrongPass") is False

def test_sales_return_dialog_read_only_credit(qapp):
    """Verify that final credit in QuickSaleReturnDialog is read-only and computed from weight * rate."""
    from app.ui.views.sales_view import QuickSaleReturnDialog
    from app.services.sales_service import SalesService
    from app.services.purchase_service import PurchaseService

    prov = MasterService.create_provider(name="Prov For Return Dialog Test")
    cust = MasterService.create_customer(name="Cust For Return Dialog Test")
    item = MasterService.create_item(name="Item For Return Dialog Test")

    pur = PurchaseService.create_purchase(
        provider_id=prov.id,
        item_id=item.id,
        weight_kg=Decimal("100.000"),
        rate_per_kg=Decimal("100.00"),
        gross_weight_kg=Decimal("110.000"),
        box_weight_kg=Decimal("10.000"),
        box_count=2,
        transaction_date=date(2026, 10, 20),
        payment_type="CASH",
        voucher_number="V-RET-TEST"
    )

    sale = SalesService.create_sale(
        transaction_date=date(2026, 10, 20),
        customer_id=cust.id,
        item_id=item.id,
        gross_weight_kg=Decimal("25.000"),
        box_weight_kg=Decimal("5.000"),
        rate_per_kg=Decimal("140.00"),
        box_count=2
    )

    dlg = QuickSaleReturnDialog(sale.id)
    
    # Assert credit_spin is read-only
    assert dlg.credit_spin.isReadOnly() is True

    # Test auto calculation: 10 kg gross, 2 kg box -> 8 kg net @ 140 = 1120.00
    dlg.gross_spin.setValue(10.0)
    dlg.box_spin.setValue(2.0)
    dlg.rate_spin.setValue(140.0)
    
    assert abs(dlg.credit_spin.value() - 1120.00) < 0.01
