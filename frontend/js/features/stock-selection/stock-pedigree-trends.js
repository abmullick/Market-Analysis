const API = "/api/stocks/pedigree";
const COLORS = ["#2563eb", "#10b981", "#f59e0b", "#8b5cf6"];

function esc(v) {
  return String(v ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");
}

function n(v) {
  return Number.isFinite(Number(v)) ? Number(v) : null;
}

function fmt(v, suffix = "", digits = 1) {
  const x = n(v);
  if (x == null) return "—";
  return `${x.toLocaleString("en-IN", { maximumFractionDigits: digits })}${suffix}`;
}

function chartOptions(yTitle, suffix = "", stacked = false) {
  return {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: "index", intersect: false },
    plugins: {
      legend: { position: "top", labels: { boxWidth: 10, usePointStyle: true, font: { size: 10 } } },
      tooltip: { callbacks: { label: (ctx) => `${ctx.dataset.label}: ${fmt(ctx.parsed.y, suffix)}` } },
    },
    scales: {
      x: { grid: { display: false }, ticks: { font: { size: 9 }, color: "#64748b" } },
      y: {
        stacked,
        beginAtZero: stacked,
        title: { display: true, text: yTitle, color: "#475569", font: { size: 10, weight: "600" } },
        grid: { color: "#edf2f7" },
        ticks: { font: { size: 9 }, color: "#64748b", callback: (v) => `${v}${suffix}` },
      },
    },
  };
}

function makeLine(canvasId, series, label, color, yTitle, suffix = "") {
  if (typeof Chart === "undefined") return;
  const canvas = document.getElementById(canvasId);
  if (!canvas || !series?.length) return;
  new Chart(canvas, {
    type: "line",
    data: {
      labels: series.map((x) => x.year),
      datasets: [{ label, data: series.map((x) => x.value), borderColor: color, backgroundColor: `${color}16`, borderWidth: 2, pointRadius: 2.5, pointHoverRadius: 5, tension: .22, spanGaps: true, fill: true }],
    },
    options: chartOptions(yTitle, suffix),
  });
}

function makeMulti(canvasId, datasets, yTitle, suffix = "", stacked = false) {
  if (typeof Chart === "undefined") return;
  const canvas = document.getElementById(canvasId);
  if (!canvas || !datasets?.length) return;
  const labels = [...new Set(datasets.flatMap((d) => (d.series || []).map((x) => x.year)))].sort();
  if (!labels.length) return;
  new Chart(canvas, {
    type: "line",
    data: {
      labels,
      datasets: datasets.map((d, i) => ({
        label: d.label,
        data: labels.map((year) => Object.fromEntries((d.series || []).map((x) => [x.year, x.value]))[year] ?? null),
        borderColor: d.color || COLORS[i % COLORS.length],
        backgroundColor: `${d.color || COLORS[i % COLORS.length]}16`,
        borderWidth: 2,
        pointRadius: 2.5,
        tension: .22,
        spanGaps: true,
        fill: stacked,
      })),
    },
    options: chartOptions(yTitle, suffix, stacked),
  });
}

function chartCard(id, title, subtitle) {
  return `<div class="stock-pedigree-chart-card"><h3>${esc(title)}</h3><small>${esc(subtitle)}</small><canvas id="${esc(id)}"></canvas></div>`;
}

function consistencyCard(label, value, note) {
  return `<div class="stock-pedigree-stat"><span>${esc(label)}</span><strong>${esc(value)}</strong><small>${esc(note)}</small></div>`;
}

function summaryNarrative(data) {
  const c = data.consistency || {};
  const revenue = c.revenue || {};
  const profit = c.profit || {};
  const fcf = c.fcf || {};
  const sh = data.shareholding?.combined || [];
  const firstPromoter = sh.find((x) => x.promoters != null)?.promoters;
  const lastPromoter = [...sh].reverse().find((x) => x.promoters != null)?.promoters;
  const promoterChange = firstPromoter != null && lastPromoter != null ? lastPromoter - firstPromoter : null;
  const points = [];
  if (revenue.positive_growth_pct != null) points.push(`Revenue grew year-over-year in ${fmt(revenue.positive_growth_pct, "%", 0)} of the available observations.`);
  if (profit.positive_growth_pct != null) points.push(`Profit grew year-over-year in ${fmt(profit.positive_growth_pct, "%", 0)} of the available observations.`);
  if (fcf.positive_growth_pct != null) points.push(`FCF grew year-over-year in ${fmt(fcf.positive_growth_pct, "%", 0)} of the available observations.`);
  if (c.roe_average != null) points.push(`Average historical ROE is ${fmt(c.roe_average, "%")}; ROE volatility is ${fmt(c.roe_volatility, " pp")}.`);
  if (promoterChange != null) points.push(`Promoter holding changed by ${fmt(promoterChange, " pp")} over the available shareholding history.`);
  return points.length ? points : ["Not enough historical observations are available to form a consistency summary."];
}

