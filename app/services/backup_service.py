import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Tuple
from app.config.settings import get_db_path

class BackupService:
    @staticmethod
    def backup_database(destination_path: Path | str) -> Tuple[bool, str]:
        """
        Safely backs up the active SQLite database using sqlite3 online backup API.
        """
        try:
            dest = Path(destination_path)
            dest.parent.mkdir(parents=True, exist_ok=True)
            
            src_db_path = get_db_path()
            if not src_db_path.exists():
                return False, f"Source database file does not exist at {src_db_path}"

            src_conn = sqlite3.connect(src_db_path)
            dest_conn = sqlite3.connect(dest)
            
            with dest_conn:
                src_conn.backup(dest_conn)
                
            src_conn.close()
            dest_conn.close()
            
            return True, f"Backup successfully created at {dest}"
        except Exception as e:
            return False, f"Backup failed: {str(e)}"

    @staticmethod
    def restore_database(backup_file_path: Path | str) -> Tuple[bool, str]:
        """
        Restores SQLite database from a backup file after validating header.
        """
        try:
            backup_path = Path(backup_file_path)
            if not backup_path.exists():
                return False, f"Backup file not found at {backup_path}"

            # Verify file is a valid SQLite database
            try:
                test_conn = sqlite3.connect(backup_path)
                cursor = test_conn.cursor()
                cursor.execute("PRAGMA schema_version;")
                test_conn.close()
            except Exception:
                return False, "Selected file is not a valid SQLite database."

            target_db_path = get_db_path()
            
            # Create a safety pre-restore backup first
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safety_backup = target_db_path.parent / f"pre_restore_safety_{timestamp}.db"
            if target_db_path.exists():
                shutil.copy2(target_db_path, safety_backup)

            # Restore using backup API
            src_conn = sqlite3.connect(backup_path)
            dest_conn = sqlite3.connect(target_db_path)
            with dest_conn:
                src_conn.backup(dest_conn)
            src_conn.close()
            dest_conn.close()

            return True, f"Database restored successfully from {backup_path}. (Pre-restore copy saved at {safety_backup.name})"
        except Exception as e:
            return False, f"Restore failed: {str(e)}"
