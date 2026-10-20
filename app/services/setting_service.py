from decimal import Decimal
from typing import Optional, Union
from app.database.connection import session_scope
from app.database.models import AppSetting
from app.utils.decimal_utils import to_decimal, round_currency

class SettingService:
    """
    Service for managing system-wide application settings and defaults,
    including the daily Main Chicken Selling Rate.
    """
    KEY_MAIN_CHICKEN_RATE = "main_chicken_rate"

    @classmethod
    def get_setting(cls, key: str, default: Optional[str] = None) -> Optional[str]:
        """Retrieves a setting string value by its key."""
        with session_scope() as session:
            setting = session.query(AppSetting).filter(AppSetting.key == key).first()
            if setting:
                return setting.value
            return default

    @classmethod
    def set_setting(cls, key: str, value: str, description: Optional[str] = None) -> None:
        """Saves or updates a setting key-value pair."""
        with session_scope() as session:
            setting = session.query(AppSetting).filter(AppSetting.key == key).first()
            if setting:
                setting.value = str(value)
                if description:
                    setting.description = description
            else:
                setting = AppSetting(key=key, value=str(value), description=description)
                session.add(setting)

    @classmethod
    def get_main_chicken_rate(cls) -> Decimal:
        """
        Retrieves the main selling rate for chicken (₹/KG).
        Defaults to 0.00 if not set.
        """
        val = cls.get_setting(cls.KEY_MAIN_CHICKEN_RATE)
        if not val or not val.strip():
            return Decimal("0.00")
        try:
            return round_currency(to_decimal(val))
        except Exception:
            return Decimal("0.00")

    @classmethod
    def set_main_chicken_rate(cls, rate: Union[Decimal, float, str, int]) -> Decimal:
        """
        Sets and persists the daily main selling rate for chicken (₹/KG).
        Validates that rate is not negative.
        """
        dec_rate = round_currency(to_decimal(rate))
        if dec_rate < Decimal("0.00"):
            raise ValueError("Main chicken rate cannot be negative.")

        cls.set_setting(
            cls.KEY_MAIN_CHICKEN_RATE,
            str(dec_rate),
            description="Daily benchmark selling rate for chicken (₹/KG)"
        )
        return dec_rate

    KEY_ADMIN_PASSWORD_HASH = "admin_password_hash"
    KEY_ADMIN_PASSWORD_SALT = "admin_password_salt"

    @classmethod
    def is_admin_password_set(cls) -> bool:
        """Returns True if an admin protection password has been configured."""
        h = cls.get_setting(cls.KEY_ADMIN_PASSWORD_HASH)
        s = cls.get_setting(cls.KEY_ADMIN_PASSWORD_SALT)
        return bool(h and s and h.strip() and s.strip())

    @classmethod
    def validate_password_strength(cls, password: str) -> tuple[bool, str]:
        """Validates that password is strong (at least 8 chars, containing letters and numbers)."""
        if not password:
            return False, "Password cannot be empty."
        if len(password) < 8:
            return False, "Password must be at least 8 characters long."
        if not any(c.isalpha() for c in password):
            return False, "Password must include at least one letter."
        if not any(c.isdigit() for c in password):
            return False, "Password must include at least one number."
        return True, ""

    @classmethod
    def set_admin_password(cls, password: str) -> tuple[bool, str]:
        """Sets and persists the admin password hash and salt with PBKDF2."""
        import hashlib
        import secrets

        valid, err_msg = cls.validate_password_strength(password)
        if not valid:
            return False, err_msg

        salt = secrets.token_bytes(16)
        h = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000)
        cls.set_setting(cls.KEY_ADMIN_PASSWORD_HASH, h.hex(), "Admin security password PBKDF2-SHA256 hash")
        cls.set_setting(cls.KEY_ADMIN_PASSWORD_SALT, salt.hex(), "Admin security password salt")
        return True, "Admin password created successfully."

    @classmethod
    def verify_admin_password(cls, password: str) -> bool:
        """Verifies provided password against stored hash."""
        import hashlib
        import secrets

        stored_hash = cls.get_setting(cls.KEY_ADMIN_PASSWORD_HASH)
        stored_salt = cls.get_setting(cls.KEY_ADMIN_PASSWORD_SALT)
        if not stored_hash or not stored_salt:
            return False
        try:
            salt = bytes.fromhex(stored_salt)
            computed = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000).hex()
            return secrets.compare_digest(computed, stored_hash)
        except Exception:
            return False

    @classmethod
    def change_admin_password(cls, current_password: str, new_password: str) -> tuple[bool, str]:
        """Changes the admin password after verifying current password."""
        if not cls.verify_admin_password(current_password):
            return False, "Current password is incorrect."
        return cls.set_admin_password(new_password)

    @classmethod
    def clear_all_data(cls, include_masters: bool = False) -> tuple[bool, str]:
        """
        Permanently clears transactional and inventory data from the database.
        Optionally removes customers and providers if include_masters is True.
        Always creates an automated safety backup before clearing.
        Preserves app settings (e.g. admin password and rate benchmark).
        """
        from datetime import datetime
        from app.config.settings import get_db_path
        from app.services.backup_service import BackupService
        from app.database.models import (
            Purchase, PurchaseBatch, Sale, SaleBatchAllocation,
            CustomerPayment, ProviderPayment, DailyStockReconciliation,
            InventoryMovement, CustomerReturn, CustomerReturnLine,
            CustomerRateAdjustment, Customer, CustomerOpeningBalance,
            Provider, ProviderOpeningBalance
        )

        # 1. Automatic safety backup
        safety_name = f"safety_pre_clear_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        safety_dir = get_db_path().parent / "backups"
        safety_dir.mkdir(parents=True, exist_ok=True)
        safety_path = str(safety_dir / safety_name)
        ok_backup, backup_msg = BackupService.backup_database(safety_path)
        if not ok_backup:
            return False, f"Failed to create pre-clear safety backup: {backup_msg}. Operation cancelled for safety."

        # 2. Delete transactional records in foreign-key safe order
        with session_scope() as session:
            session.query(CustomerReturnLine).delete()
            session.query(CustomerReturn).delete()
            session.query(SaleBatchAllocation).delete()
            session.query(Sale).delete()
            session.query(CustomerPayment).delete()
            session.query(ProviderPayment).delete()
            session.query(DailyStockReconciliation).delete()
            session.query(InventoryMovement).delete()
            session.query(PurchaseBatch).delete()
            session.query(Purchase).delete()
            session.query(CustomerRateAdjustment).delete()

            if include_masters:
                session.query(CustomerOpeningBalance).delete()
                session.query(Customer).delete()
                session.query(ProviderOpeningBalance).delete()
                session.query(Provider).delete()

        try:
            from app.database.audit_logger import AuditLogger
            AuditLogger.log_system_event(
                "SYSTEM",
                "database",
                "ALL",
                f"Permanent data clearance executed (include_masters={include_masters}). Safety backup created at {safety_path}"
            )
        except Exception:
            pass

        return True, f"Data successfully cleared. Safety backup saved at: {safety_path}"
