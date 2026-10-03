// Visual story layer for Stock Analysis.
// Adds explanatory links between existing raw metric cards, historical charts,
// and the derived Momentum / Valuation engines. It never removes or replaces
// any existing analysis content.

const STORY_STYLE_ID = "stock-analysis-story-styles";

function textOf(el) {
  return (el?.textContent || "").trim().replace(/\s+/g, " ");
}

function findSectionByTitle(root, title) {
  return [...root.querySelectorAll("section")].find((section) => {
    const h = section.querySelector("h2");
    return h && textOf(h).toLowerCase() === title.toLowerCase();
  }) || null;
}

function addMetricBadge(section, target, label) {
  if (!section || section.querySelector(".stock-story-feed-badge")) return;
  const header = section.querySelector(".stock-section-header");
  if (!header) return;
  const badge = document.createElement("span");
  badge.className = "stock-story-feed-badge";
  badge.innerHTML = `<span class="stock-story-feed-dot"></span>${label}<span class="stock-story-arrow">→</span><b>${target}</b>`;
  header.appendChild(badge);
}

function addChartStoryLabels(section) {
  if (!section || section.dataset.storyLabels === "done") return;
  const grid = section.querySelector(".stock-trends-grid");
  if (!grid) return;

  const cards = [...grid.querySelectorAll(".stock-chart-card")];
  const valuationCards = cards.filter((card) => card.classList.contains("stock-valuation-chart-card"));
  if (!cards.length || !valuationCards.length) return;

  const firstValuation = valuationCards[0];
  if (!grid.querySelector(".stock-story-chart-divider.growth")) {
    const growthDivider = document.createElement("div");
    growthDivider.className = "stock-story-chart-divider growth";
    growthDivider.innerHTML = `<span>Business evidence</span><b>Growth & returns → Fundamental Momentum</b><small>These historical charts show the underlying trajectory used by the Momentum engine.</small>`;
    grid.insertBefore(growthDivider, cards[0]);
  }

  if (!grid.querySelector(".stock-story-chart-divider.valuation")) {
    const valuationDivider = document.createElement("div");
    valuationDivider.className = "stock-story-chart-divider valuation";
    valuationDivider.innerHTML = `<span>Market valuation evidence</span><b>P/E & P/B history → Valuation Context</b><small>These charts provide the historical valuation context used by the sector-aware Valuation engine.</small>`;
    grid.insertBefore(valuationDivider, firstValuation);
  }

  section.dataset.storyLabels = "done";
}

function addEngineSourceNote(section, kind) {
  if (!section || section.querySelector(".stock-story-engine-link")) return;
  const header = section.querySelector(".stock-momentum-header, .stock-valuation-header");
  if (!header) return;
  const note = document.createElement("div");
  note.className = `stock-story-engine-link ${kind}`;
  note.innerHTML = kind === "momentum"
    ? `<span>↑</span><div><b>Read this together with the Growth section and historical Growth & Return Trends above</b><small>The current Momentum Index is the engine's latest interpretation of those underlying business trajectories. The timeline reconstructs the same framework historically.</small></div>`
    : `<span>↑</span><div><b>Read this together with the Valuation section and P/E & P/B history above</b><small>The current Valuation Context interprets today's multiples against the company's own historical valuation, using the applicable sector lens. The timeline reconstructs that context historically.</small></div>`;
  header.insertAdjacentElement("afterend", note);
}

