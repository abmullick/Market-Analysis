import { buildFundamentalSignals } from "/js/features/stock-selection/stock-fundamental-signals.js";

const STORAGE_KEY = "market-analysis-stock-portfolio-v1";
const API_BASE = "/api/stocks";
let analysisToken = 0;
let performanceCharts = [];

const esc = (value) => String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");
function num(value) { const n = Number(value); return Number.isFinite(n) ? n : null; }
function fmt(value, digits = 1) { const n = num(value); return n == null ? "—" : n.toLocaleString("en-IN", { maximumFractionDigits: digits }); }
function pct(value, digits = 1) { const n = num(value); return n == null ? "—" : `${fmt(n, digits)}%`; }
function ratio(value) { const n = num(value); return n == null ? "—" : `${fmt(n, 2)}x`; }
function weighted(rows, key) { let total = 0, weight = 0; rows.forEach(row => { const value = num(row.data?.fundamentals?.[key]); const allocation = num(row.allocation) || 0; if (value != null && allocation > 0) { total += value * allocation; weight += allocation; } }); return weight ? total / weight : null; }
function weightedCoverage(rows, key) { return rows.reduce((weight, row) => num(row.data?.fundamentals?.[key]) != null ? weight + (num(row.allocation) || 0) : weight, 0); }
function allocationRows(rows) { const groups = new Map(); rows.forEach(row => { const sector = String(row.data?.fundamentals?.sector || "Other"); groups.set(sector, (groups.get(sector) || 0) + (num(row.allocation) || 0)); }); return [...groups.entries()].sort((a, b) => b[1] - a[1]); }

function fallbackFundamentalSignals(data) {
    const f = data?.fundamentals || {}, positive = [], watch = [], roe = num(f.roe), roce = num(f.roce), revenueGrowth = num(f.revenue_growth), profitGrowth = num(f.profit_growth), debtEquity = num(f.debt_equity), pe = num(f.pe);
    if (roe != null) { if (roe >= 15) positive.push("ROE is healthy"); else if (roe < 10) watch.push("ROE is weak"); }
    if (roce != null) { if (roce >= 15) positive.push("ROCE is healthy"); else if (roce < 10) watch.push("ROCE is weak"); }
    if (revenueGrowth != null) { if (revenueGrowth >= 10) positive.push("Revenue growth is strong"); else if (revenueGrowth < 0) watch.push("Revenue is declining"); }
    if (profitGrowth != null) { if (profitGrowth >= 10) positive.push("Profit growth is strong"); else if (profitGrowth < 0) watch.push("Profit is declining"); }
    if (debtEquity != null) { if (debtEquity <= 0.5) positive.push("Debt/Equity is low"); else if (debtEquity > 1.5) watch.push("Debt/Equity is high"); }
    if (pe != null && pe > 50) watch.push("Valuation is elevated");
    return { positive, watch };
}
function signalFor(data) {
    const engine = buildFundamentalSignals(data || {}), positive = [...(engine.positive || [])], watch = [...(engine.watch || [])];
    if (!positive.length && !watch.length) { const fallback = fallbackFundamentalSignals(data); positive.push(...fallback.positive); watch.push(...fallback.watch); }
    if (watch.length && !positive.length) return { label: "Watch", cls: "watch", detail: watch.slice(0, 2).join(" · ") };
    if (positive.length && !watch.length) return { label: "Positive", cls: "positive", detail: positive.slice(0, 2).join(" · ") };
    if (positive.length || watch.length) return { label: "Mixed", cls: "mixed", detail: [...positive.slice(0, 1), ...watch.slice(0, 1)].join(" · ") };
    return { label: "No signal", cls: "neutral", detail: "Insufficient fundamental data for a directional signal" };
}
function metricCard(label, value, note = "") { return `<div class="stock-metric-card portfolio-analysis-metric"><span class="stock-metric-label">${esc(label)}</span><strong class="stock-metric-value">${esc(value)}</strong>${note ? `<small class="portfolio-metric-note">${esc(note)}</small>` : ""}</div>`; }
function renderAllocation(rows) { const max = rows[0]?.[1] || 1; return `<section class="stock-section portfolio-analysis-section"><div class="stock-section-header"><h2>Sector Allocation</h2><span>${rows.length} sector${rows.length === 1 ? "" : "s"}</span></div><div class="portfolio-sector-bars">${rows.map(([sector, allocation]) => `<div class="portfolio-sector-row"><div class="portfolio-sector-label"><span>${esc(sector)}</span><strong>${pct(allocation, 1)}</strong></div><div class="portfolio-sector-track"><span style="width:${Math.max(2, allocation / max * 100)}%"></span></div></div>`).join("")}</div></section>`; }
function renderHoldingTable(rows) { return `<section class="stock-section portfolio-analysis-section"><div class="stock-section-header"><h2>Holding Analysis</h2><span>Allocation-weighted portfolio view</span></div><div class="stock-table-wrap portfolio-analysis-table-wrap"><table class="stock-table portfolio-analysis-table"><thead><tr><th>Stock</th><th>Allocation</th><th>P/E</th><th>ROE</th><th>Revenue Growth</th><th>D/E</th><th>Signal</th></tr></thead><tbody>${rows.map(row => { const f = row.data?.fundamentals || {}, signal = signalFor(row.data); return `<tr><td><strong>${esc(f.name || row.symbol)}</strong><small>${esc(row.symbol)}${f.sector ? ` · ${esc(f.sector)}` : ""}</small></td><td><strong>${pct(row.allocation, 1)}</strong></td><td>${ratio(f.pe)}</td><td>${pct(f.roe)}</td><td>${pct(f.revenue_growth)}</td><td>${ratio(f.debt_equity)}</td><td><span class="portfolio-signal ${signal.cls}">${esc(signal.label)}</span><small>${esc(signal.detail)}</small></td></tr>`; }).join("")}</tbody></table></div></section>`; }

