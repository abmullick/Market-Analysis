import { buildFundamentalSignals } from "/js/features/stock-selection/stock-fundamental-signals.js";

const STORAGE_KEY = "market-analysis-stock-portfolio-v1";
const API_BASE = "/api/stocks";

let analysisToken = 0;

const esc = (value) => String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");

function num(value) {
    const n = Number(value);
    return Number.isFinite(n) ? n : null;
}

function fmt(value, digits = 1) {
    const n = num(value);
    return n == null ? "—" : n.toLocaleString("en-IN", { maximumFractionDigits: digits });
}

function pct(value, digits = 1) {
    const n = num(value);
    return n == null ? "—" : `${fmt(n, digits)}%`;
}

function ratio(value) {
    const n = num(value);
    return n == null ? "—" : `${fmt(n, 2)}x`;
}

function weighted(rows, key) {
    let total = 0;
    let weight = 0;
    rows.forEach(row => {
        const value = num(row.data?.fundamentals?.[key]);
        const allocation = num(row.allocation) || 0;
        if (value != null && allocation > 0) {
            total += value * allocation;
            weight += allocation;
        }
    });
    return weight ? total / weight : null;
}

function weightedCoverage(rows, key) {
    let weight = 0;
    rows.forEach(row => {
        if (num(row.data?.fundamentals?.[key]) != null) weight += num(row.allocation) || 0;
    });
    return weight;
}

function allocationRows(rows) {
    const groups = new Map();
    rows.forEach(row => {
        const sector = String(row.data?.fundamentals?.sector || row.universe?.sector || "Other");
        groups.set(sector, (groups.get(sector) || 0) + (num(row.allocation) || 0));
    });
    return [...groups.entries()].sort((a, b) => b[1] - a[1]);
}

function signalFor(data) {
    const signals = buildFundamentalSignals(data || {});
    const positive = signals.positive || [];
    const watch = signals.watch || [];
    if (watch.length && !positive.length) return { label: "Watch", cls: "watch", detail: watch[0] };
    if (positive.length && !watch.length) return { label: "Positive", cls: "positive", detail: positive[0] };
    if (positive.length || watch.length) return { label: "Mixed", cls: "mixed", detail: watch[0] || positive[0] };
    return { label: "Limited data", cls: "neutral", detail: "No directional signal available" };
}

function metricCard(label, value, note = "") {
    return `<div class="stock-metric-card portfolio-analysis-metric"><span class="stock-metric-label">${esc(label)}</span><strong class="stock-metric-value">${esc(value)}</strong>${note ? `<small class="portfolio-metric-note">${esc(note)}</small>` : ""}</div>`;
}

function renderAllocation(rows) {
    const max = rows[0]?.[1] || 1;
    return `<section class="stock-section portfolio-analysis-section">
        <div class="stock-section-header"><h2>Sector Allocation</h2><span>${rows.length} sector${rows.length === 1 ? "" : "s"}</span></div>
        <div class="portfolio-sector-bars">
            ${rows.map(([sector, allocation]) => `<div class="portfolio-sector-row">
                <div class="portfolio-sector-label"><span>${esc(sector)}</span><strong>${pct(allocation, 1)}</strong></div>
                <div class="portfolio-sector-track"><span style="width:${Math.max(2, allocation / max * 100)}%"></span></div>
            </div>`).join("")}
        </div>
    </section>`;
}

function renderHoldingTable(rows) {
    return `<section class="stock-section portfolio-analysis-section">
        <div class="stock-section-header"><h2>Holding Analysis</h2><span>Allocation-weighted portfolio view</span></div>
        <div class="stock-table-wrap portfolio-analysis-table-wrap">
            <table class="stock-table portfolio-analysis-table">
                <thead><tr><th>Stock</th><th>Allocation</th><th>P/E</th><th>ROE</th><th>Revenue Growth</th><th>D/E</th><th>Signal</th></tr></thead>
                <tbody>${rows.map(row => {
                    const f = row.data?.fundamentals || {};
                    const signal = signalFor(row.data);
                    return `<tr>
                        <td><strong>${esc(f.name || row.universe?.name || row.symbol)}</strong><small>${esc(row.symbol)}${f.sector ? ` · ${esc(f.sector)}` : ""}</small></td>
                        <td><strong>${pct(row.allocation, 1)}</strong></td>
                        <td>${ratio(f.pe)}</td>
                        <td>${pct(f.roe)}</td>
                        <td>${pct(f.revenue_growth)}</td>
                        <td>${ratio(f.debt_equity)}</td>
                        <td><span class="portfolio-signal ${signal.cls}">${esc(signal.label)}</span><small>${esc(signal.detail)}</small></td>
                    </tr>`;
                }).join("")}</tbody>
            </table>
        </div>
    </section>`;
}

