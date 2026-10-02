const PAGE_SIZE = 40;
let stocks = [];
let page = 1;
let installed = false;
let metricsPromise = null;
let liquidityPromise = null;
let capBandsPromise = null;

function esc(v) {
  return String(v ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");
}

function capKey(stockOrValue) {
  if (stockOrValue && typeof stockOrValue === "object" && stockOrValue.market_cap_band) {
    return stockOrValue.market_cap_band;
  }
  const n = Number(stockOrValue);
  if (!Number.isFinite(n)) return null;
  if (n >= 100000) return "large";
  if (n >= 20000) return "mid";
  if (n >= 5000) return "small";
  return "micro";
}

function selectedSectors() {
  const select = document.getElementById("stock-sector");
  return [...(select?.selectedOptions || [])].map(o => o.value).filter(Boolean);
}

function context() {
  return {
    sectors: selectedSectors(),
    caps: [...document.querySelectorAll("#stock-cap-filter input:checked")].map(x => x.value),
    liquidity: [...document.querySelectorAll("#stock-liquidity-filter input:checked")].map(x => x.value),
    query: (document.getElementById("stock-filter-search")?.value || "").trim().toLowerCase(),
  };
}

function filtered() {
  const f = context();
  return stocks.filter(s => {
    if (f.sectors.length && !f.sectors.includes(String(s.sector || ""))) return false;
    if (f.caps.length && !f.caps.includes(capKey(s))) return false;
    if (f.liquidity.length && (!s.liquidity_status || !f.liquidity.includes(s.liquidity_status))) return false;
    if (f.query) {
      const q = `${s.name || ""} ${s.symbol || ""}`.toLowerCase();
      if (!q.includes(f.query)) return false;
    }
    return true;
  });
}

function rowHtml(s) {
  const liq = s.liquidity_status || "";
  const cap = capKey(s);
  const capLabel = cap === "large" ? "Large Cap" : cap === "mid" ? "Mid Cap" : cap === "small" ? "Small Cap" : cap === "micro" ? "Micro Cap" : "";
  const liqLabel = liq === "high" ? "Highly liquid" : liq === "moderate" ? "Moderately liquid" : liq === "low" ? "Low liquidity" : liq === "illiquid" ? "Illiquid" : "Liquidity unavailable";
  const traded = Number(s.avg_daily_traded_value_3m_cr);
  const fallback = String(s.liquidity_source || "").includes("fallback");
  const tradedTitle = Number.isFinite(traded)
    ? `${fallback ? "Current traded value proxy" : "3M average daily traded value"}: ₹${traded.toLocaleString("en-IN", {maximumFractionDigits:1})} Cr/day`
    : "Liquidity data unavailable";
  return `<div class="stock-picker-row" data-symbol="${esc(s.symbol)}"><div><strong>${esc(s.name)}${capLabel ? ` <span class="stock-cap-badge ${cap}">${capLabel}</span>` : ""}</strong><small>${esc(s.symbol)}</small></div><div class="stock-picker-metrics"><span>Market Cap <b>${s.market_cap_cr == null ? "—" : `₹${Number(s.market_cap_cr).toLocaleString("en-IN", {maximumFractionDigits:0})} Cr`}</b></span><span>Sector <b>${esc(s.sector || "—")}</b></span><span class="stock-liquidity-badge ${esc(liq)}" title="${esc(tradedTitle)}"><i class="liquidity-dot ${esc(liq)}"></i>${esc(liqLabel)}</span></div><button class="stock-select-btn" type="button">Select</button></div>`;
}

function ensureListShell(screen) {
  if (!screen) return null;
  let list = screen.querySelector(".stock-picker-list");
  if (list) return list;
  const panel = screen.querySelector(".stock-picker-panel");
  if (!panel) return null;
  const summary = document.createElement("div");
  summary.className = "stock-result-summary";
  const newList = document.createElement("div");
  newList.className = "stock-picker-list";
  panel.append(summary, newList);
  return newList;
}

function updateCounts(total) {
  const toggle = document.getElementById("stock-filter-toggle-count");
  if (toggle) toggle.textContent = `${total} stocks`;
}

function render() {
  const screen = document.getElementById("stock-selection-screen");
  if (!screen || screen.hidden || !stocks.length) return;
  const list = ensureListShell(screen);
  if (!list) return;
  const result = filtered();
  const total = result.length;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  page = Math.min(page, pages);
  const start = (page - 1) * PAGE_SIZE;
  list.innerHTML = result.slice(start, start + PAGE_SIZE).map(rowHtml).join("") || `<div class="stock-no-data">No stocks match the current selection.</div>`;
  const summary = screen.querySelector(".stock-result-summary");
  if (summary) {
    const f = context();
    summary.innerHTML = `<strong>${total}</strong> stock${total === 1 ? "" : "s"} match the current filters${f.query ? ` · search: “${esc(f.query)}”` : ""}`;
  }
  updateCounts(total);
  list.querySelectorAll(".stock-select-btn").forEach(btn => btn.addEventListener("click", () => {
    const symbol = btn.closest(".stock-picker-row")?.dataset.symbol;
    if (symbol) window.location.href = `?symbol=${encodeURIComponent(symbol)}`;
  }));
  let pager = screen.querySelector(".stock-filter-controller-pagination");
  if (pager) pager.remove();
  if (pages > 1) {
    pager = document.createElement("div");
    pager.className = "stock-client-pagination stock-filter-controller-pagination";
    const buttons = [];
    const first = Math.max(1, Math.min(page - 2, pages - 4));
    const last = Math.min(pages, first + 4);
    for (let p = first; p <= last; p++) buttons.push(`<button type="button" class="stock-client-page-btn ${p === page ? "active" : ""}" data-filter-page="${p}">${p}</button>`);
    pager.innerHTML = `<span>Showing ${total ? start + 1 : 0}–${Math.min(start + PAGE_SIZE, total)} of ${total}</span><div class="stock-client-pagination-controls"><button type="button" class="stock-client-page-btn" data-filter-page="${page - 1}" ${page <= 1 ? "disabled" : ""}>‹</button>${buttons.join("")}<button type="button" class="stock-client-page-btn" data-filter-page="${page + 1}" ${page >= pages ? "disabled" : ""}>›</button></div>`;
    list.insertAdjacentElement("afterend", pager);
    pager.querySelectorAll("[data-filter-page]").forEach(b => b.addEventListener("click", () => { if (!b.disabled) { page = Number(b.dataset.filterPage); render(); } }));
  }
}

function mergeStocks(extra) {
  const bySymbol = new Map(stocks.map(s => [s.symbol, s]));
  for (const s of extra || []) bySymbol.set(s.symbol, {...(bySymbol.get(s.symbol) || {}), ...s});
  stocks = [...bySymbol.values()];
}

function loadCapBands() {
  if (capBandsPromise) return capBandsPromise;
  capBandsPromise = fetch("/api/stocks/market-cap-bands", {headers:{Accept:"application/json"}, cache:"no-store"})
    .then(async r => {
      const d = await r.json();
      if (!r.ok) throw new Error(d?.detail || `HTTP ${r.status}`);
      const bands = d?.bands || {};
      stocks = stocks.map(s => ({...s, market_cap_band: bands[s.symbol] || null}));
      return d;
    })
    .catch(e => { capBandsPromise = null; throw e; });
  return capBandsPromise;
}

function loadMetrics() {
  if (metricsPromise) return metricsPromise;
  metricsPromise = fetch("/api/stocks/universe?include_metrics=true", {headers:{Accept:"application/json"}, cache:"no-store"})
    .then(async r => { const d = await r.json(); if (!r.ok) throw new Error(d?.detail || `HTTP ${r.status}`); mergeStocks(d.stocks); return d; })
    .catch(e => { metricsPromise = null; throw e; });
  return metricsPromise;
}

function loadLiquidity() {
  if (liquidityPromise) return liquidityPromise;
  liquidityPromise = fetch("/api/stocks/universe?include_metrics=true&include_liquidity=true", {headers:{Accept:"application/json"}, cache:"no-store"})
    .then(async r => { const d = await r.json(); if (!r.ok) throw new Error(d?.detail || `HTTP ${r.status}`); mergeStocks(d.stocks); return d; })
    .catch(e => { liquidityPromise = null; throw e; });
  return liquidityPromise;
}

async function applyAsyncData(kind) {
  const before = stocks.length;
  try {
    if (kind === "cap") await loadCapBands();
    else if (kind === "liquidity") await loadLiquidity();
    else await loadMetrics();
  } catch (e) {
    console.warn(`Unable to load ${kind} stock data:`, e);
    // Never turn a valid 755-stock universe into an apparent zero-result
    // state just because an optional enrichment endpoint failed.
    if (before) {
      const screen = document.getElementById("stock-selection-screen");
      const notice = document.createElement("div");
      notice.className = "stock-filter-data-warning";
      notice.textContent = `${kind === "cap" ? "Market-cap" : "Liquidity"} data is temporarily unavailable; the base stock list is unchanged.`;
      screen?.querySelector(".stock-filter-controls")?.prepend(notice);
    }
  }
  page = 1;
  render();
}

function stopCoreSectorHandler() {
  document.addEventListener("change", event => {
    if (event.target?.id !== "stock-sector") return;
    event.stopPropagation();
    event.stopImmediatePropagation();
    page = 1;
    setTimeout(render, 0);
  }, true);
}

function bindFilters() {
  document.addEventListener("change", event => {
    const t = event.target;
    if (t?.matches("#stock-cap-filter input")) {
      event.stopPropagation(); event.stopImmediatePropagation(); page = 1;
      if (t.checked) applyAsyncData("cap"); else render();
    }
    if (t?.matches("#stock-liquidity-filter input")) {
      event.stopPropagation(); event.stopImmediatePropagation(); page = 1;
      if (t.checked) { render(); applyAsyncData("liquidity"); } else render();
    }
  }, true);
  document.addEventListener("input", event => {
    if (event.target?.id !== "stock-filter-search") return;
    page = 1;
    clearTimeout(window.__stockFilterControllerTimer);
    window.__stockFilterControllerTimer = setTimeout(render, 60);
  }, true);
}

async function loadBasicUniverse() {
  try {
    const r = await fetch("/api/stocks/universe", {headers:{Accept:"application/json"}, cache:"no-store"});
    const data = await r.json();
    if (!r.ok) throw new Error(data?.detail || `HTTP ${r.status}`);
    stocks = Array.isArray(data.stocks) ? data.stocks : [];
    window.__stockFilterControllerStocks = stocks;
    render();
  } catch (e) {
    console.warn("Unable to load the lightweight stock universe:", e);
  }
}

function init() {
  if (installed) return;
  installed = true;
  stopCoreSectorHandler();
  bindFilters();
  loadBasicUniverse();
}

if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init, {once:true});
else init();
