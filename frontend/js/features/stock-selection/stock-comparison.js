const API_BASE = "/api/stocks";

const COMPARE_GROUPS = [
  { title: "Valuation", metrics: [["price", "Price", "price"], ["market_cap", "Market Cap", "money"], ["enterprise_value", "Enterprise Value", "money"], ["pe", "P/E", "ratio"], ["forward_pe", "Forward P/E", "ratio"], ["pb", "Price / Book", "ratio"], ["ps", "Price / Sales", "ratio"], ["peg", "PEG", "ratio"], ["ev_ebitda", "EV / EBITDA", "ratio"], ["ev_revenue", "EV / Revenue", "ratio"], ["dividend_yield", "Dividend Yield", "percent"], ["payout_ratio", "Payout Ratio", "percent"]] },
  { title: "Profitability", metrics: [["roe", "ROE", "percent"], ["roa", "ROA", "percent"], ["gross_margin", "Gross Margin", "percent"], ["operating_margin", "Operating Margin", "percent"], ["profit_margin", "Net Margin", "percent"]] },
  { title: "Financial Health", metrics: [["debt_equity", "Debt / Equity", "ratio"], ["current_ratio", "Current Ratio", "ratio"], ["quick_ratio", "Quick Ratio", "ratio"], ["beta", "Beta", "number"], ["cash", "Cash", "money"], ["total_debt", "Total Debt", "money"]] },
  { title: "Growth", metrics: [["revenue_growth", "Revenue Growth", "percent"], ["profit_growth", "Profit Growth", "percent"], ["eps_growth", "EPS Growth", "percent"], ["revenue_cagr_3y", "Revenue CAGR 3Y", "decimal_percent"], ["revenue_cagr_5y", "Revenue CAGR 5Y", "decimal_percent"], ["profit_cagr_3y", "Profit CAGR 3Y", "decimal_percent"], ["profit_cagr_5y", "Profit CAGR 5Y", "decimal_percent"], ["eps_cagr_3y", "EPS CAGR 3Y", "decimal_percent"], ["eps_cagr_5y", "EPS CAGR 5Y", "decimal_percent"], ["fcf_cagr_3y", "FCF CAGR 3Y", "decimal_percent"], ["fcf_cagr_5y", "FCF CAGR 5Y", "decimal_percent"], ["operating_margin_change", "Operating Margin Change", "pp"]] },
  { title: "Latest Financials", metrics: [["revenue", "Revenue", "money"], ["operating_profit", "Operating Profit", "money"], ["ebitda", "EBITDA", "money"], ["net_profit", "Net Profit", "money"], ["eps", "EPS", "number"], ["operating_cash_flow", "Operating Cash Flow", "money"], ["capital_expenditure", "Capital Expenditure", "money"], ["free_cash_flow", "Free Cash Flow", "money"]] },
];

const LOWER_IS_BETTER = new Set([
  "pe", "forward_pe", "pb", "ps", "peg", "ev_ebitda", "ev_revenue", "debt_equity", "total_debt",
]);

const HIGHER_IS_BETTER = new Set([
  "dividend_yield", "roe", "roa", "gross_margin", "operating_margin", "profit_margin", "current_ratio", "quick_ratio",
  "revenue_growth", "profit_growth", "eps_growth", "revenue_cagr_3y", "revenue_cagr_5y", "profit_cagr_3y", "profit_cagr_5y",
  "eps_cagr_3y", "eps_cagr_5y", "operating_margin_change", "eps",
]);

const NEGATIVE_IS_BAD = new Set([
  "revenue_growth", "profit_growth", "eps_growth", "gross_margin", "operating_margin", "profit_margin",
  "roe", "roa", "revenue_cagr_3y", "revenue_cagr_5y", "profit_cagr_3y", "profit_cagr_5y",
  "eps_cagr_3y", "eps_cagr_5y", "fcf_cagr_3y", "fcf_cagr_5y", "operating_margin_change",
  "operating_profit", "ebitda", "net_profit", "eps", "operating_cash_flow", "free_cash_flow",
]);

let compareSymbols = [];
let observerStarted = false;
let renderingBar = false;

