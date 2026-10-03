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

function vals(series) {
  return (Array.isArray(series) ? series : [])
    .filter(x => x && n(x.value) != null)
    .map(x => ({ year: String(x.year ?? x.date ?? "").slice(0, 10), value: Number(x.value) }));
}

function rollingDelta(series, year, window = 3) {
  const a = vals(series).filter(x => x.year <= year);
  if (a.length < window * 2) return null;
  return avg(a.slice(-window).map(x => x.value)) - avg(a.slice(-window * 2, -window).map(x => x.value));
}

function score(delta, scale) {
  return delta == null ? null : clamp(50 + delta / scale * 50);
}

function historicalConsistency(t, year) {
  const positive = ["revenue_growth", "profit_growth", "fcf_margin"].flatMap(k =>
    vals(t[k]).filter(x => x.year <= year).map(x => x.value > 0 ? 100 : 0)
  );
  const growthPersistence = avg(positive);
  const roe = vals(t.roe).filter(x => x.year <= year).map(x => x.value);
  const mean = avg(roe);
  const volatility = mean == null || !roe.length ? null : Math.sqrt(avg(roe.map(v => (v - mean) ** 2)));
  const stability = volatility == null ? null : clamp(100 - volatility * 10);
  return avg([growthPersistence, stability].filter(v => v != null));
}

function historicalShareDiscipline(data) {
  const shares = n(data?.dilution?.share_count_cagr_5y ?? data?.dilution?.share_count_cagr_3y);
  return shares == null ? null : clamp(80 - Math.max(0, shares * 100 - 1) * 12);
}

function buildTimeline(data, financial) {
  const t = data?.trends || {};
  const years = [...new Set(Object.values(t).flatMap(s => vals(s).map(x => x.year)))].filter(Boolean).sort();
  const out = [];
  years.forEach(year => {
    const growth = avg(["revenue_growth", "profit_growth", "eps_growth"].map(k => score(rollingDelta(t[k], year), 8)).filter(v => v != null));
    const returns = avg(["roe", "roce"].map(k => score(rollingDelta(t[k], year), 5)).filter(v => v != null));
    const quality = financial
      ? historicalConsistency(t, year)
      : avg([score(rollingDelta(t.cash_conversion, year), 20), score(rollingDelta(t.fcf_margin, year), 5)].filter(v => v != null));
    let discipline = null;
    if (financial) {
      discipline = historicalShareDiscipline(data);
    } else {
      const debt = rollingDelta(t.debt, year), de = rollingDelta(t.debt_equity, year);
      const debtRecent = vals(t.debt).filter(x => x.year <= year).slice(-3).map(x => x.value);
      const deRecent = vals(t.debt_equity).filter(x => x.year <= year).slice(-3).map(x => x.value);
      const debtBase = Math.max(Math.abs(avg(debtRecent) || 1), 1);
      const deBase = Math.max(Math.abs(avg(deRecent) || .25), .25);
      discipline = avg([
        de == null ? null : clamp(50 - de / deBase * 100),
        debt == null ? null : clamp(50 - debt / debtBase * 100),
      ].filter(v => v != null));
    }
    const consistency = historicalConsistency(t, year);
    const available = [[growth, .30], [returns, .25], [quality, .20], [discipline, .15], [consistency, .10]]
      .filter(([, v]) => v != null);
    const weight = available.reduce((s, [, w]) => s + w, 0);
    if (!weight) return;
    const momentum = Math.round(available.reduce((s, [v, w]) => s + v * w, 0) / weight);
    out.push({ year, score: momentum, status: status(momentum) });
  });
  return out.slice(-7);
}

