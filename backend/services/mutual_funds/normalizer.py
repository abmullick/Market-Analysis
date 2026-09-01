from typing import Any

from backend.models.mutual_fund import MutualFund, NAVRecord, SchemeSearchResult


def normalize_scheme(raw: dict[str, Any]) -> MutualFund:
    meta = raw.get("meta", {})
    return MutualFund(
        scheme_code=str(meta.get("scheme_code") or raw.get("scheme_code", "")),
        scheme_name=meta.get("scheme_name", ""),
        amc=meta.get("fund_house"),
        category=meta.get("scheme_category"),
        sub_category=meta.get("scheme_type"),
        nav=_safe_float(meta.get("scheme_nav")),
        nav_date=meta.get("last_nav_date"),
        one_year_return=_safe_float(meta.get("return_1year")),
        three_year_return=_safe_float(meta.get("return_3year")),
        five_year_return=_safe_float(meta.get("return_5year")),
        expense_ratio=_safe_float(meta.get("expense_ratio")),
        minimum_investment=_safe_float(meta.get("minimum_sip_amount")),
        fund_manager=meta.get("fund_manager"),
        asset_allocation=meta.get("asset_allocation"),
        top_holdings=meta.get("top_holdings"),
    )


def normalize_nav_history(raw: dict[str, Any]) -> list[NAVRecord]:
    data = raw.get("data", [])
    records = []
    for item in data:
        date = item.get("date")
        nav = _safe_float(item.get("nav"))
        if date and nav is not None:
            normalized_date = _normalize_date(date)
            if normalized_date:
                records.append(NAVRecord(date=normalized_date, nav=nav))
    records.sort(key=lambda r: r.date)
    return records


def _normalize_date(date_str: str) -> str | None:
    """Convert date string to YYYY-MM-DD format.
    Accepts DD-MM-YYYY (MFAPI) or YYYY-MM-DD.
    """
    if not date_str:
        return None

    parts = date_str.strip().split("-")
    if len(parts) == 3:
        if len(parts[0]) == 4:
            return date_str.strip()
        if len(parts[2]) == 4:
            return f"{parts[2]}-{parts[1]}-{parts[0]}"
    return None


def normalize_search_result(raw: dict[str, Any]) -> SchemeSearchResult:
    return SchemeSearchResult(
        scheme_code=str(raw.get("scheme_code", "")),
        scheme_name=raw.get("scheme_name", ""),
        amc=raw.get("amc", ""),
        category=raw.get("category", ""),
        sub_category=raw.get("sub_category"),
    )


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