function performanceRows(rows, chartsBySymbol) {
    const periods = [{ key: "1Y", years: 1 }, { key: "3Y", years: 3 }, { key: "5Y", years: 5 }, { key: "10Y", years: 10 }];
    return periods.map(period => {
        const available = rows.map(row => { const series = chartsBySymbol.get(row.symbol)?.price_cagr || []; const point = series.find(item => String(item?.year || "").toUpperCase() === period.key); const cagr = num(point?.value); return cagr == null ? null : { ...row, cagr }; }).filter(Boolean);
        const coverage = available.reduce((sum, row) => sum + (num(row.allocation) || 0), 0);
        if (!available.length || coverage <= 0) return { ...period, cagr: null, coverage: 0, available };
        let growth = 0;
        available.forEach(row => { const weight = (num(row.allocation) || 0) / coverage; growth += weight * Math.pow(1 + row.cagr / 100, period.years); });
        return { ...period, cagr: (Math.pow(growth, 1 / period.years) - 1) * 100, coverage, available };
    });
}
function destroyPerformanceCharts() { performanceCharts.forEach(chart => { try { chart.destroy(); } catch (_) {} }); performanceCharts = []; }
function renderPerformance(rows, chartsBySymbol) {
    const periods = performanceRows(rows, chartsBySymbol), periodCards = periods.map(item => metricCard(item.key, pct(item.cagr, 1), item.coverage > 0 ? `Coverage ${pct(item.coverage, 0)}` : "No data")).join(""), chartId = `portfolio-performance-${Date.now()}`, detailId = `portfolio-performance-holdings-${Date.now()}`;
    const note = periods.some(item => item.cagr != null && item.coverage < 99.99) ? "Some holdings do not have a matching historical price CAGR, so the displayed result is calculated on the covered allocation only." : "Historical price CAGR is available for the full portfolio allocation.";
    return `<section class="stock-section portfolio-analysis-section portfolio-performance-section"><div class="stock-section-header"><div><h2>Portfolio Performance</h2><span>Historical price growth using your current allocation</span></div><span class="portfolio-performance-badge">CAGR</span></div><div class="stock-metrics-grid portfolio-performance-cards">${periodCards}</div><div class="portfolio-performance-visual"><div class="portfolio-performance-chart-wrap"><canvas id="${chartId}" class="portfolio-performance-chart"></canvas></div><div class="portfolio-performance-side"><div class="portfolio-performance-side-title">3Y holding view</div><div id="${detailId}" class="portfolio-performance-holding-bars"></div></div></div><div class="portfolio-analysis-note">${esc(note)} The calculation converts each holding's Screener price CAGR into a growth factor, applies the current portfolio weights, and converts the combined growth back to CAGR. It is not a transaction-level backtest and does not include dividends, taxes, costs or rebalancing.</div></section>`;
}
function drawPerformanceVisuals(rows, chartsBySymbol) {
    const canvas = document.querySelector(".portfolio-performance-chart"), periods = performanceRows(rows, chartsBySymbol).filter(item => item.cagr != null);
    if (canvas && typeof Chart !== "undefined" && periods.length) {
        performanceCharts.push(new Chart(canvas, { type: "bar", data: { labels: periods.map(item => item.key), datasets: [{ label: "Portfolio price CAGR", data: periods.map(item => item.cagr), backgroundColor: ["#0f172a", "#1e3a8a", "#2563eb", "#64748b"], borderRadius: 7, borderSkipped: false, maxBarThickness: 46 }] }, options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false }, tooltip: { callbacks: { label: ctx => ` Portfolio price CAGR: ${fmt(ctx.parsed.y, 1)}%` } } }, scales: { x: { grid: { display: false }, ticks: { color: "#475569", font: { weight: "600" } } }, y: { grid: { color: "#edf2f7" }, ticks: { color: "#64748b", callback: value => `${value}%` }, title: { display: true, text: "Annualised return", color: "#475569", font: { weight: "600" } } } } } }));
    }
    const holder = document.querySelector(".portfolio-performance-holding-bars");
    if (!holder) return;
    const threeYear = performanceRows(rows, chartsBySymbol).find(item => item.key === "3Y"), available = (threeYear?.available || []).filter(item => Number.isFinite(item.cagr)).sort((a, b) => b.cagr - a.cagr);
    if (!available.length) { holder.innerHTML = `<div class="portfolio-performance-empty">3Y holding data is not available.</div>`; return; }
    const max = Math.max(...available.map(item => Math.abs(item.cagr)), 1);
    holder.innerHTML = available.map(item => { const name = item.data?.fundamentals?.name || item.symbol, width = Math.max(3, Math.min(100, Math.abs(item.cagr) / max * 100)), cls = item.cagr < 0 ? "negative" : "positive"; return `<div class="portfolio-performance-holding"><div class="portfolio-performance-holding-label"><span>${esc(name)}</span><strong>${pct(item.cagr, 1)}</strong></div><div class="portfolio-performance-holding-track"><span class="${cls}" style="width:${width}%"></span></div><small>${pct(item.allocation, 1)} allocation</small></div>`; }).join("");
}