function renderSummary(rows) {
    const sectorRows = allocationRows(rows);
    const largest = [...rows].sort((a, b) => (b.allocation || 0) - (a.allocation || 0))[0];
    const fLargest = largest?.data?.fundamentals || largest?.universe || {};
    const largestName = fLargest.name || largest?.symbol || "—";
    const coverage = weightedCoverage(rows, "pe");
    const weightedPe = weighted(rows, "pe");
    const weightedRoe = weighted(rows, "roe");
    const weightedRoce = weighted(rows, "roce");
    const weightedRevenueGrowth = weighted(rows, "revenue_growth");
    const weightedProfitGrowth = weighted(rows, "profit_growth");
    const weightedDebtEquity = weighted(rows, "debt_equity");
    const weightedPb = weighted(rows, "pb");
    const weightedEbitda = weighted(rows, "ev_ebitda");
    const weightedDividend = weighted(rows, "dividend_yield");
    const concentration = rows.reduce((sum, row) => sum + Math.pow((num(row.allocation) || 0) / 100, 2), 0);

    return `<section class="stock-hero portfolio-analysis-hero">
        <div><div class="stock-eyebrow">PORTFOLIO ANALYSIS · ${rows.length} HOLDINGS</div><h1>Your Stock Portfolio</h1><p>Fundamental quality, valuation, growth and concentration based on your current allocations.</p></div>
        <div class="portfolio-analysis-total"><strong>100%</strong><span>Allocated</span></div>
    </section>
    <section class="stock-summary-grid portfolio-summary-grid">
        ${metricCard("Holdings", String(rows.length))}
        ${metricCard("Largest Position", pct(largest?.allocation, 1), largestName)}
        ${metricCard("Sectors", String(sectorRows.length))}
        ${metricCard("Concentration", pct(concentration * 100, 1), concentration >= 0.25 ? "High single-name concentration" : "Based on HHI")}
    </section>
    <section class="stock-section portfolio-analysis-section">
        <div class="stock-section-header"><h2>Portfolio Quality</h2><span>Allocation-weighted</span></div>
        <div class="stock-metrics-grid">
            ${metricCard("ROE", pct(weightedRoe), `Coverage ${pct(weightedCoverage(rows, "roe"))}`)}
            ${metricCard("ROCE", pct(weightedRoce), `Coverage ${pct(weightedCoverage(rows, "roce"))}`)}
            ${metricCard("Revenue Growth", pct(weightedRevenueGrowth), `Coverage ${pct(weightedCoverage(rows, "revenue_growth"))}`)}
            ${metricCard("Profit Growth", pct(weightedProfitGrowth), `Coverage ${pct(weightedCoverage(rows, "profit_growth"))}`)}
            ${metricCard("Debt / Equity", ratio(weightedDebtEquity), `Coverage ${pct(weightedCoverage(rows, "debt_equity"))}`)}
        </div>
    </section>
    <section class="stock-section portfolio-analysis-section">
        <div class="stock-section-header"><h2>Portfolio Valuation</h2><span>Allocation-weighted · not a portfolio P/E</span></div>
        <div class="stock-metrics-grid">
            ${metricCard("P/E", ratio(weightedPe), `Coverage ${pct(coverage)}`)}
            ${metricCard("P/B", ratio(weightedPb), `Coverage ${pct(weightedCoverage(rows, "pb"))}`)}
            ${metricCard("EV / EBITDA", ratio(weightedEbitda), `Coverage ${pct(weightedCoverage(rows, "ev_ebitda"))}`)}
            ${metricCard("Dividend Yield", pct(weightedDividend), `Coverage ${pct(weightedCoverage(rows, "dividend_yield"))}`)}
        </div>
        <div class="portfolio-analysis-note">Ratios are weighted by portfolio allocation. They are exposure indicators rather than a mathematically aggregated portfolio valuation multiple.</div>
    </section>
    ${renderAllocation(sectorRows)}
    ${renderHoldingTable(rows)}
    <section class="stock-section portfolio-analysis-section">
        <div class="stock-section-header"><h2>Data Notes</h2></div>
        <ul class="portfolio-data-notes">
            <li>Metrics reuse the same stock fundamentals endpoint and calculations used by Stock Analysis.</li>
            <li>Coverage shows the percentage of portfolio allocation for which a metric is available.</li>
            <li>Financial-sector holdings can have a different valuation lens; EV/EBITDA is not equally informative for banks and other financial companies.</li>
        </ul>
    </section>`;
}

