from pathlib import Path
from app.services.master_service import MasterService
from app.services.backup_service import BackupService
from app.database.connection import init_db

def test_backup_and_restore(tmp_path, monkeypatch):
    src_db = tmp_path / "src.db"
    monkeypatch.setattr("app.services.backup_service.get_db_path", lambda: src_db)
    
    # Initialize DB at src_db
    init_db(f"sqlite:///{src_db.as_posix()}")

    # 1. Create data
    cust = MasterService.create_customer(name="Backup Test Customer")
    assert cust.id is not None

    # 2. Perform backup
    backup_file = tmp_path / "test_backup.db"
    success, msg = BackupService.backup_database(backup_file)
    assert success is True, msg
    assert backup_file.exists()

    # 3. Perform restore
    res_success, res_msg = BackupService.restore_database(backup_file)
    assert res_success is True, res_msg

def test_admin_password_and_clear_all_data():
    from app.services.setting_service import SettingService
    from app.services.purchase_service import PurchaseService
    from app.services.master_service import MasterService
    from datetime import date
    from app.database.connection import session_scope
    from app.database.models import Purchase

    # 1. Password strength checks
    assert SettingService.validate_password_strength("")[0] is False
    assert SettingService.validate_password_strength("short")[0] is False
    assert SettingService.validate_password_strength("onlyletters")[0] is False
    assert SettingService.validate_password_strength("12345678")[0] is False
    assert SettingService.validate_password_strength("ValidPass2026")[0] is True

    # 2. Set admin password
    ok, msg = SettingService.set_admin_password("ValidPass2026")
    assert ok is True
    assert SettingService.is_admin_password_set() is True
    assert SettingService.verify_admin_password("ValidPass2026") is True
    assert SettingService.verify_admin_password("WrongPass123") is False

    # 3. Change password
    fail_change, _ = SettingService.change_admin_password("WrongCurrent", "NewPass2026")
    assert fail_change is False
    success_change, _ = SettingService.change_admin_password("ValidPass2026", "NewPass2026")
    assert success_change is True
    assert SettingService.verify_admin_password("NewPass2026") is True

    # 4. Clear data
    ok_clear, msg_clear = SettingService.clear_all_data(include_masters=False)
    assert ok_clear is True
    with session_scope() as session:
        assert session.query(Purchase).count() == 0
