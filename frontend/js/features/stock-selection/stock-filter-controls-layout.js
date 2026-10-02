function moveStockQuickFiltersOutsideCollapse() {
  const card = document.querySelector("#stock-selection-screen .stock-filter-card");
  const body = card?.querySelector("#stock-filter-body");
  const top = card?.querySelector(".stock-filter-top");
  if (!card || !body || !top) return;

  let controls = card.querySelector(":scope > .stock-filter-controls");
  if (!controls) {
    controls = document.createElement("div");
    controls.className = "stock-filter-controls";
    card.insertBefore(controls, body);
  }

  // Keep Sector + Search + Market Cap + Liquidity permanently visible.
  if (top.parentElement !== controls) controls.appendChild(top);

  const extra = top.querySelector(":scope > .stock-universe-extra-filters");
  if (extra && extra.parentElement !== controls) controls.appendChild(extra);

  body.hidden = body.hidden;
}

function installStockFilterControlsLayout() {
  const run = () => {
    moveStockQuickFiltersOutsideCollapse();
  };

  run();

  const screen = document.getElementById("stock-selection-screen");
  if (!screen || screen.dataset.quickFilterLayoutInstalled === "1") return;
  screen.dataset.quickFilterLayoutInstalled = "1";

  const observer = new MutationObserver(() => {
    window.clearTimeout(window.__stockQuickFilterLayoutTimer);
    window.__stockQuickFilterLayoutTimer = window.setTimeout(run, 0);
  });
  observer.observe(screen, { childList: true, subtree: true });
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", installStockFilterControlsLayout, { once: true });
} else {
  installStockFilterControlsLayout();
}