function individualStory(details) {
  const growth = findSectionByTitle(details, "Growth");
  const valuation = findSectionByTitle(details, "Valuation");
  const momentum = details.querySelector(".stock-fundamental-momentum");
  const valuationEngine = details.querySelector(".stock-valuation-engine");
  const trends = details.querySelector(".stock-trends-section:not(.stock-comparison-trends)");

  if (growth) addMetricBadge(growth, "Fundamental Momentum", "Feeds");
  if (valuation) addMetricBadge(valuation, "Valuation Context", "Feeds");
  if (trends) addChartStoryLabels(trends);
  if (momentum) addEngineSourceNote(momentum, "momentum");
  if (valuationEngine) addEngineSourceNote(valuationEngine, "valuation");

  if (momentum && valuationEngine && !details.querySelector(".stock-story-synthesis")) {
    const synthesis = document.createElement("div");
    synthesis.className = "stock-story-synthesis";
    synthesis.innerHTML = `<div class="stock-story-synthesis-line"><span>Business trajectory</span><i>+</i><span>Market valuation</span><strong>→</strong><b>Business–Valuation Matrix</b></div><small>The two engines are designed to be read together: one describes how fundamentals are changing; the other describes where the current valuation sits relative to the company's own history.</small>`;
    valuationEngine.insertAdjacentElement("afterend", synthesis);
  }
}

function comparisonStory(root) {
  const table = root.querySelector(".stock-comparison-table-wrap");
  const trends = root.querySelector(".stock-comparison-trends");
  const advanced = root.querySelector(".advanced-insights");
  if (!table && !trends && !advanced) return;

  if (table && !root.querySelector(".stock-comparison-story")) {
    const story = document.createElement("section");
    story.className = "stock-comparison-story";
    story.innerHTML = `<div class="stock-comparison-story-title"><span>Comparison story</span><small>Keep the existing detailed table below — this layer connects the same data into an analytical flow.</small></div><div class="stock-comparison-story-flow"><div><b>1</b><strong>Raw metrics</strong><span>Growth · Valuation · Profitability · Financial health</span></div><i>→</i><div><b>2</b><strong>Historical evidence</strong><span>Growth, returns, price and P/E/P/B trends</span></div><i>→</i><div><b>3</b><strong>Engine interpretation</strong><span>Fundamental Momentum + Valuation Context</span></div><i>→</i><div><b>4</b><strong>Relationship</strong><span>Business–Valuation Matrix + comparison summary</span></div></div>`;
    table.parentNode.insertBefore(story, table);
  }

  if (trends) addChartStoryLabels(trends);
  if (advanced && !advanced.querySelector(".stock-comparison-story-link")) {
    const link = document.createElement("div");
    link.className = "stock-comparison-story-link";
    link.innerHTML = `<span>3 → 4</span><div><b>From evidence to interpretation</b><small>The score cards translate the historical evidence into two engine outputs for each stock. The matrix then places those two outputs together, followed by the existing detailed comparison and summary.</small></div>`;
    advanced.insertAdjacentElement("afterbegin", link);
  }
}

