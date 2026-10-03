const num = (v) => Number.isFinite(Number(v)) ? Number(v) : null;
const esc = (v) => String(v ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");
const clamp = (v) => Math.max(0, Math.min(100, v));

function vals(s) { return (Array.isArray(s) ? s : []).filter(x => x && num(x.value) != null).map(x => Number(x.value)); }
function avg(a) { return a.length ? a.reduce((s, v) => s + v, 0) / a.length : null; }
function recent(s, n = 3) { return avg(vals(s).slice(-n)); }
function previous(s, n = 3) { const a = vals(s); return a.length >= n * 2 ? avg(a.slice(-n * 2, -n)) : null; }
function delta(s, n = 3) { const r = recent(s, n), p = previous(s, n); return r != null && p != null ? r - p : null; }
function score(d, scale) { return d == null ? null : clamp(50 + d / scale * 50); }
function consistency(data) {
  const c = data.consistency || {};
  const growth = [c.revenue?.positive_growth_pct, c.profit?.positive_growth_pct, c.fcf?.positive_growth_pct].filter(v => num(v) != null).map(Number);
  const stability = num(c.roe_volatility) == null ? null : clamp(100 - Number(c.roe_volatility) * 10);
  return avg([avg(growth), stability].filter(v => v != null));
}

function buildMomentum(data, financial) {
  const t = data.trends || {};
  const growth = avg(["revenue_growth", "profit_growth", "eps_growth"].map(k => score(delta(t[k]), 8)).filter(v => v != null));
  const returns = avg(["roe", "roce"].map(k => score(delta(t[k]), 5)).filter(v => v != null));
  const quality = financial ? consistency(data) : avg([score(delta(t.cash_conversion), 20), score(delta(t.fcf_margin), 5)].filter(v => v != null));
  let discipline = null;
  if (financial) {
    const shares = num(data.dilution?.share_count_cagr_5y ?? data.dilution?.share_count_cagr_3y);
    if (shares != null) discipline = clamp(80 - Math.max(0, shares * 100 - 1) * 12);
  } else {
    const debt = delta(t.debt), de = delta(t.debt_equity);
    const debtBase = Math.max(Math.abs(recent(t.debt) || 1), 1), deBase = Math.max(Math.abs(recent(t.debt_equity) || 1), .25);
    discipline = avg([debt == null ? null : clamp(50 - debt / debtBase * 100), de == null ? null : clamp(50 - de / deBase * 100)].filter(v => v != null));
  }
  const components = [
    ["Growth momentum", growth, .30, "Recent revenue, profit and EPS growth versus the preceding period", "Compares the latest 3-year average of revenue growth, profit growth and EPS growth with the preceding 3-year average. Each change is converted to a 0–100 score and the available scores are averaged. Higher means growth is accelerating; lower means it is weakening."],
    ["Return momentum", returns, .25, "Recent ROE/ROCE trajectory versus the preceding period", "Compares the latest 3-year average ROE and ROCE with the preceding 3-year average. Each change is converted to a 0–100 score. Higher means returns on capital are improving; lower means they are deteriorating."],
    [financial ? "Earnings consistency" : "Cash conversion", quality, .20, financial ? "Persistence of earnings growth" : "Recent cash conversion and FCF-margin trajectory", financial ? "Combines the percentage of annual observations with positive revenue, profit and free-cash-flow growth with ROE stability. More persistent growth and lower ROE volatility produce a higher score." : "Compares the latest 3-year average cash conversion and FCF margin with the preceding 3-year average. The resulting component scores are averaged, with higher values indicating improving cash generation relative to reported earnings."],
    [financial ? "Share discipline" : "Balance-sheet discipline", discipline, .15, financial ? "Historical share-count stability" : "Direction of debt and debt/equity", financial ? "Uses historical share-count CAGR. Stable or declining share count scores higher; material share-count expansion reduces the score because it indicates greater dilution." : "Measures the direction of debt and debt/equity over the recent period relative to their recent levels. Lower or declining leverage scores higher; rising leverage reduces the score."],
    ["Business consistency", consistency(data), .10, "Persistence of growth and stability of returns", "Combines the available growth-persistence measures with the ROE-stability measure. A higher score indicates that positive growth and returns have been more persistent and less volatile."],
  ];
  const available = components.filter(([, v]) => v != null), weight = available.reduce((s, [, , w]) => s + w, 0);
  const index = weight ? available.reduce((s, [, v, w]) => s + v * w, 0) / weight : null;
  const label = index == null ? "Insufficient history" : index >= 65 ? "Strengthening" : index >= 45 ? "Stable" : "Weakening";
  const ranked = available.slice().sort((a, b) => b[1] - a[1]), observations = [];
  if (ranked[0]) observations.push(`${ranked[0][0]} is the strongest part of the current trajectory.`);
  if (ranked.at(-1) && ranked.at(-1) !== ranked[0]) observations.push(`${ranked.at(-1)[0]} is the main area of pressure in the current trajectory.`);
  const growthConsistency = avg([data.consistency?.revenue?.positive_growth_pct, data.consistency?.profit?.positive_growth_pct, data.consistency?.fcf?.positive_growth_pct].filter(v => num(v) != null).map(Number));
  if (growthConsistency != null) observations.push(`Growth has been positive in ${growthConsistency.toFixed(0)}% of available annual observations.`);
  return { index: index == null ? null : Math.round(index), label, components, observations: observations.slice(0, 3) };
}

function render(data, details) {
  details?.querySelector(".stock-fundamental-signals")?.remove();
  details?.querySelector(".stock-fundamental-momentum")?.remove();
  if (!details) return;
  const context = details.querySelector(".stock-hero p")?.textContent || "";
  const financial = /financial services|bank|nbfc|insurance/i.test(context);
  const m = buildMomentum(data, financial);
  const cls = m.index == null ? "neutral" : m.index >= 65 ? "strong" : m.index >= 45 ? "stable" : "weak";
  const components = m.components.map(([name, value, , note, tooltip]) => `<div class="stock-momentum-component"><div class="stock-momentum-component-head"><span class="stock-momentum-label">${esc(name)} <span class="stock-momentum-info" tabindex="0" aria-label="How ${esc(name)} is calculated">i</span><span class="stock-momentum-tooltip" role="tooltip">${esc(tooltip)}</span></span><strong>${value == null ? "—" : Math.round(value)}</strong></div><div class="stock-momentum-bar"><span style="width:${value == null ? 0 : Math.round(value)}%"></span></div><small>${esc(note)}</small></div>`).join("");
  const observations = m.observations.length ? m.observations.map(x => `<li>${esc(x)}</li>`).join("") : "<li>Insufficient historical observations for a meaningful trajectory.</li>";
  const indexTooltip = "Weighted average of the available component scores: Growth 30%, Return 25%, Earnings consistency/Cash conversion 20%, Share/Balance-sheet discipline 15%, and Business consistency 10%. If a component is unavailable, the remaining weights are normalized. The result is constrained to a 0–100 scale.";
  const section = document.createElement("section");
  section.className = "stock-section stock-fundamental-momentum";
  section.innerHTML = `<div class="stock-momentum-header"><div><h2>Fundamental Momentum</h2><p>Engine-calculated view of how the business trajectory is changing across growth, returns, earnings quality, financial discipline and consistency.</p></div><div class="stock-momentum-index ${cls}"><span>Momentum Index <span class="stock-momentum-info stock-momentum-index-info" tabindex="0" aria-label="How the Momentum Index is calculated">i</span><span class="stock-momentum-tooltip stock-momentum-index-tooltip" role="tooltip">${esc(indexTooltip)}</span></span><strong>${m.index == null ? "—" : m.index}</strong><small>${esc(m.label)}</small></div></div><div class="stock-momentum-grid">${components}</div><div class="stock-momentum-observations"><h3>What changed</h3><ul>${observations}</ul><small>The index describes historical trajectory; it is not a forecast or an investment recommendation.</small></div>`;
  const anchor = details.querySelector(".stock-summary-grid") || details.querySelector(".stock-hero");
  if (anchor) anchor.insertAdjacentElement("afterend", section); else details.prepend(section);
}

function addStyles() {
  if (document.getElementById("stock-fundamental-momentum-styles")) return;
  const style = document.createElement("style"); style.id = "stock-fundamental-momentum-styles";
  style.textContent = `.stock-fundamental-signals{display:none!important}.stock-fundamental-momentum{margin-top:18px}.stock-momentum-header{display:flex;justify-content:space-between;align-items:center;gap:18px;padding-bottom:14px;border-bottom:1px solid #e2e8f0}.stock-momentum-header h2{margin:0;color:#0f1d35;font-size:18px}.stock-momentum-header p{margin:5px 0 0;color:#64748b;font-size:12px;line-height:1.5;max-width:760px}.stock-momentum-index{position:relative;min-width:130px;padding:10px 14px;border:1px solid #dbe6f1;border-radius:12px;background:#fff;text-align:center}.stock-momentum-index > span:first-child{display:block;color:#64748b;font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:.06em}.stock-momentum-index strong{display:block;margin-top:2px;color:#0f2748;font-size:28px;line-height:1.1}.stock-momentum-index small{display:block;margin-top:3px;font-weight:700;font-size:10px}.stock-momentum-index.strong small{color:#16803c}.stock-momentum-index.stable small{color:#9a6700}.stock-momentum-index.weak small{color:#c0392b}.stock-momentum-index.neutral small{color:#64748b}.stock-momentum-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin-top:14px}.stock-momentum-component{position:relative;padding:12px;border:1px solid #dbe6f1;border-radius:11px;background:#fff}.stock-momentum-component-head{display:flex;justify-content:space-between;align-items:center;color:#17355d;font-size:12px;font-weight:700}.stock-momentum-label{position:relative;display:inline-flex;align-items:center;gap:5px}.stock-momentum-component-head strong{font-size:15px;color:#0f2748;font-variant-numeric:tabular-nums}.stock-momentum-bar{height:6px;margin:8px 0 6px;background:#edf2f7;border-radius:99px;overflow:hidden}.stock-momentum-bar span{display:block;height:100%;background:#2563eb;border-radius:99px}.stock-momentum-component small{color:#7a8aa0;font-size:10px;line-height:1.35}.stock-momentum-info{display:inline-flex;align-items:center;justify-content:center;width:14px;height:14px;border:1px solid #8aa0bb;border-radius:50%;color:#52708f;font-size:9px;font-weight:800;line-height:1;cursor:help;text-transform:none;letter-spacing:0}.stock-momentum-tooltip{display:none;position:absolute;z-index:100;left:0;top:calc(100% + 9px);width:300px;padding:10px 12px;border:1px solid #cbd8e6;border-radius:9px;background:#10233f;color:#fff;font-size:11px;font-weight:400;line-height:1.5;letter-spacing:0;text-transform:none;text-align:left;box-shadow:0 8px 22px rgba(15,39,72,.18);white-space:normal;box-sizing:border-box}.stock-momentum-tooltip::before{content:"";position:absolute;left:8px;top:-5px;width:9px;height:9px;background:#10233f;border-left:1px solid #cbd8e6;border-top:1px solid #cbd8e6;transform:rotate(45deg)}.stock-momentum-info:hover + .stock-momentum-tooltip,.stock-momentum-info:focus + .stock-momentum-tooltip{display:block}.stock-momentum-index-info{display:inline-flex!important;margin-left:3px;vertical-align:middle}.stock-momentum-index-tooltip{left:auto;right:0;transform:none;top:calc(100% + 9px);width:330px}.stock-momentum-index-tooltip::before{left:auto;right:12px;transform:rotate(45deg)}.stock-momentum-index-info:hover + .stock-momentum-index-tooltip,.stock-momentum-index-info:focus + .stock-momentum-index-tooltip{display:block!important}.stock-momentum-observations{margin-top:12px;padding:12px 14px;border:1px solid #dbe6f1;border-radius:11px;background:#fff}.stock-momentum-observations h3{margin:0 0 6px;color:#17355d;font-size:13px}.stock-momentum-observations ul{margin:0;padding-left:18px;color:#475569;font-size:12px;line-height:1.55}.stock-momentum-observations small{display:block;margin-top:7px;color:#7a8aa0;font-size:10px}@media(max-width:700px){.stock-momentum-header{align-items:flex-start;flex-direction:column}.stock-momentum-index{width:100%;box-sizing:border-box}.stock-momentum-grid{grid-template-columns:1fr}.stock-momentum-tooltip{width:260px;left:-8px}.stock-momentum-index-tooltip{left:auto;right:0;width:270px}}`;
  document.head.appendChild(style);
}

function init() {
  addStyles();
  const details = document.getElementById("stock-details");
  if (!details) return;
  const originalFetch = window.fetch.bind(window);
  window.fetch = async (...args) => {
    const response = await originalFetch(...args);
    const url = String(args[0]?.url || args[0] || "");
    if (url.includes("/api/stocks/pedigree/") && !url.includes("/compare?")) {
      response.clone().json().then(data => render(data, details)).catch(() => {});
    }
    return response;
  };
  const observer = new MutationObserver(() => details.querySelector(".stock-fundamental-signals")?.remove());
  observer.observe(details, { childList: true, subtree: true });
}

if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init, { once: true }); else init();
