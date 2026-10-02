from __future__ import annotations

import re
from statistics import mean, pstdev
from typing import Any

from backend.services.data.screener import ScreenerFinanceClient


def _num(text: str | None) -> float | None:
    if text is None:
        return None
    value = re.sub(r"[^0-9.\-]", "", text.replace(",", ""))
    if value in {"", "-", "."}:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _series(rows: list[dict[str, Any]], key: str) -> list[tuple[str, float]]:
    out: list[tuple[str, float]] = []
    for row in rows:
        period = str(row.get("period", ""))[:4]
        value = row.get("values", {}).get(key)
        try:
            value = float(value) if value is not None else None
        except (TypeError, ValueError):
            value = None
        if period and value is not None:
            out.append((period, value))
    return sorted(out)


def _cagr(values: list[tuple[str, float]], years: int) -> float | None:
    if len(values) < years + 1:
        return None
    start = values[-(years + 1)][1]
    end = values[-1][1]
    if start <= 0 or end <= 0:
        return None
    return (end / start) ** (1 / years) - 1


def _growth(values: list[tuple[str, float]]) -> list[dict[str, float | str | None]]:
    out: list[dict[str, float | str | None]] = []
    for i in range(1, len(values)):
        previous = values[i - 1][1]
        current = values[i][1]
        out.append({"year": values[i][0], "value": (current / previous - 1) * 100 if previous != 0 else None})
    return out


def _trend(values: list[tuple[str, float]]) -> list[dict[str, float | str]]:
    return [{"year": year, "value": value} for year, value in values]


def _indexed(values: list[tuple[str, float]]) -> list[dict[str, float | str | None]]:
    positive = [(y, v) for y, v in values if v > 0]
    if not positive:
        return []
    base = positive[0][1]
    return [{"year": y, "value": v / base * 100 if base else None} for y, v in values]


def _shareholding(soup) -> dict[str, Any]:
    section = soup.find("section", id="shareholding")
    if section is None:
        for candidate in soup.find_all("section"):
            heading = candidate.find(["h2", "h3"])
            if heading and "shareholding pattern" in heading.get_text(" ", strip=True).casefold():
                section = candidate
                break
    if section is None:
        return {"quarterly": [], "annual": [], "categories": []}

    def parse_table(table):
        headers = [cell.get_text(" ", strip=True) for cell in table.select("thead th")]
        if not headers:
            first = table.find("tr")
            headers = [cell.get_text(" ", strip=True) for cell in first.find_all(["th", "td"])] if first else []
        date_indices = {
            i: h for i, h in enumerate(headers)
            if re.fullmatch(r"(?:Mar|Jun|Sep|Dec) \d{4}", h)
        }
        if not date_indices:
            return [], False
        values_by_date: dict[str, dict[str, float | None]] = {}
        for row in table.select("tbody tr"):
            cells = row.find_all(["th", "td"])
            if len(cells) < 2:
                continue
            label = re.sub(r"\s+", " ", cells[0].get_text(" ", strip=True)).casefold()
            category = None
            if label.startswith("promoters"):
                category = "promoters"
            elif label.startswith("fiis"):
                category = "fiis"
            elif label.startswith("diis"):
                category = "diis"
            elif label.startswith("government"):
                category = "government"
            elif label.startswith("public"):
                category = "public"
            elif label.startswith("no. of shareholders"):
                category = "shareholders"
            if not category:
                continue
            for index, date in date_indices.items():
                if index >= len(cells):
                    continue
                value = _num(cells[index].get_text(" ", strip=True))
                values_by_date.setdefault(date, {})[category] = value
        rows = []
        for date, values in sorted(values_by_date.items()):
            rows.append({"date": date, **values})
        return rows, len(date_indices) > 0

    tables = section.find_all("table")
    parsed = [parse_table(table)[0] for table in tables]
    quarterly = parsed[0] if parsed else []
    annual = parsed[1] if len(parsed) > 1 else []

    # Keep the more frequent quarterly observation when both tables contain the
    # same date, while retaining the longer annual history for older dates.
    merged: dict[str, dict[str, Any]] = {}
    for row in annual + quarterly:
        merged[row["date"]] = {**merged.get(row["date"], {}), **row}
    combined = sorted(merged.values(), key=lambda x: x["date"])
    categories = ["promoters", "fiis", "diis", "government", "public"]
    return {"quarterly": quarterly, "annual": annual, "combined": combined, "categories": categories}


