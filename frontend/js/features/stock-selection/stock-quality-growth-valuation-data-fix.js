// Repairs the decision-lens display by reusing the fully enriched /api/stocks/{symbol}
// response used by the main stock analysis page. This is intentionally a data-wiring
// layer: it does not replace the QGV engine or introduce another data source.
const API = "/api/stocks";
const num = v => (v == null || v === "" || !Number.isFinite(Number(v))) ? null : Number(v);
const pct = v => v == null ? "—" : `${Number(v).toFixed(1)}%`;
const ratio = v => v == null ? "—" : `${Number(v).toFixed(1)}x`;

function isFinancial(f = {}) {
  return /financial services|bank|nbfc|insurance|capital markets|credit/i.test(`${f.sector || ""} ${f.industry || ""}`);
}

function rows(data, statement, key) {
  return (data?.[statement] || []).map(r => num(r?.values?.[key])).filter(v => v != null);
}

function cagr(values, years = 3) {
  if (values.length < years + 1) return null;
  const end = values[0];
  const start = values[years];
  if (start <= 0 || end <= 0) return null;
  return (Math.pow(end / start, 1 / years) - 1) * 100;
}

function derive(data) {
  const f = data?.fundamentals || {};
  const financial = isFinancial(f);
  const income = data?.income_statement || [];
  const balance = data?.balance_sheet || [];
  const cash = data?.cash_flow || [];
  const profit = num(f.net_profit) ?? num(income[0]?.values?.NetIncome);
  const assets = num(balance[0]?.values?.TotalAssets);
  const equity = num(balance[0]?.values?.StockholdersEquity);
  const roe = num(f.roe) ?? (profit != null && equity ? profit / equity * 100 : null);
  const roa = num(f.roa) ?? (profit != null && assets ? profit / assets * 100 : null);
  const growth = num(f.profit_cagr_5y) ?? num(f.eps_cagr_5y) ?? num(f.profit_cagr_3y) ?? num(f.eps_cagr_3y)
    ?? cagr(rows(data, "income_statement", "NetIncome"), 5)
    ?? cagr(rows(data, "income_statement", "DilutedEPS"), 5);
  const payout = num(f.payout_ratio);
  const retention = payout == null ? null : Math.max(0, Math.min(100, 100 - payout));
  const retained = roe != null && retention != null ? roe * retention / 100 : null;
  const gap = growth != null && retained != null ? growth - retained : (growth != null && roe != null ? growth - roe : null);
  return {
    financial, f, growth, roe, roa, retained, gap,
    debtEq: num(f.debt_equity), interest: num(f.interest_coverage), nde: num(f.net_debt_ebitda),
    debtGrowth: cagr(rows(data, "balance_sheet", "TotalDebt"), 3),
    assetGrowth: cagr(rows(data, "balance_sheet", "TotalAssets"), 3),
    equityGrowth: cagr(rows(data, "balance_sheet", "StockholdersEquity"), 3),
    cfoGrowth: cagr(rows(data, "cash_flow", "OperatingCashFlow"), 3),
    fcfGrowth: cagr(rows(data, "cash_flow", "FreeCashFlow"), 3),
  };
}

function setText(el, text) { if (el) el.textContent = text; }
function metricValue(card, value, suffix = "") {
  const strong = card?.querySelector("strong");
  if (strong) strong.textContent = value == null ? "—" : `${Number(value).toFixed(1)}${suffix}`;
}
function setMetricByLabel(root, label, value, suffix = "") {
  for (const card of root.querySelectorAll(".qgv-metric")) {
    if (card.querySelector("span")?.textContent?.trim() === label) metricValue(card, value, suffix);
  }
}
function setChip(root, label, value) {
  for (const chip of root.querySelectorAll(".qgv-chip")) {
    if (chip.querySelector("b")?.textContent?.trim() === label) setText(chip.querySelector("strong"), value);
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
  if (headP) headP.textContent = `${valuationLabel} × ${qualityLabel} × earnings growth. The engine connects the factors investors often read together instead of presenting them as isolated ratios.`;

  const three = root.querySelectorAll(".qgv-three > div");
  if (three.length >= 3) {
    setText(three[0].querySelector("b"), ratio(valuation));
    setText(three[0].querySelector("small"), valuationLabel);
    setText(three[1].querySelector("b"), pct(quality));
    setText(three[1].querySelector("small"), qualityLabel);
    setText(three[2].querySelector("b"), pct(x.growth));
  }

  const story = root.querySelector(".qgv-story-line");
  if (story) story.innerHTML = `<strong>${valuationLabel}</strong><span>×</span><strong>${qualityLabel}</strong><span>×</span><strong>Earnings growth</strong>`;

  const scoreP = root.querySelector(".qgv-score-card p");
  if (scoreP) {
    scoreP.textContent = x.financial
      ? `Current ${valuationLabel} ${ratio(valuation)} is being read together with ${qualityLabel} ${pct(quality)} and earnings growth ${pct(x.growth)}.`
      : `${x.gap == null ? "Funding comparison is limited" : x.gap > 5 ? "Growth is above simple internal capacity" : "Growth is broadly supported by internal capacity"}. A positive gap is an investigation signal, not proof that the company raised external capital.`;
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
    const r = await fetch(`${API}/${encodeURIComponent(symbol)}`, { headers: { Accept: "application/json" }, cache: "no-store" });
    if (!r.ok) return;
    const data = await r.json();
    repairIndividual(root, data);
  } catch (_) {
    // The original QGV rendering remains in place if the repair request fails.
  }
}

function scheduleRepair() {
  let tries = 0;
  const tick = () => {
    tries += 1;
    if (document.querySelector(".qgv-individual")) repair();
    else if (tries < 20) setTimeout(tick, 300);
  };
  tick();
}

if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", scheduleRepair);
else scheduleRepair();
