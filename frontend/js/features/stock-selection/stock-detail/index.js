const API_BASE = "/api/stocks";

const METRIC_GROUPS = [
    {
        title: "Valuation",
        metrics: [
            ["pe", "P/E"], ["forward_pe", "Forward P/E"], ["pb", "P/B"],
            ["ps", "P/S"], ["peg", "PEG"], ["ev_ebitda", "EV/EBITDA"],
            ["ev_revenue", "EV/Revenue"], ["dividend_yield", "Dividend Yield"],
        ],
    },
    {
        title: "Profitability & Financial Health",
        metrics: [
            ["roe", "ROE"], ["roa", "ROA"], ["profit_margin", "Net Margin"],
            ["operating_margin", "Operating Margin"], ["gross_margin", "Gross Margin"],
            ["debt_equity", "Debt/Equity"], ["current_ratio", "Current Ratio"],
            ["quick_ratio", "Quick Ratio"],
        ],
    },
    {
        title: "Growth",
        metrics: [
            ["revenue_growth", "Revenue Growth"], ["profit_growth", "Profit Growth"],
            ["eps_growth", "EPS Growth"], ["revenue_cagr_3y", "Revenue CAGR 3Y"],
            ["revenue_cagr_5y", "Revenue CAGR 5Y"], ["profit_cagr_3y", "Profit CAGR 3Y"],
            ["profit_cagr_5y", "Profit CAGR 5Y"], ["eps_cagr_3y", "EPS CAGR 3Y"],
            ["eps_cagr_5y", "EPS CAGR 5Y"], ["fcf_cagr_3y", "FCF CAGR 3Y"],
            ["fcf_cagr_5y", "FCF CAGR 5Y"],
        ],
    },
];

