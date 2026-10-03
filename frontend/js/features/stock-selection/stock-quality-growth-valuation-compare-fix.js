// QGV comparison data repair: use derived annual-statement metrics consistently with individual analysis.
const API = "/api/stocks";
const num = v => (v == null || v === "" || !Number.isFinite(Number(v))) ? null : Number(v);
const pct = v => v == null ? "—" : `${Number(v).toFixed(1)}%`;
const ratio = v => v == null ? "—" : `${Number(v).toFixed(1)}x`;
function financial(f = {}) { return /financial services|bank|nbfc|insurance|capital markets|credit/i.test(`${f.sector || ""} ${f.industry || ""}`); }
function values(data, statement, key) { return (data?.[statement] || []).map(r => num(r?.values?.[key])).filter(v => v != null); }
function cagr(a, y = 3) { if (a.length < y + 1) return null; const e = a[0], s = a[y]; return s > 0 && e > 0 ? (Math.pow(e / s, 1 / y) - 1) * 100 : null; }
function derive(data) {
  const f = data?.fundamentals || {}, d = data?.derived_analysis || {}, fin = financial(f);
  const profit3 = num(d.profit_cagr_3y_derived), eps3 = num(d.eps_cagr_3y_derived);
  const growth = profit3 != null ? profit3 * 100 : eps3 != null ? eps3 * 100 : cagr(values(data, "income_statement", "NetIncome"), 3) ?? cagr(values(data, "income_statement", "DilutedEPS"), 3);
  const roe = num(d.roe_derived) != null ? num(d.roe_derived) * 100 : num(f.roe);
  const roa = num(d.roa_derived) != null ? num(d.roa_derived) * 100 : num(f.roa);
  const debt = values(data, "balance_sheet", "TotalDebt"), equity = values(data, "balance_sheet", "StockholdersEquity");
  const debtEq = num(f.debt_equity) ?? (debt[0] != null && equity[0] != null && equity[0] !== 0 ? debt[0] / equity[0] : null);
  const payout = num(f.payout_ratio), retained = roe != null && payout != null ? roe * Math.max(0, Math.min(100, 100 - payout)) / 100 : null;
  return { fin, growth, quality: fin ? roa : roe, v: fin ? num(f.pb) : num(f.pe), retained, gap: growth != null && retained != null ? growth - retained : null, debtEq, debtGrowth: cagr(debt), assetGrowth: cagr(values(data, "balance_sheet", "TotalAssets")), equityGrowth: cagr(equity) };
}
function setMetric(card, value, suffix = "") { const s = card?.querySelector("strong"); if (s) s.textContent = value == null ? "—" : `${Number(value).toFixed(1)}${suffix}`; }
async function repair() {
  const root = document.querySelector(".qgv-compare"); if (!root) return;
  const cards = [...root.querySelectorAll(".qgv-compare-card")];
  await Promise.all(cards.map(async card => {
    const symbol = card.querySelector("header span")?.textContent?.trim(); if (!symbol) return;
    try {
      const r = await fetch(`${API}/${encodeURIComponent(symbol)}`, { headers: { Accept: "application/json" }, cache: "no-store" }); if (!r.ok) return;
      const x = derive(await r.json());
      const em = card.querySelector("header em"); if (em) em.textContent = x.fin ? "Financial lens" : "Operating lens";
      const metrics = [...card.querySelectorAll(".qgv-compare-metrics .qgv-metric")];
      if (metrics.length >= 3) { setMetric(metrics[0], x.v, "x"); metrics[0].querySelector("span").textContent = x.fin ? "P/B" : "P/E"; setMetric(metrics[1], x.quality, "%"); metrics[1].querySelector("span").textContent = x.fin ? "ROA" : "ROE"; setMetric(metrics[2], x.growth, "%"); metrics[2].querySelector("span").textContent = "3Y earnings CAGR"; }
      const fund = card.querySelector(".qgv-compare-funding");
      if (fund) {
        const spans = [...fund.querySelectorAll("span")];
        const vals = x.fin ? [x.assetGrowth, x.equityGrowth] : [x.retained, x.gap, x.debtGrowth, x.debtEq];
        spans.forEach((s, i) => { const b = s.querySelector("b"); if (b && vals[i] != null) b.textContent = i === 3 && !x.fin ? ratio(vals[i]) : pct(vals[i]); });
      }
    } catch (_) {}
  }));
}
function schedule() { let n = 0; const t = () => { if (document.querySelector(".qgv-compare")) repair(); else if (++n < 20) setTimeout(t, 300); }; t(); }
if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", schedule); else schedule();
