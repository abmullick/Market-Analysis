// Visual story layer for Stock Analysis.
// Presentation only: never removes or replaces existing analysis.
const STORY_STYLE_ID = "stock-analysis-story-styles";

const textOf = (el) => (el?.textContent || "").trim().replace(/\s+/g, " ");

function findSectionByTitle(root, title) {
  return [...root.querySelectorAll(".stock-section")].find((section) => {
    const h = section.querySelector(".stock-section-header h2");
    return h && textOf(h).toLowerCase() === title.toLowerCase();
  }) || null;
}

function addFeedBadge(section, target, tone = "blue") {
  if (!section || section.querySelector(".stock-story-feed-badge")) return;
  const header = section.querySelector(".stock-section-header");
  if (!header) return;
  const badge = document.createElement("span");
  badge.className = `stock-story-feed-badge ${tone}`;
  badge.innerHTML = `<span class="stock-story-feed-dot"></span><span>Feeds</span><span class="stock-story-arrow">→</span><b>${target}</b>`;
  header.appendChild(badge);
}

function addIndividualStoryRibbon(details) {
  if (details.querySelector(".stock-analysis-story-ribbon")) return;
  const ribbon = document.createElement("section");
  ribbon.className = "stock-analysis-story-ribbon";
  ribbon.innerHTML = `
    <div class="stock-story-ribbon-heading">
      <div><span class="stock-story-kicker">HOW TO READ THE ANALYSIS</span><h2>From business evidence to valuation context</h2></div>
      <span class="stock-story-ribbon-note">Existing metrics and charts remain unchanged</span>
    </div>
    <div class="stock-story-ribbon-flow">
      <div><span>01</span><b>Business fundamentals</b><small>Growth · profitability · financial health</small></div>
      <i>→</i>
      <div><span>02</span><b>Historical evidence</b><small>Growth, returns and valuation trends</small></div>
      <i>→</i>
      <div class="accent"><span>03</span><b>Engine interpretation</b><small>Fundamental Momentum + Valuation Context</small></div>
      <i>→</i>
      <div><span>04</span><b>Combined view</b><small>Read business trajectory together with valuation</small></div>
    </div>`;
  const first = details.firstElementChild;
  if (first) first.insertAdjacentElement("afterend", ribbon);
  else details.appendChild(ribbon);
}

function addChartStoryLabels(section) {
  if (!section || section.dataset.storyLabels === "done") return;
  const grid = section.querySelector(".stock-trends-grid");
  if (!grid) return;
  const cards = [...grid.querySelectorAll(".stock-chart-card")];
  if (!cards.length) return;
  const valuationCards = cards.filter((card) => card.classList.contains("stock-valuation-chart-card"));

  if (!grid.querySelector(".stock-story-chart-divider.growth")) {
    const d = document.createElement("div");
    d.className = "stock-story-chart-divider growth";
    d.innerHTML = `<span>Business evidence</span><b>Growth & return history → Fundamental Momentum</b><small>The charts immediately below show the historical business trajectory interpreted by the Momentum engine.</small>`;
    grid.insertBefore(d, cards[0]);
  }

  if (valuationCards.length && !grid.querySelector(".stock-story-chart-divider.valuation")) {
    const d = document.createElement("div");
    d.className = "stock-story-chart-divider valuation";
    d.innerHTML = `<span>Market evidence</span><b>P/E & P/B history → Valuation Context</b><small>These valuation charts provide the historical context used by the sector-aware Valuation engine.</small>`;
    grid.insertBefore(d, valuationCards[0]);
  }
  section.dataset.storyLabels = "done";
}

