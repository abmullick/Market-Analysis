const PAGE_SIZE = 40;
let stocks = [];
let page = 1;
let installed = false;
let capBandsPromise = null;

function esc(v) {
  return String(v ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function sectors() {
  const s = document.getElementById("stock-sector");
  return [...(s?.selectedOptions || [])].map((o) => o.value).filter(Boolean);
}

function ctx() {
  return {
    sectors: sectors(),
    caps: [...document.querySelectorAll("#stock-cap-filter input:checked")].map((x) => x.value),
    query: (document.getElementById("stock-filter-search")?.value || "").trim().toLowerCase(),
  };
}

function capKey(s) {
  if (s?.market_cap_band) return s.market_cap_band;
  const n = Number(s?.market_cap_cr);
  if (!Number.isFinite(n)) return null;
  if (n >= 100000) return "large";
  if (n >= 20000) return "mid";
  if (n >= 5000) return "small";
  return "micro";
}

function filtered() {
  const f = ctx();
  return stocks.filter((s) => {
    if (f.sectors.length && !f.sectors.includes(String(s.sector || ""))) return false;
    if (f.caps.length && !f.caps.includes(capKey(s))) return false;
    if (f.query && !`${s.name || ""} ${s.symbol || ""}`.toLowerCase().includes(f.query)) return false;
    return true;
  });
}

function row(s) {
  const c = capKey(s);
  const label = c === "large" ? "Large Cap" : c === "mid" ? "Mid Cap" : c === "small" ? "Small Cap" : c === "micro" ? "Micro Cap" : "";
  return `<div class="stock-picker-row" data-symbol="${esc(s.symbol)}"><div><strong>${esc(s.name)}${label ? ` <span class="stock-cap-badge ${c}">${label}</span>` : ""}</strong><small>${esc(s.symbol)}</small></div><div class="stock-picker-metrics"><span>Market Cap <b>${s.market_cap_cr == null ? "—" : `₹${Number(s.market_cap_cr).toLocaleString("en-IN", { maximumFractionDigits: 0 })} Cr`}</b></span><span>Sector <b>${esc(s.sector || "—")}</b></span></div><button class="stock-select-btn" type="button">Select</button></div>`;
}

function render() {
  const screen = document.getElementById("stock-selection-screen");
  if (!screen || !stocks.length) return;

  const result = filtered();
  const pages = Math.max(1, Math.ceil(result.length / PAGE_SIZE));
  page = Math.min(page, pages);
  const start = (page - 1) * PAGE_SIZE;

  let list = screen.querySelector(".stock-picker-list");
  if (!list) {
    const panel = screen.querySelector(".stock-picker-panel");
    if (!panel) return;
    const summary = document.createElement("div");
    summary.className = "stock-result-summary";
    list = document.createElement("div");
    list.className = "stock-picker-list";
    panel.append(summary, list);
  }

  list.innerHTML = result.slice(start, start + PAGE_SIZE).map(row).join("") || `<div class="stock-no-data">No stocks match the current selection.</div>`;
  const summary = screen.querySelector(".stock-result-summary");
  if (summary) summary.innerHTML = `<strong>${result.length}</strong> stock${result.length === 1 ? "" : "s"} match the current selection${ctx().query ? ` · search: “${esc(ctx().query)}”` : ""}.`;

  const count = document.getElementById("stock-filter-toggle-count");
  if (count) count.textContent = `${result.length} stocks`;

  list.querySelectorAll(".stock-select-btn").forEach((b) =>
    b.addEventListener("click", () => {
      const s = b.closest(".stock-picker-row")?.dataset.symbol;
      if (s) window.location.href = `?symbol=${encodeURIComponent(s)}`;
    }),
  );

  screen.querySelector(".stock-filter-controller-pagination")?.remove();
  if (pages > 1) {
    const p = document.createElement("div");
    p.className = "stock-client-pagination stock-filter-controller-pagination";
    p.innerHTML = `<span>Showing ${start + 1}–${Math.min(start + PAGE_SIZE, result.length)} of ${result.length}</span><div class="stock-client-pagination-controls"><button type="button" data-page="${page - 1}" ${page <= 1 ? "disabled" : ""}>‹</button><span>${page} / ${pages}</span><button type="button" data-page="${page + 1}" ${page >= pages ? "disabled" : ""}>›</button></div>`;
    list.insertAdjacentElement("afterend", p);
    p.querySelectorAll("[data-page]").forEach((b) =>
      b.addEventListener("click", () => {
        if (!b.disabled) {
          page = Number(b.dataset.page);
          render();
        }
      }),
    );
  }
}

async function loadCaps() {
  if (capBandsPromise) return capBandsPromise;
  capBandsPromise = fetch("/api/stocks/market-cap-bands", {
    headers: { Accept: "application/json" },
    cache: "no-store",
  })
    .then(async (r) => {
      const d = await r.json();
      if (!r.ok) throw new Error(d?.detail || `HTTP ${r.status}`);
      const bands = d?.bands || {};
      stocks = stocks.map((s) => ({ ...s, market_cap_band: bands[s.symbol] || null }));
      return d;
    })
    .catch((e) => {
      capBandsPromise = null;
      throw e;
    });
  return capBandsPromise;
}

function bind() {
  // Do not intercept or re-toggle the Filter Results button here.
  // stock-detail/index.js owns that button. A second document-level click
  // handler was causing the panel to open and immediately close again.

  document.addEventListener("change", async (e) => {
    const t = e.target;
    if (t?.id === "stock-sector") {
      page = 1;
      render();
      return;
    }

    if (t?.matches("#stock-cap-filter input")) {
      page = 1;
      if (t.checked) {
        try {
          await loadCaps();
        } catch (err) {
          console.warn("Market-cap classification unavailable:", err);
        }
      }
      render();
    }
  });

  document.addEventListener("input", (e) => {
    if (e.target?.id !== "stock-filter-search") return;
    page = 1;
    clearTimeout(window.__stockFilterSearchTimer);
    window.__stockFilterSearchTimer = setTimeout(render, 60);
  });
}

async function load() {
  try {
    const r = await fetch("/api/stocks/universe", {
      headers: { Accept: "application/json" },
      cache: "no-store",
    });
    const d = await r.json();
    if (!r.ok) throw new Error(d?.detail || `HTTP ${r.status}`);
    stocks = Array.isArray(d.stocks) ? d.stocks : [];
    window.__stockFilterControllerStocks = stocks;
    render();
  } catch (e) {
    console.warn("Unable to load lightweight stock universe:", e);
  }
}

function init() {
  if (installed) return;
  installed = true;
  bind();
  load();
}

if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init, { once: true });
else init();
