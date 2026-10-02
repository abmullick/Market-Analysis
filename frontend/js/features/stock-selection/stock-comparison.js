const API_BASE = "/api/stocks";
const MAX_COMPARE = 4;
const CORE_COMPARE_TIMEOUT_MS = 30 * 1000;

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
let comparisonInFlightKey = null;

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
  const min = Math.min(...values);
  const max = Math.max(...values);
  if (min === max) return "neutral";

  if (LOWER_IS_BETTER.has(key)) return raw === min ? "favorable" : "unfavorable";
  if (HIGHER_IS_BETTER.has(key)) return raw === max ? "favorable" : "unfavorable";
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
    /* Selection controls intentionally use the same compact rectangular treatment as the Mutual Fund Analysis controls. */
    .stock-select-btn,
    .stock-compare-action,
    .stock-compare-remove {
      display:inline-flex!important;
      align-items:center!important;
      justify-content:center!important;
      gap:6px!important;
      min-height:36px!important;
      padding:0 14px!important;
      border-radius:var(--radius-sm)!important;
      font-family:var(--font-family)!important;
      font-size:13px!important;
      font-weight:var(--btn-font-weight)!important;
      line-height:1!important;
      border:1px solid transparent!important;
      cursor:pointer!important;
      transition:var(--btn-transition)!important;
      box-shadow:var(--btn-shadow)!important;
      white-space:nowrap!important;
    }
    .stock-select-btn,
    .stock-picker-row .stock-select-btn{width:104px!important;min-width:104px!important;max-width:104px!important;flex:0 0 104px!important;background:linear-gradient(135deg,var(--color-primary),var(--color-primary-light))!important;color:#fff!important}
    .stock-select-btn:hover,.stock-compare-action:hover{background:linear-gradient(135deg,var(--color-primary-light),var(--color-primary))!important;color:#fff!important;transform:translateY(-1px)!important;box-shadow:var(--btn-shadow-hover)!important}
    .stock-select-btn:active,.stock-compare-action:active{transform:translateY(0)!important;box-shadow:var(--btn-shadow-active)!important}

    .stock-compare-card{margin-top:18px;padding:15px;border:1px solid #dbe4f0;border-radius:var(--radius-md);background:linear-gradient(180deg,#ffffff 0%,#f6faff 100%);box-shadow:0 5px 18px rgba(15,23,42,.05)}
    .stock-compare-card-header{display:flex;align-items:flex-start;justify-content:space-between;gap:10px;margin-bottom:10px}
    .stock-compare-card-title{color:var(--color-primary);font-size:13px;font-weight:700}
    .stock-compare-card-help{margin-top:3px;color:var(--color-text-light);font-size:11px;line-height:1.4}
    .stock-compare-slots{display:grid;grid-template-columns:1fr;gap:6px;margin-bottom:10px}
    .stock-compare-slot{display:flex;align-items:center;justify-content:space-between;gap:8px;min-height:34px;padding:7px 9px;border:1px dashed #cbd5e1;border-radius:var(--radius-sm);background:#f8fafc;color:var(--color-text-light);font-size:11px}
    .stock-compare-slot.filled{border-style:solid;border-color:#c9d9ec;background:#eef6ff;color:var(--color-primary);font-weight:600}
    .stock-compare-slot-name{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
    .stock-compare-remove{min-height:24px!important;width:24px!important;min-width:24px!important;padding:0!important;border-radius:var(--radius-sm)!important;background:#fff!important;color:#64748b!important;border-color:#dbe4ee!important;box-shadow:none!important;font-size:14px!important}
    .stock-compare-remove:hover{background:#fff1f2!important;color:#dc2626!important;border-color:#fecdd3!important;transform:none!important}
    .stock-compare-action{width:100%!important;background:linear-gradient(135deg,var(--color-primary),var(--color-primary-light))!important;color:#fff!important}
    .stock-compare-action:disabled{opacity:.48!important;cursor:not-allowed!important;box-shadow:none!important;transform:none!important}
    .stock-compare-limit{margin:0;color:var(--color-text-light);font-size:10px;line-height:1.4}
    .stock-compare-choice{display:inline-flex!important;flex-direction:row!important;align-items:center!important;gap:6px!important;margin-right:10px!important;color:var(--color-text-light)!important;font-size:11px!important;font-weight:700!important;white-space:nowrap!important}
    .stock-compare-choice input{width:15px!important;height:15px!important;margin:0!important;accent-color:var(--color-primary)}

    .stock-comparison-header{margin:8px 0 18px;padding:22px 24px;border:1px solid var(--color-border);border-radius:var(--radius-lg);background:linear-gradient(135deg,#ffffff,#f0f7ff);box-shadow:var(--btn-shadow)}
    .stock-comparison-header h1{margin:0 0 5px;color:var(--color-primary);font-size:1.55rem}
    .stock-comparison-header p{margin:0;color:var(--color-text-light);font-size:13px}
    .stock-comparison-table-wrap{overflow:auto;border:1px solid var(--color-border);border-radius:var(--radius-lg);background:var(--color-surface);box-shadow:0 6px 22px rgba(15,23,42,.06)}
    .stock-comparison-table{width:100%;border-collapse:separate;border-spacing:0;min-width:760px;table-layout:fixed}
    .stock-comparison-table th,.stock-comparison-table td{padding:12px 14px;border-bottom:1px solid #edf1f6;text-align:right;font-size:13px;font-variant-numeric:tabular-nums;overflow:hidden}
    .stock-comparison-table th:first-child,.stock-comparison-table td:first-child{text-align:left;position:sticky;left:0;background:var(--color-surface);z-index:1;width:22%}
    .stock-comparison-table thead th{background:#f1f6fc;color:var(--color-primary);font-weight:700;position:sticky;top:0;z-index:2;text-align:center;vertical-align:middle;white-space:normal;line-height:1.25}
    .stock-comparison-table thead th:first-child{z-index:3;text-align:left}
    .stock-comparison-table .compare-group td{padding:11px 14px;background:#edf4fb;color:#1e3a5f;font-weight:700;text-align:left;border-bottom:1px solid #dbe7f3;letter-spacing:.02em}
    .stock-comparison-table tbody tr:hover td{background:#fbfdff}
    .stock-comparison-table tbody tr:last-child td{border-bottom:0}
    .stock-comparison-table td.compare-favorable{background:var(--color-green-50);color:var(--color-green-700);font-weight:700;box-shadow:inset 3px 0 0 var(--color-green-500)}
    .stock-comparison-table td.compare-unfavorable{background:#fff7f7;color:var(--color-text);box-shadow:inset 3px 0 0 #fca5a5}
    .stock-comparison-table td.compare-negative{background:var(--color-red-50);color:var(--color-red-700);font-weight:700;box-shadow:inset 3px 0 0 var(--color-red-500)}
    .stock-comparison-table td.compare-negative::before{content:"⚠ ";font-size:11px}
    .stock-comparison-table .compare-favorable::after{content:"✓";margin-left:6px;font-size:10px;opacity:.8}
    .stock-comparison-table tbody tr:hover td.compare-favorable{background:#dcfce7}
    .stock-comparison-table tbody tr:hover td.compare-negative,.stock-comparison-table tbody tr:hover td.compare-unfavorable{background:#fee2e2}
    @media(max-width:700px){
      .stock-compare-card{margin-top:14px}
      .stock-comparison-header{padding:18px}
      .stock-comparison-table th,.stock-comparison-table td{padding:10px 11px}
    }
  `;
  document.head.appendChild(style);
}

function renderCompareBar() {
  const screen = document.getElementById("stock-selection-screen");
  if (!screen || screen.hidden) return;
  const panel = screen.querySelector(".stock-selected-panel");
  if (!panel) return;

  let card = panel.querySelector("#stock-compare-card");
  if (!card) {
    card = document.createElement("section");
    card.id = "stock-compare-card";
    card.className = "stock-compare-card";
    panel.appendChild(card);
  }

  const slots = Array.from({ length: MAX_COMPARE }, (_, i) => {
    const symbol = compareSymbols[i];
    return symbol
      ? `<div class="stock-compare-slot filled"><span class="stock-compare-slot-name">${esc(symbol.replace(/\\.NS$|\\.BO$/i, ""))}</span><button class="stock-compare-remove" type="button" data-remove-symbol="${esc(symbol)}" aria-label="Remove ${esc(symbol)}">×</button></div>`
      : `<div class="stock-compare-slot"><span class="stock-compare-slot-name">Stock ${i + 1}</span></div>`;
  });

  const canCompare = compareSymbols.length >= 2;
  const buttonText = canCompare ? `Compare ${compareSymbols.length} Stocks` : `Select ${2 - compareSymbols.length} More`;
  card.innerHTML = `
    <div class="stock-compare-card-header">
      <div>
        <div class="stock-compare-card-title">Compare stocks</div>
        <div class="stock-compare-card-help">Select 2–4 stocks to compare all fundamental metrics side by side.</div>
      </div>
    </div>
    <div class="stock-compare-slots">${slots}</div>
    <button class="stock-compare-action" type="button" ${canCompare ? "" : "disabled"}>${buttonText}</button>
    <p class="stock-compare-limit">${compareSymbols.length}/4 selected</p>
  `;

  card.querySelectorAll("[data-remove-symbol]").forEach((button) => {
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      const symbol = button.dataset.removeSymbol;
      compareSymbols = compareSymbols.filter((x) => x !== symbol);
      renderCompareBar();
      decorateRows();
    });
  });

  card.querySelector(".stock-compare-action").addEventListener("click", () => {
    if (compareSymbols.length >= 2) showComparison(compareSymbols);
  });
}

function decorateRows() {
  const screen = document.getElementById("stock-selection-screen");
  if (!screen || screen.hidden) return;
  const rows = screen.querySelectorAll(".stock-picker-row");
  if (!rows.length) {
    if (!screen.querySelector("#stock-compare-card")) renderCompareBar();
    return;
  }

  let decoratedAny = false;
  rows.forEach((row) => {
    if (row.dataset.compareReady === "1") {
      const checkbox = row.querySelector(".stock-compare-choice input");
      if (checkbox) checkbox.checked = compareSymbols.includes(row.dataset.symbol);
      return;
    }
    row.dataset.compareReady = "1";
    decoratedAny = true;
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
        if (compareSymbols.length >= MAX_COMPARE) {
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

  if (decoratedAny || !screen.querySelector("#stock-compare-card")) renderCompareBar();
}

async function fetchStock(symbol) {
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), CORE_COMPARE_TIMEOUT_MS);
  try {
    const r = await fetch(`${API_BASE}/${encodeURIComponent(symbol)}`, {
      headers: { Accept: "application/json", "X-Stock-Core-Request": "comparison" },
      cache: "no-store",
      signal: controller.signal,
    });
    const d = await r.json();
    if (!r.ok) throw new Error(d?.detail || `HTTP ${r.status}`);
    return d;
  } finally {
    window.clearTimeout(timeoutId);
  }
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
  const stockWidth = (78 / fs.length).toFixed(4);
  return `<div class="stock-comparison-table-wrap"><table class="stock-comparison-table"><colgroup><col style="width:22%">${fs.map(() => `<col style="width:${stockWidth}%">`).join("")}</colgroup><thead><tr><th>Metric</th>${fs.map((f) => `<th>${esc(f.name || f.symbol || "Stock")}</th>`).join("")}</tr></thead><tbody>${rows}</tbody></table></div>`;
}

async function showComparison(symbols) {
  const uniqueSymbols = [...new Set(symbols)].slice(0, MAX_COMPARE);
  if (uniqueSymbols.length < 2) return;
  const comparisonKey = uniqueSymbols.join(",");
  if (comparisonInFlightKey === comparisonKey) return;
  comparisonInFlightKey = comparisonKey;

  const selection = document.getElementById("stock-selection-screen");
  const analysis = document.getElementById("stock-analysis-screen");
  const details = document.getElementById("stock-details");
  const status = document.getElementById("stock-analysis-status");
  if (!selection || !analysis || !details) {
    comparisonInFlightKey = null;
    return;
  }

  compareSymbols = uniqueSymbols;
  selection.hidden = true;
  analysis.hidden = false;
  history.pushState({}, "", `?compare=${uniqueSymbols.map(encodeURIComponent).join(",")}`);
  status.textContent = "Loading comparison…";
  details.innerHTML = `<div class="stock-loading">Loading ${uniqueSymbols.map(esc).join(", ")}…</div>`;

  try {
    const datas = await Promise.all(uniqueSymbols.map(fetchStock));
    details.innerHTML = `<div class="stock-comparison-header"><h1>Stock Comparison</h1><p>Comparing ${datas.length} stocks. Green marks the more favorable value for comparable metrics; red marks negative values. ✓ and ⚠ indicate the reason for the highlight.</p></div>${comparisonTable(datas)}`;
    status.textContent = "";
  } catch (e) {
    details.innerHTML = `<div class="stock-error"><h2>Unable to load comparison</h2><p>${esc(e.message)}</p></div>`;
    status.textContent = "";
  } finally {
    comparisonInFlightKey = null;
  }
}

export function initStockComparison() {
  injectStyles();
  const screen = document.getElementById("stock-selection-screen");
  if (!screen) return;

  if (!observerStarted) {
    observerStarted = true;
    const observer = new MutationObserver(() => {
      if (screen.hidden) return;
      const rows = screen.querySelectorAll(".stock-picker-row");
      const needsDecoration = [...rows].some((row) => row.dataset.compareReady !== "1");
      const missingCompareBar = !screen.querySelector("#stock-compare-card");
      if (needsDecoration || missingCompareBar) decorateRows();
    });
    observer.observe(screen, { childList: true, subtree: true });
  }

  decorateRows();

  const params = new URLSearchParams(location.search);
  const compare = params.get("compare");
  if (compare) {
    const symbols = compare.split(",").map((x) => decodeURIComponent(x).trim().toUpperCase()).filter(Boolean).slice(0, MAX_COMPARE);
    if (symbols.length >= 2) {
      compareSymbols = symbols;
      showComparison(symbols);
    }
  }
}