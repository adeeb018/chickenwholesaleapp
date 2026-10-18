from datetime import date, datetime, timedelta
from typing import Tuple, Optional
from enum import Enum

class DateRangePreset(Enum):
    TODAY = "Today"
    YESTERDAY = "Yesterday"
    THIS_WEEK = "This Week"
    PREVIOUS_WEEK = "Previous Week"
    THIS_MONTH = "This Month"
    PREVIOUS_MONTH = "Previous Month"
    THIS_YEAR = "This Year"
    PREVIOUS_YEAR = "Previous Year"
    CUSTOM = "Custom Date Range"

def get_date_range_for_preset(
    preset: DateRangePreset, reference_date: Optional[date] = None
) -> Tuple[date, date]:
    """
    Returns (start_date, end_date) for a given DateRangePreset.
    Uses reference_date (defaults to date.today()) as reference point.
    """
    ref = reference_date or date.today()

    if preset == DateRangePreset.TODAY:
        return ref, ref

    elif preset == DateRangePreset.YESTERDAY:
        yest = ref - timedelta(days=1)
        return yest, yest

    elif preset == DateRangePreset.THIS_WEEK:
        # Monday to Sunday of current week
        start = ref - timedelta(days=ref.weekday())
        end = start + timedelta(days=6)
        return start, end

    elif preset == DateRangePreset.PREVIOUS_WEEK:
        start_this_week = ref - timedelta(days=ref.weekday())
        start_prev_week = start_this_week - timedelta(days=7)
        end_prev_week = start_prev_week + timedelta(days=6)
        return start_prev_week, end_prev_week

    elif preset == DateRangePreset.THIS_MONTH:
        start = ref.replace(day=1)
        # Next month first day minus 1 day
        if ref.month == 12:
            next_month = ref.replace(year=ref.year + 1, month=1, day=1)
        else:
            next_month = ref.replace(month=ref.month + 1, day=1)
        end = next_month - timedelta(days=1)
        return start, end

    elif preset == DateRangePreset.PREVIOUS_MONTH:
        first_of_this_month = ref.replace(day=1)
        end_prev_month = first_of_this_month - timedelta(days=1)
        start_prev_month = end_prev_month.replace(day=1)
        return start_prev_month, end_prev_month

    elif preset == DateRangePreset.THIS_YEAR:
        start = ref.replace(month=1, day=1)
        end = ref.replace(month=12, day=31)
        return start, end

    elif preset == DateRangePreset.PREVIOUS_YEAR:
        start = ref.replace(year=ref.year - 1, month=1, day=1)
        end = ref.replace(year=ref.year - 1, month=12, day=31)
        return start, end

    else:
        # CUSTOM or fallback
        return ref, ref

def parse_date_str(val: str) -> Optional[date]:
    """Parses date from YYYY-MM-DD or DD/MM/YYYY."""
    if not val or not val.strip():
        return None
    val = val.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(val, fmt).date()
        except ValueError:
            continue
    return None

def format_date(d: Optional[date], fmt: str = "%d/%m/%Y") -> str:
    """Formats date object to string."""
    if not d:
        return ""
    return d.strftime(fmt)
