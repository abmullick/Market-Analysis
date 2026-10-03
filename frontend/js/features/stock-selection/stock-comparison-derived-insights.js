const DERIVED_API = "/api/stocks";
const DERIVED_MAX = 4;

const n = (v) => Number.isFinite(Number(v)) ? Number(v) : null;
const avg = (a) => a.length ? a.reduce((s, v) => s + v, 0) / a.length : null;
const clamp = (v) => Math.max(0, Math.min(100, v));
const esc = (v) => String(v ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");

function seriesValues(series) {
  return (Array.isArray(series) ? series : []).map(x => n(x?.value)).filter(v => v != null);
}
function recent(series, count = 3) { return avg(seriesValues(series).slice(-count)); }
function previous(series, count = 3) {
  const a = seriesValues(series);
  return a.length >= count * 2 ? avg(a.slice(-count * 2, -count)) : null;
}
function trajectory(series, scale) {
  const r = recent(series), p = previous(series);
  return r != null && p != null ? clamp(50 + ((r - p) / scale) * 50) : null;
}
function consistency(data) {
  const c = data?.consistency || {};
  const growth = [c.revenue?.positive_growth_pct, c.profit?.positive_growth_pct, c.fcf?.positive_growth_pct].filter(v => n(v) != null).map(Number);
  const stability = n(c.roe_volatility) == null ? null : clamp(100 - Number(c.roe_volatility) * 10);
  return avg([avg(growth), stability].filter(v => v != null));
}
function buildMomentum(data) {
  const t = data?.trends || {};
  const context = String(data?.sector || data?.industry || "");
  const financial = /financial services|bank|nbfc|insurance/i.test(context);
  const growth = avg([trajectory(t.revenue_growth, 8), trajectory(t.profit_growth, 8), trajectory(t.eps_growth, 8)].filter(v => v != null));
  const returns = avg([trajectory(t.roe, 5), trajectory(t.roce, 5)].filter(v => v != null));
  const quality = financial ? consistency(data) : avg([trajectory(t.cash_conversion, 20), trajectory(t.fcf_margin, 5)].filter(v => v != null));
  let discipline = null;
  if (financial) {
    const shares = n(data?.dilution?.share_count_cagr_5y ?? data?.dilution?.share_count_cagr_3y);
    if (shares != null) discipline = clamp(80 - Math.max(0, shares * 100 - 1) * 12);
  } else {
    const debt = recent(t.debt) != null && previous(t.debt) != null ? recent(t.debt) - previous(t.debt) : null;
    const de = recent(t.debt_equity) != null && previous(t.debt_equity) != null ? recent(t.debt_equity) - previous(t.debt_equity) : null;
    const debtBase = Math.max(Math.abs(recent(t.debt) || 1), 1), deBase = Math.max(Math.abs(recent(t.debt_equity) || .25), .25);
    discipline = avg([de == null ? null : clamp(50 - de / deBase * 100), debt == null ? null : clamp(50 - debt / debtBase * 100)].filter(v => v != null));
  }
  const components = [[growth,.30],[returns,.25],[quality,.20],[discipline,.15],[consistency(data),.10]].filter(x => x[0] != null);
  const totalWeight = components.reduce((s, [,w]) => s + w, 0);
  const index = totalWeight ? components.reduce((s,[v,w]) => s + v*w, 0) / totalWeight : null;
  return { index: index == null ? null : Math.round(index), label: index == null ? "Insufficient history" : index >= 65 ? "Strengthening" : index >= 45 ? "Stable" : "Weakening" };
}

function median(a) {
  const x = a.filter(v => n(v) != null).map(Number).sort((a,b) => a-b);
  if (!x.length) return null;
  const m = Math.floor(x.length / 2);
  return x.length % 2 ? x[m] : (x[m-1] + x[m]) / 2;
}
function valuationContext(current, history) {
  const pe = (history?.pe_history || []).map(x => n(x?.value)).filter(v => v != null && v > 0);
  const pb = (history?.pb_history || []).map(x => n(x?.value)).filter(v => v != null && v > 0);
  const currentPe = n(current.pe), currentPb = n(current.pb);
  const peMedian = median(pe), pbMedian = median(pb);
  const peScore = currentPe != null && peMedian != null ? clamp(50 + ((peMedian - currentPe) / peMedian) * 100) : null;
  const pbScore = currentPb != null && pbMedian != null ? clamp(50 + ((pbMedian - currentPb) / pbMedian) * 100) : null;
  const score = avg([peScore, pbScore].filter(v => v != null));
  const premium = avg([currentPe != null && peMedian != null ? (currentPe / peMedian - 1) * 100 : null, currentPb != null && pbMedian != null ? (currentPb / pbMedian - 1) * 100 : null].filter(v => v != null));
  const label = score == null ? "Limited history" : score >= 60 ? "Below own history" : score <= 40 ? "Above own history" : "Near own history";
  return { score: score == null ? null : Math.round(score), label, premium, peMedian, pbMedian, peYears: pe.length, pbYears: pb.length };
}

async function json(path) {
  const r = await fetch(path, { headers: { Accept: "application/json", "X-Stock-Derived-Insights": "1" }, cache: "no-store" });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

function scoreClass(score) { return score == null ? "neutral" : score >= 65 ? "strong" : score >= 45 ? "stable" : "weak"; }
function scoreLabel(score) { return score == null ? "—" : String(score); }
function fmtPct(v) { return v == null ? "—" : `${v >= 0 ? "+" : ""}${v.toFixed(1)}%`; }

function renderCard(stock) {
  const momentum = buildMomentum(stock.pedigree);
  const valuation = valuationContext(stock.core, stock.charts);
  const mClass = scoreClass(momentum.index);
  const vClass = scoreClass(valuation.score);
  const premiumText = valuation.premium == null ? "Insufficient valuation history" : valuation.premium > 5 ? `${fmtPct(valuation.premium)} vs own historical median` : valuation.premium < -5 ? `${fmtPct(valuation.premium)} vs own historical median` : "Within 5% of own historical median";
  return `<article class="derived-stock-card"><div class="derived-stock-card-top"><div><div class="derived-stock-name">${esc(stock.name)}</div><div class="derived-stock-symbol">${esc(stock.symbol.replace(/\.NS$|\.BO$/i,""))}</div></div><div class="derived-mini-badge ${mClass}">${esc(momentum.label)}</div></div><div class="derived-score-row"><div class="derived-score-block ${mClass}"><span>Fundamental Momentum</span><strong>${scoreLabel(momentum.index)}</strong><small>Business trajectory</small></div><div class="derived-score-block ${vClass}"><span>Valuation Context</span><strong>${scoreLabel(valuation.score)}</strong><small>${esc(valuation.label)}</small></div></div><div class="derived-valuation-line"><div><b>P/E</b> ${valuation.peMedian == null ? "—" : `vs ${valuation.peMedian.toFixed(1)}x median`}</div><div><b>P/B</b> ${valuation.pbMedian == null ? "—" : `vs ${valuation.pbMedian.toFixed(1)}x median`}</div></div><div class="derived-card-note">${esc(premiumText)}</div></article>`;
}

function renderSection(rows) {
  const existing = document.querySelector(".stock-derived-comparison");
  existing?.remove();
  const anchor = document.querySelector(".stock-comparison-table-wrap");
  if (!anchor || !rows.length) return;
  const section = document.createElement("section");
  section.className = "stock-derived-comparison";
  section.innerHTML = `<div class="derived-section-heading"><div><h2>Derived Comparison</h2><p>Two engine-calculated views that interpret the numbers rather than simply listing them.</p></div><div class="derived-legend"><span><i class="legend-dot momentum-dot"></i> Fundamental Momentum</span><span><i class="legend-dot valuation-dot"></i> Valuation Context</span></div></div><div class="derived-stock-grid">${rows.map(renderCard).join("")}</div><div class="derived-method-note">Fundamental Momentum measures the direction and consistency of the business trajectory. Valuation Context compares current P/E and P/B with the stock's own historical median. These are analytical indicators, not forecasts or investment recommendations.</div>`;
  anchor.parentNode.insertBefore(section, anchor);
}

function addStyles() {
  if (document.getElementById("stock-derived-comparison-styles")) return;
  const style = document.createElement("style"); style.id = "stock-derived-comparison-styles";
  style.textContent = `.stock-derived-comparison{margin:18px 0 20px;padding:20px;border:1px solid #dbe5f0;border-radius:16px;background:linear-gradient(135deg,#ffffff 0%,#f5f9ff 100%);box-shadow:0 7px 24px rgba(15,23,42,.06)}.derived-section-heading{display:flex;align-items:flex-start;justify-content:space-between;gap:18px;margin-bottom:14px}.derived-section-heading h2{margin:0;color:#102b4e;font-size:18px}.derived-section-heading p{margin:5px 0 0;color:#64748b;font-size:11px}.derived-legend{display:flex;gap:12px;flex-wrap:wrap;color:#64748b;font-size:10px;font-weight:600}.legend-dot{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:4px}.momentum-dot{background:#2563eb}.valuation-dot{background:#8b5cf6}.derived-stock-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.derived-stock-card{padding:14px;border:1px solid #d8e3ef;border-radius:13px;background:#fff;box-shadow:0 3px 12px rgba(15,23,42,.04)}.derived-stock-card-top{display:flex;justify-content:space-between;align-items:flex-start;gap:10px}.derived-stock-name{font-size:14px;font-weight:800;color:#102b4e}.derived-stock-symbol{margin-top:2px;color:#7890a9;font-size:9px;font-weight:700;letter-spacing:.05em}.derived-mini-badge{padding:4px 7px;border-radius:999px;font-size:9px;font-weight:800;background:#eef2f7;color:#64748b}.derived-mini-badge.strong{background:#dcfce7;color:#15803d}.derived-mini-badge.stable{background:#fef3c7;color:#a16207}.derived-mini-badge.weak{background:#fee2e2;color:#b91c1c}.derived-score-row{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:12px}.derived-score-block{padding:10px;border:1px solid #e3eaf2;border-radius:10px;background:#f9fbfd}.derived-score-block span{display:block;color:#71849a;font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:.05em}.derived-score-block strong{display:block;margin-top:3px;color:#102b4e;font-size:24px;line-height:1.05}.derived-score-block small{display:block;margin-top:3px;color:#64748b;font-size:9px}.derived-score-block.strong{border-color:#b7e2c5;background:#f3fcf5}.derived-score-block.stable{border-color:#f2d58a;background:#fffaf0}.derived-score-block.weak{border-color:#f1b7b7;background:#fff7f7}.derived-valuation-line{display:flex;gap:18px;margin-top:10px;padding-top:9px;border-top:1px solid #edf1f5;color:#64748b;font-size:10px}.derived-valuation-line b{color:#294766}.derived-card-note{margin-top:7px;color:#8291a3;font-size:9px}.derived-method-note{margin-top:12px;color:#8291a3;font-size:9px;line-height:1.5}@media(max-width:700px){.derived-section-heading{flex-direction:column}.derived-stock-grid{grid-template-columns:1fr}.derived-score-row{grid-template-columns:1fr}}`;
  document.head.appendChild(style);
}

async function enhanceComparison() {
  const table = document.querySelector(".stock-comparison-table");
  if (!table) return;
  const params = new URLSearchParams(location.search);
  const symbols = [...new Set((params.get("compare") || "").split(",").map(x => decodeURIComponent(x).trim().toUpperCase()).filter(Boolean))].slice(0, DERIVED_MAX);
  if (symbols.length < 2) return;
  const key = symbols.join(",");
  if (document.body.dataset.derivedComparisonKey === key || document.body.dataset.derivedComparisonLoading === key) return;
  document.body.dataset.derivedComparisonLoading = key;
  try {
    const tableRows = [...table.querySelectorAll("tbody tr")];
    const current = {};
    tableRows.forEach(row => {
      const label = row.querySelector("td:first-child")?.textContent?.trim();
      if (!label) return;
      const cells = [...row.querySelectorAll("td")].slice(1).map(td => Number(td.textContent.replace(/[^0-9.+-]/g,"")));
      current[label] = cells;
    });
    const payloads = await Promise.all(symbols.map(async (symbol, index) => {
      const [core, charts, pedigree] = await Promise.all([
        json(`${DERIVED_API}/${encodeURIComponent(symbol)}`),
        json(`${DERIVED_API}/${encodeURIComponent(symbol)}/charts`),
        json(`${DERIVED_API}/pedigree/${encodeURIComponent(symbol)}`),
      ]);
      return { symbol, name: core.name || core.symbol || symbol, core: { ...core, pe: Number.isFinite(current["P/E"]?.[index]) ? current["P/E"][index] : core.pe, pb: Number.isFinite(current["Price / Book"]?.[index]) ? current["Price / Book"][index] : core.pb }, charts: charts.charts || charts, pedigree };
    }));
    renderSection(payloads);
    document.body.dataset.derivedComparisonKey = key;
  } catch (error) {
    console.warn("Derived comparison insights unavailable:", error);
  } finally {
    delete document.body.dataset.derivedComparisonLoading;
  }
}

addStyles();
const observer = new MutationObserver(enhanceComparison);
observer.observe(document.body, { childList: true, subtree: true });
document.addEventListener("DOMContentLoaded", enhanceComparison);
enhanceComparison();
