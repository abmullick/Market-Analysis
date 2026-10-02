from __future__ import annotations

from typing import Any, Optional

from backend.models.fundamentals import Fundamentals


def _latest(rows: list[dict[str, Any]], key: str) -> Optional[float]:
    if not rows:
        return None
    value = rows[0].get("values", {}).get(key)
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _series(rows: list[dict[str, Any]], key: str) -> list[float]:
    values: list[float] = []
    for row in reversed(rows):
        value = row.get("values", {}).get(key)
        try:
            if value is not None:
                values.append(float(value))
        except (TypeError, ValueError):
            continue
    return values


def _safe_div(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None or b in (None, 0):
        return None
    return a / b


def _cagr(values: list[float], years: int) -> Optional[float]:
    if len(values) <= years or values[0] <= 0 or values[-1] <= 0:
        return None
    return (values[-1] / values[0]) ** (1 / years) - 1


class ScreenerEngine:
    """Derive analysis metrics from Screener financial statements.

    The engine intentionally calculates secondary ratios from the raw annual
    statements instead of treating every displayed Screener ratio as a
    separate source field. This makes the analysis transparent and reusable.
    """

    def derive_fundamental_metrics(self, data: dict[str, Any]) -> dict[str, Any]:
        income = data.get("income_statement", [])
        balance = data.get("balance_sheet", [])
        cash = data.get("cash_flow", [])
        f = data.get("fundamentals", {})

        revenue = _series(income, "TotalRevenue")
        operating_profit = _series(income, "OperatingIncome")
        ebitda = _series(income, "EBITDA")
        profit = _series(income, "NetIncome")
        eps = _series(income, "DilutedEPS")
        cfo = _series(cash, "OperatingCashFlow")
        fcf = _series(cash, "FreeCashFlow")
        debt = _series(balance, "TotalDebt")
        equity = _series(balance, "StockholdersEquity")
        assets = _series(balance, "TotalAssets")
        current_assets = _series(balance, "CurrentAssets")
        current_liabilities = _series(balance, "CurrentLiabilities")
        net_block = _series(balance, "NetBlock")
        debtors = _series(balance, "Debtors")
        inventory = _series(balance, "Inventory")
        payables = _series(balance, "TradePayables")

        latest_revenue = revenue[-1] if revenue else f.get("revenue")
        latest_profit = profit[-1] if profit else f.get("net_profit")
        latest_cfo = cfo[-1] if cfo else f.get("operating_cash_flow")
        latest_fcf = fcf[-1] if fcf else f.get("free_cash_flow")
        latest_debt = debt[-1] if debt else f.get("total_debt")
        latest_cash = f.get("cash")
        latest_ebitda = ebitda[-1] if ebitda else f.get("ebitda")

        # Cash earnings quality.
        cfo_profit = _safe_div(latest_cfo, latest_profit)
        fcf_profit = _safe_div(latest_fcf, latest_profit)
        fcf_margin = _safe_div(latest_fcf, latest_revenue)

        # Capital efficiency. Use average equity/assets where the history permits.
        avg_equity = None
        if equity:
            avg_equity = equity[-1] if len(equity) == 1 else (equity[-1] + equity[-2]) / 2
        avg_assets = None
        if assets:
            avg_assets = assets[-1] if len(assets) == 1 else (assets[-1] + assets[-2]) / 2
        roe_derived = _safe_div(latest_profit, avg_equity)
        roa_derived = _safe_div(latest_profit, avg_assets)

        # ROIC approximation aligned with Screener's documented invested-capital
        # concept: operating profit / (net block + working capital).
        invested_capital = None
        if net_block and current_assets and current_liabilities:
            working_capital = current_assets[-1] - current_liabilities[-1]
            invested_capital = net_block[-1] + working_capital
        roic = _safe_div(operating_profit[-1] if operating_profit else None, invested_capital)
        croic = _safe_div(latest_fcf, invested_capital)

        # Debt quality.
        net_debt = None
        if latest_debt is not None and latest_cash is not None:
            net_debt = latest_debt - latest_cash
        net_debt_ebitda = _safe_div(net_debt, latest_ebitda) if latest_ebitda and latest_ebitda > 0 else None

        # Historical averages/trends.
        def avg_return(values: list[float], bases: list[float], years: int) -> Optional[float]:
            if len(values) < years or len(bases) < years:
                return None
            vals = [v / b for v, b in zip(values[-years:], bases[-years:]) if b not in (None, 0)]
            return sum(vals) / len(vals) if vals else None

        avg_roe_3y = avg_return(profit, equity, 3)
        avg_roe_5y = avg_return(profit, equity, 5)
        avg_roa_3y = avg_return(profit, assets, 3)
        avg_roa_5y = avg_return(profit, assets, 5)

        margin_series = []
        for r, op in zip(revenue, operating_profit):
            if r != 0:
                margin_series.append(op / r)
        current_margin = margin_series[-1] if margin_series else None
        margin_3y = sum(margin_series[-3:]) / len(margin_series[-3:]) if len(margin_series) >= 3 else None
        margin_5y = sum(margin_series[-5:]) / len(margin_series[-5:]) if len(margin_series) >= 5 else None

        # Working-capital efficiency. Values are days based on annual flow.
        debtor_days = _safe_div(debtors[-1] * 365, latest_revenue) if debtors and latest_revenue else None
        inventory_days = _safe_div(inventory[-1] * 365, latest_revenue) if inventory and latest_revenue else None
        payable_days = _safe_div(payables[-1] * 365, latest_revenue) if payables and latest_revenue else None
        cash_conversion_cycle = (
            debtor_days + inventory_days - payable_days
            if debtor_days is not None and inventory_days is not None and payable_days is not None
            else None
        )

        # Piotroski F-score, using only signals supported by the available
        # annual statements. Missing signals are omitted rather than guessed.
        score_parts: dict[str, Optional[int]] = {}
        if len(profit) >= 2 and len(assets) >= 2:
            score_parts["positive_roa"] = int(profit[-1] / assets[-1] > 0)
            score_parts["roa_improving"] = int(profit[-1] / assets[-1] > profit[-2] / assets[-2]) if assets[-1] and assets[-2] else None
        if len(cfo) >= 1:
            score_parts["positive_cfo"] = int(cfo[-1] > 0)
        if len(debt) >= 2 and len(assets) >= 2:
            score_parts["lower_leverage"] = int(debt[-1] / assets[-1] < debt[-2] / assets[-2]) if assets[-1] and assets[-2] else None
        if len(equity) >= 2:
            score_parts["no_dilution"] = int(equity[-1] >= equity[-2])
        if len(cfo) >= 1 and len(profit) >= 1:
            score_parts["cfo_above_profit"] = int(cfo[-1] > profit[-1])
        if len(revenue) >= 2 and len(margin_series) >= 2:
            score_parts["margin_improving"] = int(margin_series[-1] > margin_series[-2])
        if len(revenue) >= 2:
            score_parts["revenue_growing"] = int(revenue[-1] > revenue[-2])
        if len(profit) >= 2:
            score_parts["profit_growing"] = int(profit[-1] > profit[-2])
        valid_scores = [v for v in score_parts.values() if v is not None]
        piotroski_proxy = sum(valid_scores) if valid_scores else None

        return {
            "cash_conversion_ratio": cfo_profit,
            "fcf_to_profit": fcf_profit,
            "fcf_margin_derived": fcf_margin,
            "roe_derived": roe_derived,
            "roa_derived": roa_derived,
            "roic": roic,
            "croic": croic,
            "net_debt": net_debt,
            "net_debt_ebitda": net_debt_ebitda,
            "average_roe_3y": avg_roe_3y,
            "average_roe_5y": avg_roe_5y,
            "average_roa_3y": avg_roa_3y,
            "average_roa_5y": avg_roa_5y,
            "operating_margin_3y_avg": margin_3y,
            "operating_margin_5y_avg": margin_5y,
            "operating_margin_current": current_margin,
            "debtor_days": debtor_days,
            "inventory_days": inventory_days,
            "payable_days": payable_days,
            "cash_conversion_cycle": cash_conversion_cycle,
            "revenue_cagr_3y_derived": _cagr(revenue, 3),
            "revenue_cagr_5y_derived": _cagr(revenue, 5),
            "profit_cagr_3y_derived": _cagr(profit, 3),
            "profit_cagr_5y_derived": _cagr(profit, 5),
            "eps_cagr_3y_derived": _cagr(eps, 3),
            "eps_cagr_5y_derived": _cagr(eps, 5),
            "fcf_cagr_3y_derived": _cagr(fcf, 3),
            "fcf_cagr_5y_derived": _cagr(fcf, 5),
            "debt_change_1y": _safe_div(debt[-1] - debt[-2], debt[-2]) if len(debt) >= 2 and debt[-2] != 0 else None,
            "debt_change_3y": _safe_div(debt[-1] - debt[-4], debt[-4]) if len(debt) >= 4 and debt[-4] != 0 else None,
            "piotroski_proxy_score": piotroski_proxy,
            "piotroski_proxy_components": score_parts,
        }

    # Existing ranking API retained for compatibility; ranking remains a
    # separate feature and is not used by the fundamental analysis page.
    def score_growth(self, fundamentals: Fundamentals) -> float:
        raise NotImplementedError("Growth scoring not yet implemented.")

    def score_roe(self, fundamentals: Fundamentals) -> float:
        raise NotImplementedError("ROE scoring not yet implemented.")

    def score_value(self, fundamentals: Fundamentals) -> float:
        raise NotImplementedError("Value scoring not yet implemented.")

    def score_quality(self, fundamentals: Fundamentals) -> float:
        raise NotImplementedError("Quality scoring not yet implemented.")

    def score_overall(self, fundamentals: Fundamentals) -> float:
        raise NotImplementedError("Overall scoring not yet implemented.")

    def apply_strategy(self, fundamentals: list[Fundamentals], strategy: str) -> list[dict[str, Any]]:
        raise NotImplementedError("Strategy application not yet implemented.")
