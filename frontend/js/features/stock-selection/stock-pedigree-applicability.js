// Sector-aware presentation for pedigree metrics whose underlying accounting model
// is not meaningful for every business type. Keeps the existing calculations intact.

const STYLE_ID = "stock-pedigree-applicability-styles";

function esc(v) {
  return String(v ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function ensureStyles() {
  if (document.getElementById(STYLE_ID)) return;
  const style = document.createElement("style");
  style.id = STYLE_ID;
  style.textContent = `
    .stock-pedigree-not-applicable,
    .stock-pedigree-no-data,
    .stock-chart-no-data {
      min-height: 238px;
      height: 100%;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 28px;
      box-sizing: border-box;
      text-align: center;
      background:
        radial-gradient(circle at 20% 15%, rgba(37,99,235,.08), transparent 38%),
        linear-gradient(135deg, #f8fbff, #ffffff 65%, #faf7ff);
      border: 1px solid #e1eaf4;
      border-radius: 14px;
    }
    .stock-pedigree-na-inner,
    .stock-pedigree-no-data-inner,
    .stock-chart-no-data-inner { max-width: 520px; }
    .stock-pedigree-na-icon,
    .stock-pedigree-no-data-icon,
    .stock-chart-no-data-icon {
      width: 42px;
      height: 42px;
      margin: 0 auto 10px;
      display: grid;
      place-items: center;
      border-radius: 50%;
      background: #edf4ff;
      color: #2563eb;
      font-size: 18px;
      font-weight: 900;
    }
    .stock-pedigree-na-inner strong,
    .stock-pedigree-no-data-inner strong,
    .stock-chart-no-data-inner strong {
      display: block;
      color: #17355d;
      font-size: 13px;
      margin-bottom: 6px;
    }
    .stock-pedigree-na-inner p,
    .stock-pedigree-no-data-inner p,
    .stock-chart-no-data-inner p {
      margin: 0;
      color: #71849a;
      font-size: 10px;
      line-height: 1.55;
    }
    .stock-pedigree-na-badge,
    .stock-pedigree-no-data-badge,
    .stock-chart-no-data-badge {
      display: inline-flex;
      margin-top: 11px;
      padding: 4px 8px;
      border: 1px solid #dbe7f3;
      border-radius: 999px;
      background: #fff;
      color: #64758a;
      font-size: 8px;
      font-weight: 800;
      letter-spacing: .05em;
      text-transform: uppercase;
    }
  `;
  document.head.appendChild(style);
}

function isFinancialSector() {
  const hero = document.querySelector("#stock-details .stock-hero p");
  const text = String(hero?.textContent || "").toLowerCase();
  return text.includes("financial services") || text.includes("financials");
}

function replaceWorkingCapitalCard() {
  const section = document.querySelector("#stock-details .stock-pedigree-section:not(.stock-pedigree-compare)");
  if (!section || !isFinancialSector()) return;

  const cards = [...section.querySelectorAll(".stock-pedigree-chart-card")];
  const card = cards.find((candidate) =>
    candidate.querySelector("h3")?.textContent?.trim().toLowerCase() === "working capital cycle"
  );
  if (!card || card.dataset.applicabilityHandled === "1") return;

  const wrap = card.querySelector(".stock-pedigree-chart-wrap");
  if (!wrap) return;

  card.dataset.applicabilityHandled = "1";
  wrap.innerHTML = `
    <div class="stock-pedigree-not-applicable">
      <div class="stock-pedigree-na-inner">
        <div class="stock-pedigree-na-icon">≈</div>
        <strong>Working Capital Cycle is not applicable</strong>
        <p>
          This diagnostic is designed for businesses with operating receivables,
          inventory and trade payables. For financial-services companies, those
          balances do not represent the same operating cycle, so the engine does
          not calculate a conventional CCC.
        </p>
        <span class="stock-pedigree-na-badge">Financial-sector lens</span>
      </div>
    </div>`;
}

function replaceEmptyChartCards() {
  if (typeof Chart === "undefined") return;

  const cards = [...document.querySelectorAll("#stock-details .stock-pedigree-chart-card")];
  cards.forEach((card) => {
    if (card.dataset.noDataHandled === "1" || card.dataset.applicabilityHandled === "1") return;

    const wrap = card.querySelector(".stock-pedigree-chart-wrap");
    const canvas = wrap?.querySelector("canvas");
    if (!wrap || !canvas) return;

    const chart = Chart.getChart(canvas);
    if (!chart) {
      card.dataset.noDataHandled = "1";
      wrap.innerHTML = `
        <div class="stock-pedigree-no-data">
          <div class="stock-pedigree-no-data-inner">
            <div class="stock-pedigree-no-data-icon">—</div>
            <strong>No historical data available</strong>
            <p>This chart needs historical observations for this metric. The available data for this company does not contain enough observations to display the trend.</p>
            <span class="stock-pedigree-no-data-badge">Data unavailable</span>
          </div>
        </div>`;
      return;
    }

    const values = (chart.data?.datasets || [])
      .flatMap((dataset) => dataset.data || [])
      .filter((value) => Number.isFinite(Number(value)));
    const labels = chart.data?.labels || [];

    if (!values.length) {
      chart.destroy();
      card.dataset.noDataHandled = "1";
      wrap.innerHTML = `
        <div class="stock-pedigree-no-data">
          <div class="stock-pedigree-no-data-inner">
            <div class="stock-pedigree-no-data-icon">—</div>
            <strong>No historical data available</strong>
            <p>This chart needs historical observations for this metric. The available data for this company does not contain enough observations to display the trend.</p>
            <span class="stock-pedigree-no-data-badge">Data unavailable</span>
          </div>
        </div>`;
    } else if (labels.length < 2) {
      chart.destroy();
      card.dataset.noDataHandled = "1";
      wrap.innerHTML = `
        <div class="stock-pedigree-no-data">
          <div class="stock-pedigree-no-data-inner">
            <div class="stock-pedigree-no-data-icon">≈</div>
            <strong>Insufficient historical data</strong>
            <p>Only limited historical observations are available for this metric, so a meaningful trend cannot be shown.</p>
            <span class="stock-pedigree-no-data-badge">Insufficient history</span>
          </div>
        </div>`;
    }
  });
}

function genericEmptyChartMarkup() {
  return `
    <div class="stock-chart-no-data">
      <div class="stock-chart-no-data-inner">
        <div class="stock-chart-no-data-icon">—</div>
        <strong>No historical data available</strong>
        <p>Historical observations for this metric are not available for this company, so there is no meaningful trend to display.</p>
        <span class="stock-chart-no-data-badge">Data unavailable</span>
      </div>
    </div>`;
}

function scheduleGenericEmptyChartCheck(card) {
  if (card.dataset.emptyStateScheduled === "1") return;
  card.dataset.emptyStateScheduled = "1";
  card.dataset.emptyStateSeenAt = String(Date.now());

  window.setTimeout(() => {
    if (!document.body.contains(card)) return;
    if (card.dataset.noDataHandled === "1") return;

    const canvas = card.querySelector("canvas.stock-chart-canvas, canvas");
    if (!canvas) return;

    // Never replace a live chart. This is deliberately different from the
    // previous implementation: absence of a Chart instance is not enough to
    // justify removing a canvas before the chart renderer has completed.
    const chart = typeof Chart !== "undefined" ? Chart.getChart(canvas) : null;
    if (chart) return;

    const age = Date.now() - Number(card.dataset.emptyStateSeenAt || Date.now());
    if (age < 2400) return;

    card.dataset.noDataHandled = "1";
    const host = canvas.parentElement;
    if (!host || !host.contains(canvas)) return;
    host.replaceChildren();
    host.insertAdjacentHTML("beforeend", genericEmptyChartMarkup());
  }, 2500);
}

function replaceGenericEmptyChartCards() {
  document.querySelectorAll("#stock-details .stock-trends-section .stock-chart-card:not([data-no-data-handled='1'])").forEach(scheduleGenericEmptyChartCheck);
}

function scan() {
  ensureStyles();
  replaceWorkingCapitalCard();
  replaceEmptyChartCards();
  replaceGenericEmptyChartCards();
}

const observer = new MutationObserver(scan);
observer.observe(document.body, { childList: true, subtree: true });
scan();