function addEngineBridge(section, kind) {
  if (!section || section.querySelector(".stock-story-engine-link")) return;
  const header = section.querySelector(".stock-momentum-header, .stock-valuation-header");
  if (!header) return;
  const note = document.createElement("div");
  note.className = `stock-story-engine-link ${kind}`;
  note.innerHTML = kind === "momentum"
    ? `<span>↑</span><div><b>Connect this with Growth and Historical Growth & Return Trends</b><small>The Momentum Index is the latest engine interpretation of the underlying business trajectory. Its Trend Timeline reconstructs the same framework historically.</small></div>`
    : `<span>↑</span><div><b>Connect this with Valuation Metrics and P/E & P/B history</b><small>Valuation Context interprets current multiples against the company's own history using the applicable sector lens. Its timeline reconstructs that context historically.</small></div>`;
  header.insertAdjacentElement("afterend", note);
}

function addSynthesis(momentum, valuation) {
  if (!momentum || !valuation || momentum.parentElement?.querySelector(".stock-story-synthesis")) return;
  const synthesis = document.createElement("section");
  synthesis.className = "stock-story-synthesis";
  synthesis.innerHTML = `<div class="stock-story-synthesis-line"><span>Business trajectory</span><i>+</i><span>Market valuation</span><strong>→</strong><b>Combined business–valuation view</b></div><small>Momentum explains how fundamentals are changing; Valuation Context explains where the current valuation sits relative to the company's own history. Read them together before the detailed tables.</small>`;
  valuation.insertAdjacentElement("afterend", synthesis);
}

function individualStory(details) {
  addIndividualStoryRibbon(details);
  const growth = findSectionByTitle(details, "Growth");
  const valuation = findSectionByTitle(details, "Valuation");
  const momentum = details.querySelector(".stock-fundamental-momentum");
  const valuationEngine = details.querySelector(".stock-valuation-engine");
  const trends = details.querySelector(".stock-trends-section:not(.stock-comparison-trends)");

  if (growth) addFeedBadge(growth, "Fundamental Momentum", "blue");
  if (valuation) addFeedBadge(valuation, "Valuation Context", "violet");
  if (trends) addChartStoryLabels(trends);
  if (momentum) addEngineBridge(momentum, "momentum");
  if (valuationEngine) addEngineBridge(valuationEngine, "valuation");
  addSynthesis(momentum, valuationEngine);
}

function comparisonStory(root) {
  const table = root.querySelector(".stock-comparison-table-wrap");
  const trends = root.querySelector(".stock-comparison-trends");
  const advanced = root.querySelector(".advanced-matrix, .advanced-stock-grid, .advanced-summary, .stock-derived-comparison");
  if (!table && !trends && !advanced) return;

  if (table && !root.querySelector(".stock-comparison-story")) {
    const story = document.createElement("section");
    story.className = "stock-comparison-story";
    story.innerHTML = `<div class="stock-comparison-story-title"><div><span class="stock-story-kicker">COMPARISON FLOW</span><h2>Read the selected stocks as a story</h2></div><small>The existing detailed comparison remains below.</small></div><div class="stock-comparison-story-flow"><div><b>01</b><strong>Raw metrics</strong><span>Growth · Valuation · Profitability · Financial health</span></div><i>→</i><div><b>02</b><strong>Historical evidence</strong><span>Growth, returns and P/E/P/B trends</span></div><i>→</i><div class="accent"><b>03</b><strong>Engine interpretation</strong><span>Momentum + Valuation Context for each stock</span></div><i>→</i><div><b>04</b><strong>Relationship</strong><span>Business–Valuation Matrix + summary</span></div></div>`;
    table.parentNode.insertBefore(story, table);
  }
  if (trends) addChartStoryLabels(trends);

  if (advanced && !root.querySelector(".stock-comparison-story-link")) {
    const link = document.createElement("div");
    link.className = "stock-comparison-story-link";
    link.innerHTML = `<span>03 → 04</span><div><b>From historical evidence to relationship</b><small>Each stock's Momentum and Valuation Context are derived from the evidence above; the Matrix and Summary combine those two views without replacing the detailed comparison.</small></div>`;
    advanced.insertAdjacentElement("beforebegin", link);
  }
}

