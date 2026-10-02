const STOCK_API = "/api/stocks";
const PALETTE = ["#2563eb", "#10b981", "#f59e0b", "#8b5cf6"];

function esc(v) {
  return String(v ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");
}

function fmt(v, suffix = "") {
  if (v == null || !Number.isFinite(Number(v))) return "—";
  return `${Number(v).toLocaleString("en-IN", { maximumFractionDigits: 2 })}${suffix}`;
}

async function getJson(path) {
  const response = await fetch(path, { headers: { Accept: "application/json" }, cache: "no-store" });
  const data = await response.json();
  if (!response.ok) throw new Error(data?.detail || `HTTP ${response.status}`);
  return data;
}

function chartCard(id, title, subtitle) {
  return `<div class="stock-chart-card"><h3>${esc(title)}</h3><small>${esc(subtitle)}</small><canvas id="${esc(id)}" class="stock-chart-canvas"></canvas></div>`;
}

function commonChartOptions(suffix = "%") {
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
      y: { grid: { color: "#edf2f7" }, ticks: { font: { size: 9 }, color: "#64748b", callback: (v) => `${v}${suffix}` } },
    },
  };
}

function drawSingleChart(canvasId, series, label, color = PALETTE[0], suffix = "%") {
  if (typeof Chart === "undefined") return;
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  const labels = series.map((x) => x.year);
  const data = series.map((x) => x.value);
  new Chart(canvas, {
    type: "line",
    data: { labels, datasets: [{ label, data, borderColor: color, backgroundColor: `${color}18`, borderWidth: 2, pointRadius: 3, pointHoverRadius: 5, tension: .25, spanGaps: true, fill: true }] },
    options: commonChartOptions(suffix),
  });
}

function drawPriceChart(canvasId, charts) {
  if (typeof Chart === "undefined") return;
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  const all = [...(charts.price_cagr_3y || []), ...(charts.price_cagr_5y || [])];
  const labels = [...new Set(all.map((x) => x.year))].sort();
  const map = (series) => Object.fromEntries((series || []).map((x) => [x.year, x.value]));
  const a = map(charts.price_cagr_3y); const b = map(charts.price_cagr_5y);
  new Chart(canvas, {
    type: "line",
    data: { labels, datasets: [
      { label: "3Y Price CAGR", data: labels.map((y) => a[y] ?? null), borderColor: PALETTE[0], backgroundColor: `${PALETTE[0]}12`, borderWidth: 2, pointRadius: 3, tension: .25, spanGaps: true },
      { label: "5Y Price CAGR", data: labels.map((y) => b[y] ?? null), borderColor: PALETTE[2], backgroundColor: `${PALETTE[2]}10`, borderWidth: 2, pointRadius: 3, tension: .25, spanGaps: true },
    ] },
    options: commonChartOptions("%"),
  });
}

