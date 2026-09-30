const API_BASE = "/api/stocks";

const GROUPS = [
    {
        title: "Valuation",
        metrics: [
            ["pe", "P/E", "ratio"], ["forward_pe", "Forward P/E", "ratio"],
            ["pb", "Price / Book", "ratio"], ["ps", "Price / Sales", "ratio"],
            ["peg", "PEG", "ratio"], ["ev_ebitda", "EV / EBITDA", "ratio"],
            ["ev_revenue", "EV / Revenue", "ratio"], ["dividend_yield", "Dividend Yield", "percent"],
            ["payout_ratio", "Payout Ratio", "percent"],
        ],
    },
    {
        title: "Profitability",
        metrics: [
            ["roe", "ROE", "percent"], ["roa", "ROA", "percent"],
            ["gross_margin", "Gross Margin", "percent"], ["operating_margin", "Operating Margin", "percent"],
            ["profit_margin", "Net Margin", "percent"],
        ],
    },
    {
        title: "Financial Health",
        metrics: [
            ["debt_equity", "Debt / Equity", "ratio"],
            ["current_ratio", "Current Ratio", "ratio"],
            ["quick_ratio", "Quick Ratio", "ratio"],
            ["beta", "Beta", "number"],
        ],
    },
    {
        title: "Growth",
        metrics: [
            ["revenue_growth", "Revenue Growth", "percent"],
            ["profit_growth", "Profit Growth", "percent"],
            ["eps_growth", "EPS Growth", "percent"],
            ["revenue_cagr_3y", "Revenue CAGR 3Y", "percent_decimal"],
            ["revenue_cagr_5y", "Revenue CAGR 5Y", "percent_decimal"],
            ["profit_cagr_3y", "Profit CAGR 3Y", "percent_decimal"],
            ["profit_cagr_5y", "Profit CAGR 5Y", "percent_decimal"],
            ["eps_cagr_3y", "EPS CAGR 3Y", "percent_decimal"],
            ["eps_cagr_5y", "EPS CAGR 5Y", "percent_decimal"],
            ["fcf_cagr_3y", "FCF CAGR 3Y", "percent_decimal"],
            ["fcf_cagr_5y", "FCF CAGR 5Y", "percent_decimal"],
            ["operating_margin_change", "Operating Margin Change", "pp"],
        ],
    },
];

let financialDisplayMode = "international";

function esc(value) {
    return String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");
}

function fmtNumber(value, digits = 2) {
    return Number(value).toLocaleString("en-IN", { maximumFractionDigits: digits, minimumFractionDigits: 0 });
}

function fmtPercent(value, multiplier = 1) {
    return value == null || !Number.isFinite(Number(value))
        ? "—"
        : `${fmtNumber(Number(value) * multiplier, 2)}%`;
}

function fmtRatio(value) {
    return value == null || !Number.isFinite(Number(value)) ? "—" : `${fmtNumber(Number(value), 2)}x`;
}

function fmtCompact(value, currency = "") {
    if (value == null || !Number.isFinite(Number(value))) return "—";
    const n = Number(value);
    const p = currency === "INR" ? "₹" : currency === "USD" ? "$" : currency ? `${currency} ` : "";
    const a = Math.abs(n);
    if (a >= 1e12) return `${p}${fmtNumber(n / 1e12, 2)}T`;
    if (a >= 1e9) return `${p}${fmtNumber(n / 1e9, 2)}B`;
    if (a >= 1e6) return `${p}${fmtNumber(n / 1e6, 2)}M`;
    if (a >= 1e3) return `${p}${fmtNumber(n / 1e3, 2)}K`;
    return `${p}${fmtNumber(n, 2)}`;
}

function fmtFinancial(value, currency = "") {
    if (value == null || !Number.isFinite(Number(value))) return "—";
    if (financialDisplayMode === "indian" && currency === "INR") {
        const n = Number(value);
        return `₹${fmtNumber(n / 1e7, 2)} Cr`;
    }
    return fmtCompact(value, currency);
}

function fmtPrice(value, currency = "") {
    if (value == null || !Number.isFinite(Number(value))) return "—";
    const n = Number(value);
    const p = currency === "INR" ? "₹" : currency === "USD" ? "$" : currency ? `${currency} ` : "";
    return `${p}${fmtNumber(n, 2)}`;
}

