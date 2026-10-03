const API_BASE = "/api/stocks";

const n = (v) => Number.isFinite(Number(v)) ? Number(v) : null;
const clamp = (v) => Math.max(0, Math.min(100, Number(v)));
const avg = (a) => a.length ? a.reduce((s, v) => s + v, 0) / a.length : null;
const esc = (v) => String(v ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");

function median(values) {
  const a = values.filter(Number.isFinite).sort((x, y) => x - y);
  if (!a.length) return null;
  const m = Math.floor(a.length / 2);
  return a.length % 2 ? a[m] : (a[m - 1] + a[m]) / 2;
}

function sectorLens(core) {
  const text = `${core?.sector || ""} ${core?.industry || ""}`.toLowerCase();
  if (/financial services|bank|nbfc|insurance|capital markets|credit/.test(text)) {
    return {
      type: "Financial",
      title: "Financial-services valuation lens",
      weights: { pe: 0.30, pb: 0.70 },
      metrics: "P/E and P/B",
      explanation: "For financial companies, P/B receives the larger weight because book value and returns on equity are central to the economics of banks, lenders and insurers. P/E remains a secondary cross-check."
    };
  }
  if (/real estate|reit|infrastructure|utilities|telecom/.test(text)) {
    return {
      type: "Capital-intensive",
      title: "Capital-intensive valuation lens",
      weights: { pe: 0.35, pb: 0.25 },
      metrics: "P/E and P/B",
      explanation: "For capital-intensive businesses, P/E remains the primary lens, with P/B as a supporting measure. EV/EBITDA is shown separately in the underlying financial data where available, but the historical engine uses the multiples with a reliable time series."
    };
  }
  return {
    type: "Operating business",
    title: "Operating-business valuation lens",
    weights: { pe: 0.70, pb: 0.30 },
    metrics: "P/E and P/B",
    explanation: "For most operating businesses, P/E receives the larger weight because earnings are the primary valuation anchor. P/B is retained as a secondary cross-check."
  };
}

function historicalValues(series) {
  return (Array.isArray(series) ? series : [])
    .map(x => ({ year: String(x.year), value: n(x.value) }))
    .filter(x => x.value != null && x.value > 0);
}

function relativeScore(current, historicalMedian) {
  if (current == null || historicalMedian == null || historicalMedian <= 0) return null;
  // 50 = own historical median. Lower multiples receive higher context scores.
  return clamp(50 - ((current / historicalMedian) - 1) * 100);
}

function currentMultiple(core, key) {
  return n(core?.[key]);
}

export function buildValuation(core, charts) {
  const lens = sectorLens(core);
  const peHistory = historicalValues(charts?.pe_history);
  const pbHistory = historicalValues(charts?.pb_history);
  const pe = currentMultiple(core, "pe");
  const pb = currentMultiple(core, "pb");
  const peMedian = median(peHistory.map(x => x.value));
  const pbMedian = median(pbHistory.map(x => x.value));
  const peScore = relativeScore(pe, peMedian);
  const pbScore = relativeScore(pb, pbMedian);
  const components = [];
  if (peScore != null) components.push({ key: "pe", label: "P/E context", score: peScore, weight: lens.weights.pe, current: pe, median: peMedian });
  if (pbScore != null) components.push({ key: "pb", label: "P/B context", score: pbScore, weight: lens.weights.pb, current: pb, median: pbMedian });
  const weight = components.reduce((s, x) => s + x.weight, 0);
  const score = weight ? Math.round(components.reduce((s, x) => s + x.score * x.weight, 0) / weight) : null;
  const label = score == null ? "Insufficient history" : score >= 65 ? "Below own historical range" : score >= 45 ? "Near own historical range" : "Above own historical range";

  const timelineYears = [...new Set([...peHistory.map(x => x.year), ...pbHistory.map(x => x.year)])].sort();
  const timeline = timelineYears.map(year => {
    const peItem = peHistory.find(x => x.year === year);
    const pbItem = pbHistory.find(x => x.year === year);
    const parts = [];
    if (peItem && peMedian != null) parts.push({ score: relativeScore(peItem.value, peMedian), weight: lens.weights.pe });
    if (pbItem && pbMedian != null) parts.push({ score: relativeScore(pbItem.value, pbMedian), weight: lens.weights.pb });
    const w = parts.reduce((s, x) => s + x.weight, 0);
    if (!w) return null;
    return { year, score: Math.round(parts.reduce((s, x) => s + x.score * x.weight, 0) / w) };
  }).filter(Boolean).slice(-8);

  const drivers = [];
  components.forEach(c => {
    if (c.current == null || c.median == null) return;
    const diff = ((c.current / c.median) - 1) * 100;
    const direction = diff > 5 ? "above" : diff < -5 ? "below" : "near";
    drivers.push(`${c.label} is ${Math.abs(diff).toFixed(0)}% ${direction} its historical median.`);
  });
  return { lens, score, label, components, timeline, drivers, peMedian, pbMedian };
}

function scoreClass(score) {
  return score == null ? "neutral" : score >= 65 ? "favourable" : score >= 45 ? "neutral" : "elevated";
}

function scoreRing(score) {
  const value = score == null ? 0 : score;
  const cls = scoreClass(score);
  return `<div class="stock-valuation-ring ${cls}" style="--valuation-p:${value * 3.6}deg"><div><strong>${score == null ? "—" : score}</strong><small>Valuation Context</small></div></div>`;
}

function renderTimeline(points) {
  if (!points.length) return `<div class="stock-valuation-empty">Not enough historical valuation observations to reconstruct the timeline.</div>`;
  return `<div class="stock-valuation-timeline"><div class="stock-valuation-timeline-head"><div><h3>Valuation Trend Timeline <span class="stock-valuation-info" tabindex="0" aria-label="How the valuation timeline is calculated">i</span><span class="stock-valuation-tooltip" role="tooltip">Each historical point reconstructs the same sector-aware valuation context using that year's P/E and/or P/B and the company's full available historical median. 50 represents the company's own median; higher means a lower relative multiple and lower means a higher relative multiple.</span></h3><p>Historical valuation context · Higher = lower relative valuation</p></div><span>Historical → Recent</span></div><div class="stock-valuation-timeline-chart">${points.map(p => { const cls = scoreClass(p.score); return `<div class="stock-valuation-point ${cls}" tabindex="0"><div class="stock-valuation-score">${p.score}</div><div class="stock-valuation-bar" style="height:${Math.max(8, p.score)}%"></div><b>${esc(p.year)}</b></div>`; }).join("")}</div></div>`;
}

function render(core, charts, details) {
  details?.querySelector(".stock-valuation-engine")?.remove();
  if (!details || !core || !charts) return;
  const valuation = buildValuation(core, charts);
  const cls = scoreClass(valuation.score);
  const components = valuation.components.map(c => {
    const diff = c.current != null && c.median != null ? ((c.current / c.median) - 1) * 100 : null;
    const relation = diff == null ? "Insufficient history" : Math.abs(diff) <= 5 ? "Near median" : diff < 0 ? `${Math.abs(diff).toFixed(0)}% below median` : `${diff.toFixed(0)}% above median`;
    return `<div class="stock-valuation-component"><div><span>${esc(c.label)} <span class="stock-valuation-info" tabindex="0" aria-label="How ${esc(c.label)} is calculated">i</span><span class="stock-valuation-tooltip" role="tooltip">The current ${c.key === "pe" ? "P/E" : "P/B"} is compared with the company's own historical median. 50 is the median; lower valuation multiples produce a higher context score.</span></span><strong>${c.current == null ? "—" : `${c.current.toFixed(1)}x`}</strong></div><div class="stock-valuation-track"><span style="width:${c.score}%"></span></div><small>${esc(relation)} · historical median ${c.median == null ? "—" : `${c.median.toFixed(1)}x`}</small></div>`;
  }).join("");
  const driverText = valuation.drivers.length ? valuation.drivers.map(x => `<li>${esc(x)}</li>`).join("") : "<li>Insufficient historical valuation data.</li>";
  const section = document.createElement("section");
  section.className = "stock-section stock-valuation-engine";
  section.innerHTML = `<div class="stock-valuation-header"><div><div class="stock-valuation-eyebrow">SECTOR-AWARE ENGINE</div><h2>Valuation Context</h2><p>Engine-calculated view of the stock's current valuation relative to its own historical valuation range.</p><div class="stock-valuation-lens"><strong>${esc(valuation.lens.title)}</strong><span>${esc(valuation.lens.metrics)} · ${esc(valuation.lens.explanation)}</span></div></div>${scoreRing(valuation.score)}</div><div class="stock-valuation-components">${components || `<div class="stock-valuation-empty">No reliable historical P/E or P/B series is available.</div>`}</div>${renderTimeline(valuation.timeline)}<div class="stock-valuation-drivers"><h3>What the valuation is telling you <span class="stock-valuation-info" tabindex="0" aria-label="How Valuation Context is calculated">i</span><span class="stock-valuation-tooltip stock-valuation-driver-tooltip" role="tooltip">The current score is a weighted average of the available P/E and P/B context scores. Weights change by sector lens. 50 means the stock is around its own historical median valuation; higher means lower relative valuation and lower means higher relative valuation. This is a valuation-context measure, not a forecast or investment recommendation.</span></h3><ul>${driverText}</ul></div>`;
  const momentum = details.querySelector(".stock-fundamental-momentum");
  if (momentum) momentum.insertAdjacentElement("afterend", section);
  else {
    const anchor = details.querySelector(".stock-summary-grid") || details.querySelector(".stock-hero");
    if (anchor) anchor.insertAdjacentElement("afterend", section); else details.prepend(section);
  }
}

function addStyles() {
  if (document.getElementById("stock-valuation-engine-styles")) return;
  const style = document.createElement("style");
  style.id = "stock-valuation-engine-styles";
  style.textContent = `.stock-valuation-engine{margin-top:18px}.stock-valuation-header{display:flex;justify-content:space-between;gap:22px;align-items:center;padding-bottom:15px;border-bottom:1px solid #e2e8f0}.stock-valuation-eyebrow{font-size:9px;letter-spacing:.09em;font-weight:800;color:#2563eb}.stock-valuation-header h2{margin:2px 0 4px;color:#0f1d35;font-size:18px}.stock-valuation-header p{margin:0;color:#64748b;font-size:12px}.stock-valuation-lens{margin-top:10px;display:flex;flex-direction:column;gap:3px;max-width:820px;padding:9px 11px;border:1px solid #dbe6f1;border-radius:10px;background:linear-gradient(90deg,#f8fbff,#fff)}.stock-valuation-lens strong{font-size:11px;color:#17355d}.stock-valuation-lens span{font-size:10px;line-height:1.45;color:#64748b}.stock-valuation-ring{--valuation-p:0deg;width:116px;height:116px;border-radius:50%;display:grid;place-items:center;flex:0 0 auto;background:conic-gradient(#2563eb var(--valuation-p),#e8eef5 0);position:relative}.stock-valuation-ring:after{content:"";position:absolute;inset:8px;border-radius:50%;background:#fff}.stock-valuation-ring>div{position:relative;z-index:1;text-align:center}.stock-valuation-ring strong{display:block;font-size:27px;line-height:1;color:#0f2748}.stock-valuation-ring small{display:block;margin-top:4px;font-size:8px;font-weight:800;color:#64748b;text-transform:uppercase;letter-spacing:.05em}.stock-valuation-ring.favourable{background:conic-gradient(#16803c var(--valuation-p),#e8eef5 0)}.stock-valuation-ring.elevated{background:conic-gradient(#d97706 var(--valuation-p),#e8eef5 0)}.stock-valuation-components{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin-top:14px}.stock-valuation-component{padding:12px;border:1px solid #dbe6f1;border-radius:11px;background:#fff}.stock-valuation-component>div:first-child{display:flex;justify-content:space-between;align-items:center;font-size:11px;font-weight:700;color:#17355d}.stock-valuation-component strong{font-size:15px;color:#0f2748}.stock-valuation-component>div:first-child>span{position:relative}.stock-valuation-track{height:7px;background:#edf2f7;border-radius:99px;margin:9px 0 5px;overflow:hidden}.stock-valuation-track span{display:block;height:100%;border-radius:99px;background:linear-gradient(90deg,#f59e0b,#2563eb)}.stock-valuation-component small{font-size:9px;color:#64748b}.stock-valuation-info{display:inline-grid;place-items:center;width:14px;height:14px;border:1px solid #94a3b8;border-radius:50%;font-size:9px;color:#2563eb;cursor:help;position:relative;vertical-align:middle}.stock-valuation-tooltip{display:none;position:absolute;z-index:10000;left:50%;bottom:calc(100% + 9px);transform:translateX(-50%);width:250px;padding:10px 11px;border-radius:8px;background:#10243d;color:#fff;box-shadow:0 8px 24px rgba(15,23,42,.22);font-size:10px;font-weight:500;line-height:1.45;text-align:left}.stock-valuation-info:hover+.stock-valuation-tooltip,.stock-valuation-info:focus+.stock-valuation-tooltip{display:block}.stock-valuation-timeline{margin-top:13px;padding:14px;border:1px solid #dbe6f1;border-radius:11px;background:linear-gradient(180deg,#fbfdff,#fff)}.stock-valuation-timeline-head{display:flex;justify-content:space-between;gap:12px;align-items:end}.stock-valuation-timeline-head h3{margin:0;font-size:13px;color:#17355d}.stock-valuation-timeline-head p{margin:4px 0 0;font-size:9px;color:#64748b}.stock-valuation-timeline-head>span{font-size:9px;color:#94a3b8}.stock-valuation-timeline-head h3> .stock-valuation-info{margin-left:4px}.stock-valuation-timeline-chart{height:155px;display:flex;align-items:end;gap:10px;padding:12px 5px 0;border-bottom:1px solid #e2e8f0}.stock-valuation-point{height:100%;flex:1;min-width:30px;display:flex;flex-direction:column;align-items:center;justify-content:end;outline:none}.stock-valuation-score{font-size:9px;font-weight:800;color:#475569;margin-bottom:3px}.stock-valuation-bar{width:min(30px,70%);min-height:8px;border-radius:7px 7px 2px 2px;background:#2563eb;transition:height .2s ease,transform .2s ease}.stock-valuation-point.favourable .stock-valuation-bar{background:#16803c}.stock-valuation-point.elevated .stock-valuation-bar{background:#d97706}.stock-valuation-point:hover .stock-valuation-bar,.stock-valuation-point:focus .stock-valuation-bar{transform:scaleX(1.12);box-shadow:0 3px 10px rgba(37,99,235,.18)}.stock-valuation-point b{font-size:9px;color:#475569;margin-top:5px}.stock-valuation-drivers{margin-top:13px;padding:12px 14px;border-radius:11px;background:#f7faff;border:1px solid #dbe6f1}.stock-valuation-drivers h3{margin:0 0 7px;font-size:12px;color:#17355d;position:relative}.stock-valuation-drivers ul{margin:0;padding-left:17px;color:#475569;font-size:10px;line-height:1.7}.stock-valuation-empty{padding:15px;border:1px dashed #cbd5e1;border-radius:10px;color:#64748b;font-size:10px}.stock-valuation-driver-tooltip{left:0;transform:none;width:290px}.stock-valuation-drivers h3>.stock-valuation-info:hover+.stock-valuation-driver-tooltip,.stock-valuation-drivers h3>.stock-valuation-info:focus+.stock-valuation-driver-tooltip{display:block}@media(max-width:760px){.stock-valuation-header{align-items:flex-start}.stock-valuation-components{grid-template-columns:1fr}.stock-valuation-ring{width:96px;height:96px}.stock-valuation-ring strong{font-size:23px}.stock-valuation-timeline-chart{gap:5px}.stock-valuation-bar{width:22px}}`;
  document.head.appendChild(style);
}

async function loadJson(url) {
  const r = await fetch(url, { headers: { Accept: "application/json", "X-Stock-Valuation-Request": "engine" }, cache: "no-store" });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

async function renderEngine() {
  if (new URLSearchParams(location.search).get("compare")) return;
  const symbol = (new URLSearchParams(location.search).get("symbol") || "").trim().toUpperCase();
  const details = document.querySelector("#stock-analysis-details") || document.querySelector(".stock-analysis-details") || document.querySelector("main");
  if (!symbol || !details || details.dataset.valuationEngine === "done" || details.dataset.valuationEngine === "loading") return;
  details.dataset.valuationEngine = "loading";
  try {
    const [core, charts] = await Promise.all([
      loadJson(`${API_BASE}/${encodeURIComponent(symbol)}`),
      loadJson(`${API_BASE}/${encodeURIComponent(symbol)}/charts`),
    ]);
    render(core, charts, details);
    details.dataset.valuationEngine = "done";
  } catch (error) {
    delete details.dataset.valuationEngine;
    console.warn("Sector-aware valuation engine unavailable:", error);
  }
}

addStyles();
const observer = new MutationObserver(renderEngine);
observer.observe(document.body, { childList: true, subtree: true });
document.addEventListener("DOMContentLoaded", renderEngine);
renderEngine();
