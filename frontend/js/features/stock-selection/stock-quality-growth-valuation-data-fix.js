// Decision-lens data repair: derive the displayed metrics directly from the annual statements.
// This prevents provider-period differences or stale derived fields from changing the QGV numbers.
const API = "/api/stocks";
const num = v => (v == null || v === "" || !Number.isFinite(Number(v))) ? null : Number(v);
const pct = v => v == null ? "—" : `${Number(v).toFixed(1)}%`;
const ratio = v => v == null ? "—" : `${Number(v).toFixed(1)}x`;

function isFinancial(f = {}) {
  return /financial services|bank|nbfc|insurance|capital markets|credit/i.test(`${f.sector || ""} ${f.industry || ""}`);
}

function series(data, statement, key) {
  return (data?.[statement] || [])
    .map(r => num(r?.values?.[key]))
    .filter(v => v != null);
}

// Statement rows are newest -> oldest. A 3Y CAGR therefore uses row 0 and row 3.
function cagr(values, years = 3) {
  if (values.length < years + 1) return null;
  const end = values[0], start = values[years];
  if (start <= 0 || end <= 0) return null;
  return (Math.pow(end / start, 1 / years) - 1) * 100;
}

function averageLatest(values) {
  if (!values.length) return null;
  return values.length >= 2 ? (values[0] + values[1]) / 2 : values[0];
}

function derive(data) {
  const f = data?.fundamentals || {};
  const d = data?.derived_analysis || {};
  const financial = isFinancial(f);

  const profit = series(data, "income_statement", "NetIncome");
  const eps = series(data, "income_statement", "DilutedEPS");
  const assets = series(data, "balance_sheet", "TotalAssets");
  const equity = series(data, "balance_sheet", "StockholdersEquity");
  const debt = series(data, "balance_sheet", "TotalDebt");

  // Use annual profit CAGR as the primary earnings-growth measure.
  // EPS CAGR is only a fallback when profit CAGR is unavailable.
  const growth = cagr(profit, 3) ?? cagr(eps, 3);

  const latestProfit = profit[0];
  const avgAssets = averageLatest(assets);
  const avgEquity = averageLatest(equity);
  const derivedRoa = latestProfit != null && avgAssets > 0 ? latestProfit / avgAssets * 100 : null;
  const derivedRoe = latestProfit != null && avgEquity > 0 ? latestProfit / avgEquity * 100 : null;

  const roe = derivedRoe ?? (num(d.roe_derived) != null ? num(d.roe_derived) * 100 : num(f.roe));
  const roa = derivedRoa ?? (num(d.roa_derived) != null ? num(d.roa_derived) * 100 : num(f.roa));

  // D/E is intentionally not used for the financial-services lens because lender
  // balance sheets make industrial-style leverage interpretation misleading.
  const debtEq = !financial
    ? num(f.debt_equity) ?? (debt[0] != null && equity[0] > 0 ? debt[0] / equity[0] : null)
    : null;

  const payout = num(f.payout_ratio);
  const retention = payout == null ? null : Math.max(0, Math.min(100, 100 - payout));
  const retained = !financial && roe != null && retention != null ? roe * retention / 100 : null;

  return {
    financial,
    f,
    growth,
    roe,
    roa,
    retained,
    gap: !financial && growth != null && retained != null ? growth - retained : null,
    debtEq,
    interest: num(f.interest_coverage),
    nde: num(d.net_debt_ebitda),
    debtGrowth: cagr(debt, 3),
    assetGrowth: cagr(assets, 3),
    equityGrowth: cagr(equity, 3),
    cfoGrowth: cagr(series(data, "cash_flow", "OperatingCashFlow"), 3),
    fcfGrowth: cagr(series(data, "cash_flow", "FreeCashFlow"), 3)
  };
}

function setText(el, text) { if (el) el.textContent = text; }

function setMetricByLabel(root, label, value, suffix = "") {
  for (const card of root.querySelectorAll(".qgv-metric")) {
    if (card.querySelector("span")?.textContent?.trim() === label) {
      const strong = card.querySelector("strong");
      if (strong) strong.textContent = value == null ? "—" : `${Number(value).toFixed(1)}${suffix}`;
    }
  }
}