function renderTrendSection(details, charts, comparison = false, names = []) {
  const prefix = comparison ? "compare" : "stock";
  const section = document.createElement("section");
  section.className = comparison ? "stock-trends-section stock-comparison-trends" : "stock-trends-section";
  section.innerHTML = `
    <div class="stock-trends-header">
      <div><h2>${comparison ? "Historical Growth & Return Trends" : "Historical Growth & Return Trends"}</h2>
      <p>${comparison ? "Compare the trajectory of earnings, revenue, ROE and market-price CAGR across the selected stocks." : "Historical trends complement the current ratios: growth quality, return on equity and the price paid for that growth."}</p></div>
    </div>
    <div class="stock-trends-grid">
      ${chartCard(`${prefix}-eps-growth`, "EPS Growth", "Annual year-over-year EPS growth")}
      ${chartCard(`${prefix}-revenue-growth`, "Revenue Growth", "Annual year-over-year revenue growth")}
      ${chartCard(`${prefix}-roe-trend`, "ROE Trend", "Derived annual ROE using average equity")}
      ${chartCard(`${prefix}-price-cagr`, "Price Growth (CAGR)", "Rolling 3-year and 5-year annualised price growth")}
    </div>`;
  details.appendChild(section);

  if (!comparison) {
    drawSingleChart(`${prefix}-eps-growth`, charts.eps_growth || [], "EPS growth");
    drawSingleChart(`${prefix}-revenue-growth`, charts.revenue_growth || [], "Revenue growth", PALETTE[1]);
    drawSingleChart(`${prefix}-roe-trend`, charts.roe_trend || [], "ROE", PALETTE[3]);
    drawPriceChart(`${prefix}-price-cagr`, charts);
    return;
  }

  const datasetsFor = (key) => names.map((name, index) => ({
    label: name,
    data: Object.fromEntries((charts[index]?.[key] || []).map((x) => [x.year, x.value])),
    color: PALETTE[index % PALETTE.length],
  }));

  [
    ["compare-eps-growth", "eps_growth", "EPS growth"],
    ["compare-revenue-growth", "revenue_growth", "Revenue growth"],
    ["compare-roe-trend", "roe_trend", "ROE"],
  ].forEach(([id, key, label]) => {
    const canvas = document.getElementById(id); if (!canvas) return;
    const rows = datasetsFor(key); const labels = [...new Set(rows.flatMap((r) => Object.keys(r.data)))].sort();
    new Chart(canvas, { type: "line", data: { labels, datasets: rows.map((r) => ({ label: r.label, data: labels.map((y) => r.data[y] ?? null), borderColor: r.color, backgroundColor: `${r.color}12`, borderWidth: 2, pointRadius: 3, tension: .25, spanGaps: true })) }, options: commonChartOptions("%") });
  });

  const canvas = document.getElementById("compare-price-cagr");
  if (canvas) {
    const rows = names.map((name, index) => ({ name, c3: Object.fromEntries((charts[index]?.price_cagr_3y || []).map((x) => [x.year, x.value])), c5: Object.fromEntries((charts[index]?.price_cagr_5y || []).map((x) => [x.year, x.value])), color: PALETTE[index % PALETTE.length] }));
    const labels = [...new Set(rows.flatMap((r) => [...Object.keys(r.c3), ...Object.keys(r.c5)]))].sort();
    new Chart(canvas, { type: "line", data: { labels, datasets: rows.flatMap((r) => [
      { label: `${r.name} · 3Y`, data: labels.map((y) => r.c3[y] ?? null), borderColor: r.color, borderWidth: 2, pointRadius: 2, tension: .25, spanGaps: true },
      { label: `${r.name} · 5Y`, data: labels.map((y) => r.c5[y] ?? null), borderColor: r.color, borderDash: [5, 4], borderWidth: 1.5, pointRadius: 2, tension: .25, spanGaps: true },
    ]) }, options: commonChartOptions("%") });
  }
}

function ratioCard(label, value, suffix = "", negative = false) {
  return `<div class="stock-ratio-card ${negative ? "is-negative" : ""}"><span>${esc(label)}</span><strong>${esc(fmt(value, suffix))}</strong></div>`;
}

function renderExtendedSingle(details, f) {
  if (details.querySelector(".stock-extended-section")) return;
  const financial = String(f.sector || "").toLowerCase() === "financial services";
  const section = document.createElement("section");
  section.className = "stock-extended-section";
  section.innerHTML = `
    <div class="stock-extended-header"><h2>Core Fundamental Cross-Checks</h2><p>${financial ? "Financial-sector lens: combine P/B + P/E with ROE and ROA; leverage and conventional FCF need sector context." : "Non-financial lens: combine earnings growth and P/E with ROE/ROCE, leverage, cash conversion and free cash flow."}</p></div>
    <div class="stock-ratio-grid">
      ${ratioCard("ROCE", f.roce, "%")}
      ${ratioCard("FCF Margin", f.fcf_margin, "%", Number(f.fcf_margin) < 0)}
      ${ratioCard("CFO / Net Profit", f.cash_conversion, "%", Number(f.cash_conversion) < 0)}
      ${ratioCard("Net Debt", f.net_debt, f.currency === "INR" ? " ₹" : "")}
      ${ratioCard("Net Debt / EBITDA", financial ? null : f.net_debt_ebitda, "x")}
      ${ratioCard("Debt / Equity", f.debt_equity, "x")}
      ${ratioCard("P/E", f.pe, "x")}
      ${ratioCard("P/B", f.pb, "x")}
    </div>
    <div class="stock-ratio-note">Use these metrics together rather than in isolation. For lenders, P/B and returns on equity/assets are central; for industrial and service businesses, P/E, ROCE, leverage and cash conversion provide a more complete cross-check.</div>`;
  details.appendChild(section);
  details.appendChild(document.createElement("div"));
}

