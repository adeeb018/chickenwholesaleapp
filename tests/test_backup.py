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