function esc(v) {
  return String(v ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");
}

function num(v, digits = 2) {
  return Number(v).toLocaleString("en-IN", { maximumFractionDigits: digits, minimumFractionDigits: 0 });
}

function value(v, type, currency = "INR") {
  if (v == null || !Number.isFinite(Number(v))) return "—";
  const n = Number(v);
  if (type === "percent" || type === "decimal_percent") return `${num(type === "decimal_percent" ? n * 100 : n)}%`;
  if (type === "ratio") return `${num(n)}x`;
  if (type === "pp") return `${num(n)} pp`;
  if (type === "price") return `${currency === "INR" ? "₹" : `${currency} `}${num(n)}`;
  if (type === "money") return currency === "INR" ? `₹${num(n / 1e7)} Cr` : `${currency} ${num(n / 1e9)} B`;
  return num(n);
}

function metricDisplay(f, key, type, currency) {
  if (key === "peg" && (f[key] == null || !Number.isFinite(Number(f[key]))) && Number(f.eps_cagr_3y) <= 0) {
    return { text: "N/M", title: "PEG is not meaningful because the 3Y EPS CAGR is zero or negative." };
  }
  if ((key === "ev_ebitda" || key === "ev_revenue") && f[key] == null && f.sector === "Financial Services") {
    return { text: "N/M", title: "Enterprise-value multiples are not meaningful for financial companies." };
  }
  return { text: value(f[key], type, currency), title: "" };
}

function comparisonState(f, key, allValues) {
  const raw = Number(f[key]);
  if (!Number.isFinite(raw)) return "neutral";

  if (NEGATIVE_IS_BAD.has(key) && raw < 0) return "negative";

  const values = allValues.filter((v) => Number.isFinite(v));
  if (values.length < 2) return "neutral";
  const other = values.find((v) => v !== raw);
  if (other == null || raw === other) return "neutral";

  if (LOWER_IS_BETTER.has(key)) return raw < Math.max(...values) && raw === Math.min(...values) ? "favorable" : "unfavorable";
  if (HIGHER_IS_BETTER.has(key)) return raw === Math.max(...values) ? "favorable" : "unfavorable";
  return "neutral";
}

function comparisonCellClass(f, key, fs) {
  const values = fs.map((x) => Number(x[key])).filter(Number.isFinite);
  const state = comparisonState(f, key, values);
  return state === "favorable" ? "compare-favorable" : state === "unfavorable" ? "compare-unfavorable" : state === "negative" ? "compare-negative" : "";
}

function injectStyles() {
  if (document.getElementById("stock-comparison-styles")) return;
  const style = document.createElement("style");
  style.id = "stock-comparison-styles";
  style.textContent = `
    .stock-compare-bar{display:flex;align-items:center;gap:12px;margin:0 0 18px;padding:14px 16px;border:1px solid var(--color-border);border-radius:var(--radius-md);background:var(--color-surface);box-shadow:var(--btn-shadow)}
    .stock-compare-bar strong{color:var(--color-primary);font-size:13px}.stock-compare-slots{display:flex;gap:8px;flex:1}.stock-compare-slot{padding:9px 12px;border:1px dashed var(--color-slate-400);border-radius:var(--radius-pill);color:var(--color-text-light);font-size:12px;min-width:130px;background:var(--color-bg)}.stock-compare-slot.filled{border-style:solid;color:var(--color-primary);background:var(--color-slate-100);font-weight:600}.stock-compare-action{margin-left:auto}.stock-compare-choice{display:inline-flex!important;flex-direction:row!important;align-items:center;gap:6px;margin-right:8px!important;color:var(--color-text-light)!important;font-size:11px!important;font-weight:700!important;white-space:nowrap}.stock-compare-choice input{width:15px!important;height:15px!important;margin:0}.stock-comparison-header{margin:8px 0 18px;padding:22px 24px;border:1px solid var(--color-border);border-radius:var(--radius-lg);background:linear-gradient(135deg,#ffffff,#f0f7ff);box-shadow:var(--btn-shadow)}.stock-comparison-header h1{margin:0 0 5px;color:var(--color-primary);font-size:1.55rem}.stock-comparison-header p{margin:0;color:var(--color-text-light);font-size:13px}.stock-comparison-table-wrap{overflow:auto;border:1px solid var(--color-border);border-radius:var(--radius-lg);background:var(--color-surface);box-shadow:0 6px 22px rgba(15,23,42,.06)}.stock-comparison-table{width:100%;border-collapse:separate;border-spacing:0;min-width:760px}.stock-comparison-table th,.stock-comparison-table td{padding:12px 14px;border-bottom:1px solid #edf1f6;text-align:right;font-size:13px;font-variant-numeric:tabular-nums}.stock-comparison-table th:first-child,.stock-comparison-table td:first-child{text-align:left;position:sticky;left:0;background:var(--color-surface);z-index:1}.stock-comparison-table thead th{background:#f1f6fc;color:var(--color-primary);font-weight:700;position:sticky;top:0;z-index:2}.stock-comparison-table thead th:first-child{z-index:3}.stock-comparison-table .compare-group td{padding:11px 14px;background:#edf4fb;color:#1e3a5f;font-weight:700;text-align:left;border-bottom:1px solid #dbe7f3;letter-spacing:.02em}.stock-comparison-table tbody tr:hover td{background:#fbfdff}.stock-comparison-table tbody tr:hover td.compare-favorable{background:#dcfce7}.stock-comparison-table tbody tr:hover td.compare-negative,.stock-comparison-table tbody tr:hover td.compare-unfavorable{background:#fee2e2}.stock-comparison-table tbody tr:last-child td{border-bottom:0}
    .stock-comparison-table td.compare-favorable{background:var(--color-green-50);color:var(--color-green-700);font-weight:700;box-shadow:inset 3px 0 0 var(--color-green-500)}.stock-comparison-table td.compare-unfavorable{background:#fff7f7;color:var(--color-text);box-shadow:inset 3px 0 0 #fca5a5}.stock-comparison-table td.compare-negative{background:var(--color-red-50);color:var(--color-red-700);font-weight:700;box-shadow:inset 3px 0 0 var(--color-red-500)}.stock-comparison-table td.compare-negative::before{content:"⚠ ";font-size:11px}.stock-comparison-table td.compare-unfavorable::before{content:""}.stock-comparison-table .compare-favorable::after{content:"✓";margin-left:6px;font-size:10px;opacity:.8}
    @media(max-width:700px){.stock-compare-bar{align-items:stretch;flex-direction:column}.stock-compare-action{width:100%}.stock-compare-slots{width:100%}.stock-compare-slot{flex:1;min-width:0}.stock-comparison-header{padding:18px}.stock-comparison-table th,.stock-comparison-table td{padding:10px 11px}}
  `;
  document.head.appendChild(style);
}

function renderCompareBar() {
  const screen = document.getElementById("stock-selection-screen");
  if (!screen || screen.hidden) return;
  let bar = document.getElementById("stock-compare-bar");
  if (!bar) {
    bar = document.createElement("div");
    bar.id = "stock-compare-bar";
    const layout = screen.querySelector(".stock-selection-layout");
    if (!layout) return;
    layout.parentElement.insertBefore(bar, layout);
  }

  renderingBar = true;
  const slots = [compareSymbols[0], compareSymbols[1]].map((s, i) =>
    `<span class="stock-compare-slot ${s ? "filled" : ""}">${s ? esc(s.replace(/\\.NS$|\\.BO$/i, "")) : `Stock ${i + 1}`}</span>`,
  ).join("");
  bar.innerHTML = `<strong>Compare stocks</strong><div class="stock-compare-slots">${slots}</div><button class="stock-compare-action btn btn-primary" type="button" ${compareSymbols.length !== 2 ? "disabled" : ""}>Compare 2 Stocks</button>`;
  bar.querySelector("button").addEventListener("click", () => showComparison(compareSymbols));
  queueMicrotask(() => { renderingBar = false; });
}

function decorateRows() {
  if (renderingBar) return;
  const rows = document.querySelectorAll("#stock-selection-screen .stock-picker-row");
  if (!rows.length) return;

  rows.forEach((row) => {
    if (row.dataset.compareReady === "1") {
      const checkbox = row.querySelector(".stock-compare-choice input");
      if (checkbox) checkbox.checked = compareSymbols.includes(row.dataset.symbol);
      return;
    }
    row.dataset.compareReady = "1";
    const symbol = row.dataset.symbol;
    const select = row.querySelector(".stock-select-btn");
    if (!select) return;

    const label = document.createElement("label");
    label.className = "stock-compare-choice";
    label.innerHTML = `<input type="checkbox" aria-label="Compare ${esc(symbol)}"><span>Compare</span>`;
    label.querySelector("input").checked = compareSymbols.includes(symbol);
    label.querySelector("input").addEventListener("click", (event) => event.stopPropagation());
    label.querySelector("input").addEventListener("change", (event) => {
      if (event.target.checked) {
        if (compareSymbols.length >= 2) {
          event.target.checked = false;
          return;
        }
        compareSymbols = [...compareSymbols, symbol];
      } else {
        compareSymbols = compareSymbols.filter((x) => x !== symbol);
      }
      renderCompareBar();
      decorateRows();
    });
    select.parentElement.insertBefore(label, select);
  });
  renderCompareBar();
}

async function fetchStock(symbol) {
  const r = await fetch(`${API_BASE}/${encodeURIComponent(symbol)}`, { headers: { Accept: "application/json" }, cache: "no-store" });
  const d = await r.json();
  if (!r.ok) throw new Error(d?.detail || `HTTP ${r.status}`);
  return d;
}

function comparisonTable(datas) {
  const fs = datas.map((d) => d.fundamentals || {});
  const currency = fs[0]?.currency || "INR";
  let rows = "";
  for (const group of COMPARE_GROUPS) {
    rows += `<tr class="compare-group"><td colspan="${fs.length + 1}">${esc(group.title)}</td></tr>`;
    for (const [key, label, type] of group.metrics) {
      rows += `<tr><td>${esc(label)}</td>${fs.map((f) => { const d = metricDisplay(f, key, type, currency); const cls = comparisonCellClass(f, key, fs); return `<td class="${cls}"${d.title ? ` title="${esc(d.title)}"` : ""}>${esc(d.text)}</td>`; }).join("")}</tr>`;
    }
  }
  return `<div class="stock-comparison-table-wrap"><table class="stock-comparison-table"><thead><tr><th>Metric</th>${fs.map((f) => `<th>${esc(f.name || f.symbol || "Stock")}</th>`).join("")}</tr></thead><tbody>${rows}</tbody></table></div>`;
}

async function showComparison(symbols) {
  if (symbols.length !== 2) return;
  const selection = document.getElementById("stock-selection-screen");
  const analysis = document.getElementById("stock-analysis-screen");
  const details = document.getElementById("stock-details");
  const status = document.getElementById("stock-analysis-status");
  if (!selection || !analysis || !details) return;

  selection.hidden = true;
  analysis.hidden = false;
  history.pushState({}, "", `?compare=${symbols.map(encodeURIComponent).join(",")}`);
  status.textContent = "Loading comparison…";
  details.innerHTML = `<div class="stock-loading">Loading ${esc(symbols[0])} and ${esc(symbols[1])}…</div>`;

  try {
    const datas = await Promise.all(symbols.map(fetchStock));
    details.innerHTML = `<div class="stock-comparison-header"><h1>Stock Comparison</h1><p>Green marks the more favorable value for comparable metrics. Red marks negative or materially unfavorable values. ✓ and ⚠ indicate the reason for the highlight.</p></div>${comparisonTable(datas)}`;
    status.textContent = "";
  } catch (e) {
    details.innerHTML = `<div class="stock-error"><h2>Unable to load comparison</h2><p>${esc(e.message)}</p></div>`;
    status.textContent = "";
  }
}

export function initStockComparison() {
  injectStyles();
  const screen = document.getElementById("stock-selection-screen");
  if (!screen) return;

  if (!observerStarted) {
    observerStarted = true;
    const observer = new MutationObserver(() => {
      if (!renderingBar) decorateRows();
    });
    observer.observe(screen, { childList: true, subtree: true });
  }

  decorateRows();

  const params = new URLSearchParams(location.search);
  const compare = params.get("compare");
  if (compare) {
    const symbols = compare.split(",").map((x) => decodeURIComponent(x).trim().toUpperCase()).filter(Boolean).slice(0, 2);
    if (symbols.length === 2) {
      compareSymbols = symbols;
      showComparison(symbols);
    }
  }
}
