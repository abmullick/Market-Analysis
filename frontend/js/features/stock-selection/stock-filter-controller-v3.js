const STOCK_FILTER_PAGE_SIZE = 40;
let stockFilterStocks = [];
let stockFilterPage = 1;
let stockFilterInstalled = false;
let stockCapBandsPromise = null;

function sfEsc(v) {
  return String(v ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");
}

function sfSelectedSectors() {
  const select = document.getElementById("stock-sector");
  return [...(select?.selectedOptions || [])].map(o => String(o.value || "").trim()).filter(Boolean);
}

function sfContext() {
  return {
    sectors: sfSelectedSectors(),
    caps: [...document.querySelectorAll("#stock-cap-filter input:checked")].map(x => String(x.value || "").trim().toLowerCase()),
    query: (document.getElementById("stock-filter-search")?.value || "").trim().toLowerCase(),
  };
}

function sfCapKey(stock) {
  const supplied = String(stock?.market_cap_band || "").trim().toLowerCase();
  if (["large", "mid", "small", "micro"].includes(supplied)) return supplied;
  const n = Number(stock?.market_cap_cr);
  if (!Number.isFinite(n)) return null;
  if (n >= 100000) return "large";
  if (n >= 20000) return "mid";
  if (n >= 5000) return "small";
  return "micro";
}

function sfFiltered() {
  const f = sfContext();
  return stockFilterStocks.filter(s => {
    const sector = String(s.sector || "").trim();
    if (f.sectors.length && !f.sectors.includes(sector)) return false;
    if (f.caps.length && !f.caps.includes(sfCapKey(s))) return false;
    if (f.query) {
      const q = `${s.name || ""} ${s.symbol || ""}`.toLowerCase();
      if (!q.includes(f.query)) return false;
    }
    return true;
  });
}

function sfRow(s) {
  const cap = sfCapKey(s);
  const capLabel = cap === "large" ? "Large Cap" : cap === "mid" ? "Mid Cap" : cap === "small" ? "Small Cap" : cap === "micro" ? "Micro Cap" : "";
  return `<div class="stock-picker-row" data-symbol="${sfEsc(s.symbol)}">
    <div><strong>${sfEsc(s.name)}${capLabel ? ` <span class="stock-cap-badge ${cap}">${capLabel}</span>` : ""}</strong><small>${sfEsc(s.symbol)}</small></div>
    <div class="stock-picker-metrics">
      <span>Market Cap <b>${s.market_cap_cr == null ? "—" : `₹${Number(s.market_cap_cr).toLocaleString("en-IN", {maximumFractionDigits:0})} Cr`}</b></span>
      <span>Sector <b>${sfEsc(s.sector || "—")}</b></span>
    </div>
    <button class="stock-select-btn" type="button">Select</button>
  </div>`;
}

function sfEnsureShell(screen) {
  let list = screen?.querySelector(".stock-picker-list");
  if (list) return list;
  const panel = screen?.querySelector(".stock-picker-panel");
  if (!panel) return null;
  const summary = document.createElement("div");
  summary.className = "stock-result-summary";
  list = document.createElement("div");
  list.className = "stock-picker-list";
  panel.append(summary, list);
  return list;
}

function sfMoveQuickFiltersOutsideCollapse() {
  const card = document.querySelector("#stock-selection-screen .stock-filter-card");
  const body = card?.querySelector("#stock-filter-body");
  const top = card?.querySelector(".stock-filter-top");
  const toggle = card?.querySelector("#stock-filter-toggle");
  if (!card || !body || !top || !toggle) return;
  if (top.parentElement !== card) card.insertBefore(top, toggle);
  const extra = top.querySelector(".stock-universe-extra-filters");
  if (extra) extra.style.display = "block";
}

function sfRender() {
  const screen = document.getElementById("stock-selection-screen");
  if (!screen || !stockFilterStocks.length) return;
  sfMoveQuickFiltersOutsideCollapse();
  const result = sfFiltered();
  const pages = Math.max(1, Math.ceil(result.length / STOCK_FILTER_PAGE_SIZE));
  stockFilterPage = Math.min(stockFilterPage, pages);
  const start = (stockFilterPage - 1) * STOCK_FILTER_PAGE_SIZE;
  const list = sfEnsureShell(screen);
  if (!list) return;

  list.innerHTML = result.slice(start, start + STOCK_FILTER_PAGE_SIZE).map(sfRow).join("") || `<div class="stock-no-data">No stocks match the current selection.</div>`;
  const summary = screen.querySelector(".stock-result-summary");
  if (summary) summary.innerHTML = `<strong>${result.length}</strong> stock${result.length === 1 ? "" : "s"} match the current selection${sfContext().query ? ` · search: “${sfEsc(sfContext().query)}”` : ""}.`;
  const count = document.getElementById("stock-filter-toggle-count");
  if (count) count.textContent = `${result.length} stocks`;

  // Selecting a stock is deliberately different from analyzing it. The
  // stock-detail module owns selectedStock and the left-side Selected Stock
  // card. Do not navigate here; its handler runs first and updates that state.
  // The separate compare auto-add module also observes this click and adds the
  // symbol to Compare Stocks.

  screen.querySelector(".stock-filter-controller-pagination")?.remove();
  if (pages > 1) {
    const pager = document.createElement("div");
    pager.className = "stock-client-pagination stock-filter-controller-pagination";
    pager.innerHTML = `<span>Showing ${start + 1}–${Math.min(start + STOCK_FILTER_PAGE_SIZE, result.length)} of ${result.length}</span><div class="stock-client-pagination-controls"><button type="button" data-page="${stockFilterPage - 1}" ${stockFilterPage <= 1 ? "disabled" : ""}>‹</button><span>${stockFilterPage} / ${pages}</span><button type="button" data-page="${stockFilterPage + 1}" ${stockFilterPage >= pages ? "disabled" : ""}>›</button></div>`;
    list.insertAdjacentElement("afterend", pager);
    pager.querySelectorAll("[data-page]").forEach(b => b.addEventListener("click", () => {
      if (!b.disabled) {
        stockFilterPage = Number(b.dataset.page);
        sfRender();
      }
    }));
  }
}

async function sfLoadCapBands() {
  if (stockCapBandsPromise) return stockCapBandsPromise;
  stockCapBandsPromise = fetch("/api/stocks/market-cap-bands", { headers: { Accept: "application/json" }, cache: "no-store" })
    .then(async r => {
      const d = await r.json();
      if (!r.ok) throw new Error(d?.detail || `HTTP ${r.status}`);
      const bands = d?.bands || {};
      stockFilterStocks = stockFilterStocks.map(s => ({ ...s, market_cap_band: bands[s.symbol] || null }));
      return d;
    })
    .catch(e => {
      stockCapBandsPromise = null;
      throw e;
    });
  return stockCapBandsPromise;
}

function sfBindEvents() {
  document.addEventListener("change", async event => {
    const t = event.target;
    if (t?.id === "stock-sector") {
      event.stopPropagation();
      event.stopImmediatePropagation();
      stockFilterPage = 1;
      sfRender();
      return;
    }
    if (t?.matches("#stock-cap-filter input")) {
      event.stopPropagation();
      event.stopImmediatePropagation();
      stockFilterPage = 1;
      if (t.checked) {
        try { await sfLoadCapBands(); } catch (e) { console.warn("Market-cap classification unavailable:", e); }
      }
      sfRender();
    }
  }, true);

  document.addEventListener("input", event => {
    if (event.target?.id !== "stock-filter-search") return;
    stockFilterPage = 1;
    clearTimeout(window.__stockFilterSearchTimer);
    window.__stockFilterSearchTimer = setTimeout(sfRender, 60);
  }, true);
}

async function sfLoadUniverse() {
  try {
    const r = await fetch("/api/stocks/universe", { headers: { Accept: "application/json" }, cache: "no-store" });
    const data = await r.json();
    if (!r.ok) throw new Error(data?.detail || `HTTP ${r.status}`);
    stockFilterStocks = Array.isArray(data.stocks) ? data.stocks : [];
    window.__stockFilterControllerStocks = stockFilterStocks;
    sfRender();
  } catch (e) {
    console.warn("Unable to load lightweight stock universe:", e);
  }
}

function sfInstall() {
  if (stockFilterInstalled) return;
  stockFilterInstalled = true;
  sfBindEvents();
  sfLoadUniverse();
}

if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", sfInstall, { once: true });
else sfInstall();
