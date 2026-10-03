// Sector-aware Valuation Context for individual stock analysis.
// Uses the existing stock fundamentals and /charts endpoints; no new data source.

const VALUATION_API = "/api/stocks";
const vNum = (v) => Number.isFinite(Number(v)) ? Number(v) : null;
const vClamp = (v) => Math.max(0, Math.min(100, Number(v)));
const vEsc = (v) => String(v ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");

function median(values) {
  const a = values.filter(Number.isFinite).slice().sort((x, y) => x - y);
  if (!a.length) return null;
  const m = Math.floor(a.length / 2);
  return a.length % 2 ? a[m] : (a[m - 1] + a[m]) / 2;
}

function series(series) {
  return (Array.isArray(series) ? series : [])
    .map(x => ({ year: String(x?.year ?? x?.period ?? ""), value: vNum(x?.value) }))
    .filter(x => x.year && x.value != null && x.value > 0);
}

function sectorLens(f) {
  const text = `${f?.sector || ""} ${f?.industry || ""}`.toLowerCase();
  if (/bank|nbfc|financial services|insurance|capital markets|credit/.test(text)) {
    return {
      name: "Financial-services lens",
      weights: { pe: .30, pb: .70 },
      explanation: "P/B carries the larger weight because book value and returns on equity are central valuation anchors for banks, lenders and insurers. P/E is used as a secondary earnings cross-check."
    };
  }
  if (/real estate|reit|infrastructure|utilities|telecom|oil|gas|metals|mining|cement/.test(text)) {
    return {
      name: "Capital-intensive lens",
      weights: { pe: .60, pb: .40 },
      explanation: "P/E remains the primary valuation anchor, with P/B as a supporting measure for businesses where asset intensity and balance-sheet value are meaningful."
    };
  }
  return {
    name: "Operating-business lens",
    weights: { pe: .70, pb: .30 },
    explanation: "P/E is the primary valuation anchor for most operating businesses, with P/B retained as a secondary cross-check."
  };
}

function relativeScore(multiple, ownMedian) {
  if (multiple == null || ownMedian == null || ownMedian <= 0) return null;
  // 50 = the company's own historical median. Lower multiples score higher.
  return vClamp(50 - ((multiple / ownMedian) - 1) * 100);
}

function relation(current, medianValue) {
  if (current == null || medianValue == null) return "Insufficient history";
  const pct = ((current / medianValue) - 1) * 100;
  if (Math.abs(pct) <= 5) return "Near own median";
  return pct < 0 ? `${Math.abs(pct).toFixed(0)}% below own median` : `${pct.toFixed(0)}% above own median`;
}

function buildValuation(f, charts) {
  const lens = sectorLens(f);
  const peHistory = series(charts?.pe_history);
  const pbHistory = series(charts?.pb_history);
  const pe = vNum(f?.pe);
  const pb = vNum(f?.pb);
  const peMedian = median(peHistory.map(x => x.value));
  const pbMedian = median(pbHistory.map(x => x.value));
  const peScore = relativeScore(pe, peMedian);
  const pbScore = relativeScore(pb, pbMedian);
  const components = [
    peScore == null ? null : { key: "pe", name: "P/E context", current: pe, median: peMedian, score: peScore, weight: lens.weights.pe },
    pbScore == null ? null : { key: "pb", name: "P/B context", current: pb, median: pbMedian, score: pbScore, weight: lens.weights.pb },
  ].filter(Boolean);
  const weight = components.reduce((s, x) => s + x.weight, 0);
  const score = weight ? Math.round(components.reduce((s, x) => s + x.score * x.weight, 0) / weight) : null;

  const years = [...new Set([...peHistory.map(x => x.year), ...pbHistory.map(x => x.year)])].sort();
  const timeline = years.map(year => {
    const peItem = peHistory.find(x => x.year === year);
    const pbItem = pbHistory.find(x => x.year === year);
    const parts = [];
    if (peItem && peMedian != null) parts.push({ score: relativeScore(peItem.value, peMedian), weight: lens.weights.pe });
    if (pbItem && pbMedian != null) parts.push({ score: relativeScore(pbItem.value, pbMedian), weight: lens.weights.pb });
    const w = parts.reduce((s, x) => s + x.weight, 0);
    return w ? { year, score: Math.round(parts.reduce((s, x) => s + x.score * x.weight, 0) / w) } : null;
  }).filter(Boolean).slice(-8);

  const label = score == null ? "Insufficient history" : score >= 65 ? "Relatively lower valuation" : score >= 45 ? "Near own historical range" : "Relatively higher valuation";
  const drivers = components.map(c => `${c.name} is ${relation(c.current, c.median).toLowerCase()}.`);
  return { lens, score, label, components, timeline, drivers };
}

function scoreClass(score) {
  return score == null ? "neutral" : score >= 65 ? "lower" : score >= 45 ? "mid" : "higher";
}

function renderRing(score, label) {
  const value = score == null ? 0 : score;
  return `<div class="stock-valuation-ring ${scoreClass(score)}" style="--valuation-score:${value * 3.6}deg"><div class="stock-valuation-ring-inner"><strong>${score == null ? "—" : score}</strong><span>/100</span><small>${vEsc(label)}</small></div></div>`;
}

function renderTimeline(points) {
  if (!points.length) return `<div class="stock-valuation-empty">Not enough historical P/E or P/B observations to reconstruct valuation context.</div>`;
  const first = points[0], last = points.at(-1), delta = last.score - first.score;
  const direction = delta >= 5 ? "↗ Lower relative valuation" : delta <= -5 ? "↘ Higher relative valuation" : "→ Broadly stable";
  const bars = points.map(p => `<div class="stock-valuation-point ${scoreClass(p.score)}" tabindex="0" title="${vEsc(p.year)}: ${p.score} / 100"><div class="stock-valuation-point-score">${p.score}</div><div class="stock-valuation-point-bar" style="height:${Math.max(10, p.score)}%"></div><small>${vEsc(p.year)}</small></div>`).join("");
  return `<div class="stock-valuation-timeline"><div class="stock-valuation-timeline-head"><div><h3>Valuation Trend Timeline <span class="stock-valuation-info" tabindex="0" aria-label="How the valuation timeline is calculated">i</span><span class="stock-valuation-tooltip stock-valuation-timeline-tooltip" role="tooltip">The Valuation Context score shown above is the current/latest score. This timeline reconstructs the same sector-aware P/E/P/B scoring framework at earlier historical points, using the company's own available historical median as the reference. 50 represents the company's own median; higher means a lower relative multiple and lower means a higher relative multiple.</span></h3><p>Historical reconstruction · Higher score = lower relative valuation</p></div><span class="stock-valuation-direction ${scoreClass(last.score)}">${direction}</span></div><div class="stock-valuation-chart">${bars}</div><div class="stock-valuation-timeline-foot"><span>${vEsc(first.year)} · ${first.score}</span><strong>Latest ${last.score}</strong><span>${vEsc(last.year)}</span></div></div>`;
}

function render(f, charts, details) {
  details?.querySelector(".stock-valuation-engine")?.remove();
  const valuation = buildValuation(f, charts);
  const components = valuation.components.length ? valuation.components.map(c => `<div class="stock-valuation-component"><div class="stock-valuation-component-head"><span>${vEsc(c.name)} <span class="stock-valuation-info" tabindex="0" aria-label="How ${vEsc(c.name)} is calculated">i</span><span class="stock-valuation-tooltip" role="tooltip">The current ${c.key === "pe" ? "P/E" : "P/B"} is compared with this company's own historical median. A score of 50 equals the median. Lower valuation multiples produce higher valuation-context scores.</span></span><strong>${c.current.toFixed(1)}x</strong></div><div class="stock-valuation-track"><span style="width:${c.score}%"></span></div><small>${vEsc(relation(c.current, c.median))} · historical median ${c.median.toFixed(1)}x</small></div>`).join("") : `<div class="stock-valuation-empty">No reliable historical P/E or P/B series is available.</div>`;
  const drivers = valuation.drivers.length ? valuation.drivers.map(x => `<li>${vEsc(x)}</li>`).join("") : "<li>Insufficient historical valuation observations.</li>";
  const section = document.createElement("section");
  section.className = "stock-section stock-valuation-engine";
  section.innerHTML = `<div class="stock-valuation-header"><div class="stock-valuation-copy"><div class="stock-valuation-eyebrow">SECTOR-AWARE ENGINE</div><h2>Valuation Context <span class="stock-valuation-info" tabindex="0" aria-label="How Valuation Context is calculated">i</span><span class="stock-valuation-tooltip stock-valuation-header-tooltip" role="tooltip">This is a relative valuation-context measure, not a cheap/expensive verdict. The score combines available P/E and P/B context against the company's own historical medians. Weighting changes by sector lens. 50 means approximately the company's own historical median valuation.</span></h2><p>How the current market valuation compares with this company's own history.</p><div class="stock-valuation-lens"><strong>${vEsc(valuation.lens.name)}</strong><span>${vEsc(valuation.lens.explanation)}</span></div></div>${renderRing(valuation.score, valuation.label)}</div><div class="stock-valuation-components">${components}</div>${renderTimeline(valuation.timeline)}<div class="stock-valuation-drivers"><h3>What the valuation is telling you</h3><ul>${drivers}</ul><small>Historical context only; this engine does not forecast returns or make an investment recommendation.</small></div>`;
  const momentum = details.querySelector(".stock-fundamental-momentum");
  if (momentum) momentum.insertAdjacentElement("afterend", section); else details.appendChild(section);
}

function addStyles() {
  if (document.getElementById("stock-valuation-engine-styles")) return;
  const style = document.createElement("style");
  style.id = "stock-valuation-engine-styles";
  style.textContent = `
.stock-valuation-engine{margin-top:18px;overflow:visible}.stock-valuation-header{display:flex;justify-content:space-between;align-items:center;gap:24px;padding:4px 2px 16px;border-bottom:1px solid #e2e8f0}.stock-valuation-copy{min-width:0}.stock-valuation-eyebrow{font-size:9px;letter-spacing:.1em;font-weight:800;color:#2563eb}.stock-valuation-header h2{margin:3px 0 4px;color:#0f1d35;font-size:18px;position:relative}.stock-valuation-header p{margin:0;color:#64748b;font-size:12px}.stock-valuation-lens{margin-top:10px;max-width:860px;padding:9px 11px;border:1px solid #dbe6f1;border-radius:10px;background:linear-gradient(90deg,#f8fbff,#fff)}.stock-valuation-lens strong{display:block;font-size:10px;color:#17355d}.stock-valuation-lens span{display:block;margin-top:3px;font-size:10px;line-height:1.45;color:#64748b}.stock-valuation-ring{width:124px;height:124px;flex:0 0 124px;border-radius:50%;display:grid;place-items:center;position:relative;background:conic-gradient(#2563eb var(--valuation-score),#e8eef5 0);box-shadow:0 5px 18px rgba(37,99,235,.12)}.stock-valuation-ring::before{content:"";position:absolute;inset:8px;border-radius:50%;background:#fff}.stock-valuation-ring.lower{background:conic-gradient(#16803c var(--valuation-score),#e8eef5 0)}.stock-valuation-ring.higher{background:conic-gradient(#d97706 var(--valuation-score),#e8eef5 0)}.stock-valuation-ring-inner{position:relative;z-index:1;text-align:center}.stock-valuation-ring-inner strong{display:inline-block;font-size:29px;line-height:1;color:#102b4e}.stock-valuation-ring-inner>span{font-size:9px;color:#64748b;font-weight:700}.stock-valuation-ring-inner small{display:block;max-width:92px;margin:5px auto 0;font-size:8px;line-height:1.25;color:#64748b;font-weight:800;text-transform:uppercase}.stock-valuation-components{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin-top:14px}.stock-valuation-component{padding:12px;border:1px solid #dbe6f1;border-radius:11px;background:#fff}.stock-valuation-component-head{display:flex;justify-content:space-between;gap:10px;align-items:center;color:#17355d;font-size:11px;font-weight:700}.stock-valuation-component-head>span{position:relative}.stock-valuation-component-head strong{font-size:15px;color:#0f2748}.stock-valuation-track{height:7px;margin:9px 0 5px;background:#edf2f7;border-radius:99px;overflow:hidden}.stock-valuation-track span{display:block;height:100%;border-radius:99px;background:linear-gradient(90deg,#f59e0b,#2563eb)}.stock-valuation-component small{font-size:9px;color:#64748b}.stock-valuation-info{display:inline-grid;place-items:center;width:14px;height:14px;border:1px solid #91a5bb;border-radius:50%;font-size:9px;color:#315a83;font-weight:800;cursor:help;vertical-align:middle}.stock-valuation-tooltip{display:none;position:absolute;z-index:10000;width:270px;padding:10px 11px;border-radius:9px;background:#10243d;color:#fff;box-shadow:0 10px 25px rgba(15,23,42,.25);font-size:10px;font-weight:500;line-height:1.45;text-align:left}.stock-valuation-info:hover+.stock-valuation-tooltip,.stock-valuation-info:focus+.stock-valuation-tooltip{display:block}.stock-valuation-component-head .stock-valuation-tooltip{left:0;bottom:calc(100% + 8px)}.stock-valuation-header-tooltip,.stock-valuation-timeline-tooltip{left:0;top:calc(100% + 8px)}.stock-valuation-timeline{margin-top:13px;padding:14px;border:1px solid #dbe6f1;border-radius:12px;background:linear-gradient(135deg,#fbfdff,#f6faff);overflow:visible}.stock-valuation-timeline-head{display:flex;justify-content:space-between;align-items:flex-start;gap:14px}.stock-valuation-timeline-head h3{margin:0;color:#17355d;font-size:13px;position:relative}.stock-valuation-timeline-head p{margin:4px 0 0;color:#71849a;font-size:9px}.stock-valuation-direction{padding:6px 9px;border-radius:999px;background:#eef4fb;color:#49627e;font-size:9px;font-weight:800;white-space:nowrap}.stock-valuation-direction.lower{background:#ecfdf3;color:#15803d}.stock-valuation-direction.higher{background:#fff7ed;color:#b45309}.stock-valuation-chart{height:135px;display:flex;align-items:flex-end;gap:10px;margin-top:13px;padding:0 8px;border-bottom:1px solid #dbe4ee}.stock-valuation-point{height:100%;flex:1;min-width:32px;display:flex;flex-direction:column;align-items:center;justify-content:flex-end;gap:5px;outline:none}.stock-valuation-point-score{font-size:8px;font-weight:800;color:#48617d}.stock-valuation-point-bar{width:24px;min-height:10px;border-radius:7px 7px 2px 2px;background:linear-gradient(180deg,#3b82f6,#2563eb);transition:transform .15s ease}.stock-valuation-point:hover .stock-valuation-point-bar,.stock-valuation-point:focus .stock-valuation-point-bar{transform:translateY(-3px)}.stock-valuation-point.lower .stock-valuation-point-bar{background:linear-gradient(180deg,#22c55e,#16a34a)}.stock-valuation-point.higher .stock-valuation-point-bar{background:linear-gradient(180deg,#f2b84b,#d97706)}.stock-valuation-point small{font-size:8px;color:#71849a}.stock-valuation-timeline-foot{display:flex;justify-content:space-between;margin-top:7px;color:#8492a2;font-size:9px}.stock-valuation-timeline-foot strong{color:#17355d}.stock-valuation-drivers{margin-top:12px;padding:12px 14px;border:1px solid #e2e8f0;border-radius:11px;background:#fff}.stock-valuation-drivers h3{margin:0;color:#17355d;font-size:12px}.stock-valuation-drivers ul{margin:7px 0 5px;padding-left:17px;color:#52677f;font-size:10px;line-height:1.6}.stock-valuation-drivers small{color:#94a3b8;font-size:9px}@media(max-width:700px){.stock-valuation-header{align-items:flex-start}.stock-valuation-ring{width:100px;height:100px;flex-basis:100px}.stock-valuation-components{grid-template-columns:1fr}.stock-valuation-timeline-head{flex-direction:column}.stock-valuation-tooltip{width:260px}.stock-valuation-chart{gap:6px}.stock-valuation-point-bar{width:20px}}
`;
  document.head.appendChild(style);
}

let valuationLastSymbol = "";
let valuationLoading = false;

async function loadAndRenderValuation(symbol, details) {
  if (!symbol || valuationLoading) return;
  valuationLoading = true;
  try {
    const encoded = encodeURIComponent(symbol);
    const [analysisResponse, chartsResponse] = await Promise.all([
      fetch(`${VALUATION_API}/${encoded}`, { headers: { Accept: "application/json" } }),
      fetch(`${VALUATION_API}/${encoded}/charts`, { headers: { Accept: "application/json" } }),
    ]);
    if (!analysisResponse.ok || !chartsResponse.ok) throw new Error("Valuation data unavailable");
    const [analysis, chartPayload] = await Promise.all([analysisResponse.json(), chartsResponse.json()]);
    if (valuationLastSymbol === symbol) render(analysis.fundamentals || analysis, chartPayload.charts || chartPayload, details);
  } catch (error) {
    console.warn("Valuation Context unavailable:", error);
  } finally {
    valuationLoading = false;
  }
}

function detectSymbol(details) {
  const eyebrow = details?.querySelector(".stock-eyebrow")?.textContent || "";
  const parts = eyebrow.split(/[·•]/).map(x => x.trim()).filter(Boolean);
  return parts.length > 1 ? parts[1].toUpperCase() : "";
}

function scanValuation() {
  const details = document.getElementById("stock-details");
  if (!details) return;
  const symbol = detectSymbol(details);
  if (!symbol || symbol === valuationLastSymbol) return;
  valuationLastSymbol = symbol;
  loadAndRenderValuation(symbol, details);
}

addStyles();
const valuationObserver = new MutationObserver(scanValuation);
valuationObserver.observe(document.body, { childList: true, subtree: true });
document.addEventListener("DOMContentLoaded", scanValuation);
scanValuation();
