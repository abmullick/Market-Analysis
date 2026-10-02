const VALUATION_API = "/api/stocks";
const VALUATION_PALETTE = ["#2563eb", "#10b981", "#f59e0b", "#8b5cf6"];

function valuationFmt(v) {
  if (v == null || !Number.isFinite(Number(v))) return "—";
  return Number(v).toLocaleString("en-IN", { maximumFractionDigits: 2 });
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

function valuationCard(id, title, subtitle) {
  return `<div class="stock-chart-card stock-valuation-chart-card"><h3>${title}</h3><small>${subtitle}</small><canvas id="${id}" class="stock-chart-canvas"></canvas></div>`;
}

async function valuationJson(symbol) {
  const response = await fetch(`${VALUATION_API}/${encodeURIComponent(symbol)}/charts`, { headers: { Accept: "application/json" }, cache: "no-store" });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}

function selectedSymbols() {
  return [...document.querySelectorAll(".stock-picker-row.selected[data-symbol]")].map((el) => el.dataset.symbol).filter(Boolean);
}

function drawValuationChart(canvas, seriesList, labels, yLabel) {
  if (typeof Chart === "undefined" || !canvas || !seriesList.some((s) => s.length)) return;
  const years = [...new Set(seriesList.flatMap((s) => s.map((x) => x.year)))].sort();
  if (!years.length) return;
  new Chart(canvas, {
    type: "line",
    data: { labels: years, datasets: seriesList.map((series, index) => {
      const map = Object.fromEntries(series.map((x) => [x.year, x.value]));
      const color = VALUATION_PALETTE[index % VALUATION_PALETTE.length];
      return { label: labels[index], data: years.map((y) => map[y] ?? null), borderColor: color, backgroundColor: `${color}12`, borderWidth: 2, pointRadius: 3, pointHoverRadius: 5, tension: .25, spanGaps: true, fill: true };
    }) },
    options: valuationOptions(),
  });
}

async function renderValuationCharts(section) {
  if (section.dataset.valuationCharts === "done" || section.dataset.valuationCharts === "loading") return;
  const symbols = selectedSymbols();
  if (!symbols.length) return;
  section.dataset.valuationCharts = "loading";

  try {
    const responses = await Promise.all(symbols.map(valuationJson));
    const charts = responses.map((x) => x.charts || {});
    const names = symbols.map((s) => s.replace(/\.NS$|\.BO$/i, ""));
    const grid = section.querySelector(".stock-trends-grid");
    if (!grid) return;

    grid.insertAdjacentHTML("beforeend", valuationCard("valuation-pe-history", "P/E History", "Year-end market P/E based on annual EPS"));
    grid.insertAdjacentHTML("beforeend", valuationCard("valuation-pb-history", "P/B History", "Historical price-to-book multiple"));

    drawValuationChart(document.getElementById("valuation-pe-history"), charts.map((c) => c.pe_history || []), names, "P/E (x)");
    drawValuationChart(document.getElementById("valuation-pb-history"), charts.map((c) => c.pb_history || []), names, "P/B (x)");
    section.dataset.valuationCharts = "done";
  } catch (error) {
    delete section.dataset.valuationCharts;
    console.warn("Historical valuation charts unavailable:", error);
  }
}

function scanValuationSections() {
  document.querySelectorAll(".stock-trends-section").forEach(renderValuationCharts);
}

const valuationObserver = new MutationObserver(scanValuationSections);
valuationObserver.observe(document.body, { childList: true, subtree: true });
scanValuationSections();