function ensureStyles() {
  if (document.getElementById(STORY_STYLE_ID)) return;
  const style = document.createElement("style");
  style.id = STORY_STYLE_ID;
  style.textContent = `
.stock-analysis-story-ribbon{margin:0 0 16px;padding:16px 18px;border:1px solid #d7e4f0;border-radius:16px;background:linear-gradient(135deg,#fafdff 0%,#f1f7ff 100%);box-shadow:0 7px 22px rgba(15,23,42,.055)}
.stock-story-ribbon-heading{display:flex;align-items:flex-start;justify-content:space-between;gap:15px;margin-bottom:12px}.stock-story-kicker{display:block;font-size:8px;letter-spacing:.11em;font-weight:900;color:#64748b}.stock-story-ribbon-heading h2{margin:3px 0 0;color:#102b4e;font-size:16px}.stock-story-ribbon-note{font-size:8px;color:#7b8da0;padding:5px 8px;border:1px solid #dce6ef;border-radius:999px;background:#fff}.stock-story-ribbon-flow{display:grid;grid-template-columns:1fr auto 1fr auto 1fr auto 1fr;align-items:center;gap:7px}.stock-story-ribbon-flow>div{min-height:65px;padding:9px 10px;border:1px solid #dbe5ef;border-radius:11px;background:#fff}.stock-story-ribbon-flow>div.accent{border-color:#c8d9f6;background:linear-gradient(135deg,#fff,#f3f8ff);box-shadow:inset 0 2px 0 #2563eb}.stock-story-ribbon-flow span,.stock-comparison-story-flow b{display:grid;place-items:center;width:19px;height:19px;border-radius:50%;background:#e8f1ff;color:#2563eb;font-size:8px;font-weight:900}.stock-story-ribbon-flow b{display:block;margin-top:5px;color:#17355d;font-size:10px}.stock-story-ribbon-flow small{display:block;margin-top:3px;color:#7a8da1;font-size:8px;line-height:1.35}.stock-story-ribbon-flow>i{font-style:normal;color:#8aa0b6;font-size:16px}
.stock-story-feed-badge{margin-left:auto;display:inline-flex;align-items:center;gap:5px;padding:5px 8px;border:1px solid #dbe7f3;border-radius:999px;background:#f7fbff;color:#64758a;font-size:8px;font-weight:800;white-space:nowrap}.stock-story-feed-badge.violet{background:#faf7ff;border-color:#e6dcfb}.stock-story-feed-badge b{color:#2563eb}.stock-story-feed-badge.violet b{color:#7c3aed}.stock-story-feed-dot{width:6px;height:6px;border-radius:50%;background:#2563eb}.stock-story-feed-badge.violet .stock-story-feed-dot{background:#7c3aed}.stock-story-arrow{color:#94a3b8}
.stock-story-chart-divider{grid-column:1/-1;display:flex;align-items:center;gap:9px;margin-top:5px;padding:9px 12px;border:1px solid #dce7f2;border-radius:10px;background:linear-gradient(90deg,#f7fbff,#fff)}.stock-story-chart-divider span{font-size:8px;text-transform:uppercase;letter-spacing:.08em;font-weight:900;color:#64748b}.stock-story-chart-divider b{font-size:10px;color:#17355d}.stock-story-chart-divider small{font-size:9px;color:#8291a3}
.stock-story-engine-link{display:flex;align-items:flex-start;gap:9px;margin:11px 0 0;padding:10px 12px;border:1px solid #dce7f2;border-radius:10px;background:#f8fbff}.stock-story-engine-link>span{display:grid;place-items:center;width:21px;height:21px;border-radius:50%;background:#e8f1ff;color:#2563eb;font-weight:900;font-size:12px;flex:0 0 21px}.stock-story-engine-link b{display:block;color:#284968;font-size:9px}.stock-story-engine-link small{display:block;margin-top:3px;color:#71849a;font-size:9px;line-height:1.4}.stock-story-synthesis{margin:12px 0 0;padding:13px 14px;border:1px solid #d9e5f0;border-radius:12px;background:linear-gradient(90deg,#f7fbff,#fff);text-align:center}.stock-story-synthesis-line{display:flex;align-items:center;justify-content:center;gap:8px;flex-wrap:wrap;color:#536b84;font-size:10px}.stock-story-synthesis-line span{padding:5px 8px;border-radius:999px;background:#edf5ff;color:#315a83;font-weight:800}.stock-story-synthesis-line i{font-style:normal;color:#94a3b8}.stock-story-synthesis-line strong{color:#2563eb;font-size:14px}.stock-story-synthesis-line b{color:#17355d}.stock-story-synthesis>small{display:block;margin-top:5px;color:#71849a;font-size:9px;line-height:1.4}
.stock-comparison-story{margin:0 0 15px;padding:16px 18px;border:1px solid #d7e4f0;border-radius:16px;background:linear-gradient(135deg,#fafdff,#f1f7ff);box-shadow:0 7px 22px rgba(15,23,42,.055)}.stock-comparison-story-title{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:12px}.stock-comparison-story-title h2{margin:3px 0 0;color:#102b4e;font-size:16px}.stock-comparison-story-title small{color:#7a8da1;font-size:9px}.stock-comparison-story-flow{display:grid;grid-template-columns:1fr auto 1fr auto 1fr auto 1fr;align-items:center;gap:7px}.stock-comparison-story-flow>div{min-height:65px;padding:9px;border:1px solid #dbe5ef;border-radius:11px;background:#fff}.stock-comparison-story-flow>div.accent{border-color:#c8d9f6;background:#f5f9ff;box-shadow:inset 0 2px 0 #2563eb}.stock-comparison-story-flow strong{display:block;margin-top:5px;color:#17355d;font-size:10px}.stock-comparison-story-flow span{display:block;margin-top:3px;color:#7a8da1;font-size:8px;line-height:1.35}.stock-comparison-story-flow>i{font-style:normal;color:#8aa0b6;font-size:16px}.stock-comparison-story-link{display:flex;gap:9px;align-items:flex-start;margin:0 0 12px;padding:10px 12px;border:1px solid #dbe7f3;border-radius:10px;background:#f8fbff}.stock-comparison-story-link>span{padding:4px 6px;border-radius:999px;background:#e9f2ff;color:#2563eb;font-size:8px;font-weight:900}.stock-comparison-story-link b{display:block;color:#284968;font-size:9px}.stock-comparison-story-link small{display:block;margin-top:3px;color:#71849a;font-size:9px;line-height:1.4}
@media(max-width:850px){.stock-story-ribbon-heading,.stock-comparison-story-title{display:block}.stock-story-ribbon-note,.stock-comparison-story-title small{display:inline-block;margin-top:6px}.stock-story-ribbon-flow,.stock-comparison-story-flow{grid-template-columns:1fr}.stock-story-ribbon-flow>i,.stock-comparison-story-flow>i{transform:rotate(90deg);justify-self:center}.stock-story-feed-badge{margin-left:0;margin-top:5px}.stock-story-chart-divider{align-items:flex-start;flex-wrap:wrap}.stock-story-chart-divider small{width:100%}}
  `;
  document.head.appendChild(style);
}

function scan() {
  ensureStyles();
  const details = document.getElementById("stock-details");
  const screen = document.getElementById("stock-analysis-screen");
  if (details && screen && !screen.hidden) individualStory(details);
  if (screen && !screen.hidden) comparisonStory(screen);
}

const observer = new MutationObserver(() => scan());
observer.observe(document.body, { childList: true, subtree: true });
document.addEventListener("DOMContentLoaded", scan);
scan();
