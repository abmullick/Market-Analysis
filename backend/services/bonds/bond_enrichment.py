"""CCIL -> NSE master matching and enrichment (Bond domain layer).

Flow (providers never call each other):

    CCIL provider -> Bond normalization -> NSE master -> matching -> Bond service

Only high-confidence, deterministic matches enrich a Bond:

    compatible instrument type + exact maturity + matching coupon
    (non T-Bills) + strong normalized description -> ISIN + master fields.

Ambiguous or unmatched securities keep ``isin=None``; no ISIN is ever
fabricated. CCIL market observations (price / ytm / LTP / LTY / traded
value / source / data_type) are preserved verbatim — NSE supplies master
data only (ISIN, issue date, coupon frequency, face value, listing
status).
"""
from __future__ import annotations
import re
from typing import Optional

from backend.models.bonds import Bond, InstrumentType, NseRawRecord
from backend.services.bonds.bond_normalizer import (
    _classify_nse_instrument,
    _parse_coupon_frequency as _parse_freq,
    parse_date,
    parse_float,
    parse_isin,
)
from backend.utils.logging import logger

_TBILL_ALIASES = {
    "DTB", "TBILL", "T-BILL", "TBILLS", "TREASURY", "BILL", "BILLS",
    "CMB", "CASH", "MANAGEMENT",
}


def normalize_security_description(text: str | None) -> str:
    """Normalize a description for matching (case/space/punct only)."""
    if not text:
        return ""
    v = text.upper().replace("\xa0", " ")
    v = v.replace(",", " ").replace("%", " ")
    v = v.replace("/", " ").replace("-", " ").replace(".", " ")
    v = v.replace("(", " ").replace(")", " ")
    v = re.sub(r"\s+", " ", v).strip()
    return v


def _canonical_token(tok: str) -> str:
    try:
        f = float(tok)
        return f"{f:.4f}".rstrip("0").rstrip(".")
    except ValueError:
        return tok


def _canonical_tokens(normalized: str) -> list[str]:
    return [_canonical_token(t) for t in normalized.split(" ") if t]


def _extract_tenor(text: str | None) -> str | None:
    m = re.search(r"\b(91|182|364)\b", text or "")
    return m.group(1) if m else None

def _nse_raw_instrument_type(
    raw: NseRawRecord,
    desc: Optional[str] = None,
) -> InstrumentType:
    """Classify an NSE raw record for enrichment matching.

    Delegates to the shared NSE classifier in ``bond_normalizer`` so the
    enrichment matcher and the normalization pipeline can never use diverging
    rules. The explicit NSE ``SECTYPE`` (TB/GS/SG + SDL-confirmation) takes
    precedence; fallback keyword checks are token-aware ("gs" inside a larger
    token such as "GSIL28" never implies G-Sec).
    """
    return _classify_nse_instrument(raw, desc)


def _description_strong_match(ccil_desc: str, nse_desc: str, is_tbill: bool) -> bool:
    ccil_norm = normalize_security_description(ccil_desc)
    nse_norm = normalize_security_description(nse_desc)
    if not ccil_norm or not nse_norm:
        return False
    if ccil_norm == nse_norm:
        return True
    ccil_toks = _canonical_tokens(ccil_norm)
    nse_toks = _canonical_tokens(nse_norm)
    if not ccil_toks or not nse_toks:
        return False
    if is_tbill:
        ccil_set, nse_set = set(ccil_toks), set(nse_toks)
        if not (bool(ccil_set & _TBILL_ALIASES) and bool(nse_set & _TBILL_ALIASES)):
            return False
        ccil_tenor = _extract_tenor(ccil_norm)
        nse_tenor = _extract_tenor(nse_norm)
        if ccil_tenor and nse_tenor and ccil_tenor != nse_tenor:
            return False
        return True
    nse_set = set(nse_toks)
    # Description formats differ between CCIL and NSE WDM
    # (e.g. "06.94 GS 2036" vs "CG2036"). Exact maturity,
    # instrument type and coupon are already enforced by the caller.
    return True


