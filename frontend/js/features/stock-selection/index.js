const API_BASE = "/api/stocks/universe";

const state = { sector: "", query: "", selected: null, stocks: [], loading: false };
const $ = (id) => document.getElementById(id);

function esc(value) {
    return String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");
}
function fmtCr(value) {
    if (value == null || !Number.isFinite(Number(value))) return "—";
    return `₹${Number(value).toLocaleString("en-IN", { maximumFractionDigits: 0 })} Cr`;
}
function fmtMetric(value, suffix = "") {
    if (value == null || !Number.isFinite(Number(value))) return "—";
    return `${Number(value).toLocaleString("en-IN", { maximumFractionDigits: 2 })}${suffix}`;
}
function setStatus(text, error = false) {
    const el = $("stock-selection-status");
    if (!el) return;
    el.textContent = text || "";
    el.classList.toggle("error", error);
}
function populateSectors(sectors) {
    const select = $("stock-sector-filter");
    if (!select) return;
    select.innerHTML = '<option value="">Select a sector</option>' + sectors.map(s => `<option value="${esc(s)}">${esc(s)}</option>`).join("");
}
function filterParams() {
    const params = new URLSearchParams({ sector: state.sector });
    if (state.query.trim()) params.set("query", state.query.trim());
    const cap = $("stock-market-cap-filter")?.value || "";
    if (cap) {
        const [min, max] = cap.split("-");
        if (min) params.set("min_market_cap_cr", min);
        if (max) params.set("max_market_cap_cr", max);
    }
    const pe = $("stock-pe-filter")?.value || "";
    if (pe) params.set("max_pe", pe);
    const roe = $("stock-roe-filter")?.value || "";
    if (roe) params.set("min_roe", roe);
    return params;
}
function renderResults() {
    const container = $("stock-selection-results");
    if (!container) return;
    if (!state.sector) {
        container.innerHTML = '<div class="stock-select-empty-state"><div class="stock-select-empty-icon">⌕</div><h3>Select a sector</h3><p>The stocks belonging to that sector will appear here.</p></div>';
        return;
    }
    if (state.loading) {
        container.innerHTML = '<div class="stock-select-loading"><div class="stock-select-spinner"></div><span>Loading stocks and live fundamentals…</span></div>';
        return;
    }
    if (!state.stocks.length) {
        container.innerHTML = '<div class="stock-select-empty-state"><div class="stock-select-empty-icon">∅</div><h3>No stocks match</h3><p>Try clearing one or more filters.</p></div>';
        return;
    }
    container.innerHTML = `<div class="stock-results-heading"><strong>${state.stocks.length} stocks</strong><span>${esc(state.sector)}</span></div><div class="stock-card-list">${state.stocks.map(stock => {
        const selected = state.selected?.symbol === stock.symbol;
        return `<article class="stock-choice-card ${selected ? "selected" : ""}" data-symbol="${esc(stock.symbol)}"><div class="stock-choice-main"><h3>${esc(stock.name)}</h3><div class="stock-choice-symbol">${esc(stock.symbol)}</div><div class="stock-choice-metrics"><span>Market Cap <strong>${esc(fmtCr(stock.market_cap_cr))}</strong></span><span>P/E <strong>${esc(fmtMetric(stock.pe, "x"))}</strong></span><span>ROE <strong>${esc(fmtMetric(stock.roe, "%"))}</strong></span></div></div><button type="button" class="stock-choice-btn" data-symbol="${esc(stock.symbol)}">${selected ? "Selected" : "Select"}</button></article>`;
    }).join("")}</div>`;
    container.querySelectorAll(".stock-choice-btn").forEach(btn => btn.addEventListener("click", () => selectStock(btn.dataset.symbol)));
    container.querySelectorAll(".stock-choice-card").forEach(card => card.addEventListener("click", e => {
        if (!e.target.closest("button")) selectStock(card.dataset.symbol);
    }));
}
function selectStock(symbol) {
    state.selected = state.stocks.find(stock => stock.symbol === symbol) || null;
    renderSelected();
    renderResults();
}
function renderSelected() {
    const empty = $("stock-selected-empty");
    const card = $("stock-selected-card");
    const button = $("stock-analyze-btn");
    const hint = $("stock-analyze-hint");
    if (!empty || !card || !button) return;
    if (!state.selected) {
        empty.classList.remove("hidden"); card.classList.add("hidden"); button.disabled = true;
        if (hint) hint.textContent = "Select one stock to continue.";
        return;
    }
    empty.classList.add("hidden"); card.classList.remove("hidden");
    card.innerHTML = `<strong>${esc(state.selected.name)}</strong><span>${esc(state.selected.symbol)}</span><small>${esc(state.selected.sector)}</small>`;
    button.disabled = false;
    if (hint) hint.textContent = "One stock selected.";
}
async function loadStocks() {
    if (!state.sector) { renderResults(); return; }
    state.loading = true; setStatus("Loading live fundamentals…"); renderResults();
    try {
        const response = await fetch(`${API_BASE}?${filterParams().toString()}`, { headers: { Accept: "application/json" } });
        const data = await response.json();
        if (!response.ok) throw new Error(data?.detail || `HTTP ${response.status}`);
        state.stocks = data.stocks || []; state.loading = false;
        setStatus(`${state.stocks.length} stocks match the current filters.`);
        if (state.selected && !state.stocks.some(stock => stock.symbol === state.selected.symbol)) state.selected = null;
        renderResults(); renderSelected();
    } catch (error) {
        state.loading = false; state.stocks = []; setStatus(error.message || "Unable to load stocks.", true); renderResults();
    }
}
function wireControls() {
    $("stock-sector-filter")?.addEventListener("change", event => {
        state.sector = event.target.value; state.query = ""; state.selected = null;
        const search = $("stock-search-input");
        if (search) { search.disabled = !state.sector; search.value = ""; }
        renderSelected(); loadStocks();
    });
    $("stock-search-input")?.addEventListener("input", event => {
        state.query = event.target.value;
        clearTimeout(wireControls.searchTimer);
        wireControls.searchTimer = setTimeout(loadStocks, 350);
    });
    ["stock-market-cap-filter", "stock-pe-filter", "stock-roe-filter"].forEach(id => $(id)?.addEventListener("change", loadStocks));
    $("stock-analyze-btn")?.addEventListener("click", () => {
        if (!state.selected) return;
        const url = new URL(window.location.href); url.searchParams.set("symbol", state.selected.symbol); window.location.href = url.toString();
    });
}
async function showAnalysis(symbol) {
    const selection = document.querySelector(".stock-select-layout");
    const progress = document.querySelector(".stock-select-progress");
    const stepLabel = document.querySelector(".stock-select-step-label");
    const header = document.querySelector(".stock-select-header");
    const details = $("stock-details");
    const status = $("stock-analysis-status");
    if (!details || !selection) return;
    selection.classList.add("hidden");
    if (progress) progress.innerHTML = '<div class="stock-select-step"><span>1</span><strong>Select Stock</strong></div><div class="stock-select-connector stock-select-connector--active"></div><div class="stock-select-step stock-select-step--active"><span>2</span><strong>Analyze</strong></div>';
    if (stepLabel) stepLabel.textContent = "Step 2 of 2";
    if (header) header.innerHTML = `<div class="stock-analysis-back"><button type="button" id="stock-back-btn">← Back to Stock Selection</button></div><h1 class="mf-page-title">Stock Analysis</h1><p class="mf-page-subtitle">Fundamental analysis of ${esc(symbol)} using Yahoo Finance data.</p>`;
    details.classList.remove("hidden");
    const { loadStock } = await import("./stock-detail/index.js");
    $("stock-back-btn")?.addEventListener("click", () => { const url = new URL(window.location.href); url.searchParams.delete("symbol"); window.location.href = url.toString(); });
    await loadStock(symbol, details, status);
}
export async function initStockSelection() {
    wireControls();
    const params = new URLSearchParams(window.location.search);
    const symbol = (params.get("symbol") || "").trim().toUpperCase();
    if (symbol) { await showAnalysis(symbol); return; }
    try {
        const response = await fetch(API_BASE, { headers: { Accept: "application/json" } });
        const data = await response.json();
        if (!response.ok) throw new Error(data?.detail || `HTTP ${response.status}`);
        populateSectors(data.sectors || []);
    } catch (error) { setStatus(error.message || "Unable to load stock sectors.", true); }
    renderSelected();
    renderResults();
}
