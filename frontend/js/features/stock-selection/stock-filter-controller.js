const PAGE_SIZE = 40;
const CAP_KEYS = new Set(["large", "mid", "small", "micro"]);
const LIQ_KEYS = new Set(["high", "moderate", "low", "illiquid"]);
let stocks = [];
let page = 1;
let installed = false;
let loading = false;

function esc(v) {
  return String(v ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function capKey(value) {
  const n = Number(value);
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
    if (f.caps.length && !f.caps.includes(capKey(s.market_cap_cr))) return false;
    if (f.liquidity.length) {
      if (!s.liquidity_status || !f.liquidity.includes(s.liquidity_status)) return false;
    }
    if (f.query) {
      const q = `${s.name || ""} ${s.symbol || ""}`.toLowerCase();
      if (!q.includes(f.query)) return false;
    }
    return true;
  });
}

function rowHtml(s) {
  const liq = s.liquidity_status || "";
  const cap = capKey(s.market_cap_cr);
  const capLabel = cap === "large" ? "Large Cap" : cap === "mid" ? "Mid Cap" : cap === "small" ? "Small Cap" : cap === "micro" ? "Micro Cap" : "";
  const liqLabel = liq === "high" ? "Highly liquid" : liq === "moderate" ? "Moderately liquid" : liq === "low" ? "Low liquidity" : liq === "illiquid" ? "Illiquid" : "Liquidity unavailable";
  const traded = Number(s.avg_daily_traded_value_3m_cr);
  const tradedTitle = Number.isFinite(traded) ? `3M average daily traded value: ₹${traded.toLocaleString("en-IN", {maximumFractionDigits:1})} Cr/day` : "Liquidity data unavailable";

  return `<div class="stock-picker-row" data-symbol="${esc(s.symbol)}">
    <div><strong>${esc(s.name)}${capLabel ? ` <span class="stock-cap-badge ${cap}">${capLabel}</span>` : ""}</strong><small>${esc(s.symbol)}</small></div>
    <div class="stock-picker-metrics">
      <span>Market Cap <b>${s.market_cap_cr == null ? "—" : `₹${Number(s.market_cap_cr).toLocaleString("en-IN", {maximumFractionDigits:0})} Cr`}</b></span>
      <span>Sector <b>${esc(s.sector || "—")}</b></span>
      <span class="stock-liquidity-badge ${esc(liq)}" title="${esc(tradedTitle)}"><i class="liquidity-dot ${esc(liq)}"></i>${esc(liqLabel)}</span>
    </div>
    <button class="stock-select-btn" type="button">Select</button>
  </div>`;
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
  document.querySelectorAll(".stock-filter-footer span:last-child").forEach(el => { el.textContent = `${total} stocks`; });
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
    if (t?.matches("#stock-cap-filter input, #stock-liquidity-filter input")) {
      event.stopPropagation();
      event.stopImmediatePropagation();
      page = 1;
      render();
    }
  }, true);
  document.addEventListener("input", event => {
    if (event.target?.id !== "stock-filter-search") return;
    page = 1;
    clearTimeout(window.__stockFilterControllerTimer);
    window.__stockFilterControllerTimer = setTimeout(render, 60);
  }, true);
}

async function load() {
  if (loading) return;
  loading = true;
  try {
    // Do not request liquidity here. The previous implementation requested
    // the full 755-stock metric universe a second time and made Ctrl+R appear
    // to hang. Liquidity is added to the same universe payload when available.
    const r = await fetch("/api/stocks/universe?include_metrics=true", { headers: {Accept:"application/json"}, cache:"no-store" });
    const data = await r.json();
    if (!r.ok) throw new Error(data?.detail || `HTTP ${r.status}`);
    stocks = Array.isArray(data.stocks) ? data.stocks : [];
    window.__stockFilterControllerStocks = stocks;
    render();
  } catch (e) {
    console.warn("Stock filter controller could not load the universe:", e);
  } finally {
    loading = false;
  }
}

function init() {
  if (installed) return;
  installed = true;
  stopCoreSectorHandler();
  bindFilters();

  const screen = document.getElementById("stock-selection-screen");
  if (screen) {
    new MutationObserver(() => {
      if (stocks.length && screen.querySelector(".stock-picker-panel")) {
        window.clearTimeout(window.__stockFilterRenderTimer);
        window.__stockFilterRenderTimer = window.setTimeout(render, 25);
      }
    }).observe(screen, {childList:true, subtree:true});
  }
  load();
}

if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init, {once:true});
else init();
