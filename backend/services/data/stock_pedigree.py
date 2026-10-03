from __future__ import annotations

import re
from statistics import mean, pstdev
from typing import Any

from backend.services.data.screener import ScreenerFinanceClient


def _raw(value: Any) -> float | None:
    if isinstance(value, dict):
        value = value.get("raw")
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _series(section: dict[str, list[dict[str, Any]]], key: str) -> list[tuple[str, float]]:
    rows = section.get(key, []) if isinstance(section, dict) else []
    out: list[tuple[str, float]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        year = str(row.get("asOfDate", ""))[:4]
        value = _raw(row.get(key))
        if year and value is not None:
            out.append((year, value))
    return sorted(out)


def _cagr(values: list[tuple[str, float]], years: int) -> float | None:
    if len(values) < years + 1:
        return None
    start, end = values[-(years + 1)][1], values[-1][1]
    if start <= 0 or end <= 0:
        return None
    return (end / start) ** (1 / years) - 1


def _growth(values: list[tuple[str, float]]) -> list[dict[str, Any]]:
    return [{"year": values[i][0], "value": (values[i][1] / values[i - 1][1] - 1) * 100 if values[i - 1][1] != 0 else None} for i in range(1, len(values))]


def _trend(values: list[tuple[str, float]]) -> list[dict[str, Any]]:
    return [{"year": year, "value": value} for year, value in values]


def _indexed(values: list[tuple[str, float]]) -> list[dict[str, Any]]:
    positive = [(y, v) for y, v in values if v > 0]
    if not positive:
        return []
    base = positive[0][1]
    return [{"year": y, "value": v / base * 100} for y, v in values]


def _shareholding(soup):
    section = soup.find("section", id="shareholding")
    if section is None:
        for candidate in soup.find_all("section"):
            heading = candidate.find(["h2", "h3"])
            if heading and "shareholding pattern" in heading.get_text(" ", strip=True).casefold():
                section = candidate
                break
    if section is None:
        return {"quarterly": [], "annual": [], "combined": [], "categories": []}

    def parse_table(table):
        headers = [cell.get_text(" ", strip=True) for cell in table.select("thead th")]
        if not headers:
            first = table.find("tr")
            headers = [cell.get_text(" ", strip=True) for cell in first.find_all(["th", "td"])] if first else []
        date_indices = {i: h for i, h in enumerate(headers) if re.fullmatch(r"(?:Mar|Jun|Sep|Dec) \d{4}", h)}
        if not date_indices:
            return []
        values_by_date: dict[str, dict[str, Any]] = {}
        for row in table.select("tbody tr"):
            cells = row.find_all(["th", "td"])
            if len(cells) < 2:
                continue
            label = re.sub(r"\s+", " ", cells[0].get_text(" ", strip=True)).casefold()
            category = None
            if label.startswith("promoters"):
                category = "promoters"
            elif label.startswith("fiis") or label.startswith("foreign institutional"):
                category = "fiis"
            elif label.startswith("diis") or label.startswith("domestic institutional"):
                category = "diis"
            elif label.startswith("government"):
                category = "government"
            elif label.startswith("public"):
                category = "public"
            elif label.startswith("no. of shareholders") or label.startswith("number of shareholders"):
                category = "shareholders"
            if not category:
                continue
            for index, date in date_indices.items():
                if index < len(cells):
                    text = cells[index].get_text(" ", strip=True).replace(",", "").replace("%", "")
                    try:
                        values_by_date.setdefault(date, {})[category] = float(text) if text not in {"", "-", "--"} else None
                    except ValueError:
                        values_by_date.setdefault(date, {})[category] = None
        return [{"date": date, **values} for date, values in sorted(values_by_date.items())]

    parsed = [parse_table(table) for table in section.find_all("table")]
    quarterly, annual = (parsed[0] if parsed else []), (parsed[1] if len(parsed) > 1 else [])
    merged: dict[str, dict[str, Any]] = {}
    for row in annual + quarterly:
        merged[row["date"]] = {**merged.get(row["date"], {}), **row}
    combined = sorted(merged.values(), key=lambda x: x["date"])
    return {"quarterly": quarterly, "annual": annual, "combined": combined, "categories": ["promoters", "fiis", "diis", "government", "public"]}


def _consistency(values: list[tuple[str, float]]) -> dict[str, Any]:
    if len(values) < 2:
        return {"years": len(values), "positive_growth_years": None, "positive_growth_pct": None}
    growth = [(values[i][1] / values[i - 1][1] - 1) for i in range(1, len(values)) if values[i - 1][1] != 0]
    positive = sum(1 for x in growth if x > 0)
    return {"years": len(values), "positive_growth_years": positive, "growth_observations": len(growth), "positive_growth_pct": positive / len(growth) * 100 if growth else None}


def build_stock_pedigree(client: ScreenerFinanceClient, symbol: str) -> dict[str, Any]:
    history = client.financial_history(symbol)
    soup = client._fetch(symbol)
    income = history.get("income", {})
    balance = history.get("balance", {})
    cash = history.get("cash", {})

    revenue = _series(income, "annualTotalRevenue")
    operating = _series(income, "annualOperatingIncome")
    profit = _series(income, "annualNetIncome")
    eps = _series(income, "annualDilutedEPS")
    ebitda = _series(income, "annualEBITDA")
    cfo = _series(cash, "annualOperatingCashFlow")
    capex = _series(cash, "annualCapitalExpenditure")
    fcf = _series(cash, "annualFreeCashFlow")
    debt = _series(balance, "annualTotalDebt")
    equity = _series(balance, "annualStockholdersEquity")
    assets = _series(balance, "annualTotalAssets")
    net_block = _series(balance, "annualNetBlock")
    current_assets = _series(balance, "annualCurrentAssets")
    current_liabilities = _series(balance, "annualCurrentLiabilities")
    debtors = _series(balance, "annualDebtors")
    inventory = _series(balance, "annualInventory")
    payables = _series(balance, "annualTradePayables")

    maps = {name: dict(values) for name, values in {
        "revenue": revenue, "equity": equity, "assets": assets,
        "current_assets": current_assets, "current_liabilities": current_liabilities,
        "net_block": net_block, "debtors": debtors, "inventory": inventory,
        "payables": payables, "operating": operating, "fcf": fcf,
        "capex": capex, "profit": profit, "eps": eps, "cfo": cfo,
    }.items()}

    roe: list[tuple[str, float]] = []
    roa: list[tuple[str, float]] = []
    roce: list[tuple[str, float]] = []
    opm: list[tuple[str, float]] = []
    net_margin: list[tuple[str, float]] = []
    fcf_margin: list[tuple[str, float]] = []
    cash_conversion: list[tuple[str, float]] = []
    fcf_conversion: list[tuple[str, float]] = []
    ccc: list[tuple[str, float]] = []
    capex_to_cfo: list[tuple[str, float]] = []
    capex_to_revenue: list[tuple[str, float]] = []
    implied_shares: list[tuple[str, float]] = []
    profit_eps_gap: list[tuple[str, float]] = []
    debt_equity = [
        (year, debt_value / equity_value)
        for year, debt_value in debt
        if (equity_value := maps["equity"].get(year)) is not None and equity_value > 0
    ]

    for i, (year, profit_value) in enumerate(profit):
        eq, asset = maps["equity"].get(year), maps["assets"].get(year)
        prev = profit[i - 1][0] if i else None
        prev_eq = maps["equity"].get(prev) if prev else eq
        prev_assets = maps["assets"].get(prev) if prev else asset
        avg_eq = (eq + prev_eq) / 2 if eq is not None and prev_eq is not None else eq
        avg_assets = (asset + prev_assets) / 2 if asset is not None and prev_assets is not None else asset
        if avg_eq not in (None, 0):
            roe.append((year, profit_value / avg_eq * 100))
        if avg_assets not in (None, 0):
            roa.append((year, profit_value / avg_assets * 100))

        rev, op = maps["revenue"].get(year), maps["operating"].get(year)
        if rev not in (None, 0):
            if op is not None:
                opm.append((year, op / rev * 100))
            net_margin.append((year, profit_value / rev * 100))
            fcf_value = maps["fcf"].get(year)
            if fcf_value is not None:
                fcf_margin.append((year, fcf_value / rev * 100))
            debtor, inv, payable = maps["debtors"].get(year), maps["inventory"].get(year), maps["payables"].get(year)
            if debtor is not None and inv is not None and payable is not None:
                ccc.append((year, (debtor + inv - payable) / rev * 365))
            capex_value = maps["capex"].get(year)
            if capex_value is not None:
                capex_to_revenue.append((year, abs(capex_value) / abs(rev) * 100))

        cash_value = maps["cfo"].get(year)
        if cash_value is not None and profit_value != 0:
            cash_conversion.append((year, cash_value / profit_value * 100))
        fcf_value = maps["fcf"].get(year)
        if fcf_value is not None and profit_value != 0:
            fcf_conversion.append((year, fcf_value / profit_value * 100))
        capex_value = maps["capex"].get(year)
        if capex_value is not None and cash_value not in (None, 0):
            capex_to_cfo.append((year, abs(capex_value) / abs(cash_value) * 100))

        eps_value = maps["eps"].get(year)
        if eps_value not in (None, 0):
            # Net profit is in crore and EPS is rupees/share, so this yields
            # an implied share count in crore shares. It is a useful historical
            # dilution proxy when annual share-count history is not separately reported.
            implied = profit_value / eps_value
            if implied > 0:
                implied_shares.append((year, implied))

        nb, ca, cl = maps["net_block"].get(year), maps["current_assets"].get(year), maps["current_liabilities"].get(year)
        if op is not None and nb is not None and ca is not None and cl is not None:
            invested = nb + ca - cl
            if invested != 0:
                roce.append((year, op / invested * 100))

    sh = _shareholding(soup)
    combined = sh.get("combined", [])
    promoter = [(r["date"], r["promoters"]) for r in combined if r.get("promoters") is not None]
    fii = [(r["date"], r["fiis"]) for r in combined if r.get("fiis") is not None]
    dii = [(r["date"], r["diis"]) for r in combined if r.get("diis") is not None]
    government = [(r["date"], r["government"]) for r in combined if r.get("government") is not None]
    public = [(r["date"], r["public"]) for r in combined if r.get("public") is not None]
    shareholders = [(r["date"], r["shareholders"]) for r in combined if r.get("shareholders") is not None]

    def volatility(series):
        vals = [v for _, v in series]
        return pstdev(vals) if len(vals) >= 2 else None

    def latest_change(series, years=3):
        return series[-1][1] - series[-(years + 1)][1] if len(series) >= years + 1 else None

    def aligned_growth(a: list[tuple[str, float]], b: list[tuple[str, float]], years: int) -> float | None:
        ca, cb = _cagr(a, years), _cagr(b, years)
        return ca - cb if ca is not None and cb is not None else None

    consistency = {
        "revenue": _consistency(revenue), "profit": _consistency(profit),
        "eps": _consistency(eps), "fcf": _consistency(fcf),
        "roe_volatility": volatility(roe), "operating_margin_volatility": volatility(opm),
        "roe_average": mean(v for _, v in roe) if roe else None,
        "roce_average": mean(v for _, v in roce) if roce else None,
        "operating_margin_average": mean(v for _, v in opm) if opm else None,
        "debt_change_3y": latest_change(debt, 3), "debt_change_5y": latest_change(debt, 5),
    }

    # Capital allocation, earnings quality and dilution analytics.
    capital_allocation = {
        "capex": _trend(capex),
        "cfo": _trend(cfo),
        "fcf": _trend(fcf),
        "capex_to_cfo": _trend(capex_to_cfo),
        "capex_to_revenue": _trend(capex_to_revenue),
        "fcf_to_cfo": _trend([(y, f / c * 100) for y, f in fcf if (c := maps["cfo"].get(y)) not in (None, 0)]),
        "debt": _trend(debt),
        "debt_change": _growth(debt),
    }
    earnings_quality = {
        "net_profit": _trend(profit),
        "cfo": _trend(cfo),
        "fcf": _trend(fcf),
        "cfo_to_profit": _trend(cash_conversion),
        "fcf_to_profit": _trend(fcf_conversion),
        "net_profit_indexed": _indexed(profit),
        "cfo_indexed": _indexed(cfo),
        "fcf_indexed": _indexed(fcf),
        "profit_growth": _growth(profit),
        "cfo_growth": _growth(cfo),
        "fcf_growth": _growth(fcf),
        "cfo_profit_gap_3y": aligned_growth(cfo, profit, 3),
        "cfo_profit_gap_5y": aligned_growth(cfo, profit, 5),
        "fcf_profit_gap_3y": aligned_growth(fcf, profit, 3),
        "fcf_profit_gap_5y": aligned_growth(fcf, profit, 5),
    }
    dilution = {
        "implied_shares": _trend(implied_shares),
        "share_count_growth": _growth(implied_shares),
        "share_count_cagr_3y": _cagr(implied_shares, 3),
        "share_count_cagr_5y": _cagr(implied_shares, 5),
        "profit_vs_eps_cagr_gap_3y": aligned_growth(profit, eps, 3),
        "profit_vs_eps_cagr_gap_5y": aligned_growth(profit, eps, 5),
        "eps_cagr_3y": _cagr(eps, 3),
        "eps_cagr_5y": _cagr(eps, 5),
    }

    return {
        "symbol": symbol.strip().upper(),
        "shareholding": {"quarterly": sh.get("quarterly", []), "annual": sh.get("annual", []), "combined": combined, "categories": sh.get("categories", [])},
        "trends": {
            "revenue": _trend(revenue), "profit": _trend(profit), "ebitda": _trend(ebitda),
            "cfo": _trend(cfo), "fcf": _trend(fcf), "debt": _trend(debt),
            "debt_equity": _trend(debt_equity),
            "roe": _trend(roe), "roa": _trend(roa), "roce": _trend(roce),
            "operating_margin": _trend(opm), "net_margin": _trend(net_margin),
            "fcf_margin": _trend(fcf_margin), "cash_conversion": _trend(cash_conversion),
            "cash_conversion_cycle": _trend(ccc), "revenue_indexed": _indexed(revenue),
            "profit_indexed": _indexed(profit), "fcf_indexed": _indexed(fcf),
            "revenue_growth": _growth(revenue), "profit_growth": _growth(profit), "eps_growth": _growth(eps),
            "promoter_holding": _trend(promoter), "fii_holding": _trend(fii), "dii_holding": _trend(dii),
            "government_holding": _trend(government), "public_holding": _trend(public), "shareholders": _trend(shareholders),
        },
        "capital_allocation": capital_allocation,
        "earnings_quality": earnings_quality,
        "dilution": dilution,
        "consistency": consistency,
        "cagr": {
            "revenue_3y": _cagr(revenue, 3), "revenue_5y": _cagr(revenue, 5),
            "profit_3y": _cagr(profit, 3), "profit_5y": _cagr(profit, 5),
            "eps_3y": _cagr(eps, 3), "eps_5y": _cagr(eps, 5),
            "fcf_3y": _cagr(fcf, 3), "fcf_5y": _cagr(fcf, 5),
        },
    }