function renderIndividual(data, details) {
  if (details.querySelector(".stock-pedigree-section")) return;
  const t = data.trends || {};
  const c = data.consistency || {};
  const sh = data.shareholding || {};

  const revenueConsistency = c.revenue?.positive_growth_pct != null ? fmt(c.revenue.positive_growth_pct, "%", 0) : "—";
  const profitConsistency = c.profit?.positive_growth_pct != null ? fmt(c.profit.positive_growth_pct, "%", 0) : "—";
  const fcfConsistency = c.fcf?.positive_growth_pct != null ? fmt(c.fcf.positive_growth_pct, "%", 0) : "—";

  const section = document.createElement("section");
  section.className = "stock-pedigree-section";
  section.innerHTML = `
    <div class="stock-pedigree-header">
      <div><h2>Company Pedigree, Consistency & Trends</h2><p>Historical patterns derived from Screener financial statements and shareholding data. These are descriptive diagnostics, not a forecast or investment score.</p></div>
    </div>
    <div class="stock-pedigree-stats">
      ${consistencyCard("Revenue consistency", revenueConsistency, "Share of available YoY observations with growth")}
      ${consistencyCard("Profit consistency", profitConsistency, "Share of available YoY observations with growth")}
      ${consistencyCard("FCF consistency", fcfConsistency, "Share of available YoY observations with growth")}
      ${consistencyCard("Average ROE", fmt(c.roe_average, "%"), "Average across available annual observations")}
      ${consistencyCard("ROE volatility", fmt(c.roe_volatility, " pp"), "Population standard deviation of annual ROE")}
      ${consistencyCard("5Y debt change", fmt(c.debt_change_5y, ""), "Absolute change in reported debt")}
    </div>
    <div class="stock-pedigree-chart-grid">
      ${chartCard("pedigree-scale", "Business Scale & Cash Generation", "Indexed to 100 at the first positive observation")}
      ${chartCard("pedigree-returns", "ROE / ROCE / Operating Margin", "Historical profitability and capital efficiency")}
      ${chartCard("pedigree-cash", "Cash Conversion & FCF Margin", "Earnings-to-cash quality over time")}
      ${chartCard("pedigree-debt", "Debt Trend", "Reported total debt by financial year")}
      ${chartCard("pedigree-ccc", "Working Capital Cycle", "Debtor + inventory − payable days")}
      ${chartCard("pedigree-shareholding", "Historical Shareholding Pattern", "Quarterly observations where available")}
      ${chartCard("pedigree-shareholders", "Shareholder Base", "Number of shareholders over time")}
    </div>
    <div class="stock-pedigree-narrative"><h3>Consistency observations</h3><ul>${summaryNarrative(data).map((x) => `<li>${esc(x)}</li>`).join("")}</ul><p class="stock-pedigree-source">Source: ${esc(data.source || "Screener.in")}. Shareholding classifications can change over time; Screener notes that the XBRL classification change from Sep 2022 can affect historical FII/DII comparisons.</p></div>`;
  details.appendChild(section);

  makeMulti("pedigree-scale", [
    { label: "Revenue", series: t.revenue_indexed, color: COLORS[0] },
    { label: "Net Profit", series: t.profit_indexed, color: COLORS[1] },
    { label: "FCF", series: t.fcf_indexed, color: COLORS[2] },
  ], "Index (100 = first positive observation)");
  makeMulti("pedigree-returns", [
    { label: "ROE", series: t.roe, color: COLORS[0] },
    { label: "ROCE", series: t.roce, color: COLORS[1] },
    { label: "Operating Margin", series: t.operating_margin, color: COLORS[2] },
  ], "Percent", "%");
  makeMulti("pedigree-cash", [
    { label: "CFO / Net Profit", series: t.cash_conversion, color: COLORS[0] },
    { label: "FCF Margin", series: t.fcf_margin, color: COLORS[1] },
  ], "Percent", "%");
  makeLine("pedigree-debt", t.debt, "Total Debt", COLORS[3], "Reported debt");
  makeLine("pedigree-ccc", t.cash_conversion_cycle, "Cash Conversion Cycle", COLORS[2], "Days", " days");
  makeMulti("pedigree-shareholding", [
    { label: "Promoters", series: t.promoter_holding, color: COLORS[0] },
    { label: "FIIs", series: t.fii_holding, color: COLORS[1] },
    { label: "DIIs", series: t.dii_holding, color: COLORS[2] },
    { label: "Public", series: t.public_holding, color: COLORS[3] },
  ], "Holding (%)", "%");
  makeLine("pedigree-shareholders", t.shareholders, "Shareholders", COLORS[0], "Count");
}

