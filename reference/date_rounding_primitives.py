"""Internal source primitives preserved from the July 2026 calculation milestone."""

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
import math
import re


DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def round_half_away_from_zero(value: float, scale: int = 1) -> int:
    if not math.isfinite(value):
        raise ValueError("cannot round nonfinite value")
    sign = -1 if value < 0 else 1
    rounded = (Decimal(str(abs(value))) * Decimal(scale)).to_integral_value(rounding=ROUND_HALF_UP)
    return sign * int(rounded)


def is_valid_civil_date(value: str) -> bool:
    if not isinstance(value, str) or not DATE_RE.match(value):
        return False
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return False
    return parsed.isoformat() == value