function renderError(container, errors) {
    container.innerHTML = `<section class="stock-section portfolio-analysis-section portfolio-analysis-error"><div class="stock-section-header"><h2>Portfolio Analysis</h2></div><p>Some holdings could not be loaded.</p><small>${esc(errors.join(" · "))}</small><button id="portfolio-analysis-retry" class="stock-analyze-btn" type="button">Retry Analysis</button></section>`;
    document.getElementById("portfolio-analysis-retry")?.addEventListener("click", () => showAnalysis(container));
}

async function showAnalysis(container) {
    const token = ++analysisToken;
    let holdings = [];
    try {
        const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
        if (Array.isArray(saved)) holdings = saved
            .map(item => ({ symbol: String(item?.symbol || "").trim().toUpperCase(), allocation: num(item?.allocation) || 0 }))
            .filter(item => item.symbol && item.allocation > 0);
    } catch (_) {}

    if (!holdings.length) {
        container.innerHTML = `<section class="stock-section"><div class="stock-section-header"><h2>No portfolio selected</h2></div><p>Add stocks and allocations first.</p></section>`;
        return;
    }

    container.innerHTML = `<section class="stock-section portfolio-analysis-loading"><div class="stock-loading">Loading portfolio fundamentals…</div><p>Using the same Stock Analysis data and calculation engine for each holding.</p></section>`;

    const results = await Promise.all(holdings.map(async holding => {
        try {
            const response = await fetch(`${API_BASE}/${encodeURIComponent(holding.symbol)}`, { headers: { Accept: "application/json" }, cache: "no-store" });
            const data = await response.json();
            if (!response.ok) throw new Error(data?.detail || `HTTP ${response.status}`);
            return { ...holding, data };
        } catch (error) {
            return { ...holding, error: error?.message || "Unable to load" };
        }
    }));

    if (token !== analysisToken) return;
    const good = results.filter(row => row.data);
    const errors = results.filter(row => row.error).map(row => `${row.symbol}: ${row.error}`);
    if (!good.length) {
        renderError(container, errors);
        return;
    }

    container.innerHTML = renderSummary(good);
    if (errors.length) {
        const note = document.createElement("div");
        note.className = "portfolio-partial-warning";
        note.textContent = `${errors.length} holding${errors.length === 1 ? "" : "s"} could not be loaded and is excluded from the analysis. ${errors.join(" · ")}`;
        container.prepend(note);
    }
}

export function initStockPortfolioAnalysis() {
    const builder = document.getElementById("stock-portfolio-builder-content");
    const analysis = document.getElementById("stock-portfolio-analysis-content");
    const continueButton = document.getElementById("portfolio-continue");
    const backButton = document.getElementById("portfolio-analysis-back");
    if (!builder || !analysis || !continueButton || !backButton) return;

    continueButton.addEventListener("click", event => {
        event.preventDefault();
        if (continueButton.disabled) return;
        builder.hidden = true;
        analysis.hidden = false;
        window.scrollTo({ top: 0, behavior: "smooth" });
        showAnalysis(analysis);
    });

    backButton.addEventListener("click", () => {
        analysis.hidden = true;
        builder.hidden = false;
        window.scrollTo({ top: 0, behavior: "smooth" });
    });
}