function valueForMetric(key, value, type) {
    if (value == null) return "—";
    if (type === "percent") return fmtPercent(value);
    if (type === "percent_decimal") return fmtPercent(value, 100);
    if (type === "ratio") return fmtRatio(value);
    if (type === "pp") return `${fmtNumber(Number(value), 2)} pp`;
    if (type === "text") return String(value);
    return fmtNumber(Number(value), 2);
}

function metricCard(key, label, value, type) {
    const display = valueForMetric(key, value, type);
    const cls = Number(value) > 0 && (type === "percent" || type === "percent_decimal" || type === "pp")
        ? "metric-positive"
        : Number(value) < 0 && (type === "percent" || type === "percent_decimal" || type === "pp")
            ? "metric-negative" : "";
    return `<div class="stock-metric-card">
        <span class="stock-metric-label">${esc(label)}</span>
        <strong class="stock-metric-value ${cls}">${esc(display)}</strong>
    </div>`;
}

function renderGroup(group, f) {
    return `<section class="stock-section">
        <div class="stock-section-header"><h2>${esc(group.title)}</h2></div>
        <div class="stock-metrics-grid">
            ${group.metrics.map(([key, label, type]) => metricCard(key, label, f[key], type)).join("")}
        </div>
    </section>`;
}

function renderCompany(f) {
    const currency = f.currency || "";
    return `<section class="stock-hero">
        <div>
            <div class="stock-eyebrow">${esc(f.exchange || "")} · ${esc(f.symbol || "")}</div>
            <h1>${esc(f.name || f.symbol || "")}</h1>
            <p>${esc(f.sector || "")}${f.industry ? ` · ${esc(f.industry)}` : ""}${f.country ? ` · ${esc(f.country)}` : ""}</p>
        </div>
        <div class="stock-price-block">
            <strong>${esc(fmtPrice(f.price, currency))}</strong>
            <span>${esc(currency)}</span>
        </div>
    </section>

    <section class="stock-summary-grid">
        ${metricCard("market_cap", "Market Cap", fmtFinancial(f.market_cap, currency), "text")}
        ${metricCard("enterprise_value", "Enterprise Value", fmtFinancial(f.enterprise_value, currency), "text")}
        ${metricCard("revenue", "Latest Revenue", fmtFinancial(f.revenue, currency), "text")}
        ${metricCard("net_profit", "Latest Net Profit", fmtFinancial(f.net_profit, currency), "text")}
        ${metricCard("ebitda", "Latest EBITDA", fmtFinancial(f.ebitda, currency), "text")}
        ${metricCard("free_cash_flow", "Latest Free Cash Flow", fmtFinancial(f.free_cash_flow, currency), "text")}
    </section>`;
}

function statementTable(title, rows, currency) {
    if (!rows?.length) {
        return `<section class="stock-section"><div class="stock-section-header"><h2>${esc(title)}</h2></div><div class="stock-no-data">No historical data available.</div></section>`;
    }

    const fields = [...new Set(rows.flatMap(r => Object.keys(r.values || {})))];

    return `<section class="stock-section">
        <div class="stock-section-header"><h2>${esc(title)}</h2><span>Annual</span></div>
        <div class="stock-table-wrap">
            <table class="stock-table">
                <thead>
                    <tr><th>Metric</th>${rows.map(r => `<th>${esc(r.period.slice(0, 4))}</th>`).join("")}</tr>
                </thead>
                <tbody>
                    ${fields.map(field => `<tr>
                        <td>${esc(field.replace(/([a-z])([A-Z])/g, "$1 $2"))}</td>
                        ${rows.map(row => `<td>${esc(formatStatementValue(field, row.values?.[field], currency))}</td>`).join("")}
                    </tr>`).join("")}
                </tbody>
            </table>
        </div>
    </section>`;
}

function formatStatementValue(field, value, currency) {
    if (value == null) return "—";
    if (field.toLowerCase().includes("eps")) return fmtNumber(value, 2);
    return fmtFinancial(value, currency);
}

