const STOCK_PAGE_SIZE = 40;

let stockUniverse = [];
let stockSelectedSymbol = null;
let stockPage = 1;
let stockRenderInProgress = false;
let stockObserverStarted = false;
let stockSearchTimer = null;

function markNegativeValues(root) {
  root.querySelectorAll(".stock-summary-grid .stock-metric-card, .stock-metrics-grid .stock-metric-card").forEach((card) => {
    const value = card.querySelector(".stock-metric-value");
    const text = value?.textContent?.trim() || "";
    card.classList.toggle("stock-negative-card", /^-/.test(text) || /₹-/.test(text) || /\$-/.test(text));
  });

  root.querySelectorAll(".stock-table td").forEach((cell) => {
    const text = cell.textContent?.trim() || "";
    cell.classList.toggle("stock-negative-cell", /^-/.test(text) || /₹-/.test(text) || /\$-/.test(text));
  });
}

function addSelectionStyles() {
  if (document.getElementById("stock-ui-enhancement-styles")) return;

  const style = document.createElement("style");
  style.id = "stock-ui-enhancement-styles";
  style.textContent = `
    .stock-compare-action { width: auto !important; min-width: 0 !important; flex: 0 0 auto !important; padding: 9px 16px !important; white-space: nowrap; }
    .stock-client-pagination { display:flex; align-items:center; justify-content:space-between; gap:12px; margin-top:14px; padding:10px 2px 0; color:var(--color-text-light,#64748b); font-size:12px; }
    .stock-client-pagination-controls { display:flex; align-items:center; gap:5px; flex-wrap:wrap; }
    .stock-client-page-btn { min-width:32px; height:32px; padding:0 9px; border:1px solid var(--color-border,#dbe4f0); border-radius:var(--radius-sm,7px); background:var(--color-surface,#fff); color:var(--color-text,#334155); font:inherit; font-weight:600; cursor:pointer; }
    .stock-client-page-btn:hover:not(:disabled) { background:var(--color-slate-100,#f1f5f9); border-color:var(--color-text-light,#94a3b8); }
    .stock-client-page-btn.active { background:var(--color-primary,#17324f); border-color:var(--color-primary,#17324f); color:#fff; }
    .stock-client-page-btn:disabled { opacity:.45; cursor:not-allowed; }
    @media (max-width:700px) { .stock-client-pagination { align-items:flex-start; flex-direction:column; } }
  `;
  document.head.appendChild(style);
}

