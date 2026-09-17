"""Stable record identity for Bond API selection.

The Bond detail and analytics endpoints are keyed by identity. When a source
record carries an ISIN, the ISIN is the identity. CCIL market-watch rows do not
carry ISINs (confirmed by live validation: all 85 CCIL records had none), so a
deterministic, source-scoped fallback key is derived from source-provided
fields only.

Fallback key format::

    nosin:<source>:<slug(security description)>:<maturity|none>:<coupon|none>

Limitations (must be documented wherever the key is exposed):
    - The fallback key is NOT a globally unique security identifier and is NOT
      an ISIN. It only identifies a record within a single source snapshot.
    - Identity is source-scoped by design: a CCIL record and an NSE record are
      never merged or considered the same security because their descriptions
      match.
    - If a source changes a description, maturity string, or coupon value, the
      fallback key changes with it.
    - Two distinct securities from the same source could theoretically collide
      if every fallback component is identical; callers must treat the key as
      opaque and must not parse meaning out of it.
"""

from __future__ import annotations

import re
from typing import Optional

from backend.models.bonds import Bond

_WS_RE = re.compile(r"\s+")
_SAFE_RE = re.compile(r"[^a-z0-9]+")


def sanitize_key_part(value: Optional[str], fallback: str = "none") -> str:
    """Normalize one identity component deterministically.

    Lowercases, collapses whitespace to single dashes, and strips characters
    outside ``[a-z0-9-]``. Empty/None input maps to *fallback*.
    """
    if value is None:
        return fallback
    text = _WS_RE.sub(" ", str(value)).strip().lower()
    if not text:
        return fallback
    slug = _SAFE_RE.sub("-", text)
    slug = _WS_RE.sub("-", slug).strip("-")
    return slug or fallback


def bond_record_key(bond: Bond) -> str:
    """Return the stable identity for *bond*.

    ISIN when the source provides one; otherwise the source-scoped fallback
    built from security description, maturity date, and coupon rate.
    """
    isin = (bond.isin or "").strip() if bond.isin else ""
    if isin:
        return isin

    source = sanitize_key_part(bond.source, fallback="unknown")
    description = sanitize_key_part(
        bond.security_name or bond.issuer, fallback="nodesc"
    )
    maturity = (
        bond.maturity_date.isoformat() if bond.maturity_date else "none"
    )
    coupon = (
        f"{bond.coupon_rate:.6g}" if bond.coupon_rate is not None else "none"
    )
    return f"nosin:{source}:{description}:{maturity}:{coupon}"


def key_is_isin(key: str) -> bool:
    """True when *key* looks like a real ISIN (12 chars, alpha-num pattern)."""
    text = (key or "").strip()
    return len(text) == 12 and text[:2].isalpha() and text.isalnum()