function setChip(root, label, value) {
  for (const chip of root.querySelectorAll(".qgv-chip")) {
    if (chip.querySelector("b")?.textContent?.trim() === label) {
      setText(chip.querySelector("strong"), value);
    }
  }
}

function repairIndividual(root, data) {
  const x = derive(data);
  const f = x.f;
  const valuation = x.financial ? num(f.pb) : num(f.pe);
  const quality = x.financial ? x.roa : x.roe;
  const valuationLabel = x.financial ? "P/B" : "P/E";
  const qualityLabel = x.financial ? "ROA" : "ROE";

  setText(root.querySelector(".qgv-lens"), x.financial ? "FINANCIAL SERVICES LENS" : "OPERATING BUSINESS LENS");
  const headP = root.querySelector(".qgv-head p");
  if (headP) headP.textContent = `${valuationLabel} × ${qualityLabel} × 3Y earnings CAGR. The engine connects valuation, business quality and the pace of earnings growth.`;

  const three = root.querySelectorAll(".qgv-three > div");
  if (three.length >= 3) {
    setText(three[0].querySelector("b"), ratio(valuation));
    setText(three[0].querySelector("small"), valuationLabel);
    setText(three[1].querySelector("b"), pct(quality));
    setText(three[1].querySelector("small"), qualityLabel);
    setText(three[2].querySelector("b"), pct(x.growth));
    setText(three[2].querySelector("small"), "3Y earnings CAGR");
  }

  const story = root.querySelector(".qgv-story-line");
  if (story) story.innerHTML = `<strong>${valuationLabel}</strong><span>×</span><strong>${qualityLabel}</strong><span>×</span><strong>3Y earnings CAGR</strong>`;

  const scoreP = root.querySelector(".qgv-score-card p");
  if (scoreP) {
    scoreP.textContent = x.financial
      ? `Current ${valuationLabel} ${ratio(valuation)} is being read with current ${qualityLabel} ${pct(quality)} and 3Y earnings CAGR ${pct(x.growth)}.`
      : `${x.gap == null ? "Funding comparison is limited" : x.gap > 5 ? "Growth is above simple internal capacity" : "Growth is broadly supported by internal capacity"}. A positive gap is an investigation signal, not proof of external funding.`;
  }

  if (x.financial) {
    setChip(root, "P/B", ratio(valuation));
    setChip(root, "ROA", pct(quality));
    setChip(root, "Earnings growth", pct(x.growth));
    setChip(root, "Asset growth", pct(x.assetGrowth));
    setChip(root, "Book growth", pct(x.equityGrowth));
  } else {
    setMetricByLabel(root, "Earnings growth", x.growth, "%");
    setMetricByLabel(root, "ROE", x.roe, "%");
    setMetricByLabel(root, "Retained-earnings capacity", x.retained, "%");
    setMetricByLabel(root, "Growth gap", x.gap, " pp");
    setMetricByLabel(root, "Debt / Equity", x.debtEq, "x");
    setMetricByLabel(root, "Interest coverage", x.interest, "x");
    setMetricByLabel(root, "Net Debt / EBITDA", x.nde, "x");
    setMetricByLabel(root, "Debt growth 3Y", x.debtGrowth, "%");
    setMetricByLabel(root, "Operating cash growth 3Y", x.cfoGrowth, "%");
    setMetricByLabel(root, "FCF growth 3Y", x.fcfGrowth, "%");
  }

  const path = root.querySelectorAll(".qgv-path-node");
  if (path.length >= 4) {
    setText(path[0].querySelector("b"), pct(x.growth));
    setText(path[1].querySelector("b"), pct(x.retained));
    setText(path[2].querySelector("b"), pct(x.debtGrowth));
  }
}

async function repair() {
  const root = document.querySelector(".qgv-individual");
  const symbol = new URLSearchParams(location.search).get("symbol");
  if (!root || !symbol) return;
  try {
    const r = await fetch(`${API}/${encodeURIComponent(symbol)}`, {
      headers: { Accept: "application/json" },
      cache: "no-store"
    });
    if (r.ok) repairIndividual(root, await r.json());
  } catch (_) {}
}

function scheduleRepair() {
  let tries = 0;
  const tick = () => {
    if (document.querySelector(".qgv-individual")) repair();
    else if (++tries < 30) setTimeout(tick, 300);
  };
  tick();
}

if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", scheduleRepair);
else scheduleRepair();