def _consistency(values: list[tuple[str, float]]) -> dict[str, Any]:
    if len(values) < 2:
        return {"years": len(values), "positive_growth_years": None, "positive_growth_pct": None}
    growth = [(values[i][1] / values[i - 1][1] - 1) for i in range(1, len(values)) if values[i - 1][1] != 0]
    positive = sum(1 for x in growth if x > 0)
    return {
        "years": len(values),
        "positive_growth_years": positive,
        "growth_observations": len(growth),
        "positive_growth_pct": positive / len(growth) * 100 if growth else None,
    }


def build_stock_pedigree(client: ScreenerFinanceClient, symbol: str) -> dict[str, Any]:
    history = client.financial_history(symbol)
    soup = client._fetch(symbol)

    income = history.get("income", [])
    balance = history.get("balance", [])
    cash = history.get("cash", [])

    revenue = _series(income, "TotalRevenue")
    operating = _series(income, "OperatingIncome")
    profit = _series(income, "NetIncome")
    eps = _series(income, "DilutedEPS")
    ebitda = _series(income, "EBITDA")
    cfo = _series(cash, "OperatingCashFlow")
    fcf = _series(cash, "FreeCashFlow")
    debt = _series(balance, "TotalDebt")
    equity = _series(balance, "StockholdersEquity")
    assets = _series(balance, "TotalAssets")
    net_block = _series(balance, "NetBlock")
    current_assets = _series(balance, "CurrentAssets")
    current_liabilities = _series(balance, "CurrentLiabilities")
    debtors = _series(balance, "Debtors")
    inventory = _series(balance, "Inventory")
    payables = _series(balance, "TradePayables")

    revenue_map = dict(revenue)
    equity_map = dict(equity)
    assets_map = dict(assets)
    current_assets_map = dict(current_assets)
    current_liabilities_map = dict(current_liabilities)
    net_block_map = dict(net_block)
    debtors_map = dict(debtors)
    inventory_map = dict(inventory)
    payables_map = dict(payables)

    roe: list[tuple[str, float]] = []
    roa: list[tuple[str, float]] = []
    roce: list[tuple[str, float]] = []
    opm: list[tuple[str, float]] = []
    net_margin: list[tuple[str, float]] = []
    fcf_margin: list[tuple[str, float]] = []
    cash_conversion: list[tuple[str, float]] = []
    ccc: list[tuple[str, float]] = []

    for i, (year, profit_value) in enumerate(profit):
        eq = equity_map.get(year)
        asset = assets_map.get(year)
        prev_year = profit[i - 1][0] if i else None
        prev_eq = equity_map.get(prev_year) if prev_year else eq
        prev_assets = assets_map.get(prev_year) if prev_year else asset
        avg_eq = (eq + prev_eq) / 2 if eq is not None and prev_eq is not None else eq
        avg_assets = (asset + prev_assets) / 2 if asset is not None and prev_assets is not None else asset
        if avg_eq not in (None, 0):
            roe.append((year, profit_value / avg_eq * 100))
        if avg_assets not in (None, 0):
            roa.append((year, profit_value / avg_assets * 100))
        rev = revenue_map.get(year)
        op = dict(operating).get(year)
        if rev not in (None, 0):
            if op is not None:
                opm.append((year, op / rev * 100))
            net_margin.append((year, profit_value / rev * 100))
            debtor = debtors_map.get(year)
            inv = inventory_map.get(year)
            payable = payables_map.get(year)
            if debtor is not None and inv is not None and payable is not None:
                ccc.append((year, (debtor + inv - payable) / rev * 365))
        cash_value = dict(cfo).get(year)
        if cash_value is not None and profit_value != 0:
            cash_conversion.append((year, cash_value / profit_value * 100))
        fcf_value = dict(fcf).get(year)
        if fcf_value is not None and rev not in (None, 0):
            fcf_margin.append((year, fcf_value / rev * 100))
        nb = net_block_map.get(year)
        ca = current_assets_map.get(year)
        cl = current_liabilities_map.get(year)
        if op is not None and nb is not None and ca is not None and cl is not None:
            invested = nb + ca - cl
            if invested != 0:
                roce.append((year, op / invested * 100))

    shareholding = _shareholding(soup)
    combined_sh = shareholding.get("combined", [])
    promoter = [(r["date"], r["promoters"]) for r in combined_sh if r.get("promoters") is not None]
    fii = [(r["date"], r["fiis"]) for r in combined_sh if r.get("fiis") is not None]
    dii = [(r["date"], r["diis"]) for r in combined_sh if r.get("diis") is not None]
    government = [(r["date"], r["government"]) for r in combined_sh if r.get("government") is not None]
    public = [(r["date"], r["public"]) for r in combined_sh if r.get("public") is not None]
    shareholders = [(r["date"], r["shareholders"]) for r in combined_sh if r.get("shareholders") is not None]

    def volatility(series: list[tuple[str, float]]) -> float | None:
        vals = [v for _, v in series]
        return pstdev(vals) if len(vals) >= 2 else None

    def latest_change(series: list[tuple[str, float]], years: int = 3) -> float | None:
        if len(series) < years + 1:
            return None
        return series[-1][1] - series[-(years + 1)][1]

    consistency = {
        "revenue": _consistency(revenue),
        "profit": _consistency(profit),
        "eps": _consistency(eps),
        "fcf": _consistency(fcf),
        "roe_volatility": volatility(roe),
        "operating_margin_volatility": volatility(opm),
        "roe_average": mean(v for _, v in roe) if roe else None,
        "roce_average": mean(v for _, v in roce) if roce else None,
        "operating_margin_average": mean(v for _, v in opm) if opm else None,
        "debt_change_3y": latest_change(debt, 3),
        "debt_change_5y": latest_change(debt, 5),
    }

    return {
        "symbol": symbol.strip().upper(),
        "source": "Screener.in",
        "shareholding": {
            "quarterly": shareholding.get("quarterly", []),
            "annual": shareholding.get("annual", []),
            "combined": combined_sh,
            "categories": shareholding.get("categories", []),
            "classification_note": "Screener notes that shareholding classifications may have changed from Sep 2022 because of the XBRL format and that historical FII/DII comparisons can be affected.",
        },
        "trends": {
            "revenue": _trend(revenue),
            "profit": _trend(profit),
            "ebitda": _trend(ebitda),
            "cfo": _trend(cfo),
            "fcf": _trend(fcf),
            "debt": _trend(debt),
            "roe": _trend(roe),
            "roa": _trend(roa),
            "roce": _trend(roce),
            "operating_margin": _trend(opm),
            "net_margin": _trend(net_margin),
            "fcf_margin": _trend(fcf_margin),
            "cash_conversion": _trend(cash_conversion),
            "cash_conversion_cycle": _trend(ccc),
            "revenue_indexed": _indexed(revenue),
            "profit_indexed": _indexed(profit),
            "fcf_indexed": _indexed(fcf),
            "revenue_growth": _growth(revenue),
            "profit_growth": _growth(profit),
            "eps_growth": _growth(eps),
            "promoter_holding": _trend(promoter),
            "fii_holding": _trend(fii),
            "dii_holding": _trend(dii),
            "government_holding": _trend(government),
            "public_holding": _trend(public),
            "shareholders": _trend(shareholders),
        },
        "consistency": consistency,
        "cagr": {
            "revenue_3y": _cagr(revenue, 3),
            "revenue_5y": _cagr(revenue, 5),
            "profit_3y": _cagr(profit, 3),
            "profit_5y": _cagr(profit, 5),
            "eps_3y": _cagr(eps, 3),
            "eps_5y": _cagr(eps, 5),
            "fcf_3y": _cagr(fcf, 3),
            "fcf_5y": _cagr(fcf, 5),
        },
    }
