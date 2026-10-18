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
