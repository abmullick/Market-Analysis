// QGV comparison data repair: derive the decision-lens numbers directly from the annual statements.
// Do not trust cached/provider CAGR fields here: the comparison must use the same annual-statement
// calculation as the individual decision lens.
const API = "/api/stocks";
const num = v => (v == null || v === "" || !Number.isFinite(Number(v))) ? null : Number(v);
const pct = v => v == null ? "—" : `${Number(v).toFixed(1)}%`;
const ratio = v => v == null ? "—" : `${Number(v).toFixed(1)}x`;

function financial(f = {}) {
  return /financial services|bank|nbfc|insurance|capital markets|credit/i.test(
    `${f.sector || ""} ${f.industry || ""}`
  );
}

function values(data, statement, key) {
  return (data?.[statement] || [])
    .map(r => num(r?.values?.[key]))
    .filter(v => v != null);
}

// API statement rows are newest -> oldest. The 3Y CAGR is therefore
// latest value / value exactly 3 annual observations earlier.
function cagr(a, years = 3) {
  if (a.length < years + 1) return null;
  const end = a[0];
  const start = a[years];
  if (start <= 0 || end <= 0) return null;
  return (Math.pow(end / start, 1 / years) - 1) * 100;
}

function derivedRatio(d, key) {
  const v = num(d?.[key]);
  if (v == null) return null;
  return Math.abs(v) <= 1.5 ? v * 100 : v;
}

function derive(data) {
  const f = data?.fundamentals || {};
  const d = data?.derived_analysis || {};
  const fin = financial(f);

  const profit = values(data, "income_statement", "NetIncome");
  const eps = values(data, "income_statement", "DilutedEPS");
  const assets = values(data, "balance_sheet", "TotalAssets");
  const equity = values(data, "balance_sheet", "StockholdersEquity");
  const debt = values(data, "balance_sheet", "TotalDebt");

  // Annual profit CAGR first. EPS CAGR is only a fallback when profit CAGR
  // cannot be calculated because the starting profit is non-positive/missing.
  const growth = cagr(profit, 3) ?? cagr(eps, 3);

  // Derive quality from the annual statements so the comparison cannot drift
  // from the individual analysis because of a provider ratio or stale cache.
  const latestProfit = profit[0];
  const avgAssets = assets.length >= 2 ? (assets[0] + assets[1]) / 2 : assets[0];
  const avgEquity = equity.length >= 2 ? (equity[0] + equity[1]) / 2 : equity[0];
  const derivedRoa = latestProfit != null && avgAssets > 0 ? latestProfit / avgAssets * 100 : null;
  const derivedRoe = latestProfit != null && avgEquity > 0 ? latestProfit / avgEquity * 100 : null;

  const quality = fin
    ? derivedRoa ?? derivedRatio(d, "roa_derived") ?? num(f.roa)
    : derivedRoe ?? derivedRatio(d, "roe_derived") ?? num(f.roe);

  const valuation = fin ? num(f.pb) : num(f.pe);

  const payout = num(f.payout_ratio);
  const retention = payout == null ? null : Math.max(0, Math.min(100, 100 - payout));
  const retained = !fin && quality != null && retention != null ? quality * retention / 100 : null;
  const gap = !fin && growth != null && retained != null ? growth - retained : null;

  // D/E is useful for operating businesses, but is intentionally not shown
  // as an industrial-leverage signal for banks/NBFCs/other lenders.
  const debtEq = !fin
    ? num(f.debt_equity) ?? (debt[0] != null && equity[0] > 0 ? debt[0] / equity[0] : null)
    : null;

  return {
    fin,
    growth,
    quality,
    valuation,
    retained,
    gap,
    debtEq,
    debtGrowth: cagr(debt, 3),
    assetGrowth: cagr(assets, 3),
    bookGrowth: cagr(equity, 3),
  };
}

function setMetric(card, value, suffix = "") {
  const s = card?.querySelector("strong");
  if (s) s.textContent = value == null ? "—" : `${Number(value).toFixed(1)}${suffix}`;
}

function renderFinancialFunding(fund, x) {
  fund.innerHTML = `
    <span><b>Asset growth</b> ${pct(x.assetGrowth)}</span>
    <span><b>Book growth</b> ${pct(x.bookGrowth)}</span>
    <span><b>Share count</b> —</span>
  `;
}

function renderOperatingFunding(fund, x) {
  fund.innerHTML = `
    <span><b>Retained capacity</b> ${pct(x.retained)}</span>
    <span><b>Growth gap</b> ${x.gap == null ? "—" : `${Number(x.gap).toFixed(1)} pp`}</span>
    <span><b>Debt growth 3Y</b> ${pct(x.debtGrowth)}</span>
    <span><b>D/E</b> ${ratio(x.debtEq)}</span>
  `;
}

async function repair() {
  const root = document.querySelector(".qgv-compare");
  if (!root) return;

  const cards = [...root.querySelectorAll(".qgv-compare-card")];

  await Promise.all(cards.map(async card => {
    const symbol = card.querySelector("header span")?.textContent?.trim();
    if (!symbol) return;

    try {
      const r = await fetch(`${API}/${encodeURIComponent(symbol)}`, {
        headers: { Accept: "application/json" },
        cache: "no-store"
      });
      if (!r.ok) return;

      const x = derive(await r.json());

      const em = card.querySelector("header em");
      if (em) em.textContent = x.fin ? "Financial lens" : "Operating lens";

      const metrics = [...card.querySelectorAll(".qgv-compare-metrics .qgv-metric")];
      if (metrics.length >= 3) {
        setMetric(metrics[0], x.valuation, "x");
        metrics[0].querySelector("span").textContent = x.fin ? "P/B" : "P/E";

        setMetric(metrics[1], x.quality, "%");
        metrics[1].querySelector("span").textContent = x.fin ? "ROA" : "ROE";

        setMetric(metrics[2], x.growth, "%");
        metrics[2].querySelector("span").textContent = "3Y earnings CAGR";
      }

      const fund = card.querySelector(".qgv-compare-funding");
      if (fund) {
        if (x.fin) renderFinancialFunding(fund, x);
        else renderOperatingFunding(fund, x);
      }
    } catch (_) {
      // Keep the server-rendered card if the repair request fails.
    }
  }));
}

function schedule() {
  let n = 0;
  const t = () => {
    if (document.querySelector(".qgv-compare")) repair();
    else if (++n < 30) setTimeout(t, 300);
  };
  t();
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", schedule);
} else {
  schedule();
}