function ensureStyles() {
  if (document.getElementById(STORY_STYLE_ID)) return;
  const style = document.createElement("style");
  style.id = STORY_STYLE_ID;
  style.textContent = `
.stock-story-feed-badge{margin-left:auto;display:inline-flex;align-items:center;gap:6px;padding:5px 8px;border:1px solid #dbe7f3;border-radius:999px;background:#f7fbff;color:#60758d;font-size:9px;font-weight:700;white-space:nowrap}.stock-story-feed-badge b{color:#1d4ed8}.stock-story-feed-dot{width:6px;height:6px;border-radius:50%;background:#2563eb}.stock-story-arrow{color:#94a3b8}.stock-story-chart-divider{grid-column:1/-1;display:flex;align-items:center;gap:9px;margin-top:5px;padding:8px 11px;border:1px solid #dce7f2;border-radius:10px;background:linear-gradient(90deg,#f7fbff,#fff)}.stock-story-chart-divider span{font-size:8px;text-transform:uppercase;letter-spacing:.08em;font-weight:800;color:#64748b}.stock-story-chart-divider b{font-size:10px;color:#17355d}.stock-story-chart-divider small{font-size:9px;color:#8291a3}.stock-story-engine-link{display:flex;align-items:flex-start;gap:9px;margin:11px 0 0;padding:9px 11px;border:1px solid #dce7f2;border-radius:10px;background:#f8fbff}.stock-story-engine-link>span{display:grid;place-items:center;width:20px;height:20px;border-radius:50%;background:#e8f1ff;color:#2563eb;font-weight:800;font-size:12px;flex:0 0 20px}.stock-story-engine-link b{display:block;color:#284968;font-size:9px}.stock-story-engine-link small{display:block;margin-top:3px;color:#71849a;font-size:9px;line-height:1.4}.stock-story-synthesis{margin:12px 0 0;padding:12px 14px;border:1px solid #d9e5f0;border-radius:12px;background:linear-gradient(90deg,#f7fbff,#fff);text-align:center}.stock-story-synthesis-line{display:flex;align-items:center;justify-content:center;gap:8px;flex-wrap:wrap;color:#536b84;font-size:10px}.stock-story-synthesis-line span{padding:5px 8px;border-radius:999px;background:#edf5ff;color:#315a83;font-weight:700}.stock-story-synthesis-line i{font-style:normal;color:#94a3b8}.stock-story-synthesis-line strong{color:#2563eb;font-size:14px}.stock-story-synthesis-line b{color:#17355d}.stock-story-synthesis>small{display:block;margin-top:5px;color:#71849a;font-size:9px;line-height:1.4}.stock-comparison-story{margin:0 0 15px;padding:14px 16px;border:1px solid #dbe6f1;border-radius:15px;background:linear-gradient(135deg,#fbfdff,#f4f9ff);box-shadow:0 5px 18px rgba(15,23,42,.04)}.stock-comparison-story-title{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:11px}.stock-comparison-story-title span{color:#17355d;font-size:13px;font-weight:800}.stock-comparison-story-title small{color:#7a8da1;font-size:9px}.stock-comparison-story-flow{display:grid;grid-template-columns:1fr auto 1fr auto 1fr auto 1fr;align-items:center;gap:7px}.stock-comparison-story-flow>div{min-height:72px;padding:9px;border:1px solid #dbe5ef;border-radius:11px;background:#fff}.stock-comparison-story-flow b{display:grid;place-items:center;width:19px;height:19px;border-radius:50%;background:#e9f2ff;color:#2563eb;font-size:9px}.stock-comparison-story-flow strong{display:block;margin-top:5px;color:#17355d;font-size:10px}.stock-comparison-story-flow span{display:block;margin-top:3px;color:#7a8da1;font-size:8px;line-height:1.35}.stock-comparison-story-flow>i{font-style:normal;color:#8aa0b6;font-size:16px}.stock-comparison-story-link{display:flex;gap:9px;align-items:flex-start;margin-bottom:12px;padding:9px 11px;border:1px solid #dbe7f3;border-radius:10px;background:#f8fbff}.stock-comparison-story-link>span{padding:4px 6px;border-radius:999px;background:#e9f2ff;color:#2563eb;font-size:8px;font-weight:800}.stock-comparison-story-link b{display:block;color:#284968;font-size:9px}.stock-comparison-story-link small{display:block;margin-top:3px;color:#71849a;font-size:9px;line-height:1.4}@media(max-width:850px){.stock-story-feed-badge{margin-left:0;margin-top:5px}.stock-story-chart-divider{align-items:flex-start;flex-wrap:wrap}.stock-story-chart-divider small{width:100%}.stock-comparison-story-flow{grid-template-columns:1fr}.stock-comparison-story-flow>i{transform:rotate(90deg);justify-self:center}.stock-comparison-story-title{display:block}.stock-comparison-story-title small{display:block;margin-top:4px}}
  `;
  document.head.appendChild(style);
}

function scan() {
  ensureStyles();
  const details = document.getElementById("stock-details");
  if (details && !document.getElementById("stock-analysis-screen")?.hidden) individualStory(details);

  const screen = document.getElementById("stock-analysis-screen");
  if (screen && !screen.hidden) comparisonStory(screen);
}

const observer = new MutationObserver(() => scan());
observer.observe(document.body, { childList: true, subtree: true });
document.addEventListener("DOMContentLoaded", scan);
scan();
