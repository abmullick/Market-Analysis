function addQuickFilterLayoutStyles() {
  if (document.getElementById("stock-quick-filter-layout-styles")) return;
  const style = document.createElement("style");
  style.id = "stock-quick-filter-layout-styles";
  style.textContent = `
    #stock-selection-screen .stock-filter-card {
      display:flex;
      flex-direction:column;
    }
    #stock-selection-screen .stock-filter-card > .stock-filter-controls {
      display:block;
      width:100%;
      margin:0;
      order:1;
    }
    #stock-selection-screen .stock-filter-card > #stock-filter-toggle { order:2; }
    #stock-selection-screen .stock-filter-card > #stock-filter-body { order:3; }
    #stock-selection-screen .stock-filter-card > .stock-filter-controls > .stock-filter-top {
      display:grid;
      grid-template-columns:minmax(0,1fr) minmax(0,1fr);
      gap:12px;
      margin:0 0 12px;
    }
    #stock-selection-screen .stock-filter-card > .stock-filter-controls > .stock-universe-extra-filters {
      display:grid;
      grid-template-columns:1fr;
      gap:12px;
      margin:0 0 12px;
    }
    #stock-selection-screen .stock-filter-card > #stock-filter-body { margin-top:0; }
    #stock-selection-screen .stock-filter-data-warning {
      margin-bottom:10px;
      padding:8px 12px;
      border:1px solid #f2c46d;
      border-radius:9px;
      background:#fff8e8;
      color:#8a5a00;
      font-size:12px;
    }
    @media (max-width:850px) {
      #stock-selection-screen .stock-filter-card > .stock-filter-controls > .stock-filter-top,
      #stock-selection-screen .stock-filter-card > .stock-filter-controls > .stock-universe-extra-filters {
        grid-template-columns:1fr;
      }
    }
  `;
  document.head.appendChild(style);
}

function moveStockQuickFiltersOutsideCollapse() {
  const card = document.querySelector("#stock-selection-screen .stock-filter-card");
  if (!card) return;

  const body = card.querySelector("#stock-filter-body");
  const top = card.querySelector(".stock-filter-top");
  const toggle = card.querySelector("#stock-filter-toggle");
  if (!body || !top || !toggle) return;

  let controls = card.querySelector(":scope > .stock-filter-controls");
  if (!controls) {
    controls = document.createElement("div");
    controls.className = "stock-filter-controls";
    card.insertBefore(controls, toggle);
  }

  if (top.parentElement !== controls) controls.appendChild(top);

  const extra = top.querySelector(":scope > .stock-universe-extra-filters");
  if (extra && extra.parentElement !== controls) controls.appendChild(extra);

  card.classList.add("stock-quick-filters-visible");
}

function installStockFilterControlsLayout() {
  addQuickFilterLayoutStyles();
  const run = () => moveStockQuickFiltersOutsideCollapse();
  run();

  const screen = document.getElementById("stock-selection-screen");
  if (!screen || screen.dataset.quickFilterLayoutInstalled === "1") return;
  screen.dataset.quickFilterLayoutInstalled = "1";

  // Only watch direct replacement of the selection screen. Observing the
  // whole subtree caused this layout script to observe its own DOM moves and
  // continuously re-run, producing the visible "dancing" effect.
  const observer = new MutationObserver(() => {
    window.clearTimeout(window.__stockQuickFilterLayoutTimer);
    window.__stockQuickFilterLayoutTimer = window.setTimeout(run, 0);
  });
  observer.observe(screen, { childList: true, subtree: false });
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", installStockFilterControlsLayout, { once: true });
} else {
  installStockFilterControlsLayout();
}