function renderCompare(datas, details) {
  if (details.querySelector(".stock-pedigree-compare")) return;
  const names = datas.map((d) => d.symbol);
  const colors = names.map((_, i) => COLORS[i % COLORS.length]);
  const section = document.createElement("section");
  section.className = "stock-pedigree-section stock-pedigree-compare";
  section.innerHTML = `
    <div class="stock-pedigree-header"><div><h2>Company Pedigree & Trend Comparison</h2><p>Compare historical consistency, operating quality, leverage and ownership trends using the same derived methodology for every selected company.</p></div></div>
    <div class="stock-pedigree-chart-grid">
      ${chartCard("pedigree-compare-scale", "Business Scale — Indexed", "Revenue, net profit and FCF start at 100 for each company")}
      ${chartCard("pedigree-compare-returns", "ROE / ROCE Trend", "Capital efficiency over time")}
      ${chartCard("pedigree-compare-margin", "Operating Margin Trend", "Margin expansion or compression")}
      ${chartCard("pedigree-compare-fcf", "FCF Margin Trend", "Free cash flow relative to revenue")}
      ${chartCard("pedigree-compare-debt", "Debt Trend", "Reported total debt by year")}
      ${chartCard("pedigree-compare-promoter", "Promoter Holding Trend", "Historical promoter ownership")}
      ${chartCard("pedigree-compare-institutional", "Institutional Holding Trend", "FII + DII holding")}
      ${chartCard("pedigree-compare-shareholders", "Shareholder Base Trend", "Number of shareholders")}
    </div>
    <div class="stock-pedigree-compare-table"><h3>Consistency Snapshot</h3><div class="stock-table-wrap"><table class="stock-table"><thead><tr><th>Metric</th>${names.map((x) => `<th>${esc(x)}</th>`).join("")}</tr></thead><tbody>
      ${[
        ["Revenue growth consistency", (d) => d.consistency?.revenue?.positive_growth_pct, "%"],
        ["Profit growth consistency", (d) => d.consistency?.profit?.positive_growth_pct, "%"],
        ["FCF growth consistency", (d) => d.consistency?.fcf?.positive_growth_pct, "%"],
        ["Average ROE", (d) => d.consistency?.roe_average, "%"],
        ["ROE volatility", (d) => d.consistency?.roe_volatility, " pp"],
        ["5Y debt change", (d) => d.consistency?.debt_change_5y, ""],
      ].map(([label, fn, suffix]) => `<tr><td>${esc(label)}</td>${datas.map((d) => `<td>${esc(fmt(fn(d), suffix))}</td>`).join("")}</tr>`).join("")}
    </tbody></table></div></div>`;
  details.appendChild(section);

  const ds = (key, labelKey = key) => datas.map((d, i) => ({ label: names[i], series: d.trends?.[labelKey] || [], color: colors[i] }));
  makeMulti("pedigree-compare-scale", datas.flatMap((d, i) => [
    { label: `${names[i]} · Revenue`, series: d.trends?.revenue_indexed || [], color: colors[i] },
  ]), "Index (100 = first positive observation)");
  makeMulti("pedigree-compare-returns", ds("roe").concat(ds("roce")), "Percent", "%");
  makeMulti("pedigree-compare-margin", ds("operating_margin"), "Percent", "%");
  makeMulti("pedigree-compare-fcf", ds("fcf_margin"), "Percent", "%");
  makeMulti("pedigree-compare-debt", ds("debt"), "Reported debt");
  makeMulti("pedigree-compare-promoter", ds("promoter_holding"), "Holding (%)", "%");
  makeMulti("pedigree-compare-institutional", datas.map((d, i) => ({
    label: names[i],
    color: colors[i],
    series: (d.shareholding?.combined || []).map((r) => ({ year: r.date, value: (n(r.fiis) || 0) + (n(r.diis) || 0) })),
  })), "Holding (%)", "%");
  makeMulti("pedigree-compare-shareholders", ds("shareholders"), "Count");
}

async function load() {
  const details = document.getElementById("stock-details");
  if (!details) return;
  const params = new URLSearchParams(location.search);
  const compare = params.get("compare");
  try {
    if (compare) {
      const symbols = compare.split(",").map((x) => decodeURIComponent(x).trim().toUpperCase()).filter(Boolean).slice(0, 4);
      if (!symbols.length) return;
      const response = await fetch(`${API}/compare?${symbols.map((s) => `symbols=${encodeURIComponent(s)}`).join("&")}`, { cache: "no-store", headers: { Accept: "application/json" } });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      if (data.stocks?.length) renderCompare(data.stocks, details);
      return;
    }
    const symbol = (params.get("symbol") || "").trim().toUpperCase();
    if (!symbol) return;
    const response = await fetch(`${API}/${encodeURIComponent(symbol)}`, { cache: "no-store", headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    renderIndividual(await response.json(), details);
  } catch (error) {
    console.warn("Stock pedigree trends unavailable:", error);
  }
}

let queued = false;
const observer = new MutationObserver(() => {
  const details = document.getElementById("stock-details");
  if (!details || queued || details.querySelector(".stock-pedigree-section")) return;
  queued = true;
  queueMicrotask(() => { queued = false; load(); });
});

if (document.body) observer.observe(document.body, { childList: true, subtree: true });
document.addEventListener("DOMContentLoaded", load);
setTimeout(load, 500);
setTimeout(load, 1800);