function escapeHtml(value) {
    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

function compact(value, currency = "") {
    if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
    const n = Number(value);
    const prefix = currency === "INR" ? "₹" : currency === "USD" ? "$" : currency ? `${currency} ` : "";
    const abs = Math.abs(n);
    if (abs >= 1e12) return `${prefix}${(n / 1e12).toFixed(2)}T`;
    if (abs >= 1e9) return `${prefix}${(n / 1e9).toFixed(2)}B`;
    if (abs >= 1e6) return `${prefix}${(n / 1e6).toFixed(2)}M`;
    if (abs >= 1e3) return `${prefix}${(n / 1e3).toFixed(2)}K`;
    return `${prefix}${n.toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
}

function percent(value, decimals = 2) {
    if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
    return `${(Number(value) * 100).toFixed(decimals)}%`;
}

function metricValue(key, value) {
    if (value === null || value === undefined) return "—";
    if (key.includes("yield") || key.includes("margin") || key === "roe" || key === "roa" || key.includes("growth") || key.includes("cagr")) {
        return percent(value);
    }
    return Number(value).toLocaleString("en-IN", { maximumFractionDigits: 2 });
}

function metricCard(key, label, value) {
    return `<div class="stock-metric-card">
        <span class="stock-metric-label">${escapeHtml(label)}</span>
        <strong class="stock-metric-value">${escapeHtml(metricValue(key, value))}</strong>
    </div>`;
}

function statementTable(title, rows, currency) {
    if (!rows?.length) return "";
    const fields = [...new Set(rows.flatMap(row => Object.keys(row.values || {})))];
    return `<section class="stock-section">
        <div class="stock-section-header"><h2>${escapeHtml(title)}</h2></div>
        <div class="stock-table-wrap"><table class="stock-table">
            <thead><tr><th>Metric</th>${rows.map(r => `<th>${escapeHtml(r.period)}</th>`).join("")}</tr></thead>
            <tbody>${fields.map(field => `<tr><td>${escapeHtml(field.replaceAll(/([a-z])([A-Z])/g, "$1 $2"))}</td>${rows.map(row => `<td>${compact(row.values?.[field], currency)}</td>`).join("")}</tr>`).join("")}</tbody>
        </table></div>
    </section>`;
}

function render(data, container, symbol) {
    const f = data.fundamentals || {};
    const currency = f.currency || "";
    const displaySymbol = f.symbol || symbol;

    container.innerHTML = `
        <div class="stock-toolbar">
            <form id="stock-search-form" class="stock-search-form">
                <input id="stock-symbol-input" value="${escapeHtml(symbol)}" placeholder="e.g. RELIANCE.NS or AAPL" aria-label="Stock symbol">
                <button type="submit" class="stock-page-btn">Analyze</button>
            </form>
            <span class="stock-source">Source: ${escapeHtml(f.source || "Yahoo Finance")}</span>
        </div>

        <section class="stock-hero">
            <div>
                <div class="stock-eyebrow">${escapeHtml(f.exchange || "")} · ${escapeHtml(displaySymbol)}</div>
                <h1>${escapeHtml(f.name || displaySymbol)}</h1>
                <p>${escapeHtml(f.sector || "")} ${f.industry ? `· ${escapeHtml(f.industry)}` : ""} ${f.country ? `· ${escapeHtml(f.country)}` : ""}</p>
            </div>
            <div class="stock-price-block">
                <strong>${compact(f.price, currency)}</strong>
                <span>${escapeHtml(currency)}</span>
            </div>
        </section>

        <section class="stock-summary-grid">
            ${metricCard("market_cap", "Market Cap", f.market_cap)}
            ${metricCard("enterprise_value", "Enterprise Value", f.enterprise_value)}
            ${metricCard("shares_outstanding", "Shares Outstanding", f.shares_outstanding)}
            ${metricCard("beta", "Beta", f.beta)}
            ${metricCard("revenue", "Revenue", f.revenue)}
            ${metricCard("net_profit", "Net Profit", f.net_profit)}
            ${metricCard("ebitda", "EBITDA", f.ebitda)}
            ${metricCard("free_cash_flow", "Free Cash Flow", f.free_cash_flow)}
        </section>

        ${METRIC_GROUPS.map(group => `<section class="stock-section"><div class="stock-section-header"><h2>${escapeHtml(group.title)}</h2></div><div class="stock-metrics-grid">${group.metrics.map(([key, label]) => metricCard(key, label, f[key])).join("")}</div></section>`).join("")}

        <section class="stock-section">
            <div class="stock-section-header"><h2>Core Financial Trend</h2><span>Latest annual data</span></div>
            <div class="stock-trend-grid">
                ${metricCard("revenue_cagr_3y", "Revenue CAGR 3Y", f.revenue_cagr_3y)}
                ${metricCard("profit_cagr_3y", "Profit CAGR 3Y", f.profit_cagr_3y)}
                ${metricCard("eps_cagr_3y", "EPS CAGR 3Y", f.eps_cagr_3y)}
                ${metricCard("fcf_cagr_3y", "FCF CAGR 3Y", f.fcf_cagr_3y)}
                ${metricCard("operating_margin_change", "Operating Margin Change", f.operating_margin_change)}
            </div>
        </section>

        ${statementTable("Income Statement", data.income_statement, currency)}
        ${statementTable("Balance Sheet", data.balance_sheet, currency)}
        ${statementTable("Cash Flow", data.cash_flow, currency)}

        <section class="stock-section stock-warnings">
            <div class="stock-section-header"><h2>Data Notes</h2></div>
            <ul>${(data.warnings || []).map(w => `<li>${escapeHtml(w)}</li>`).join("")}</ul>
            <small>Data as of ${escapeHtml(f.data_as_of || "—")}</small>
        </section>
    `;

    document.getElementById("stock-search-form")?.addEventListener("submit", event => {
        event.preventDefault();
        const next = document.getElementById("stock-symbol-input")?.value.trim().toUpperCase();
        if (!next) return;
        const url = new URL(window.location.href);
        url.searchParams.set("symbol", next);
        window.history.pushState({}, "", url);
        loadStock(next, container);
    });
}

async function loadStock(symbol, container) {
    container.innerHTML = `<div class="stock-loading">Loading ${escapeHtml(symbol)} fundamentals…</div>`;
    try {
        const response = await fetch(`${API_BASE}/${encodeURIComponent(symbol)}`);
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`);
        render(data, container, symbol);
    } catch (error) {
        container.innerHTML = `<div class="stock-error"><h2>Unable to load ${escapeHtml(symbol)}</h2><p>${escapeHtml(error.message)}</p><p>Check the symbol format, for example <code>RELIANCE.NS</code>, <code>TCS.NS</code>, <code>HDFCBANK.NS</code>, or <code>AAPL</code>.</p></div>`;
    }
}

export function initStockAnalysis() {
    const container = document.getElementById("stock-details");
    if (!container) return;
    const params = new URLSearchParams(window.location.search);
    const symbol = (params.get("symbol") || "RELIANCE.NS").trim().toUpperCase();
    loadStock(symbol, container);
}
