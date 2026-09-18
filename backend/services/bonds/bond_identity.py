"""Stable, source-scoped identity for normalized bond records.

CCIL market-watch records do not carry an ISIN, so the Bond Analysis API needs
an additional stable identifier to be able to select a single record that has
no ISIN. The identifier is deliberately *source-scoped*:

    record_id = "<source>|<data_type>|sha1(description|maturity|coupon)[:12]"

It is **never** presented as an ISIN and it **never** claims that records from
two different sources describe the same security.

Documented limitations
----------------------
* The source prefix guarantees that CCIL and NSE records can never collide,
  but it also means the two sources are never merged automatically.
* Two *distinct* securities from the *same* source that share the same
  normalized security description, maturity date and coupon rate would produce
  the same ``record_id``. That residual collision risk is accepted here and is
  covered by a regression test; an ISIN always takes precedence whenever the
  source provides one.
* ``record_id`` is deterministic for a given set of source fields, so it is
  stable across restarts and cache rebuilds.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any, Optional

__all__ = [
    "build_record_id",
    "describe_identity_limits",
    "RECORD_ID_FIELDS",
]

#: Fields that participate in the fallback digest, in a fixed order.
RECORD_ID_FIELDS = ("security_name", "maturity_date", "coupon_rate")

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def _text(value: Any) -> str:
    """Return a trimmed string for *value*, or an empty string when absent."""
    if value is None:
        return ""
    if isinstance(value, (bytes, bytearray)):
        value = value.decode("utf-8", "replace")
    return str(value).strip()


def _normalize(value: Any) -> str:
    """Case-fold and strip punctuation so cosmetic differences do not fork identity."""
    return _NON_ALNUM.sub("", _text(value).lower())


def _enum_value(value: Any) -> str:
    """Return the lower-cased enum ``value`` (or the plain string) for *value*."""
    if value is None:
        return ""
    raw = getattr(value, "value", value)
    return _text(raw).lower()


def build_record_id(bond: Any) -> Optional[str]:
    """Build the deterministic, source-scoped identifier for *bond*.

    ``bond`` may be any object exposing the normalized bond attributes
    (``source``, ``data_type``, ``security_name``, ``maturity_date``,
    ``coupon_rate``). Missing attributes are treated as absent, never guessed.

    Returns ``None`` only when *bond* carries none of the identifying fields at
    all, in which case no stable identifier can be derived from the source.
    """
    if bond is None:
        return None

    source = _enum_value(getattr(bond, "source", None)) or "unknown"
    data_type = _enum_value(getattr(bond, "data_type", None)) or "unknown"

    parts = [_normalize(getattr(bond, field, None)) for field in RECORD_ID_FIELDS]
    if not any(parts):
        return None

    payload = "|".join(parts)
    digest = hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]
    return f"{source}|{data_type}|{digest}"


def describe_identity_limits() -> str:
    """Human-readable description of the fallback identity limitations."""
    return (
        "record_id is a source-scoped fallback identifier, not an ISIN. "
        "Records from different sources are never merged, and two distinct "
        "securities from the same source that share the same normalized "
        "security description, maturity date and coupon rate can collide."
    )