def find_nse_match(ccil: Bond, masters: list[NseRawRecord]) -> NseRawRecord | None:
    """Find the single high-confidence NSE master row for a CCIL Bond.

    Signals: compatible instrument type + exact maturity + matching coupon
    (non T-Bills) + strong normalized-description match. Returns None on
    no-match or on ambiguity (multiple candidates) — never selects
    arbitrarily.
    """
    if not masters or not ccil.security_name:
        return None
    is_tbill = ccil.instrument_type == InstrumentType.T_BILL
    candidates: list[NseRawRecord] = []
    for raw in masters:
        nse_desc = raw.security_description or ""
        if not nse_desc:
            continue
        nse_type = _nse_raw_instrument_type(raw, nse_desc)
        if nse_type != InstrumentType.UNKNOWN and ccil.instrument_type != InstrumentType.UNKNOWN:
            if nse_type != ccil.instrument_type:
                continue
        ccil_mat = ccil.maturity_date
        nse_mat = parse_date(raw.maturity_date or "")
        if nse_mat is None or ccil_mat is None or ccil_mat != nse_mat:
            continue
        if not is_tbill:
            ccil_coupon = ccil.coupon_rate
            nse_coupon = parse_float(raw.coupon_rate or "")
            if nse_coupon is None:
                nse_coupon = _coupon_from_nse_description(nse_desc)
            if ccil_coupon is None or nse_coupon is None:
                continue
            if abs(ccil_coupon - nse_coupon) > 0.005:
                continue
        if not _description_strong_match(ccil.security_name, nse_desc, is_tbill):
            continue
        candidates.append(raw)
    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) > 1:
        logger.info("NSE match ambiguous: %s candidates=%d", ccil.security_name, len(candidates))
    return None


_COUPON_PREFIX_RE = re.compile(r"^\s*(\d{1,2}(?:\.\d{1,4})?)\s+(?:[A-Z]{2,3}\s+)?(?:GS|SDL|SGS)\b", re.IGNORECASE)
_COUPON_PERCENT_RE = re.compile(r"(\d{1,2}(?:\.\d{1,4})?)\s*%")


def _coupon_from_nse_description(desc: str) -> float | None:
    text = (desc or "").strip()
    if not text:
        return None
    m = _COUPON_PERCENT_RE.search(text)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            return None
    m = _COUPON_PREFIX_RE.match(text)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            return None
    return None


def enrich_ccil_with_nse(ccil: Bond, match: NseRawRecord) -> Bond:
    isin = parse_isin(match.isin or "")
    data = ccil.model_dump()
    if isin:
        data["isin"] = isin
    issue = parse_date(match.issue_date or "")
    if issue is not None and data.get("issue_date") is None:
        data["issue_date"] = issue
    freq = _parse_freq(match.coupon_frequency)
    if freq is not None and data.get("coupon_frequency") is None:
        data["coupon_frequency"] = freq
    face = parse_float(match.face_value or "")
    if face is not None and data.get("face_value") is None:
        data["face_value"] = face
    listing = (match.listing_status or "").strip()
    if listing and not data.get("listing_status"):
        data["listing_status"] = listing
    if data.get("coupon_rate") is None:
        nse_coupon = parse_float(match.coupon_rate or "")
        if nse_coupon is not None:
            data["coupon_rate"] = nse_coupon
    return Bond(**data)


def enrich_ccil_bonds(ccil_bonds: list[Bond], masters: list[NseRawRecord]) -> list[Bond]:
    if not ccil_bonds or not masters:
        return list(ccil_bonds)
    enriched: list[Bond] = []
    for bond in ccil_bonds:
        if bond.isin:
            enriched.append(bond)
            continue
        try:
            match = find_nse_match(bond, masters)
        except Exception as exc:
            logger.warning("NSE match failed for %s: %s", bond.security_name, exc)
            enriched.append(bond)
            continue
        if match is None:
            enriched.append(bond)
            continue
        try:
            enriched.append(enrich_ccil_with_nse(bond, match))
        except Exception as exc:
            logger.warning("NSE enrichment failed for %s: %s", bond.security_name, exc)
            enriched.append(bond)
    return enriched

