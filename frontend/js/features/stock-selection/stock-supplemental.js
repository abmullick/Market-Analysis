const API = "/api/stocks";

const INDIVIDUAL_MAP = {
  "Enterprise Value": ["enterprise_value", "money"],
  "Latest EBITDA": ["ebitda", "money"],
  "Forward P/E": ["forward_pe", "ratio"],
  "EV / EBITDA": ["ev_ebitda", "ratio"],
  "EV / Revenue": ["ev_revenue", "ratio"],
  "Gross Margin": ["gross_margin", "percent"],
  "Current Ratio": ["current_ratio", "ratio"],
  "Quick Ratio": ["quick_ratio", "ratio"],
  "Beta": ["beta", "number"],
  "Debt / Equity": ["debt_equity", "ratio"],
};

function esc(v) {
  return String(v ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");
}

function n(v) {
  return Number.isFinite(Number(v)) ? Number(v) : null;
}

function fmtMoney(v) {
  const x = n(v);
  if (x == null) return "—";
  const a = Math.abs(x);
  if (a >= 1e12) return `₹${(x / 1e12).toLocaleString("en-IN", { maximumFractionDigits: 2 })}T`;
  if (a >= 1e9) return `₹${(x / 1e9).toLocaleString("en-IN", { maximumFractionDigits: 2 })}B`;
  if (a >= 1e6) return `₹${(x / 1e6).toLocaleString("en-IN", { maximumFractionDigits: 2 })}M`;
  return `₹${x.toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
}

function fmt(v, type) {
  const x = n(v);
  if (x == null) return "—";
  if (type === "money") return fmtMoney(x);
  if (type === "ratio") return `${x.toLocaleString("en-IN", { maximumFractionDigits: 2 })}x`;
  if (type === "percent") return `${x.toLocaleString("en-IN", { maximumFractionDigits: 2 })}%`;
  if (type === "days") return `${x.toLocaleString("en-IN", { maximumFractionDigits: 1 })} days`;
  if (type === "pp") return `${x.toLocaleString("en-IN", { maximumFractionDigits: 1 })} pp`;
  return x.toLocaleString("en-IN", { maximumFractionDigits: 2 });
}

function meaningfulText(payload, key, type) {
  if (payload.not_meaningful?.[key]) return "N/M — Not Meaningful";
  return fmt(payload.computed?.[key] ?? payload.yahoo?.[key], type);
}

async function getSupplemental(symbol) {
  const response = await fetch(`${API}/${encodeURIComponent(symbol)}/supplemental`, {
    headers: { Accept: "application/json" },
    cache: "no-store",
  });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}

async function getAnalysis(symbol) {
  const response = await fetch(`${API}/${encodeURIComponent(symbol)}`, {
    headers: { Accept: "application/json" },
    cache: "no-store",
  });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}

function patchCard(details, label, payload, key, type) {
  const cards = [...details.querySelectorAll(".stock-metric-card")];
  const card = cards.find((el) => el.querySelector(".stock-metric-label")?.textContent?.trim() === label);
  if (!card) return;
  const value = card.querySelector(".stock-metric-value");
  if (!value) return;
  value.textContent = meaningfulText(payload, key, type);
  value.title = payload.not_meaningful?.[key] ? "Not meaningful for financial companies." : "";
}

function patchIndividual(payload) {
  const details = document.getElementById("stock-details");
  if (!details) return;
  for (const [label, [key, type]] of Object.entries(INDIVIDUAL_MAP)) {
    const source = key === "forward_pe" || key === "beta" ? payload.yahoo?.[key] : payload.computed?.[key];
    if (key === "forward_pe" || key === "beta") {
      if (n(source) != null) {
        const cards = [...details.querySelectorAll(".stock-metric-card")];
        const card = cards.find((el) => el.querySelector(".stock-metric-label")?.textContent?.trim() === label);
        if (card) card.querySelector(".stock-metric-value").textContent = fmt(source, type);
      }
    } else {
      patchCard(details, label, payload, key, type);
    }
  }
}

function derivedCard(label, value, type, note = "") {
  const display = fmt(value, type);
  return `<div class="stock-metric-card">
    <span class="stock-metric-label">${esc(label)}</span>
    <strong class="stock-metric-value">${esc(display)}</strong>
    ${note ? `<small class="stock-derived-note">${esc(note)}</small>` : ""}
  </div>`;
}

function renderDerivedAnalysis(data, symbol) {
  const details = document.getElementById("stock-details");
  const d = data?.derived_analysis;
  if (!details || !d || details.querySelector(".stock-derived-analysis")) return;

  const f = data.fundamentals || {};
  const cards = [
    ["Cash Conversion", d.cash_conversion_ratio != null ? d.cash_conversion_ratio * 100 : null, "percent", "CFO ÷ Net Profit"],
    ["FCF / Net Profit", d.fcf_to_profit != null ? d.fcf_to_profit * 100 : null, "percent", "Free cash flow ÷ Net Profit"],
    ["FCF Margin", d.fcf_margin_derived != null ? d.fcf_margin_derived * 100 : null, "percent", "Free cash flow ÷ Revenue"],
    ["ROIC", d.roic != null ? d.roic * 100 : null, "percent", "Operating profit ÷ invested capital"],
    ["CROIC", d.croic != null ? d.croic * 100 : null, "percent", "FCF ÷ invested capital"],
    ["Net Debt / EBITDA", d.net_debt_ebitda, "ratio", "Net debt ÷ EBITDA"],
    ["3Y Average ROE", d.average_roe_3y != null ? d.average_roe_3y * 100 : null, "percent", "Average annual ROE"],
    ["5Y Average ROE", d.average_roe_5y != null ? d.average_roe_5y * 100 : null, "percent", "Average annual ROE"],
    ["3Y Average OPM", d.operating_margin_3y_avg != null ? d.operating_margin_3y_avg * 100 : null, "percent", "Average operating margin"],
    ["5Y Average OPM", d.operating_margin_5y_avg != null ? d.operating_margin_5y_avg * 100 : null, "percent", "Average operating margin"],
    ["Debtor Days", d.debtor_days, "days", "Receivables ÷ Revenue × 365"],
    ["Inventory Days", d.inventory_days, "days", "Inventory ÷ Revenue × 365"],
    ["Payable Days", d.payable_days, "days", "Payables ÷ Revenue × 365"],
    ["Cash Conversion Cycle", d.cash_conversion_cycle, "days", "Debtor + Inventory − Payable days"],
    ["Debt Change 1Y", d.debt_change_1y != null ? d.debt_change_1y * 100 : null, "percent", "Year-over-year change"],
    ["Debt Change 3Y", d.debt_change_3y != null ? d.debt_change_3y * 100 : null, "percent", "Change over three years"],
    ["Piotroski Signals", d.piotroski_proxy_score, "number", "Available signals only; not a full 9-point score when source fields are missing"],
  ];

  const income = data.income_statement || [];
  const balance = data.balance_sheet || [];
  const years = income.slice(0, 6).map((r) => String(r.period || "").slice(0, 4));
  const trendRows = [
    ["Revenue", income, "TotalRevenue", "money"],
    ["Net Profit", income, "NetIncome", "money"],
    ["Operating Margin", income, "OperatingIncome", "margin"],
    ["Debt", balance, "TotalDebt", "money"],
  ];

  const trendHtml = trendRows.map(([label, rows, key, type]) => {
    const vals = rows.slice(0, 6).map((r) => {
      const value = n(r.values?.[key]);
      if (type === "margin") {
        const revenue = n(r.values?.TotalRevenue);
        return value != null && revenue ? `${(value / revenue * 100).toFixed(1)}%` : "—";
      }
      return value == null ? "—" : fmtMoney(value);
    });
    return `<tr><td>${esc(label)}</td>${vals.map((v) => `<td>${esc(v)}</td>`).join("")}</tr>`;
  }).join("");

  const section = document.createElement("section");
  section.className = "stock-section stock-derived-analysis";
  section.innerHTML = `<div class="stock-section-header">
      <h2>Derived Fundamental Analysis</h2>
      <span>Calculated from Screener financial statements</span>
    </div>
    <div class="stock-metrics-grid">
      ${cards.map(([label, value, type, note]) => derivedCard(label, value, type, note)).join("")}
    </div>
    <div class="stock-derived-explanation">
      <strong>How to read this section</strong>
      <p>These are calculated metrics, not additional source fields. They use the annual income statement, balance sheet and cash-flow data supplied by Screener. Definitions may differ from Screener's own ratio library where a proprietary or alternative convention is used.</p>
    </div>
    ${years.length ? `<div class="stock-derived-trend"><h3>Historical Trend</h3><div class="stock-table-wrap"><table class="stock-table"><thead><tr><th>Metric</th>${years.map((y) => `<th>${esc(y)}</th>`).join("")}</tr></thead><tbody>${trendHtml}</tbody></table></div></div>` : ""}`;

  details.appendChild(section);
}

function patchComparison(payloads, symbols) {
  const table = document.querySelector(".stock-comparison-table");
  if (!table) return;
  const rows = [...table.querySelectorAll("tbody tr")];
  const rowByLabel = new Map();
  rows.forEach((row) => {
    const label = row.querySelector("td")?.textContent?.trim();
    if (label) rowByLabel.set(label, row);
  });
  for (const [label, [key, type]] of Object.entries(INDIVIDUAL_MAP)) {
    const row = rowByLabel.get(label);
    if (!row) continue;
    const cells = [...row.querySelectorAll("td")].slice(1);
    payloads.forEach((payload, index) => {
      const cell = cells[index];
      if (!cell) return;
      const source = key === "forward_pe" || key === "beta" ? payload.yahoo?.[key] : payload.computed?.[key];
      if (payload.not_meaningful?.[key]) {
        cell.textContent = "N/M — Not Meaningful";
        cell.title = "Not meaningful for financial companies.";
      } else if (n(source) != null) {
        cell.textContent = fmt(source, type);
        cell.title = "";
      }
    });
  }
}

async function refreshCurrentView() {
  const params = new URLSearchParams(location.search);
  const compare = params.get("compare");
  try {
    if (compare) {
      const symbols = compare.split(",").map((x) => decodeURIComponent(x).trim().toUpperCase()).filter(Boolean);
      const payloads = await Promise.all(symbols.map(getSupplemental));
      patchComparison(payloads, symbols);
      return;
    }
    const symbol = (params.get("symbol") || "").trim().toUpperCase();
    if (symbol) {
      const [payload, analysis] = await Promise.all([getSupplemental(symbol), getAnalysis(symbol)]);
      patchIndividual(payload);
      renderDerivedAnalysis(analysis, symbol);
    }
  } catch (error) {
    console.warn("Supplemental stock metrics unavailable:", error);
  }
}

let refreshQueued = false;
const observer = new MutationObserver(() => {
  const details = document.getElementById("stock-details");
  if (details?.querySelector(".stock-metric-card") && !details.querySelector(".stock-derived-analysis") && !refreshQueued) {
    refreshQueued = true;
    queueMicrotask(() => {
      refreshQueued = false;
      refreshCurrentView();
    });
  }
});
observer.observe(document.body, { childList: true, subtree: true });
document.addEventListener("DOMContentLoaded", refreshCurrentView);