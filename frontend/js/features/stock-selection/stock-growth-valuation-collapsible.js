function initGrowthValuationCard(section) {
  if (!section || section.dataset.growthValuationCollapsible === "1") return;
  const grid = section.querySelector(".stock-trends-grid");
  const oldHeader = section.querySelector(".stock-trends-header");
  if (!grid || !oldHeader) return;

  section.dataset.growthValuationCollapsible = "1";

  const title = oldHeader.querySelector("h2")?.textContent?.trim() || "Historical Growth & Return Trends";
  const subtitle = oldHeader.querySelector("p")?.textContent?.trim() || "Historical earnings growth, returns and valuation trends.";

  // Reuse the exact collapsible-card structure already used by the seven-chart
  // Historical Business & Financial Trends block. The existing section remains
  // .stock-trends-section so the valuation renderer can continue to discover it.
  section.classList.add("stock-pedigree-trends-card", "stock-growth-valuation-trends-card");
  section.innerHTML = `
    <div class="stock-pedigree-trends-card-header" role="button" tabindex="0" aria-expanded="true">
      <div class="stock-pedigree-trends-card-main">
        <span class="stock-pedigree-trends-icon" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="3 17 8 12 12 14 21 5"></polyline>
            <polyline points="15 5 21 5 21 11"></polyline>
          </svg>
        </span>
        <span class="stock-pedigree-trends-title">${title}<small>${subtitle}</small></span>
      </div>
      <div class="stock-pedigree-trends-controls">
        <button type="button" class="stock-pedigree-trends-caret" aria-expanded="true" aria-label="Collapse historical growth and return trends">
          <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M5 7.5L10 12.5L15 7.5"></path>
          </svg>
        </button>
      </div>
    </div>
    <div class="stock-pedigree-trends-card-body"></div>
  `;

  const body = section.querySelector(".stock-pedigree-trends-card-body");
  const header = section.querySelector(".stock-pedigree-trends-card-header");
  const button = section.querySelector(".stock-pedigree-trends-caret");

  // Move the existing chart grid as-is. No chart cards, canvases, data or
  // rendering logic are recreated or removed.
  body.appendChild(grid);

  const setOpen = (open) => {
    header.setAttribute("aria-expanded", open ? "true" : "false");
    button?.setAttribute("aria-expanded", open ? "true" : "false");
    button?.setAttribute("aria-label", `${open ? "Collapse" : "Expand"} historical growth and return trends`);
    body.hidden = !open;
    section.classList.toggle("is-open", open);
    if (open && typeof Chart !== "undefined") {
      requestAnimationFrame(() => body.querySelectorAll("canvas").forEach((canvas) => Chart.getChart(canvas)?.resize()));
    }
  };

  const toggle = () => setOpen(header.getAttribute("aria-expanded") !== "true");
  header.addEventListener("click", (event) => {
    if (!event.target.closest("button")) toggle();
  });
  header.addEventListener("keydown", (event) => {
    if (event.target.closest("button")) return;
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      toggle();
    }
  });
  button?.addEventListener("click", (event) => {
    event.preventDefault();
    event.stopPropagation();
    toggle();
  });

  setOpen(true);
  requestAnimationFrame(() => setOpen(false));
}

function scanGrowthValuationSections() {
  document.querySelectorAll(".stock-trends-section").forEach(initGrowthValuationCard);
}

const growthValuationObserver = new MutationObserver(scanGrowthValuationSections);
growthValuationObserver.observe(document.body, { childList: true, subtree: true });
document.addEventListener("DOMContentLoaded", scanGrowthValuationSections);
scanGrowthValuationSections();