function render(data, container) {
    const f = data.fundamentals || {};
    const indianUnitsAvailable = f.currency === "INR";
    if (!indianUnitsAvailable) financialDisplayMode = "international";

    container.innerHTML = `
        ${renderCompany(f)}
        ${GROUPS.map(group => renderGroup(group, f)).join("")}

        <section class="stock-section">
            <div class="stock-section-header">
                <h2>Financial Statements</h2>
                <div class="stock-display-controls">
                    <span>Display:</span>
                    <label class="stock-unit-toggle">
                        <input type="radio" name="stock-financial-unit" value="international" ${financialDisplayMode === "international" ? "checked" : ""}>
                        <span>B / T</span>
                    </label>
                    <label class="stock-unit-toggle ${indianUnitsAvailable ? "" : "disabled"}">
                        <input type="radio" name="stock-financial-unit" value="indian" ${financialDisplayMode === "indian" ? "checked" : ""} ${indianUnitsAvailable ? "" : "disabled"}>
                        <span>₹ Cr</span>
                    </label>
                </div>
            </div>
            <div class="stock-statement-tabs">
                <button class="stock-tab active" data-tab="income">Income Statement</button>
                <button class="stock-tab" data-tab="balance">Balance Sheet</button>
                <button class="stock-tab" data-tab="cash">Cash Flow</button>
            </div>
            <div id="stock-statement-content">
                ${statementTable("Income Statement", data.income_statement, f.currency || "")}
            </div>
        </section>

        <section class="stock-section stock-warnings">
            <div class="stock-section-header"><h2>Data Notes</h2></div>
            <ul>${(data.warnings || []).map(w => `<li>${esc(w)}</li>`).join("")}</ul>
            <small>Data as of ${esc(f.data_as_of || "—")} · Source: ${esc(f.source || "Yahoo Finance")}</small>
        </section>`;

    const content = document.getElementById("stock-statement-content");
    container.querySelectorAll(".stock-tab").forEach(tab => {
        tab.addEventListener("click", () => {
            container.querySelectorAll(".stock-tab").forEach(t => t.classList.remove("active"));
            tab.classList.add("active");
            const kind = tab.dataset.tab;
            if (kind === "income") content.innerHTML = statementTable("Income Statement", data.income_statement, f.currency || "");
            if (kind === "balance") content.innerHTML = statementTable("Balance Sheet", data.balance_sheet, f.currency || "");
            if (kind === "cash") content.innerHTML = statementTable("Cash Flow", data.cash_flow, f.currency || "");
        });
    });

    container.querySelectorAll('input[name="stock-financial-unit"]').forEach(input => {
        input.addEventListener("change", () => {
            financialDisplayMode = input.value;
            render(data, container);
        });
    });
}

async function loadStock(symbol, container, status) {
    status.textContent = `Loading ${symbol}…`;
    container.innerHTML = `<div class="stock-loading">Loading ${esc(symbol)} fundamentals…</div>`;

    try {
        const response = await fetch(`${API_BASE}/${encodeURIComponent(symbol)}`, {
            headers: { "Accept": "application/json" }
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data?.detail || `HTTP ${response.status}`);
        }

        render(data, container);
        status.textContent = "";
    } catch (error) {
        container.innerHTML = `<div class="stock-error">
            <h2>Unable to load ${esc(symbol)}</h2>
            <p>${esc(error.message)}</p>
            <p>Examples: <code>RELIANCE.NS</code>, <code>TCS.NS</code>, <code>HDFCBANK.NS</code>, <code>AAPL</code>.</p>
        </div>`;
        status.textContent = "";
    }
}

export function initStockAnalysis() {
    const container = document.getElementById("stock-details");
    const form = document.getElementById("stock-search-form");
    const input = document.getElementById("stock-symbol-input");
    const status = document.getElementById("stock-analysis-status");

    if (!container || !form || !input) return;

    const params = new URLSearchParams(window.location.search);
    const initial = (params.get("symbol") || "RELIANCE.NS").trim().toUpperCase();
    input.value = initial;

    form.addEventListener("submit", event => {
        event.preventDefault();
        const symbol = input.value.trim().toUpperCase();
        if (!symbol) return;
        const url = new URL(window.location.href);
        url.searchParams.set("symbol", symbol);
        window.history.pushState({}, "", url);
        loadStock(symbol, container, status);
    });

    loadStock(initial, container, status);
}
