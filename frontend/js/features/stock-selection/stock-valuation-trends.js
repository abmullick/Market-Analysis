const VALUATION_API = "/api/stocks";
const VALUATION_PALETTE = ["#2563eb", "#10b981", "#f59e0b", "#8b5cf6"];

function valuationFmt(v) {
  if (v == null || !Number.isFinite(Number(v))) return "—";
  return Number(v).toLocaleString("en-IN", { maximumFractionDigits: 2 });
}

function valuationCard(key, title, subtitle) {
  return `<div class="stock-chart-card stock-valuation-chart-card"><h3>${title}</h3><small>${subtitle}</small><div style="position:relative;height:250px"><canvas class="stock-chart-canvas ${key}" aria-label="${title}"></canvas></div></div>`;
}

function valuationEmpty(canvas) {
  if (!canvas?.parentElement) return;
  canvas.parentElement.innerHTML = `<div class="stock-chart-no-data"><div class="stock-chart-no-data-inner"><div class="stock-chart-no-data-icon">—</div><strong>No historical data available</strong><p>Historical observations for this valuation metric are not available, so there is no meaningful trend to display.</p><span class="stock-chart-no-data-badge">Data unavailable</span></div></div>`;
}

function valuationOptions() {
  return {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: "index", intersect: false },
    plugins: {
      legend: { position: "top", labels: { boxWidth: 10, usePointStyle: true, font: { size: 10 } } },
      tooltip: { callbacks: { label: (ctx) => `${ctx.dataset.label}: ${valuationFmt(ctx.parsed.y)}x` } },
    },
    scales: {
      x: { title: { display: true, text: "Financial year", color: "#475569", font: { size: 10, weight: "600" } }, grid: { display: false }, ticks: { font: { size: 9 }, color: "#64748b" } },
      y: { title: { display: true, text: "Multiple (x)", color: "#475569", font: { size: 10, weight: "600" } }, grid: { color: "#edf2f7" }, ticks: { font: { size: 9 }, color: "#64748b", callback: (v) => `${v}x` } },
    },
  };
}

function selectedSymbols() {
  const params = new URLSearchParams(location.search);
  const compare = params.get("compare");
  if (compare) return [...new Set(compare.split(",").map((x) => decodeURIComponent(x).trim().toUpperCase()).filter(Boolean))];
  const symbol = (params.get("symbol") || "").trim().toUpperCase();
  if (symbol) return [symbol];
  const rows = [...document.querySelectorAll(".stock-picker-row.selected[data-symbol]")];
  return [...new Set(rows.map((el) => el.dataset.symbol).filter(Boolean))];
}

async function valuationJson(symbol) {
  const response = await fetch(`${VALUATION_API}/${encodeURIComponent(symbol)}/charts`, { headers: { Accept: "application/json" }, cache: "no-store" });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}

function drawValuationChart(canvas, seriesList, labels) {
  if (!canvas) return false;
  if (typeof Chart === "undefined") return false;
  if (!seriesList.some((series) => series?.length)) { valuationEmpty(canvas); return true; }
  const years = [...new Set(seriesList.flatMap((series) => (series || []).map((x) => x.year)))].sort();
  if (!years.length) { valuationEmpty(canvas); return true; }
  const values = seriesList.flatMap((series) => (series || []).map((x) => x.value)).filter((v) => Number.isFinite(Number(v)));
  if (!values.length) { valuationEmpty(canvas); return true; }

  const chart = new Chart(canvas, {
    type: "line",
    data: { labels: years, datasets: seriesList.map((series, index) => {
      const map = Object.fromEntries((series || []).map((x) => [x.year, x.value]));
      const color = VALUATION_PALETTE[index % VALUATION_PALETTE.length];
      return { label: labels[index], data: years.map((year) => map[year] ?? null), borderColor: color, backgroundColor: `${color}12`, borderWidth: 2, pointRadius: 3, pointHoverRadius: 5, tension: .25, spanGaps: true, fill: true };
    }) },
    options: valuationOptions(),
  });

  requestAnimationFrame(() => {
    chart.resize();
    chart.update("none");
  });
  return true;
}

async function renderValuationCharts(section) {
  if (section.dataset.valuationCharts === "done" || section.dataset.valuationCharts === "loading") return;
  if (typeof Chart === "undefined") {
    setTimeout(() => renderValuationCharts(section), 100);
    return;
  }
  const symbols = selectedSymbols();
  if (!symbols.length) return;
  const grid = section.querySelector(".stock-trends-grid");
  if (!grid) return;
  section.dataset.valuationCharts = "loading";
  try {
    const responses = await Promise.all(symbols.map(valuationJson));
    const charts = responses.map((response) => response.charts || {});
    const names = responses.map((response, index) => response.name || response.symbol || symbols[index].replace(/\.NS$|\.BO$/i, ""));
    if (!grid.querySelector(".stock-valuation-chart-card")) {
      grid.insertAdjacentHTML("beforeend", valuationCard("valuation-pe-history", "P/E History", "Year-end market P/E based on annual EPS") + valuationCard("valuation-pb-history", "P/B History", "Historical price-to-book multiple"));
    }
    const peCanvas = grid.querySelector(".valuation-pe-history");
    const pbCanvas = grid.querySelector(".valuation-pb-history");
    const peDrawn = drawValuationChart(peCanvas, charts.map((chart) => chart.pe_history || []), names);
    const pbDrawn = drawValuationChart(pbCanvas, charts.map((chart) => chart.pb_history || []), names);
    if (peDrawn && pbDrawn) section.dataset.valuationCharts = "done";
    else delete section.dataset.valuationCharts;
  } catch (error) {
    delete section.dataset.valuationCharts;
    console.warn("Historical P/E and P/B charts unavailable:", error);
  }
}

function scanValuationSections() { document.querySelectorAll(".stock-trends-section").forEach((section) => renderValuationCharts(section)); }
const valuationObserver = new MutationObserver(scanValuationSections);
valuationObserver.observe(document.body, { childList: true, subtree: true });
document.addEventListener("DOMContentLoaded", scanValuationSections);
scanValuationSections();
