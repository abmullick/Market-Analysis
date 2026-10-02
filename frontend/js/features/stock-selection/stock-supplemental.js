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
      const payload = await getSupplemental(symbol);
      patchIndividual(payload);
    }
  } catch (error) {
    console.warn("Supplemental stock metrics unavailable:", error);
  }
}

const observer = new MutationObserver(() => {
  if (document.getElementById("stock-details")?.querySelector(".stock-metric-card, .stock-comparison-table")) {
    refreshCurrentView();
  }
});
observer.observe(document.body, { childList: true, subtree: true });
document.addEventListener("DOMContentLoaded", refreshCurrentView);
