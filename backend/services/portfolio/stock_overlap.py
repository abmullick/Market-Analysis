"""Stock Overlap & Concentration calculation logic.

Pure backend calculation over normalized AMFI holdings
(see backend/services/data/amfi_holdings.py).

- ISIN is the sole stock identifier (no name fuzzy-matching).
- effective_exposure = (fund allocation / 100) * portfolio_weight
- Duplicate ISINs within one fund are summed before exposure calc.
- Holdings with blank/missing ISIN or missing weight are ignored.
- Allocations are used as-given (never normalized to 100%).
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence


def _holding_field(holding: Any, *names: str) -> Any:
    """Read a field from a dataclass/object or a mapping."""
    if isinstance(holding, Mapping):
        for name in names:
            if name in holding:
                return holding[name]
        return None
    for name in names:
        if hasattr(holding, name):
            return getattr(holding, name)
    return None


def _safe_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result


def compute_stock_overlap(
    selected_funds: Sequence[Mapping[str, Any]],
    holdings: Sequence[Any],
) -> dict[str, Any]:
    """Aggregate effective equity exposure by ISIN across selected funds.

    Args:
        selected_funds: [{"scheme_code", "scheme_name", "allocation"}].
            ``allocation`` is a percentage (e.g. 60 for 60%).
        holdings: normalized AMFI holdings (AmfiHolding objects or
            mappings with scheme_code/isins/security_name/portfolio_weight
            or holding_weight keys).

    Returns:
        {"overlapping_stock_count", "total_unique_stock_count", "stocks"}
        where each stock has isin/security_name/fund_count/
        effective_portfolio_exposure/funds[...].
    """
    alloc_by_code: dict[str, dict[str, Any]] = {}
    for fund in selected_funds:
        if not isinstance(fund, Mapping):
            continue
        code = str(fund.get("scheme_code") or "").strip()
        if not code:
            continue
        allocation = _safe_float(fund.get("allocation"))
        if allocation is None:
            allocation = 0.0
        alloc_by_code[code] = {
            "scheme_name": str(fund.get("scheme_name") or ""),
            "allocation": allocation,
        }

    # (isin, scheme_code) -> aggregated holding weight + names.
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for holding in holdings:
        code = str(_holding_field(holding, "scheme_code") or "").strip()
        if not code or code not in alloc_by_code:
            continue
        raw_isin = _holding_field(holding, "isin", "ISIN")
        isin = str(raw_isin or "").strip()
        if not isin:
            continue
        weight = _safe_float(
            _holding_field(holding, "portfolio_weight", "holding_weight",
                           "MarketValuePercentage"))
        if weight is None:
            continue
        key = (isin, code)
        entry = grouped.get(key)
        if entry is None:
            grouped[key] = {
                "isin": isin,
                "scheme_code": code,
                "security_name": str(
                    _holding_field(holding, "security_name",
                                   "Company_Name") or "").strip(),
                "holding_weight": weight,
            }
        else:
            entry["holding_weight"] += weight
            if not entry["security_name"]:
                entry["security_name"] = str(
                    _holding_field(holding, "security_name",
                                   "Company_Name") or "").strip()

    # ISIN -> per-fund exposures.
    by_isin: dict[str, dict[str, Any]] = {}
    for (isin, code), entry in grouped.items():
        fund_info = alloc_by_code[code]
        allocation = fund_info["allocation"]
        holding_weight = entry["holding_weight"]
        effective = (allocation / 100.0) * holding_weight
        stock = by_isin.get(isin)
        if stock is None:
            stock = {
                "isin": isin,
                "security_name": entry["security_name"],
                "funds": [],
                "effective_portfolio_exposure": 0.0,
            }
            by_isin[isin] = stock
        if not stock["security_name"] and entry["security_name"]:
            stock["security_name"] = entry["security_name"]
        stock["funds"].append({
            "scheme_code": code,
            "scheme_name": fund_info["scheme_name"],
            "allocation": allocation,
            "holding_weight": holding_weight,
            "effective_exposure": effective,
        })
        stock["effective_portfolio_exposure"] += effective

    stocks: list[dict[str, Any]] = []
    for stock in by_isin.values():
        stock["fund_count"] = len(stock["funds"])
        stock["funds"].sort(key=lambda f: f["effective_exposure"],
                            reverse=True)
        stocks.append(stock)
    stocks.sort(key=lambda s: s["effective_portfolio_exposure"], reverse=True)

    overlapping = sum(1 for s in stocks if s["fund_count"] >= 2)
    return {
        "overlapping_stock_count": overlapping,
        "total_unique_stock_count": len(stocks),
        "stocks": stocks,
    }
