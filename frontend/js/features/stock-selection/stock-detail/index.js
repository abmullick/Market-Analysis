const API_BASE = "/api/stocks";

const GROUPS = [
  {
    title: "Valuation",
    metrics: [
      ["pe", "P/E", "ratio"],
      ["forward_pe", "Forward P/E", "ratio"],
      ["pb", "Price / Book", "ratio"],
      ["ps", "Price / Sales", "ratio"],
      ["peg", "PEG", "ratio"],
      ["ev_ebitda", "EV / EBITDA", "ratio"],
      ["ev_revenue", "EV / Revenue", "ratio"],
      ["dividend_yield", "Dividend Yield", "percent"],
      ["payout_ratio", "Payout Ratio", "percent"],
    ],
  },
  {
    title: "Profitability",
    metrics: [
      ["roe", "ROE", "percent"],
      ["roa", "ROA", "percent"],
      ["gross_margin", "Gross Margin", "percent"],
      ["operating_margin", "Operating Margin", "percent"],
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

const FILTERS = [
  ["min_market_cap_cr", "Market Cap Min", "stock-min-mcap", "number", "₹ Cr"],
  ["max_market_cap_cr", "Market Cap Max", "stock-max-mcap", "number", "₹ Cr"],
  ["min_pe", "P/E Min", "stock-min-pe", "number", ""],
  ["max_pe", "P/E Max", "stock-max-pe", "number", ""],
  ["min_pb", "P/B Min", "stock-min-pb", "number", ""],
  ["max_pb", "P/B Max", "stock-max-pb", "number", ""],
  ["min_peg", "PEG Min", "stock-min-peg", "number", ""],
  ["max_peg", "PEG Max", "stock-max-peg", "number", ""],
  ["min_roe", "ROE Min", "stock-min-roe", "number", "%"],
  ["max_roe", "ROE Max", "stock-max-roe", "number", "%"],
  ["min_roa", "ROA Min", "stock-min-roa", "number", "%"],
  ["max_roa", "ROA Max", "stock-max-roa", "number", "%"],
  ["min_debt_equity", "D/E Min", "stock-min-de", "number", ""],
  ["max_debt_equity", "D/E Max", "stock-max-de", "number", ""],
  ["min_current_ratio", "Current Ratio Min", "stock-min-current", "number", ""],
  ["max_current_ratio", "Current Ratio Max", "stock-max-current", "number", ""],
  ["min_ev_ebitda", "EV/EBITDA Min", "stock-min-ev-ebitda", "number", ""],
  ["max_ev_ebitda", "EV/EBITDA Max", "stock-max-ev-ebitda", "number", ""],
  ["min_ev_revenue", "EV/Revenue Min", "stock-min-ev-revenue", "number", ""],
  ["max_ev_revenue", "EV/Revenue Max", "stock-max-ev-revenue", "number", ""],
  ["min_dividend_yield", "Dividend Yield Min", "stock-min-dividend", "number", "%"],
  ["max_dividend_yield", "Dividend Yield Max", "stock-max-dividend", "number", "%"],
];

let financialDisplayMode = "international";
let selectedStock = null;
let universeStocks = [];
let universeSectors = [];
let selectionRequestId = 0;

const val = (id) => document.getElementById(id)?.value ?? "";

function esc(v) {
  return String(v ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function fmtNumber(v, d = 2) {
  return Number(v).toLocaleString("en-IN", {
    maximumFractionDigits: d,
    minimumFractionDigits: 0,
  });
}

function fmtPercent(v, m = 1) {
  return v == null || !Number.isFinite(Number(v))
    ? "—"
    : `${fmtNumber(Number(v) * m, 2)}%`;
}

function fmtRatio(v) {
  return v == null || !Number.isFinite(Number(v))
    ? "—"
    : `${fmtNumber(Number(v), 2)}x`;
}

function fmtCompact(v, c = "") {
  if (v == null || !Number.isFinite(Number(v))) return "—";
  const n = Number(v);
  const p = c === "INR" ? "₹" : c === "USD" ? "$" : c ? `${c} ` : "";
  const a = Math.abs(n);

  if (a >= 1e12) return `${p}${fmtNumber(n / 1e12)}T`;
  if (a >= 1e9) return `${p}${fmtNumber(n / 1e9)}B`;
  if (a >= 1e6) return `${p}${fmtNumber(n / 1e6)}M`;
  if (a >= 1e3) return `${p}${fmtNumber(n / 1e3)}K`;
  return `${p}${fmtNumber(n)}`;
}

function fmtFinancial(v, c = "") {
  if (v == null || !Number.isFinite(Number(v))) return "—";
  return financialDisplayMode === "indian" && c === "INR"
    ? `₹${fmtNumber(Number(v) / 1e7)} Cr`
    : fmtCompact(v, c);
}

function fmtPrice(v, c = "") {
  if (v == null || !Number.isFinite(Number(v))) return "—";
  const p = c === "INR" ? "₹" : c === "USD" ? "$" : c ? `${c} ` : "";
  return `${p}${fmtNumber(v)}`;
}

function metricValue(k, v, t) {
  if (v == null) return "—";
  if (t === "percent") return fmtPercent(v);
  if (t === "percent_decimal") return fmtPercent(v, 100);
  if (t === "ratio") return fmtRatio(v);
  if (t === "pp") return `${fmtNumber(v)} pp`;
  if (t === "text") return String(v);
  return fmtNumber(v);
}

function metricCard(k, l, v, t) {
  const d = metricValue(k, v, t);
  const cls =
    Number(v) > 0 && ["percent", "percent_decimal", "pp"].includes(t)
      ? "metric-positive"
      : Number(v) < 0 && ["percent", "percent_decimal", "pp"].includes(t)
        ? "metric-negative"
        : "";

  return `<div class="stock-metric-card">
    <span class="stock-metric-label">${esc(l)}</span>
    <strong class="stock-metric-value ${cls}">${esc(d)}</strong>
  </div>`;
}

function renderGroup(g, f) {
  const pegNote =
    g.title === "Valuation" &&
    f.peg != null &&
    f.pe != null &&
    f.eps_cagr_3y != null &&
    f.eps_cagr_3y > 0
      ? `<div class="stock-metric-note">
          PEG is calculated as P/E ÷ 3Y EPS CAGR:
          ${fmtNumber(f.pe)} ÷ ${fmtPercent(f.eps_cagr_3y, 100)}
          = ${fmtRatio(f.peg)}
        </div>`
      : "";

  return `<section class="stock-section">
    <div class="stock-section-header"><h2>${esc(g.title)}</h2></div>
    <div class="stock-metrics-grid">
      ${g.metrics.map(([k, l, t]) => metricCard(k, l, f[k], t)).join("")}
    </div>
    ${pegNote}
  </section>`;
}

function renderCompany(f) {
  const c = f.currency || "";

  return `<section class="stock-hero">
    <div>
      <div class="stock-eyebrow">${esc(f.exchange || "")} · ${esc(f.symbol || "")}</div>
      <h1>${esc(f.name || f.symbol || "")}</h1>
      <p>${esc(f.sector || "")}${f.industry ? ` · ${esc(f.industry)}` : ""}${f.country ? ` · ${esc(f.country)}` : ""}</p>
    </div>
    <div class="stock-price-block">
      <strong>${esc(fmtPrice(f.price, c))}</strong>
      <span>${esc(c)}</span>
    </div>
  </section>
  <section class="stock-summary-grid">
    ${metricCard("market_cap", "Market Cap", fmtFinancial(f.market_cap, c), "text")}
    ${metricCard("enterprise_value", "Enterprise Value", fmtFinancial(f.enterprise_value, c), "text")}
    ${metricCard("revenue", "Latest Revenue", fmtFinancial(f.revenue, c), "text")}
    ${metricCard("net_profit", "Latest Net Profit", fmtFinancial(f.net_profit, c), "text")}
    ${metricCard("ebitda", "Latest EBITDA", fmtFinancial(f.ebitda, c), "text")}
    ${metricCard("free_cash_flow", "Latest Free Cash Flow", fmtFinancial(f.free_cash_flow, c), "text")}
  </section>`;
}

function statementTable(title, rows, c) {
  if (!rows?.length) {
    return `<section class="stock-section">
      <div class="stock-section-header"><h2>${esc(title)}</h2></div>
      <div class="stock-no-data">No historical data available.</div>
    </section>`;
  }

  const fields = [...new Set(rows.flatMap((r) => Object.keys(r.values || {})))];

  return `<section class="stock-section">
    <div class="stock-section-header"><h2>${esc(title)}</h2><span>Annual</span></div>
    <div class="stock-table-wrap">
      <table class="stock-table">
        <thead><tr><th>Metric</th>${rows.map((r) => `<th>${esc(r.period.slice(0, 4))}</th>`).join("")}</tr></thead>
        <tbody>
          ${fields.map((f) =>
            `<tr><td>${esc(f.replace(/([a-z])([A-Z])/g, "$1 $2"))}</td>${rows
              .map((r) => `<td>${esc(f.toLowerCase().includes("eps") ? fmtNumber(r.values?.[f]) : fmtFinancial(r.values?.[f], c))}</td>`)
              .join("")}</tr>`
          ).join("")}
        </tbody>
      </table>
    </div>
  </section>`;
}

function renderAnalysis(data, container) {
  const f = data.fundamentals || {};
  const indian = f.currency === "INR";

  if (!indian) financialDisplayMode = "international";

  container.innerHTML =
    `${renderCompany(f)}${GROUPS.map((g) => renderGroup(g, f)).join("")}` +
    `<section class="stock-section">
      <div class="stock-section-header">
        <h2>Financial Statements</h2>
        <div class="stock-display-controls">
          <span>Display:</span>
          <label class="stock-unit-toggle">
            <input type="radio" name="stock-financial-unit" value="international" ${financialDisplayMode === "international" ? "checked" : ""}>
            <span>B / T</span>
          </label>
          <label class="stock-unit-toggle ${indian ? "" : "disabled"}">
            <input type="radio" name="stock-financial-unit" value="indian" ${financialDisplayMode === "indian" ? "checked" : ""} ${indian ? "" : "disabled"}>
            <span>₹ Cr</span>
          </label>
        </div>
      </div>
      <div class="stock-statement-tabs">
        <button class="stock-tab active" data-tab="income">Income Statement</button>
        <button class="stock-tab" data-tab="balance">Balance Sheet</button>
        <button class="stock-tab" data-tab="cash">Cash Flow</button>
      </div>
      <div id="stock-statement-content">${statementTable("Income Statement", data.income_statement, f.currency || "")}</div>
    </section>
    <section class="stock-section stock-warnings">
      <div class="stock-section-header"><h2>Data Notes</h2></div>
      <ul>${(data.warnings || []).map((w) => `<li>${esc(w)}</li>`).join("")}</ul>
      <small>Data as of ${esc(f.data_as_of || "—")} · Source: ${esc(f.source || "—")}</small>
    </section>`;

  const content = document.getElementById("stock-statement-content");

  container.querySelectorAll(".stock-tab").forEach((t) =>
    t.addEventListener("click", () => {
      container.querySelectorAll(".stock-tab").forEach((x) => x.classList.remove("active"));
      t.classList.add("active");
      const k = t.dataset.tab;
      content.innerHTML = statementTable(
        k === "income" ? "Income Statement" : k === "balance" ? "Balance Sheet" : "Cash Flow",
        k === "income" ? data.income_statement : k === "balance" ? data.balance_sheet : data.cash_flow,
        f.currency || "",
      );
    }),
  );

  container.querySelectorAll('input[name="stock-financial-unit"]').forEach((i) =>
    i.addEventListener("change", () => {
      financialDisplayMode = i.value;
      renderAnalysis(data, container);
    }),
  );
}

async function loadStock(symbol, container, status) {
  status.textContent = `Loading ${symbol}…`;
  container.innerHTML = `<div class="stock-loading">Loading ${esc(symbol)} fundamentals…</div>`;

  try {
    const r = await fetch(`${API_BASE}/${encodeURIComponent(symbol)}`, {
      headers: { Accept: "application/json" },
    });

    const d = await r.json();

    if (!r.ok) throw new Error(d?.detail || `HTTP ${r.status}`);

    renderAnalysis(d, container);
    status.textContent = "";
  } catch (e) {
    container.innerHTML = `<div class="stock-error"><h2>Unable to load ${esc(symbol)}</h2><p>${esc(e.message)}</p></div>`;
    status.textContent = "";
  }
}

function filters() {
  const out = {
    sector: val("stock-sector"),
    query: val("stock-filter-search").trim(),
  };

  FILTERS.forEach(([key, , id]) => {
    out[key] = val(id);
  });

  return out;
}

function hasFundamentalFilters(f) {
  return FILTERS.some(([key]) => f[key] !== "");
}

function clientSectorData() {
  const f = filters();
  const q = f.query.toLowerCase();

  let stocks = universeStocks.filter((s) => !f.sector || s.sector === f.sector);

  if (q) {
    stocks = stocks.filter(
      (s) =>
        String(s.symbol || "").toLowerCase().includes(q) ||
        String(s.name || "").toLowerCase().includes(q),
    );
  }

  return {
    sector: f.sector,
    stocks,
    count: stocks.length,
    sectors: universeSectors,
    universe: "Nifty Total Market",
    classification_source: "NSE Indices / Nifty Total Market constituent CSV",
  };
}

function stockRow(s) {
  return `<div class="stock-picker-row ${selectedStock?.symbol === s.symbol ? "selected" : ""}" data-symbol="${esc(s.symbol)}">
    <div>
      <strong>${esc(s.name)}</strong>
      <small>${esc(s.symbol)}</small>
    </div>
    <div class="stock-picker-metrics">
      <span>Market Cap <b>${s.market_cap_cr == null ? "—" : `₹${fmtNumber(s.market_cap_cr, 0)} Cr`}</b></span>
      <span>P/E <b>${s.pe == null ? "—" : `${fmtNumber(s.pe)}x`}</b></span>
      <span>P/B <b>${s.pb == null ? "—" : `${fmtNumber(s.pb)}x`}</b></span>
      <span>ROE <b>${s.roe == null ? "—" : `${fmtNumber(s.roe)}%`}</b></span>
      <span>ROA <b>${s.roa == null ? "—" : `${fmtNumber(s.roa)}%`}</b></span>
      <span>PEG <b>${s.peg == null ? "—" : `${fmtNumber(s.peg)}x`}</b></span>
    </div>
    <button class="stock-select-btn" type="button">${selectedStock?.symbol === s.symbol ? "Selected" : "Select"}</button>
  </div>`;
}

function renderFilterField([key, label, id, type, suffix]) {
  const current = val(id);

  return `<label>
    ${esc(label)}
    <div class="stock-filter-input-wrap">
      <input id="${esc(id)}" type="${type}" min="0" step="0.1" value="${esc(current)}">
      ${suffix ? `<span>${esc(suffix)}</span>` : ""}
    </div>
  </label>`;
}

function renderSelection(data, screen, notice = "") {
  const f = filters();
  const sectors = (data.sectors || universeSectors)
    .map(
      (s) =>
        `<option value="${esc(s)}" ${s === f.sector ? "selected" : ""}>${esc(s)}</option>`,
    )
    .join("");

  const rows = (data.stocks || []).map(stockRow).join("");
  const matchCount = data.count ?? data.stocks?.length ?? 0;
  const activeFilterCount = FILTERS.filter(([, , id]) => val(id) !== "").length + (f.query ? 1 : 0);

  const filterGroups = [
    {
      title: "Valuation",
      keys: [
        "min_market_cap_cr", "max_market_cap_cr",
        "min_pe", "max_pe",
        "min_pb", "max_pb",
        "min_peg", "max_peg",
        "min_ev_ebitda", "max_ev_ebitda",
        "min_ev_revenue", "max_ev_revenue",
      ],
    },
    {
      title: "Profitability",
      keys: ["min_roe", "max_roe", "min_roa", "max_roa"],
    },
    {
      title: "Financial Health",
      keys: [
        "min_debt_equity", "max_debt_equity",
        "min_current_ratio", "max_current_ratio",
      ],
    },
    {
      title: "Income / Shareholder Return",
      keys: ["min_dividend_yield", "max_dividend_yield"],
    },
  ];

  const filterMap = new Map(FILTERS.map((item) => [item[0], item]));

  const filterHtml = filterGroups
    .map(
      (group) =>
        `<div class="stock-filter-group">
          <h3>${esc(group.title)}</h3>
          <div class="stock-filter-group-grid">
            ${group.keys.map((key) => renderFilterField(filterMap.get(key))).join("")}
          </div>
        </div>`,
    )
    .join("");

  screen.innerHTML = `<div class="stock-selection-layout">
    <aside class="stock-selected-panel">
      <div class="stock-selection-kicker">SELECTED STOCK</div>
      ${selectedStock
        ? `<div class="stock-selected-card">
            <strong>${esc(selectedStock.name)}</strong>
            <small>${esc(selectedStock.symbol)}</small>
            <span>${esc(selectedStock.sector || "")}</span>
          </div>`
        : `<div class="stock-no-selection">No stock selected</div>`}
      <button id="stock-analyze-selected" class="stock-analyze-btn" type="button" ${selectedStock ? "" : "disabled"}>Analyze Stock</button>
      <small>${selectedStock ? "One stock selected." : "Select one stock from the list."}</small>
    </aside>

    <section class="stock-picker-panel">
      <div class="stock-filter-card">
        <button id="stock-filter-toggle" class="stock-filter-toggle" type="button" aria-expanded="false" aria-controls="stock-filter-body">
          <span class="stock-filter-toggle-icon" aria-hidden="true">▸</span>
          <span class="stock-filter-toggle-label">Filter Results</span>
          <span id="stock-filter-toggle-count" class="stock-filter-toggle-count">${matchCount} stocks${activeFilterCount ? ` · ${activeFilterCount} filter${activeFilterCount === 1 ? "" : "s"} active` : ""}</span>
        </button>

        <div id="stock-filter-body" class="stock-filter-body" hidden>
          <div class="stock-filter-top">
            <label>
              SECTOR
              <select id="stock-sector">
                <option value="">All sectors</option>
                ${sectors}
              </select>
            </label>

            <label>
              SEARCH
              <input id="stock-filter-search" value="${esc(f.query)}" placeholder="Search company or symbol…">
            </label>
          </div>

          <div class="stock-filter-groups">
            ${filterHtml}
          </div>

          <div class="stock-filter-actions">
            <button id="stock-apply-filters" class="stock-page-btn" type="button">Apply Filters</button>
            <button id="stock-clear-filters" class="stock-page-btn stock-secondary-btn" type="button">Clear Filters</button>
          </div>

          <div class="stock-filter-footer">
            <span>Fundamental filters are applied when you click <strong>Apply Filters</strong>.</span>
            <span>${matchCount} stocks</span>
          </div>
        </div>
      </div>

      ${f.sector
        ? `<div class="stock-result-summary">
            ${matchCount} stocks match the current filters.
            ${notice ? esc(notice) : ""}
          </div>
          <div class="stock-picker-list">
            ${rows || `<div class="stock-no-data">No stocks match these filters.</div>`}
          </div>`
        : `<div class="stock-selection-instruction">
            Choose a sector first, then refine the list using the fundamental filters.
          </div>`}
    </section>
  </div>`;

  const toggle = document.getElementById("stock-filter-toggle");
  const body = document.getElementById("stock-filter-body");
  const apply = document.getElementById("stock-apply-filters");
  const clear = document.getElementById("stock-clear-filters");
  const sector = document.getElementById("stock-sector");
  const analyze = document.getElementById("stock-analyze-selected");

  toggle.addEventListener("click", () => {
    const open = toggle.getAttribute("aria-expanded") === "true";
    toggle.setAttribute("aria-expanded", String(!open));
    toggle.querySelector(".stock-filter-toggle-icon").textContent = open ? "▸" : "▾";
    body.hidden = open;
  });

  apply.addEventListener("click", () => loadUniverse(screen, { forceServer: true }));

  clear.addEventListener("click", () => {
    selectedStock = null;

    FILTERS.forEach(([, , id]) => {
      const el = document.getElementById(id);
      if (el) el.value = "";
    });

    const search = document.getElementById("stock-filter-search");
    if (search) search.value = "";

    if (universeStocks.length) {
      renderSelection(clientSectorData(), screen);
    } else {
      loadUniverse(screen, { forceServer: true });
    }
  });

  sector.addEventListener("change", () => {
    selectedStock = null;

    if (universeStocks.length) {
      renderSelection(clientSectorData(), screen);
    } else {
      loadUniverse(screen);
    }
  });

  analyze.addEventListener("click", () => {
    if (selectedStock) showAnalysis(selectedStock.symbol);
  });

  screen.querySelectorAll(".stock-select-btn").forEach((b) =>
    b.addEventListener("click", () => {
      selectedStock =
        (data.stocks || []).find(
          (s) => s.symbol === b.closest(".stock-picker-row").dataset.symbol,
        ) || null;

      renderSelection(data, screen, notice);
    }),
  );
}

async function loadUniverse(screen, { background = false, forceServer = false } = {}) {
  const f = filters();

  if (!f.sector && !forceServer) {
    screen.innerHTML = `<div class="stock-loading">Loading stock universe…</div>`;
  } else if (f.sector && background) {
    selectionRequestId += 1;
  } else {
    screen.innerHTML = `<div class="stock-loading">Loading stocks…</div>`;
  }

  const requestId = selectionRequestId;
  const p = new URLSearchParams();

  Object.entries(f).forEach(([k, v]) => {
    if (v !== "") p.set(k, v);
  });

  try {
    const r = await fetch(`${API_BASE}/universe?${p}`, {
      headers: { Accept: "application/json" },
      cache: "no-store",
    });

    const d = await r.json();

    if (!r.ok) throw new Error(d?.detail || `HTTP ${r.status}`);

    if (!f.sector && !hasFundamentalFilters(f) && !f.query) {
      universeStocks = d.stocks || [];
      universeSectors = d.sectors || [];
    }

    if (background && requestId !== selectionRequestId) return;

    renderSelection(d, screen);
  } catch (e) {
    if (universeStocks.length && f.sector) {
      renderSelection(clientSectorData(), screen, "Live screening is unavailable; showing the cached NSE universe.");
      return;
    }

    screen.innerHTML = `<div class="stock-error">
      <h2>Unable to load stock selection</h2>
      <p>${esc(e.message)}</p>
      <button class="stock-page-btn" id="stock-retry">Retry</button>
    </div>`;

    document.getElementById("stock-retry")?.addEventListener("click", () => loadUniverse(screen));
  }
}

function showAnalysis(symbol) {
  document.getElementById("stock-selection-screen").hidden = true;
  document.getElementById("stock-analysis-screen").hidden = false;
  history.pushState({}, "", `?symbol=${encodeURIComponent(symbol)}`);

  loadStock(
    symbol,
    document.getElementById("stock-details"),
    document.getElementById("stock-analysis-status"),
  );
}

function showSelection() {
  const analysis = document.getElementById("stock-analysis-screen");
  const s = document.getElementById("stock-selection-screen");
  if (!analysis || !s) return;

  // Reset the actual module state instead of only hiding the analysis screen.
  // This keeps the selection page clean on every device and avoids stale stock
  // details when the user selects another company.
  selectedStock = null;
  const details = document.getElementById("stock-details");
  const status = document.getElementById("stock-analysis-status");
  if (details) details.replaceChildren();
  if (status) status.textContent = "";

  analysis.hidden = true;
  s.hidden = false;
  history.replaceState({}, "", location.pathname);
  window.scrollTo(0, 0);
  loadUniverse(s);
}

export function initStockAnalysis() {
  const s = document.getElementById("stock-selection-screen");
  if (!s) return;

  document.getElementById("stock-back-to-selection")?.addEventListener("click", (event) => {
    event.preventDefault();
    showSelection();
  });

  const symbol = (new URLSearchParams(location.search).get("symbol") || "").trim().toUpperCase();

  addEventListener("popstate", () => {
    const x = new URLSearchParams(location.search).get("symbol");
    x ? showAnalysis(x.toUpperCase()) : showSelection();
  });

  symbol ? showAnalysis(symbol) : loadUniverse(s);
}