function renderExtendedCompare(details, fs) {
  if (details.querySelector(".stock-extended-compare")) return;
  const keys = [
    ["ROCE", "roce", "%"], ["FCF Margin", "fcf_margin", "%"], ["CFO / Net Profit", "cash_conversion", "%"],
    ["Net Debt / EBITDA", "net_debt_ebitda", "x"], ["Debt / Equity", "debt_equity", "x"], ["P/E", "pe", "x"], ["P/B", "pb", "x"], ["PEG", "peg", "x"],
  ];
  const table = document.createElement("div"); table.className = "stock-extended-compare";
  const direction = { roce: "high", fcf_margin: "high", cash_conversion: "high", net_debt_ebitda: "low", debt_equity: "low", pe: "low", pb: "low", peg: "low" };
  const val = (f, k, suffix) => {
    if (f[k] == null || !Number.isFinite(Number(f[k]))) return "—";
    return `${fmt(f[k])}${suffix}`;
  };
  const rows = keys.map(([label, key, suffix]) => {
    const values = fs.map((f) => Number(f[key])).filter(Number.isFinite);
    const best = values.length > 1 ? (direction[key] === "high" ? Math.max(...values) : Math.min(...values)) : null;
    return `<tr><td>${esc(label)}</td>${fs.map((f) => {
      const n = Number(f[key]);
      const cls = best != null && Number.isFinite(n) && n === best ? "good" : Number.isFinite(n) && ["fcf_margin", "cash_conversion"].includes(key) && n < 0 ? "bad" : "";
      return `<td class="${cls}">${esc(val(f, key, suffix))}</td>`;
    }).join("")}</tr>`;
  }).join("");
  table.innerHTML = `<table><thead><tr><th>Additional Ratio</th>${fs.map((f) => `<th>${esc(f.name || f.symbol)}</th>`).join("")}</tr></thead><tbody>${rows}</tbody></table>`;
  details.appendChild(table);
}

async function renderIndividual(symbol, details) {
  try {
    const [analysis, trend] = await Promise.all([
      getJson(`${STOCK_API}/${encodeURIComponent(symbol)}`),
      getJson(`${STOCK_API}/${encodeURIComponent(symbol)}/charts`),
    ]);
    renderExtendedSingle(details, analysis.fundamentals || {});
    renderTrendSection(details, trend.charts || {});
  } catch (error) {
    console.warn("Stock trend panels unavailable:", error);
  }
}

async function renderComparison(symbols, details) {
  try {
    const [analyses, trends] = await Promise.all([
      Promise.all(symbols.map((s) => getJson(`${STOCK_API}/${encodeURIComponent(s)}`))),
      Promise.all(symbols.map((s) => getJson(`${STOCK_API}/${encodeURIComponent(s)}/charts`))),
    ]);
    const fs = analyses.map((x) => x.fundamentals || {});
    renderExtendedCompare(details, fs);
    renderTrendSection(details, trends.map((x) => x.charts || {}), true, fs.map((f) => f.name || f.symbol));
  } catch (error) {
    console.warn("Stock comparison trend panels unavailable:", error);
  }
}

function init() {
  const details = document.getElementById("stock-details");
  if (!details) return;
  let lastKey = "";
  const render = () => {
    const params = new URLSearchParams(location.search);
    const symbol = params.get("symbol");
    const compare = params.get("compare");
    const key = symbol ? `symbol:${symbol}` : compare ? `compare:${compare}` : "";
    if (!key || key === lastKey || !details.children.length) return;
    lastKey = key;
    if (symbol) renderIndividual(symbol.trim().toUpperCase(), details);
    else if (compare) renderComparison(compare.split(",").map((x) => decodeURIComponent(x).trim().toUpperCase()).filter(Boolean).slice(0, 4), details);
  };
  new MutationObserver(render).observe(details, { childList: true, subtree: true });
  addEventListener("popstate", () => { lastKey = ""; setTimeout(render, 50); });
  setTimeout(render, 250);
}

init();
