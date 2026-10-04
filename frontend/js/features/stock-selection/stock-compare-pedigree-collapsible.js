function makeIcon() {
  return `<span class="stock-pedigree-trends-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 17 8 12 12 14 21 5"></polyline><polyline points="15 5 21 5 21 11"></polyline></svg></span>`;
}

function enhance(section) {
  if (!section || section.dataset.comparePedigreeCollapsible === "1") return;
  const grid = section.querySelector(":scope > .stock-pedigree-chart-grid");
  const heading = section.querySelector(":scope > .stock-pedigree-header");
  if (!grid || !heading) return;

  section.dataset.comparePedigreeCollapsible = "1";
  const title = heading.querySelector("h2")?.textContent?.trim() || "Company Pedigree & Trend Comparison";
  const subtitle = heading.querySelector("p")?.textContent?.trim() || "Historical consistency, operating quality, leverage and ownership trends using the same calculations for every selected company.";

  const card = document.createElement("div");
  card.className = "stock-pedigree-trends-card stock-compare-pedigree-card";
  card.innerHTML = `
    <div class="stock-pedigree-trends-card-header" role="button" tabindex="0" aria-expanded="true">
      <div class="stock-pedigree-trends-card-main">
        ${makeIcon()}
        <span class="stock-pedigree-trends-title">${title}<small>${subtitle}</small></span>
      </div>
      <div class="stock-pedigree-trends-controls">
        <button type="button" class="stock-pedigree-trends-caret" aria-expanded="true" aria-label="Collapse company pedigree and trend comparison">
          <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M5 7.5L10 12.5L15 7.5"></path></svg>
        </button>
      </div>
    </div>
    <div class="stock-pedigree-trends-card-body"></div>`;

  const body = card.querySelector(".stock-pedigree-trends-card-body");
  body.appendChild(grid);
  heading.replaceWith(card);

  const header = card.querySelector(".stock-pedigree-trends-card-header");
  const button = card.querySelector(".stock-pedigree-trends-caret");

  const setOpen = (open) => {
    header.setAttribute("aria-expanded", open ? "true" : "false");
    button.setAttribute("aria-expanded", open ? "true" : "false");
    button.setAttribute("aria-label", `${open ? "Collapse" : "Expand"} company pedigree and trend comparison`);
    body.hidden = !open;
    card.classList.toggle("is-open", open);
    if (open && typeof Chart !== "undefined") {
      requestAnimationFrame(() => body.querySelectorAll("canvas").forEach(canvas => Chart.getChart(canvas)?.resize()));
    }
  };

  const toggle = () => setOpen(header.getAttribute("aria-expanded") !== "true");
  header.addEventListener("click", event => { if (!event.target.closest("button")) toggle(); });
  header.addEventListener("keydown", event => {
    if (event.target.closest("button")) return;
    if (event.key === "Enter" || event.key === " ") { event.preventDefault(); toggle(); }
  });
  button.addEventListener("click", event => { event.preventDefault(); event.stopPropagation(); toggle(); });

  setOpen(true);
  requestAnimationFrame(() => setOpen(false));
}

function scan() {
  document.querySelectorAll("#stock-details .stock-pedigree-compare").forEach(enhance);
}

function init() {
  const details = document.getElementById("stock-details");
  if (!details) return;
  const observer = new MutationObserver(scan);
  observer.observe(details, { childList: true, subtree: true });
  scan();
}

if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init, { once: true });
else init();
