"""Stable, source-scoped identity for normalized bond records.

CCIL market-watch records do not carry an ISIN, so the Bond Analysis API needs
an additional stable identifier to be able to select a single record that has
no ISIN. The identifier is deliberately *source-scoped*:

    record_id = "<source>|<instrument_type>|sha1(description|maturity|coupon)[:12]"

``description`` is the normalized ``security_name``; missing maturity or coupon
values are rendered as the literal string ``"none"`` so the digest is stable.

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
from collections.abc import Iterable, Mapping
from datetime import date, datetime
from typing import Any, Optional

__all__ = [
    "SOURCE_CCIL",
    "SOURCE_NSE",
    "RECORD_ID_FIELDS",
    "RECORD_ID_PATTERN",
    "attach_record_id",
    "build_record_id",
    "compute_record_id",
    "describe_identity_limits",
    "ensure_record_id",
    "ensure_record_ids",
    "is_valid_record_id",
    "normalize_identity_text",
    "parse_record_id",
    "record_id_for",
    "record_id_for_bond",
    "record_id_source",
]

#: Canonical source identifiers used by the bond providers.
SOURCE_CCIL = "CCIL"
SOURCE_NSE = "NSE"

#: Fields that participate in the fallback digest, in a fixed order.
RECORD_ID_FIELDS = ("security_name", "maturity_date", "coupon_rate")

#: ``<source>|<instrument_type>|<12 hex chars>``
RECORD_ID_PATTERN = re.compile(r"^[a-z0-9_]+\|[a-z0-9_]+\|[0-9a-f]{12}$")

_WHITESPACE_RE = re.compile(r"\s+")
_UNSAFE_RE = re.compile(r"[^a-z0-9_]+")

_MISSING = "none"
_UNKNOWN = "unknown"


def normalize_identity_text(value: Any) -> str:
    """Collapse whitespace and upper-case *value* so cosmetic differences do not fork identity."""
    if value is None:
        return ""
    if isinstance(value, (bytes, bytearray)):
        value = value.decode("utf-8", "replace")
    text = str(value).replace("\u00a0", " ")
    return _WHITESPACE_RE.sub(" ", text).strip().upper()


def _token(value: Any, default: str = _UNKNOWN) -> str:
    """Normalize a source/instrument-type label into a lowercase, string-safe token."""
    raw = getattr(value, "value", value)
    token = _UNSAFE_RE.sub("_", normalize_identity_text(raw).lower()).strip("_")
    return token or default


def _description(value: Any) -> str:
    """Return the normalized security description, or ``"none"`` when absent."""
    return normalize_identity_text(value) or _MISSING


def _maturity(value: Any) -> str:
    """Return the normalized maturity date, or ``"none"`` when absent."""
    if value is None:
        return _MISSING
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, date):
        return value.isoformat()
    return normalize_identity_text(value) or _MISSING


def _coupon(value: Any) -> str:
    """Return the normalized coupon rate, or ``"none"`` when absent."""
    if value is None:
        return _MISSING
    try:
        number = float(value)
    except (TypeError, ValueError):
        return normalize_identity_text(value) or _MISSING
    text = repr(number)
    if text.endswith(".0"):
        text = text[:-2]
    return text


def record_id_for(
    source: Any,
    instrument_type: Any,
    description: Any,
    maturity_date: Any,
    coupon_rate: Any,
) -> str:
    """Build ``"<source>|<instrument_type>|sha1(description|maturity|coupon)[:12]"``."""
    identity = (
        f"{_description(description)}|{_maturity(maturity_date)}|{_coupon(coupon_rate)}"
    )
    digest = hashlib.sha1(identity.encode("utf-8")).hexdigest()[:12]
    return f"{_token(source)}|{_token(instrument_type)}|{digest}"


def _field(bond: Any, *names: str) -> Any:
    """Return the first non-``None`` value from *bond* (mapping or object)."""
    if isinstance(bond, Mapping):
        for name in names:
            if bond.get(name) is not None:
                return bond[name]
        return None
    for name in names:
        value = getattr(bond, name, None)
        if value is not None:
            return value
    return None


def record_id_for_bond(bond: Any) -> Optional[str]:
    """Build the record_id for a bond-like mapping or object.

    ``security_name`` is used as the description; ``instrument_type`` is used
    when present, with ``data_type`` as the fallback.
    """
    if bond is None:
        return None
    return record_id_for(
        _field(bond, "source"),
        _field(bond, "instrument_type", "data_type"),
        _field(bond, "security_name", "security_description", "description"),
        _field(bond, "maturity_date"),
        _field(bond, "coupon_rate"),
    )


def build_record_id(bond: Any) -> Optional[str]:
    """Alias of :func:`record_id_for_bond` (bond-like object in, record_id out)."""
    return record_id_for_bond(bond)


def compute_record_id(
    source: Any,
    instrument_type: Any,
    description: Any,
    maturity_date: Any,
    coupon_rate: Any,
) -> str:
    """Alias of :func:`record_id_for` for component-based callers/validators."""
    return record_id_for(
        source, instrument_type, description, maturity_date, coupon_rate
    )


def attach_record_id(bond: Any) -> Any:
    """Stamp ``record_id`` on *bond* when missing and return *bond* unchanged."""
    if bond is None:
        return None
    existing = (
        bond.get("record_id")
        if isinstance(bond, Mapping)
        else getattr(bond, "record_id", None)
    )
    if existing:
        return bond
    record_id = record_id_for_bond(bond)
    if record_id is None:
        return bond
    if isinstance(bond, Mapping):
        bond["record_id"] = record_id
    else:
        try:
            setattr(bond, "record_id", record_id)
        except (AttributeError, TypeError, ValueError):
            return bond
    return bond


def ensure_record_id(bond: Any) -> Any:
    """Alias of :func:`attach_record_id` for raw provider records."""
    return attach_record_id(bond)


def ensure_record_ids(bonds: Iterable[Any]) -> list[Any]:
    """Stamp ``record_id`` on every record, preserving order."""
    return [ensure_record_id(bond) for bond in bonds]


def describe_identity_limits() -> str:
    """Human-readable description of the fallback identity limitations."""
    return (
        "record_id is a source-scoped fallback identifier, not an ISIN. "
        "Records from different sources are never merged, and two distinct "
        "securities from the same source that share the same normalized "
        "security description, maturity date and coupon rate can collide."
    )


def is_valid_record_id(value: Any) -> bool:
    """Return ``True`` when *value* matches ``<source>|<type>|<12 hex>``."""
    return isinstance(value, str) and RECORD_ID_PATTERN.match(value) is not None


def parse_record_id(value: Any) -> Optional[dict[str, str]]:
    """Split a valid record_id into ``source`` / ``data_type`` / ``digest``."""
    if not is_valid_record_id(value):
        return None
    source, data_type, digest = value.split("|")
    return {"source": source, "data_type": data_type, "digest": digest}


def record_id_source(value: Any) -> Optional[str]:
    """Return the source prefix of *value*, or ``None`` when it is not a record_id."""
    parsed = parse_record_id(value)
    return parsed["source"] if parsed else None
