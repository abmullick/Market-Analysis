import { buildMomentum } from "/js/features/stock-selection/stock-fundamental-momentum.js";

const DERIVED_API = "/api/stocks";
const DERIVED_MAX = 4;
const coreBySymbol = Object.create(null);

const n = (v) => Number.isFinite(Number(v)) ? Number(v) : null;
const avg = (a) => a.length ? a.reduce((s, v) => s + v, 0) / a.length : null;
const clamp = (v) => Math.max(0, Math.min(100, v));
const esc = (v) => String(v ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");

function median(values) {
  const x = values.filter(v => n(v) != null).map(Number).sort((a, b) => a - b);
  if (!x.length) return null;
  const m = Math.floor(x.length / 2);
  return x.length % 2 ? x[m] : (x[m - 1] + x[m]) / 2;
}

function valuationContext(fundamentals, charts) {
  const peHistory = (charts?.pe_history || []).map(x => n(x?.value)).filter(v => v != null && v > 0);
  const pbHistory = (charts?.pb_history || []).map(x => n(x?.value)).filter(v => v != null && v > 0);
  const currentPe = n(fundamentals?.pe);
  const currentPb = n(fundamentals?.pb);
  const peMedian = median(peHistory);
  const pbMedian = median(pbHistory);
  const peScore = currentPe != null && peMedian != null ? clamp(50 + ((peMedian - currentPe) / peMedian) * 100) : null;
  const pbScore = currentPb != null && pbMedian != null ? clamp(50 + ((pbMedian - currentPb) / pbMedian) * 100) : null;
  const score = avg([peScore, pbScore].filter(v => v != null));
  const premium = avg([
    currentPe != null && peMedian != null ? (currentPe / peMedian - 1) * 100 : null,
    currentPb != null && pbMedian != null ? (currentPb / pbMedian - 1) * 100 : null,
  ].filter(v => v != null));
  const label = score == null ? "Limited history" : score >= 60 ? "Below own history" : score <= 40 ? "Above own history" : "Near own history";
  return { score: score == null ? null : Math.round(score), label, premium, peMedian, pbMedian };
}

async function json(path) {
  const response = await fetch(path, {
    headers: { Accept: "application/json", "X-Stock-Derived-Insights": "1" },
    cache: "no-store",
  });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}

function scoreClass(score) {
  return score == null ? "neutral" : score >= 65 ? "strong" : score >= 45 ? "stable" : "weak";
}

function fmtPct(value) {
  return value == null ? "—" : `${value >= 0 ? "+" : ""}${value.toFixed(1)}%`;
}

function stockName(data, symbol) {
  return data?.fundamentals?.name || data?.fundamentals?.longName || data?.name || symbol;
}

function renderCard(row) {
  const fundamentals = row.core?.fundamentals || {};
  const context = `${fundamentals.sector || ""} ${fundamentals.industry || ""}`;
  const financial = /financial services|bank|nbfc|insurance/i.test(context);
  const momentum = buildMomentum(row.pedigree, financial);
  const valuation = valuationContext(fundamentals, row.charts);
  const mClass = scoreClass(momentum.index);
  const vClass = scoreClass(valuation.score);
  const premiumText = valuation.premium == null
    ? "Historical valuation context is not available."
    : `${fmtPct(valuation.premium)} average premium/discount to its own historical median.`;

  return `<article class="derived-stock-card">
    <div class="derived-stock-card-top">
      <div>
        <div class="derived-stock-name">${esc(stockName(row.core, row.symbol))}</div>
        <div class="derived-stock-symbol">${esc(row.symbol.replace(/\.NS$|\.BO$/i, ""))}</div>
      </div>
    </div>
    <div class="derived-stock-context">All scores below belong to <strong>${esc(stockName(row.core, row.symbol))}</strong>.</div>
    <div class="derived-score-row">
      <div class="derived-score-block ${mClass}">
        <span>Fundamental Momentum</span>
        <strong>${momentum.index == null ? "—" : momentum.index}</strong>
        <small>${esc(momentum.label)} · Business trajectory</small>
      </div>
      <div class="derived-score-block ${vClass}">
        <span>Valuation Context</span>
        <strong>${valuation.score == null ? "—" : valuation.score}</strong>
        <small>${esc(valuation.label)} · Own historical valuation</small>
      </div>
    </div>
    <div class="derived-valuation-line">
      <div><b>P/E</b> ${fundamentals.pe == null ? "—" : `${Number(fundamentals.pe).toFixed(1)}x`} <span>vs ${valuation.peMedian == null ? "—" : `${valuation.peMedian.toFixed(1)}x median`}</span></div>
      <div><b>P/B</b> ${fundamentals.pb == null ? "—" : `${Number(fundamentals.pb).toFixed(1)}x`} <span>vs ${valuation.pbMedian == null ? "—" : `${valuation.pbMedian.toFixed(1)}x median`}</span></div>
    </div>
    <div class="derived-card-note">${esc(premiumText)}</div>
  </article>`;
}

function renderSection(rows) {
  document.querySelector(".stock-derived-comparison")?.remove();
  const anchor = document.querySelector(".stock-comparison-table-wrap");
  if (!anchor || !rows.length) return;
  const section = document.createElement("section");
  section.className = "stock-derived-comparison";
  section.innerHTML = `<div class="derived-section-heading">
    <div><h2>Derived Comparison</h2><p>Engine-calculated context for <strong>each stock individually</strong>. The Momentum and Valuation scores are not a single score for the comparison.</p></div>
    <div class="derived-legend"><span><i class="legend-dot momentum-dot"></i> Fundamental Momentum</span><span><i class="legend-dot valuation-dot"></i> Valuation Context</span></div>
  </div>
  <div class="derived-stock-grid">${rows.map(renderCard).join("")}</div>
  <div class="derived-method-note">Fundamental Momentum uses the same calculation as the individual stock page. Valuation Context compares the current P/E and P/B with that <strong>same stock's own historical median</strong>. These are descriptive analytical indicators, not forecasts or investment recommendations.</div>`;
  anchor.parentNode.insertBefore(section, anchor);
}

function addStyles() {
  if (document.getElementById("stock-derived-comparison-styles")) return;
  const style = document.createElement("style"); style.id = "stock-derived-comparison-styles";
  style.textContent = `.stock-derived-comparison{margin:18px 0 20px;padding:20px;border:1px solid #dbe5f0;border-radius:16px;background:linear-gradient(135deg,#ffffff 0%,#f5f9ff 100%);box-shadow:0 7px 24px rgba(15,23,42,.06)}.derived-section-heading{display:flex;align-items:flex-start;justify-content:space-between;gap:18px;margin-bottom:14px}.derived-section-heading h2{margin:0;color:#102b4e;font-size:18px}.derived-section-heading p{margin:5px 0 0;color:#64748b;font-size:11px;line-height:1.5}.derived-legend{display:flex;gap:12px;flex-wrap:wrap;color:#64748b;font-size:10px;font-weight:600}.legend-dot{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:4px}.momentum-dot{background:#2563eb}.valuation-dot{background:#8b5cf6}.derived-stock-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.derived-stock-card{padding:14px;border:1px solid #d8e3ef;border-radius:13px;background:#fff;box-shadow:0 3px 12px rgba(15,23,42,.04)}.derived-stock-card-top{display:flex;justify-content:space-between;align-items:flex-start;gap:10px}.derived-stock-name{font-size:14px;font-weight:800;color:#102b4e}.derived-stock-symbol{margin-top:2px;color:#7890a9;font-size:9px;font-weight:700;letter-spacing:.05em}.derived-stock-context{margin-top:7px;color:#7b8da1;font-size:9px}.derived-score-row{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:12px}.derived-score-block{padding:11px;border:1px solid #e3eaf2;border-radius:10px;background:#f9fbfd}.derived-score-block span{display:block;color:#71849a;font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:.05em}.derived-score-block strong{display:block;margin-top:3px;color:#102b4e;font-size:25px;line-height:1.05}.derived-score-block small{display:block;margin-top:4px;color:#64748b;font-size:9px}.derived-score-block.strong{border-color:#b7e2c5;background:#f3fcf5}.derived-score-block.stable{border-color:#f2d58a;background:#fffaf0}.derived-score-block.weak{border-color:#f1b7b7;background:#fff7f7}.derived-score-block.neutral{background:#f8fafc}.derived-valuation-line{display:flex;gap:18px;margin-top:10px;padding-top:9px;border-top:1px solid #edf1f5;color:#64748b;font-size:10px;flex-wrap:wrap}.derived-valuation-line b{color:#294766}.derived-valuation-line span{color:#8a99a9}.derived-card-note{margin-top:7px;color:#8291a3;font-size:9px}.derived-method-note{margin-top:12px;color:#8291a3;font-size:9px;line-height:1.5}@media(max-width:700px){.derived-section-heading{flex-direction:column}.derived-stock-grid{grid-template-columns:1fr}.derived-score-row{grid-template-columns:1fr}}`;
  document.head.appendChild(style);
}

function captureComparisonCore() {
  const originalFetch = window.fetch.bind(window);
  window.fetch = async (...args) => {
    const response = await originalFetch(...args);
    const url = String(args[0]?.url || args[0] || "");
    const headers = args[1]?.headers;
    const isComparisonCore = headers && typeof headers.get === "function"
      ? headers.get("X-Stock-Core-Request") === "comparison"
      : headers?.["X-Stock-Core-Request"] === "comparison";
    const match = url.match(/\/api\/stocks\/([^/?]+)$/);
    if (isComparisonCore && match) {
      const symbol = decodeURIComponent(match[1]).toUpperCase();
      response.clone().json().then(data => {
        coreBySymbol[symbol] = data;
        window.dispatchEvent(new CustomEvent("stock-comparison-core-ready"));
      }).catch(() => {});
    }
    return response;
  };
}

async function enhanceComparison() {
  const table = document.querySelector(".stock-comparison-table");
  if (!table) return;
  const params = new URLSearchParams(location.search);
  const symbols = [...new Set((params.get("compare") || "").split(",").map(x => decodeURIComponent(x).trim().toUpperCase()).filter(Boolean))].slice(0, DERIVED_MAX);
  if (symbols.length < 2 || symbols.some(symbol => !coreBySymbol[symbol])) return;
  const key = symbols.join(",");
  if (document.body.dataset.derivedComparisonKey === key || document.body.dataset.derivedComparisonLoading === key) return;
  document.body.dataset.derivedComparisonLoading = key;
  try {
    const [pedigreeResponse, ...chartResponses] = await Promise.all([
      json(`${DERIVED_API}/pedigree/compare?${symbols.map(s => `symbols=${encodeURIComponent(s)}`).join("&")}`),
      ...symbols.map(symbol => json(`${DERIVED_API}/${encodeURIComponent(symbol)}/charts`)),
    ]);
    const pedigreeBySymbol = Object.fromEntries((pedigreeResponse.stocks || []).map(stock => [String(stock.symbol).toUpperCase(), stock]));
    const rows = symbols.map((symbol, index) => ({
      symbol,
      core: coreBySymbol[symbol],
      pedigree: pedigreeBySymbol[symbol],
      charts: chartResponses[index]?.charts || chartResponses[index] || {},
    })).filter(row => row.pedigree);
    renderSection(rows);
    if (rows.length) document.body.dataset.derivedComparisonKey = key;
  } catch (error) {
    console.warn("Derived comparison insights unavailable:", error);
  } finally {
    delete document.body.dataset.derivedComparisonLoading;
  }
}

addStyles();
captureComparisonCore();
const observer = new MutationObserver(enhanceComparison);
observer.observe(document.body, { childList: true, subtree: true });
window.addEventListener("stock-comparison-core-ready", enhanceComparison);
document.addEventListener("DOMContentLoaded", enhanceComparison);
enhanceComparison();
