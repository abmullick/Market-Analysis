const API = "/api/stocks/pedigree";

const clamp = (v, lo = 0, hi = 100) => Math.max(lo, Math.min(hi, v));
const num = (v) => Number.isFinite(Number(v)) ? Number(v) : null;
const esc = (v) => String(v ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");

function series(value) {
  return (Array.isArray(value) ? value : [])
    .filter((x) => x && num(x.value) != null)
    .map((x) => ({ year: x.year, value: Number(x.value) }));
}

function average(values) {
  const a = values.filter((v) => num(v) != null).map(Number);
  return a.length ? a.reduce((s, v) => s + v, 0) / a.length : null;
}

function recentAverage(s, count = 3) {
  const a = series(s).slice(-count).map((x) => x.value);
  return average(a);
}

function previousAverage(s, count = 3) {
  const a = series(s);
  if (a.length < count * 2) return null;
  return average(a.slice(-count * 2, -count).map((x) => x.value));
}

function current(s) {
  const a = series(s);
  return a.length ? a.at(-1).value : null;
}

function trendDelta(s, count = 3) {
  const recent = recentAverage(s, count);
  const previous = previousAverage(s, count);
  return recent != null && previous != null ? recent - previous : null;
}

function scoreFromDelta(delta, scale) {
  if (delta == null) return null;
  return clamp(50 + (delta / scale) * 50);
}

function returnScore(trends) {
  const deltas = [];
  for (const key of ["roe", "roce"]) {
    const d = trendDelta(trends[key], 3);
    if (d != null) deltas.push(d);
  }
  return deltas.length ? average(deltas.map((d) => scoreFromDelta(d, 5))) : null;
}

function growthScore(trends) {
  const scores = [];
  for (const key of ["revenue_growth", "profit_growth", "eps_growth"]) {
    const d = trendDelta(trends[key], 3);
    if (d != null) scores.push(scoreFromDelta(d, 8));
  }
  return scores.length ? average(scores) : null;
}

function cashScore(data, financial) {
  if (financial) return consistencyScore(data);
  const scores = [];
  const cashDelta = trendDelta(data.trends?.cash_conversion, 3);
  const fcfDelta = trendDelta(data.trends?.fcf_margin, 3);
  if (cashDelta != null) scores.push(scoreFromDelta(cashDelta, 20));
  if (fcfDelta != null) scores.push(scoreFromDelta(fcfDelta, 5));
  return scores.length ? average(scores) : null;
}

function disciplineScore(data, financial) {
  if (financial) {
    const shareGrowth = num(data.dilution?.share_count_cagr_5y ?? data.dilution?.share_count_cagr_3y);
    if (shareGrowth == null) return null;
    return clamp(80 - Math.max(0, shareGrowth * 100 - 1) * 12);
  }
  const scores = [];
  const debtDelta = trendDelta(data.trends?.debt, 3);
  const deDelta = trendDelta(data.trends?.debt_equity, 3);
  if (debtDelta != null) {
    const base = Math.max(Math.abs(recentAverage(data.trends?.debt, 3) || 1), 1);
    scores.push(clamp(50 - (debtDelta / base) * 100));
  }
  if (deDelta != null) {
    const base = Math.max(Math.abs(recentAverage(data.trends?.debt_equity, 3) || 1), 0.25);
    scores.push(clamp(50 - (deDelta / base) * 100));
  }
  return scores.length ? average(scores) : null;
}

function consistencyScore(data) {
  const c = data.consistency || {};
  const growth = [c.revenue?.positive_growth_pct, c.profit?.positive_growth_pct, c.fcf?.positive_growth_pct]
    .filter((v) => num(v) != null)
    .map(Number);
  const growthScoreValue = growth.length ? average(growth) : null;
  const roeVol = num(c.roe_volatility);
  const roeScore = roeVol == null ? null : clamp(100 - roeVol * 10);
  const values = [growthScoreValue, roeScore].filter((v) => v != null);
  return values.length ? average(values) : null;
}

function momentum(data = {}) {
  const trends = data.trends || {};
  const financial = /financial|bank|nbfc|insurance/i.test(`${data.sector || ""} ${data.industry || ""}`);
  const components = [
    ["Growth momentum", growthScore(trends), 0.30, "Change in recent revenue, profit and EPS growth"],
    ["Return momentum", returnScore(trends), 0.25, "Recent ROE/ROCE trajectory versus the preceding period"],
    [financial ? "Earnings consistency" : "Cash conversion", cashScore(data, financial), 0.20, financial ? "Consistency of reported earnings growth" : "Change in cash conversion and FCF margin"],
    [financial ? "Share discipline" : "Balance-sheet discipline", disciplineScore(data, financial), 0.15, financial ? "Implied share-count stability" : "Direction of debt and debt/equity"],
    ["Business consistency", consistencyScore(data), 0.10, "Persistence of growth and stability of returns"],
  ];

  const available = components.filter(([, score]) => score != null);
  const weight = available.reduce((s, [, , w]) => s + w, 0);
  const score = weight ? available.reduce((s, [, value, w]) => s + value * w, 0) / weight : null;
  const label = score == null ? "Insufficient history" : score >= 65 ? "Strengthening" : score >= 45 ? "Stable" : "Weakening";

  const observations = [];
  const ranked = available.slice().sort((a, b) => b[1] - a[1]);
  const top = ranked[0];
  const bottom = ranked.at(-1);
  if (top) observations.push(`${top[0]} is the strongest part of the current trajectory.`);
  if (bottom && bottom !== top) observations.push(`${bottom[0]} is the main area of pressure in the current trajectory.`);

  const growthConsistency = average([
    data.consistency?.revenue?.positive_growth_pct,
    data.consistency?.profit?.positive_growth_pct,
    data.consistency?.fcf?.positive_growth_pct,
  ].filter((v) => num(v) != null).map(Number));
  if (growthConsistency != null) {
    observations.push(`Growth has been positive in ${growthConsistency.toFixed(0)}% of the available annual observations.`);
  }

  return {
    score: score == null ? null : Math.round(score),
    label,
    financial_sector: financial,
    components: components.map(([name, value, weightValue, note]) => ({ name, score: value == null ? null : Math.round(value), weight: weightValue, note })),
    observations: observations.slice(0, 3),
  };
}

function scoreClass(score) {
  if (score == null) return "neutral";
  if (score >= 65) return "strong";
  if (score >= 45) return "stable";
  return "weak";
}

function render(data, details) {
  if (!details) return;
  details.querySelector(".stock-fundamental-signals")?.remove();
  details.querySelector(".stock-fundamental-momentum")?.remove();

  const m = momentum(data);
  const componentHtml = m.components.map((c) => `
    <div class="stock-momentum-component">
      <div class="stock-momentum-component-head"><span>${esc(c.name)}</span><strong>${c.score == null ? "—" : c.score}</strong></div>
      <div class="stock-momentum-bar"><span style="width:${c.score == null ? 0 : c.score}%"></span></div>
      <small>${esc(c.note)}</small>
    </div>`).join("");

  const observationHtml = m.observations.length
    ? m.observations.map((x) => `<li>${esc(x)}</li>`).join("")
    : "<li>Insufficient historical observations for a meaningful trajectory.</li>";

  const section = document.createElement("section");
  section.className = "stock-section stock-fundamental-momentum";
  section.innerHTML = `
    <div class="stock-momentum-header">
      <div>
        <h2>Fundamental Momentum</h2>
        <p>Engine-calculated view of how the business trajectory is changing, using growth, returns, cash/earnings quality, financial discipline and consistency.</p>
      </div>
      <div class="stock-momentum-index ${scoreClass(m.score)}">
        <span>Momentum Index</span>
        <strong>${m.score == null ? "—" : m.score}</strong>
        <small>${esc(m.label)}</small>
      </div>
    </div>
    <div class="stock-momentum-grid">${componentHtml}</div>
    <div class="stock-momentum-observations">
      <h3>What changed</h3>
      <ul>${observationHtml}</ul>
      <small>The index describes historical trajectory; it is not a forecast or an investment recommendation.</small>
    </div>`;

  const anchor = details.querySelector(".stock-summary-grid") || details.querySelector(".stock-hero");
  if (anchor) anchor.insertAdjacentElement("afterend", section);
  else details.prepend(section);
}

async function load() {
  const details = document.getElementById("stock-details");
  if (!details) return;
  const params = new URLSearchParams(location.search);
  const symbol = (params.get("symbol") || "").trim().toUpperCase();
  if (!symbol) return;
  try {
    const response = await fetch(`${API}/${encodeURIComponent(symbol)}`, { cache: "no-store", headers: { Accept: "application/json" } });
    if (!response.ok) return;
    render(await response.json(), details);
  } catch (error) {
    console.warn("Fundamental momentum unavailable:", error);
  }
}

function addStyles() {
  if (document.getElementById("stock-fundamental-momentum-styles")) return;
  const style = document.createElement("style");
  style.id = "stock-fundamental-momentum-styles";
  style.textContent = `
    .stock-fundamental-momentum{margin-top:18px}
    .stock-momentum-header{display:flex;justify-content:space-between;align-items:center;gap:18px;padding-bottom:14px;border-bottom:1px solid #e2e8f0}
    .stock-momentum-header h2{margin:0;color:#0f1d35;font-size:18px}
    .stock-momentum-header p{margin:5px 0 0;color:#64748b;font-size:12px;line-height:1.5;max-width:760px}
    .stock-momentum-index{min-width:130px;padding:10px 14px;border:1px solid #dbe6f1;border-radius:12px;background:#fff;text-align:center}
    .stock-momentum-index span{display:block;color:#64748b;font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:.06em}
    .stock-momentum-index strong{display:block;margin-top:2px;color:#0f2748;font-size:28px;line-height:1.1}
    .stock-momentum-index small{display:block;margin-top:3px;font-weight:700;font-size:10px}
    .stock-momentum-index.strong small{color:#16803c}.stock-momentum-index.stable small{color:#9a6700}.stock-momentum-index.weak small{color:#c0392b}.stock-momentum-index.neutral small{color:#64748b}
    .stock-momentum-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin-top:14px}
    .stock-momentum-component{padding:12px;border:1px solid #dbe6f1;border-radius:11px;background:#fff}
    .stock-momentum-component-head{display:flex;justify-content:space-between;align-items:center;color:#17355d;font-size:12px;font-weight:700}
    .stock-momentum-component-head strong{font-size:15px;color:#0f2748;font-variant-numeric:tabular-nums}
    .stock-momentum-bar{height:6px;margin:8px 0 6px;background:#edf2f7;border-radius:99px;overflow:hidden}.stock-momentum-bar span{display:block;height:100%;background:#2563eb;border-radius:99px}
    .stock-momentum-component small{color:#7a8aa0;font-size:10px;line-height:1.35}
    .stock-momentum-observations{margin-top:12px;padding:12px 14px;border:1px solid #dbe6f1;border-radius:11px;background:#fff}
    .stock-momentum-observations h3{margin:0 0 6px;color:#17355d;font-size:13px}.stock-momentum-observations ul{margin:0;padding-left:18px;color:#475569;font-size:12px;line-height:1.55}.stock-momentum-observations small{display:block;margin-top:7px;color:#7a8aa0;font-size:10px}
    @media(max-width:700px){.stock-momentum-header{align-items:flex-start;flex-direction:column}.stock-momentum-index{width:100%;box-sizing:border-box}.stock-momentum-grid{grid-template-columns:1fr}}
  `;
  document.head.appendChild(style);
}

function init() {
  addStyles();
  const details = document.getElementById("stock-details");
  if (!details) return;
  const observer = new MutationObserver(() => {
    if (details.querySelector(".stock-hero") && !details.querySelector(".stock-fundamental-momentum")) load();
  });
  observer.observe(details, { childList: true, subtree: true });
  setTimeout(load, 250);
}

if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init, { once: true });
else init();
