from decimal import Decimal, ROUND_HALF_UP
from typing import Union, Optional

# Precision constants
MONEY_QUANT = Decimal("0.01")      # 2 decimal places for INR / currency
WEIGHT_QUANT = Decimal("0.001")    # 3 decimal places for weight in KG (gram precision)
PERCENT_QUANT = Decimal("0.01")    # 2 decimal places for percentage

NumericType = Union[int, float, str, Decimal]

def to_decimal(val: Optional[NumericType], default: str = "0.00") -> Decimal:
    """Safely converts input value to Python Decimal."""
    if val is None:
        return Decimal(default)
    if isinstance(val, Decimal):
        return val
    try:
        # If float, convert via str to avoid float binary representation artifacts
        val_str = str(val).strip()
        if not val_str:
            return Decimal(default)
        return Decimal(val_str)
    except Exception:
        return Decimal(default)

def round_money(val: NumericType) -> Decimal:
    """Rounds a decimal value to 2 decimal places for money."""
    d = to_decimal(val)
    return d.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)

# Convenient alias
round_currency = round_money

def round_weight(val: NumericType) -> Decimal:
    """Rounds a decimal value to 3 decimal places for weight in KG."""
    d = to_decimal(val)
    return d.quantize(WEIGHT_QUANT, rounding=ROUND_HALF_UP)

def round_percent(val: NumericType) -> Decimal:
    """Rounds a decimal value to 2 decimal places for percentages."""
    d = to_decimal(val)
    return d.quantize(PERCENT_QUANT, rounding=ROUND_HALF_UP)

def format_currency(val: NumericType) -> str:
    """Formats numeric value as Indian Rupee string e.g. ₹1,500.50 or -₹500.00."""
    d = round_money(val)
    is_negative = d < 0
    abs_d = abs(d)
    
    # Format whole and fraction
    parts = f"{abs_d:.2f}".split(".")
    integer_part = parts[0]
    fractional_part = parts[1]
    
    # Indian numbering format formatting if length > 3
    if len(integer_part) > 3:
        last_three = integer_part[-3:]
        rest = integer_part[:-3]
        groups = []
        while len(rest) > 2:
            groups.insert(0, rest[-2:])
            rest = rest[:-2]
        if rest:
            groups.insert(0, rest)
        formatted_int = ",".join(groups) + "," + last_three
    else:
        formatted_int = integer_part

    res = f"₹{formatted_int}.{fractional_part}"
    return f"-{res}" if is_negative else res

def format_weight(val: NumericType, include_unit: bool = True) -> str:
    """Formats weight in KG e.g. '95.500 KG' or '95.500'."""
    d = round_weight(val)
    formatted = f"{d:,.3f}"
    return f"{formatted} KG" if include_unit else formatted