function esc(v) {
  return String(v ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");
}

function hasFundamentalFilters() {
  return [
    "stock-min-mcap", "stock-max-mcap", "stock-min-pe", "stock-max-pe", "stock-min-pb", "stock-max-pb",
    "stock-min-peg", "stock-max-peg", "stock-min-roe", "stock-max-roe", "stock-min-roa", "stock-max-roa",
    "stock-min-de", "stock-max-de", "stock-min-current", "stock-max-current", "stock-min-ev-ebitda",
    "stock-max-ev-ebitda", "stock-min-ev-revenue", "stock-max-ev-revenue", "stock-min-dividend", "stock-max-dividend",
  ].some((id) => {
    const el = document.getElementById(id);
    return el && el.value !== "";
  });
}

function currentContext() {
  const sectorEl = document.getElementById("stock-sector");
  const sectors = sectorEl?.multiple
    ? [...(sectorEl.selectedOptions || [])].map((o) => o.value).filter(Boolean)
    : sectorEl?.value ? [sectorEl.value] : [];
  const caps = [...document.querySelectorAll("#stock-cap-filter input:checked")].map((x) => x.value);
  const liquidity = [...document.querySelectorAll("#stock-liquidity-filter input:checked")].map((x) => x.value);
  return {
    sectors,
    caps,
    liquidity,
    query: (document.getElementById("stock-filter-search")?.value || "").trim().toLowerCase(),
  };
}

function capKey(cr) {
  const n = Number(cr);
  if (!Number.isFinite(n)) return null;
  if (n >= 100000) return "large";
  if (n >= 20000) return "mid";
  if (n >= 5000) return "small";
  return "micro";
}

function filterUniverse() {
  const { sectors, caps, liquidity, query } = currentContext();
  return stockUniverse.filter((stock) => {
    if (sectors.length && !sectors.includes(stock.sector)) return false;
    if (caps.length && !caps.includes(capKey(stock.market_cap_cr))) return false;
    if (liquidity.length && !liquidity.includes(stock.liquidity_status)) return false;
    if (!query) return true;
    return String(stock.symbol || "").toLowerCase().includes(query) || String(stock.name || "").toLowerCase().includes(query);
  });
}

function stockRowHtml(stock) {
  const selected = stockSelectedSymbol === stock.symbol;
  return `<div class="stock-picker-row ${selected ? "selected" : ""}" data-symbol="${esc(stock.symbol)}" data-market-cap-cr="${stock.market_cap_cr ?? ""}">
    <div><strong>${esc(stock.name)}</strong><small>${esc(stock.symbol)}</small></div>
    <div class="stock-picker-metrics">
      <span>Market Cap <b>${stock.market_cap_cr == null ? "—" : `₹${Number(stock.market_cap_cr).toLocaleString("en-IN", { maximumFractionDigits: 0 })} Cr`}</b></span>
      <span>Sector <b>${esc(stock.sector || "—")}</b></span>
    </div>
    <button class="stock-select-btn" type="button">${selected ? "Selected" : "Select"}</button>
  </div>`;
}

function updateSelectedPanel() {
  const panel = document.querySelector(".stock-selected-panel");
  if (!panel) return;
  const stock = stockUniverse.find((s) => s.symbol === stockSelectedSymbol);
  const analyze = panel.querySelector("#stock-analyze-selected");
  const note = panel.querySelector(":scope > small");
  const existing = panel.querySelector(".stock-selected-card");
  const empty = panel.querySelector(".stock-no-selection");

  if (stock) {
    if (empty) empty.remove();
    if (existing) existing.innerHTML = `<strong>${esc(stock.name)}</strong><small>${esc(stock.symbol)}</small><span>${esc(stock.sector || "")}</span>`;
    else {
      const card = document.createElement("div");
      card.className = "stock-selected-card";
      card.innerHTML = `<strong>${esc(stock.name)}</strong><small>${esc(stock.symbol)}</small><span>${esc(stock.sector || "")}</span>`;
      panel.querySelector(".stock-selection-kicker")?.insertAdjacentElement("afterend", card);
    }
    if (analyze) analyze.disabled = false;
    if (note) note.textContent = "One stock selected.";
  } else {
    if (existing) existing.remove();
    if (!empty) {
      const emptyCard = document.createElement("div");
      emptyCard.className = "stock-no-selection";
      emptyCard.textContent = "No stock selected";
      panel.querySelector(".stock-selection-kicker")?.insertAdjacentElement("afterend", emptyCard);
    }
    if (analyze) analyze.disabled = true;
    if (note) note.textContent = "Select one stock from the list.";
  }
}

function goToAnalysis() {
  if (!stockSelectedSymbol) return;
  window.location.href = `?symbol=${encodeURIComponent(stockSelectedSymbol)}`;
}

function renderPagination(total) {
  const pages = Math.max(1, Math.ceil(total / STOCK_PAGE_SIZE));
  stockPage = Math.min(stockPage, pages);
  const start = total ? (stockPage - 1) * STOCK_PAGE_SIZE + 1 : 0;
  const end = Math.min(stockPage * STOCK_PAGE_SIZE, total);
  const maxButtons = 7;
  let first = Math.max(1, stockPage - 3);
  let last = Math.min(pages, first + maxButtons - 1);
  first = Math.max(1, last - maxButtons + 1);
  const pageButtons = [];
  for (let page = first; page <= last; page += 1) pageButtons.push(`<button class="stock-client-page-btn ${page === stockPage ? "active" : ""}" type="button" data-stock-page="${page}">${page}</button>`);
  return `<div class="stock-client-pagination"><span>Showing ${start}–${end} of ${total} stocks</span><div class="stock-client-pagination-controls"><button class="stock-client-page-btn" type="button" data-stock-page="${stockPage - 1}" ${stockPage <= 1 ? "disabled" : ""}>‹</button>${pageButtons.join("")}<button class="stock-client-page-btn" type="button" data-stock-page="${stockPage + 1}" ${stockPage >= pages ? "disabled" : ""}>›</button></div></div>`;
}

function renderClientResults(screen, force = false) {
  if (!screen || !stockUniverse.length || hasFundamentalFilters()) return false;
  const stocks = filterUniverse();
  const total = stocks.length;
  const pages = Math.max(1, Math.ceil(total / STOCK_PAGE_SIZE));
  stockPage = Math.min(stockPage, pages);
  const start = total ? (stockPage - 1) * STOCK_PAGE_SIZE : 0;
  const visible = stocks.slice(start, start + STOCK_PAGE_SIZE);
  const context = currentContext();
  const renderKey = `${context.sectors.join(",")}|${context.caps.join(",")}|${context.liquidity.join(",")}|${context.query}|${stockPage}`;
  const filterCard = screen.querySelector(".stock-filter-card");
  const panel = screen.querySelector(".stock-picker-panel");
  if (!panel || !filterCard) return false;
  stockRenderInProgress = true;

  let summary = panel.querySelector(".stock-result-summary");
  let pagination = panel.querySelector(".stock-client-pagination");
  panel.querySelector(".stock-selection-instruction")?.remove();
  if (!summary) { summary = document.createElement("div"); summary.className = "stock-result-summary"; filterCard.insertAdjacentElement("afterend", summary); }
  let list = panel.querySelector(".stock-picker-list");
  if (!list) { list = document.createElement("div"); list.className = "stock-picker-list"; summary.insertAdjacentElement("afterend", list); }
  if (!force && list.dataset.clientRenderKey === renderKey) { stockRenderInProgress = false; return true; }

  const rawQuery = document.getElementById("stock-filter-search")?.value || "";
  summary.innerHTML = `<strong>${total}</strong> stock${total === 1 ? "" : "s"} match the current filters${rawQuery ? ` · search: “${esc(rawQuery)}”` : ""}`;
  list.dataset.clientRenderKey = renderKey;
  list.innerHTML = visible.length ? visible.map(stockRowHtml).join("") : `<div class="stock-no-data">No stocks match the current selection.</div>`;
  pagination?.remove();
  const paginationWrap = document.createElement("div");
  paginationWrap.innerHTML = renderPagination(total);
  list.insertAdjacentElement("afterend", paginationWrap.firstElementChild);

  list.querySelectorAll(".stock-select-btn").forEach((button) => button.addEventListener("click", () => {
    stockSelectedSymbol = button.closest(".stock-picker-row")?.dataset.symbol || null;
    updateSelectedPanel();
    renderClientResults(screen, true);
  }));
  panel.querySelectorAll("[data-stock-page]").forEach((button) => button.addEventListener("click", () => {
    if (button.disabled) return;
    stockPage = Number(button.dataset.stockPage);
    renderClientResults(screen, true);
  }));

  updateSelectedPanel();
  stockRenderInProgress = false;
  return true;
}

function filterCurrentServerRows() {
  const screen = document.getElementById("stock-selection-screen");
  const query = currentContext().query;
  const rows = screen?.querySelectorAll(".stock-picker-list .stock-picker-row") || [];
  rows.forEach((row) => {
    const text = row.textContent.toLowerCase();
    row.hidden = Boolean(query && !text.includes(query));
  });
}

function bindSelectionControls(screen) {
  const sector = screen.querySelector("#stock-sector");
  const search = screen.querySelector("#stock-filter-search");
  const analyze = screen.querySelector("#stock-analyze-selected");
  if (!sector || !search) return;

  if (sector.dataset.uiEnhanced !== "1") {
    sector.dataset.uiEnhanced = "1";
    sector.addEventListener("change", () => {
      stockPage = 1;
      if (!hasFundamentalFilters()) setTimeout(() => renderClientResults(screen, true), 0);
    });
  }

  if (search.dataset.uiEnhanced !== "1") {
    search.dataset.uiEnhanced = "1";
    search.addEventListener("input", () => {
      clearTimeout(stockSearchTimer);
      stockSearchTimer = setTimeout(() => {
        stockPage = 1;
        if (!hasFundamentalFilters()) renderClientResults(screen, true);
        else filterCurrentServerRows();
      }, 80);
    });
  }

  ["#stock-cap-filter", "#stock-liquidity-filter"].forEach((selector) => {
    const filter = screen.querySelector(selector);
    if (filter && filter.dataset.uiEnhanced !== "1") {
      filter.dataset.uiEnhanced = "1";
      filter.addEventListener("change", () => {
        stockPage = 1;
        if (!hasFundamentalFilters()) renderClientResults(screen, true);
      });
    }
  });

  if (analyze && analyze.dataset.uiEnhanced !== "1") {
    analyze.dataset.uiEnhanced = "1";
    analyze.addEventListener("click", () => goToAnalysis(), { capture: true });
  }
}

async function loadStockUniverse() {
  try {
    const r = await fetch("/api/stocks/universe?include_metrics=true", { headers: { Accept: "application/json" }, cache: "no-store" });
    const data = await r.json();
    if (!r.ok) throw new Error(data?.detail || `HTTP ${r.status}`);
    stockUniverse = Array.isArray(data.stocks) ? data.stocks : [];
    return true;
  } catch (error) {
    console.warn("Stock universe client cache unavailable:", error);
    return false;
  }
}

function enhanceSelection() {
  const screen = document.getElementById("stock-selection-screen");
  if (!screen || screen.hidden || stockRenderInProgress) return;
  bindSelectionControls(screen);
  if (stockUniverse.length && !hasFundamentalFilters()) renderClientResults(screen);
  else if (hasFundamentalFilters()) filterCurrentServerRows();
}

function init() {
  addSelectionStyles();
  const details = document.getElementById("stock-details");
  if (details) {
    const observer = new MutationObserver(() => markNegativeValues(details));
    observer.observe(details, { childList: true, subtree: true, characterData: true });
    markNegativeValues(details);
  }
  const screen = document.getElementById("stock-selection-screen");
  if (!screen || stockObserverStarted) return;
  stockObserverStarted = true;
  loadStockUniverse().then(() => enhanceSelection());
  const observer = new MutationObserver(() => {
    if (stockRenderInProgress) return;
    window.clearTimeout(window.__stockEnhancementTimer);
    window.__stockEnhancementTimer = window.setTimeout(() => enhanceSelection(), 0);
  });
  observer.observe(screen, { childList: true, subtree: true });
}

if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init, { once: true });
else init();
