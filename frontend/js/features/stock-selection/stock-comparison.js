const API_BASE = "/api/stocks";

const COMPARE_GROUPS = [
  { title: "Valuation", metrics: [["price", "Price", "price"], ["market_cap", "Market Cap", "money"], ["enterprise_value", "Enterprise Value", "money"], ["pe", "P/E", "ratio"], ["forward_pe", "Forward P/E", "ratio"], ["pb", "Price / Book", "ratio"], ["ps", "Price / Sales", "ratio"], ["peg", "PEG", "ratio"], ["ev_ebitda", "EV / EBITDA", "ratio"], ["ev_revenue", "EV / Revenue", "ratio"], ["dividend_yield", "Dividend Yield", "percent"], ["payout_ratio", "Payout Ratio", "percent"]] },
  { title: "Profitability", metrics: [["roe", "ROE", "percent"], ["roa", "ROA", "percent"], ["gross_margin", "Gross Margin", "percent"], ["operating_margin", "Operating Margin", "percent"], ["profit_margin", "Net Margin", "percent"]] },
  { title: "Financial Health", metrics: [["debt_equity", "Debt / Equity", "ratio"], ["current_ratio", "Current Ratio", "ratio"], ["quick_ratio", "Quick Ratio", "ratio"], ["beta", "Beta", "number"], ["cash", "Cash", "money"], ["total_debt", "Total Debt", "money"]] },
  { title: "Growth", metrics: [["revenue_growth", "Revenue Growth", "percent"], ["profit_growth", "Profit Growth", "percent"], ["eps_growth", "EPS Growth", "percent"], ["revenue_cagr_3y", "Revenue CAGR 3Y", "decimal_percent"], ["revenue_cagr_5y", "Revenue CAGR 5Y", "decimal_percent"], ["profit_cagr_3y", "Profit CAGR 3Y", "decimal_percent"], ["profit_cagr_5y", "Profit CAGR 5Y", "decimal_percent"], ["eps_cagr_3y", "EPS CAGR 3Y", "decimal_percent"], ["eps_cagr_5y", "EPS CAGR 5Y", "decimal_percent"], ["fcf_cagr_3y", "FCF CAGR 3Y", "decimal_percent"], ["fcf_cagr_5y", "FCF CAGR 5Y", "decimal_percent"], ["operating_margin_change", "Operating Margin Change", "pp"]] },
  { title: "Latest Financials", metrics: [["revenue", "Revenue", "money"], ["operating_profit", "Operating Profit", "money"], ["ebitda", "EBITDA", "money"], ["net_profit", "Net Profit", "money"], ["eps", "EPS", "number"], ["operating_cash_flow", "Operating Cash Flow", "money"], ["capital_expenditure", "Capital Expenditure", "money"], ["free_cash_flow", "Free Cash Flow", "money"]] },
];

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

function injectStyles() {
  if (document.getElementById("stock-comparison-styles")) return;
  const style = document.createElement("style");
  style.id = "stock-comparison-styles";
  style.textContent = `
    .stock-compare-bar{display:flex;align-items:center;gap:12px;margin:0 0 14px;padding:12px 14px;border:1px solid #dbe4f0;border-radius:10px;background:#fff;box-shadow:0 2px 8px rgba(15,23,42,.04)}
    .stock-compare-bar strong{color:#17324f;font-size:13px}.stock-compare-slots{display:flex;gap:6px;flex:1}.stock-compare-slot{padding:7px 10px;border:1px dashed #cbd5e1;border-radius:7px;color:#64748b;font-size:12px;min-width:120px}.stock-compare-slot.filled{border-style:solid;color:#17324f;background:#f8fafc;font-weight:600}.stock-compare-action{margin-left:auto;border:0;border-radius:7px;padding:8px 13px;background:#2876c5;color:#fff;font-weight:700;cursor:pointer}.stock-compare-action:disabled{opacity:.45;cursor:not-allowed}.stock-compare-choice{display:inline-flex!important;flex-direction:row!important;align-items:center;gap:5px;margin-right:8px!important;color:#53637a!important;font-size:11px!important;font-weight:700!important;white-space:nowrap}.stock-compare-choice input{width:15px!important;height:15px!important;margin:0}.stock-comparison-header{margin-bottom:16px}.stock-comparison-header h1{margin:0 0 5px;color:#17324f}.stock-comparison-header p{margin:0;color:#64748b}.stock-comparison-table-wrap{overflow:auto;border:1px solid #dbe4f0;border-radius:10px;background:#fff}.stock-comparison-table{width:100%;border-collapse:collapse;min-width:680px}.stock-comparison-table th,.stock-comparison-table td{padding:10px 12px;border-bottom:1px solid #edf1f6;text-align:right;font-size:13px}.stock-comparison-table th:first-child,.stock-comparison-table td:first-child{text-align:left;position:sticky;left:0;background:#fff}.stock-comparison-table thead th{background:#f8fafc;color:#17324f;font-weight:700}.stock-comparison-table .compare-group td{padding:12px;background:#f5f8fc;color:#334155;font-weight:700;text-align:left}.stock-comparison-table tbody tr:last-child td{border-bottom:0}
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
  bar.innerHTML = `<strong>Compare stocks</strong><div class="stock-compare-slots">${slots}</div><button class="stock-compare-action" type="button" ${compareSymbols.length !== 2 ? "disabled" : ""}>Compare 2 Stocks</button>`;
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
      rows += `<tr><td>${esc(label)}</td>${fs.map((f) => { const d = metricDisplay(f, key, type, currency); return `<td${d.title ? ` title="${esc(d.title)}"` : ""}>${esc(d.text)}</td>`; }).join("")}</tr>`;
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
    details.innerHTML = `<div class="stock-comparison-header"><h1>Stock Comparison</h1><p>Side-by-side comparison of all available valuation, profitability, financial-health, growth and latest-financial metrics.</p></div>${comparisonTable(datas)}`;
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