function renderSummary(rows, performanceMarkup = "") {
    const sectorRows = allocationRows(rows), largest = [...rows].sort((a, b) => (b.allocation || 0) - (a.allocation || 0))[0], largestName = largest?.data?.fundamentals?.name || largest?.symbol || "—";
    const weightedPe = weighted(rows, "pe"), weightedRoe = weighted(rows, "roe"), weightedRoce = weighted(rows, "roce"), weightedRevenueGrowth = weighted(rows, "revenue_growth"), weightedProfitGrowth = weighted(rows, "profit_growth"), weightedDebtEquity = weighted(rows, "debt_equity"), weightedPb = weighted(rows, "pb"), weightedEbitda = weighted(rows, "ev_ebitda"), weightedDividend = weighted(rows, "dividend_yield");
    const concentration = rows.reduce((sum, row) => sum + Math.pow((num(row.allocation) || 0) / 100, 2), 0);
    return `<section class="stock-hero portfolio-analysis-hero"><div><div class="stock-eyebrow">PORTFOLIO ANALYSIS · ${rows.length} HOLDINGS</div><h1>Your Stock Portfolio</h1><p>Fundamental quality, valuation, growth and concentration based on your current allocations.</p></div><div class="portfolio-analysis-total"><strong>100%</strong><span>Allocated</span></div></section>
<section class="stock-summary-grid portfolio-summary-grid">${metricCard("Holdings", String(rows.length))}${metricCard("Largest Position", pct(largest?.allocation, 1), largestName)}${metricCard("Sectors", String(sectorRows.length))}${metricCard("Concentration", pct(concentration * 100, 1), "Based on HHI")}</section>
<section class="stock-section portfolio-analysis-section"><div class="stock-section-header"><h2>Portfolio Quality</h2><span>Allocation-weighted</span></div><div class="stock-metrics-grid">${metricCard("ROE", pct(weightedRoe), `Coverage ${pct(weightedCoverage(rows, "roe"))}`)}${metricCard("ROCE", pct(weightedRoce), `Coverage ${pct(weightedCoverage(rows, "roce"))}`)}${metricCard("Revenue Growth", pct(weightedRevenueGrowth), `Coverage ${pct(weightedCoverage(rows, "revenue_growth"))}`)}${metricCard("Profit Growth", pct(weightedProfitGrowth), `Coverage ${pct(weightedCoverage(rows, "profit_growth"))}`)}${metricCard("Debt / Equity", ratio(weightedDebtEquity), `Coverage ${pct(weightedCoverage(rows, "debt_equity"))}`)}</div></section>
<section class="stock-section portfolio-analysis-section"><div class="stock-section-header"><h2>Portfolio Valuation</h2><span>Allocation-weighted · not a portfolio P/E</span></div><div class="stock-metrics-grid">${metricCard("P/E", ratio(weightedPe), `Coverage ${pct(weightedCoverage(rows, "pe"))}`)}${metricCard("P/B", ratio(weightedPb), `Coverage ${pct(weightedCoverage(rows, "pb"))}`)}${metricCard("EV / EBITDA", ratio(weightedEbitda), `Coverage ${pct(weightedCoverage(rows, "ev_ebitda"))}`)}${metricCard("Dividend Yield", pct(weightedDividend), `Coverage ${pct(weightedCoverage(rows, "dividend_yield"))}`)}</div><div class="portfolio-analysis-note">Ratios are weighted by portfolio allocation. They are exposure indicators rather than a mathematically aggregated portfolio valuation multiple.</div></section>
${renderAllocation(sectorRows)}${renderHoldingTable(rows)}${performanceMarkup}<section class="stock-section portfolio-analysis-section"><div class="stock-section-header"><h2>Data Notes</h2></div><ul class="portfolio-data-notes"><li>Metrics reuse the same stock fundamentals endpoint and calculations used by Stock Analysis.</li><li>Signals use the shared Stock Analysis trend engine when historical series are available, with a current-fundamentals fallback when only snapshot metrics are returned.</li><li>Coverage shows the percentage of portfolio allocation for which a metric is available.</li><li>Financial-sector holdings can have a different valuation lens; EV/EBITDA is not equally informative for financial companies.</li></ul></section>`;
}
function renderError(container, errors) { container.innerHTML = `<section class="stock-section portfolio-analysis-section portfolio-analysis-error"><div class="stock-section-header"><h2>Portfolio Analysis</h2></div><p>Some holdings could not be loaded.</p><small>${esc(errors.join(" · "))}</small><button id="portfolio-analysis-retry" class="stock-analyze-btn" type="button">Retry Analysis</button></section>`; document.getElementById("portfolio-analysis-retry")?.addEventListener("click", () => showAnalysis(container)); }

