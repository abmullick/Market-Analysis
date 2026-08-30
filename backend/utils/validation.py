import re
from typing import Optional


def validate_symbol(symbol: str) -> bool:
    return bool(re.match(r"^[A-Z0-9]{1,10}$", symbol.upper()))


def sanitize_string(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    return value.strip()