function status(value) {
  return value >= 65 ? "Strengthening" : value >= 45 ? "Stable" : "Weakening";
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

function renderTimeline(data, financial) {
  const points = buildTimeline(data, financial);
  if (points.length < 2) {
    return `<div class="derived-timeline-empty">Not enough annual history to reconstruct a meaningful momentum timeline.</div>`;
  }
  const first = points[0];
  const last = points.at(-1);
  const min = Math.min(...points.map(p => p.score));
  const max = Math.max(...points.map(p => p.score));
  const range = Math.max(max - min, 1);
  const bars = points.map(p => {
    const height = 28 + ((p.score - min) / range) * 62;
    return `<div class="derived-timeline-point" tabindex="0" title="${esc(p.year)}: ${p.score} — ${esc(p.status)}">
      <div class="derived-timeline-score">${p.score}</div>
      <div class="derived-timeline-bar ${scoreClass(p.score)}" style="height:${height}px"></div>
      <small>${esc(p.year)}</small>
    </div>`;
  }).join("");
  const direction = last.score - first.score;
  return `<div class="derived-timeline">
    <div class="derived-timeline-head">
      <div><span>Fundamental Trend</span><small>Historical reconstruction of the same momentum framework</small></div>
      <b class="${scoreClass(last.score)}">${direction >= 5 ? "↗" : direction <= -5 ? "↘" : "→"} ${esc(status(last.score))}</b>
    </div>
    <div class="derived-timeline-chart">${bars}</div>
    <div class="derived-timeline-foot"><span>${esc(first.year)} · ${first.score}</span><strong>Current ${last.score}</strong><span>${esc(last.year)}</span></div>
  </div>`;
}

function renderComponents(momentum) {
  return momentum.components.map(([name, value, weight]) => `
    <div class="derived-factor">
      <div><span>${esc(name)}</span><b>${value == null ? "—" : Math.round(value)}</b></div>
      <div class="derived-factor-track"><i style="width:${value == null ? 0 : Math.round(value)}%"></i></div>
      <small>${Math.round(weight * 100)}% weight</small>
    </div>`).join("");
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
  const lens = financial ? "Financial lens" : "Operating business lens";

  return `<article class="derived-stock-card">
    <div class="derived-stock-card-top">
      <div>
        <div class="derived-stock-name">${esc(stockName(row.core, row.symbol))}</div>
        <div class="derived-stock-symbol">${esc(row.symbol.replace(/\.NS$|\.BO$/i, ""))}</div>
      </div>
      <span class="derived-lens">${esc(lens)}</span>
    </div>
    <div class="derived-stock-context">Every score and timeline below belongs only to <strong>${esc(stockName(row.core, row.symbol))}</strong>.</div>
    <div class="derived-score-row">
      <div class="derived-score-block ${mClass}">
        <span>Fundamental Momentum</span>
        <strong>${momentum.index == null ? "—" : momentum.index}</strong>
        <small>${esc(momentum.label)} · current trajectory</small>
      </div>
      <div class="derived-score-block ${vClass}">
        <span>Valuation Context</span>
        <strong>${valuation.score == null ? "—" : valuation.score}</strong>
        <small>${esc(valuation.label)} · own historical valuation</small>
      </div>
    </div>
    <div class="derived-factors">${renderComponents(momentum)}</div>
    ${renderTimeline(row.pedigree, financial)}
    <div class="derived-valuation-line">
      <div><b>P/E</b> ${fundamentals.pe == null ? "—" : `${Number(fundamentals.pe).toFixed(1)}x`} <span>vs ${valuation.peMedian == null ? "—" : `${valuation.peMedian.toFixed(1)}x median`}</span></div>
      <div><b>P/B</b> ${fundamentals.pb == null ? "—" : `${Number(fundamentals.pb).toFixed(1)}x`} <span>vs ${valuation.pbMedian == null ? "—" : `${valuation.pbMedian.toFixed(1)}x median`}</span></div>
    </div>
    <div class="derived-card-note">${esc(premiumText)}</div>
  </article>`;
}

function removeOrphanedIndividualMomentum() {
  if (!new URLSearchParams(location.search).has("compare")) return;
  document.querySelectorAll("#stock-details > .stock-fundamental-momentum, #stock-details .stock-fundamental-momentum").forEach(el => el.remove());
  document.querySelectorAll("#stock-details > .stock-fundamental-signals, #stock-details .stock-fundamental-signals").forEach(el => el.remove());
}

function renderSection(rows) {
  document.querySelector(".stock-derived-comparison")?.remove();
  const anchor = document.querySelector(".stock-comparison-table-wrap");
  if (!anchor || !rows.length) return;
  const section = document.createElement("section");
  section.className = "stock-derived-comparison";
  section.innerHTML = `<div class="derived-section-heading">
    <div><div class="derived-eyebrow">COMPARATIVE DECISION LENS</div><h2>Fundamental Momentum × Valuation</h2><p>Each stock is calculated independently. The comparison does not create a blended Momentum Index.</p></div>
    <div class="derived-legend"><span><i class="legend-dot momentum-dot"></i> Momentum</span><span><i class="legend-dot valuation-dot"></i> Valuation context</span></div>
  </div>
  <div class="derived-stock-grid">${rows.map(renderCard).join("")}</div>
  <div class="derived-method-note"><strong>How to read this:</strong> the Momentum Index and each historical timeline belong to the stock named on the card. Momentum uses the same engine as individual analysis; the timeline reconstructs earlier points from the same underlying data. Valuation Context compares the current multiple(s) with that stock's own history. These are descriptive analytical indicators, not forecasts or recommendations.</div>`;
  anchor.parentNode.insertBefore(section, anchor);
}

function addStyles() {
  if (document.getElementById("stock-derived-comparison-styles")) return;
  const style = document.createElement("style"); style.id = "stock-derived-comparison-styles";
  style.textContent = `.stock-derived-comparison{margin:18px 0 20px;padding:20px;border:1px solid #d8e3ef;border-radius:18px;background:radial-gradient(circle at 8% 0%,rgba(37,99,235,.08),transparent 32%),linear-gradient(135deg,#fff 0%,#f5f9ff 100%);box-shadow:0 10px 30px rgba(15,23,42,.07)}.derived-section-heading{display:flex;align-items:flex-start;justify-content:space-between;gap:18px;margin-bottom:16px}.derived-eyebrow{font-size:9px;font-weight:800;letter-spacing:.14em;color:#2563eb;margin-bottom:4px}.derived-section-heading h2{margin:0;color:#102b4e;font-size:19px}.derived-section-heading p{margin:5px 0 0;color:#64748b;font-size:11px;line-height:1.5}.derived-legend{display:flex;gap:12px;flex-wrap:wrap;color:#64748b;font-size:10px;font-weight:700;padding-top:4px}.legend-dot{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:4px}.momentum-dot{background:#2563eb}.valuation-dot{background:#8b5cf6}.derived-stock-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.derived-stock-card{position:relative;padding:15px;border:1px solid #d8e3ef;border-radius:14px;background:rgba(255,255,255,.94);box-shadow:0 4px 16px rgba(15,23,42,.045);overflow:hidden}.derived-stock-card::before{content:"";position:absolute;left:0;right:0;top:0;height:3px;background:linear-gradient(90deg,#2563eb,#8b5cf6)}.derived-stock-card-top{display:flex;justify-content:space-between;align-items:flex-start;gap:10px}.derived-stock-name{font-size:14px;font-weight:800;color:#102b4e}.derived-stock-symbol{margin-top:2px;color:#7890a9;font-size:9px;font-weight:800;letter-spacing:.07em}.derived-lens{padding:4px 7px;border-radius:999px;background:#eef4ff;color:#38618d;font-size:8px;font-weight:800;white-space:nowrap}.derived-stock-context{margin-top:7px;color:#7b8da1;font-size:9px}.derived-score-row{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:12px}.derived-score-block{padding:11px;border:1px solid #e3eaf2;border-radius:11px;background:#f9fbfd}.derived-score-block span{display:block;color:#71849a;font-size:8px;font-weight:800;text-transform:uppercase;letter-spacing:.07em}.derived-score-block strong{display:block;margin-top:3px;color:#102b4e;font-size:25px;line-height:1.05;font-variant-numeric:tabular-nums}.derived-score-block small{display:block;margin-top:4px;color:#64748b;font-size:9px}.derived-score-block.strong{border-color:#b7e2c5;background:linear-gradient(135deg,#f3fcf5,#fff)}.derived-score-block.stable{border-color:#f2d58a;background:linear-gradient(135deg,#fffaf0,#fff)}.derived-score-block.weak{border-color:#f1b7b7;background:linear-gradient(135deg,#fff7f7,#fff)}.derived-score-block.neutral{background:#f8fafc}.derived-factors{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:6px;margin-top:10px}.derived-factor{padding:7px 8px;border:1px solid #e6edf4;border-radius:9px;background:#fbfdff}.derived-factor>div:first-child{display:flex;justify-content:space-between;gap:5px;align-items:center}.derived-factor span{color:#61758d;font-size:8px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.derived-factor b{color:#17355d;font-size:10px;font-variant-numeric:tabular-nums}.derived-factor-track{height:4px;margin-top:5px;background:#eaf0f6;border-radius:99px;overflow:hidden}.derived-factor-track i{display:block;height:100%;border-radius:99px;background:linear-gradient(90deg,#3b82f6,#2563eb)}.derived-factor small{display:block;margin-top:4px;color:#91a0b0;font-size:7px}.derived-timeline{margin-top:10px;padding:10px 11px;border:1px solid #e1e9f2;border-radius:11px;background:linear-gradient(180deg,#fbfdff,#f6faff)}.derived-timeline-head{display:flex;justify-content:space-between;align-items:flex-start;gap:8px}.derived-timeline-head span{display:block;color:#294766;font-size:10px;font-weight:800}.derived-timeline-head small{display:block;margin-top:2px;color:#8492a2;font-size:8px}.derived-timeline-head b{padding:4px 7px;border-radius:999px;font-size:8px;white-space:nowrap}.derived-timeline-head b.strong{background:#ecfdf3;color:#15803d}.derived-timeline-head b.stable{background:#fff8e7;color:#9a6700}.derived-timeline-head b.weak{background:#fff1f2;color:#c0392b}.derived-timeline-chart{height:108px;display:flex;align-items:flex-end;gap:7px;margin-top:9px;padding:0 3px;border-bottom:1px solid #dbe4ee}.derived-timeline-point{height:100%;flex:1;min-width:24px;display:flex;flex-direction:column;align-items:center;justify-content:flex-end;gap:4px;outline:none}.derived-timeline-score{height:14px;color:#48617d;font-size:8px;font-weight:800}.derived-timeline-bar{width:18px;min-height:8px;border-radius:6px 6px 2px 2px;box-shadow:0 3px 8px rgba(37,99,235,.1);transition:transform .15s ease}.derived-timeline-bar.strong{background:linear-gradient(180deg,#22c55e,#16a34a)}.derived-timeline-bar.stable{background:linear-gradient(180deg,#f2b84b,#d89b14)}.derived-timeline-bar.weak{background:linear-gradient(180deg,#ef6a6a,#dc4b4b)}.derived-timeline-point:hover .derived-timeline-bar,.derived-timeline-point:focus .derived-timeline-bar{transform:translateY(-3px)}.derived-timeline-point small{color:#71849a;font-size:7px}.derived-timeline-foot{display:flex;justify-content:space-between;gap:5px;margin-top:6px;color:#8998a8;font-size:8px}.derived-timeline-foot strong{color:#17355d}.derived-timeline-empty{margin-top:10px;padding:11px;border:1px dashed #d7e1eb;border-radius:10px;color:#8796a7;font-size:8px;background:#fafcff}.derived-valuation-line{display:flex;gap:16px;margin-top:10px;padding-top:9px;border-top:1px solid #edf1f5;color:#64748b;font-size:9px;flex-wrap:wrap}.derived-valuation-line b{color:#294766}.derived-valuation-line span{color:#8a99a9}.derived-card-note{margin-top:6px;color:#8291a3;font-size:8px}.derived-method-note{margin-top:13px;padding-top:11px;border-top:1px solid #dfe7ef;color:#71849a;font-size:9px;line-height:1.5}.derived-method-note strong{color:#49627e}@media(max-width:850px){.derived-stock-grid{grid-template-columns:1fr}.derived-factors{grid-template-columns:repeat(3,minmax(0,1fr))}}@media(max-width:560px){.derived-section-heading{flex-direction:column}.derived-score-row{grid-template-columns:1fr}.derived-factors{grid-template-columns:repeat(2,minmax(0,1fr))}}`;
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
  removeOrphanedIndividualMomentum();
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