async function showAnalysis(container) {
    const token = ++analysisToken; destroyPerformanceCharts();
    let holdings = [];
    try { const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]"); if (Array.isArray(saved)) holdings = saved.map(item => ({ symbol: String(item?.symbol || "").trim().toUpperCase(), allocation: num(item?.allocation) || 0 })).filter(item => item.symbol && item.allocation > 0); } catch (_) {}
    if (!holdings.length) { container.innerHTML = `<section class="stock-section"><div class="stock-section-header"><h2>No portfolio selected</h2></div><p>Add stocks and allocations first.</p></section>`; return; }
    container.innerHTML = `<section class="stock-section portfolio-analysis-loading"><div class="stock-loading">Loading portfolio fundamentals and historical performance…</div><p>Using the same Stock Analysis data and historical price engine for each holding.</p></section>`;
    const results = await Promise.all(holdings.map(async holding => { try { const response = await fetch(`${API_BASE}/${encodeURIComponent(holding.symbol)}`, { headers: { Accept: "application/json" }, cache: "no-store" }); const data = await response.json(); if (!response.ok) throw new Error(data?.detail || `HTTP ${response.status}`); return { ...holding, data }; } catch (error) { return { ...holding, error: error?.message || "Unable to load" }; } }));
    if (token !== analysisToken) return;
    const good = results.filter(row => row.data), errors = results.filter(row => row.error).map(row => `${row.symbol}: ${row.error}`);
    if (!good.length) { renderError(container, errors); return; }
    const chartResults = await Promise.all(good.map(async row => { try { const response = await fetch(`${API_BASE}/${encodeURIComponent(row.symbol)}/charts`, { headers: { Accept: "application/json" }, cache: "no-store" }); const data = await response.json(); if (!response.ok) throw new Error(data?.detail || `HTTP ${response.status}`); return { symbol: row.symbol, charts: data?.charts || {} }; } catch (_) { return { symbol: row.symbol, charts: {} }; } }));
    if (token !== analysisToken) return;
    const chartsBySymbol = new Map(chartResults.map(item => [item.symbol, item.charts]));
    container.innerHTML = renderSummary(good, renderPerformance(good, chartsBySymbol));
    drawPerformanceVisuals(good, chartsBySymbol);
    if (errors.length) { const note = document.createElement("div"); note.className = "portfolio-partial-warning"; note.textContent = `${errors.length} holding${errors.length === 1 ? "" : "s"} could not be loaded and is excluded from the analysis. ${errors.join(" · ")}`; container.prepend(note); }
}

export function initStockPortfolioAnalysis() {
    const builder = document.getElementById("stock-portfolio-builder-content"), analysis = document.getElementById("stock-portfolio-analysis-content"), results = document.getElementById("portfolio-analysis-results"), continueButton = document.getElementById("portfolio-continue"), backButton = document.getElementById("portfolio-analysis-back");
    if (!builder || !analysis || !results || !continueButton || !backButton) return;
    continueButton.addEventListener("click", event => { event.preventDefault(); if (continueButton.disabled) return; builder.hidden = true; analysis.hidden = false; window.scrollTo({ top: 0, behavior: "smooth" }); showAnalysis(results); });
    backButton.addEventListener("click", () => { destroyPerformanceCharts(); analysis.hidden = true; builder.hidden = false; window.scrollTo({ top: 0, behavior: "smooth" }); });
}
