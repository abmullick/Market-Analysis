// Mobile stock-selection interaction, responsive historical tables, and UI cleanup.
// Kept isolated from the main selection/detail modules.

(function installStockMobileFix() {
  const isStockSelection = () => document.getElementById("stock-selection-screen");

  function installResponsiveTableStyles() {
    if (document.getElementById("stock-mobile-responsive-fix-style")) return;
    const style = document.createElement("style");
    style.id = "stock-mobile-responsive-fix-style";
    style.textContent = `
      .stock-table-wrap {
        display: block;
        width: 100%;
        max-width: 100%;
        overflow-x: auto !important;
        overflow-y: hidden;
        -webkit-overflow-scrolling: touch;
        overscroll-behavior-x: contain;
        scrollbar-width: thin;
        touch-action: pan-x pan-y;
      }
      .stock-table-wrap .stock-table {
        min-width: 720px;
        width: max-content;
        max-width: none;
      }
      .stock-table-wrap .stock-table th,
      .stock-table-wrap .stock-table td {
        white-space: nowrap;
      }
      @media (max-width: 700px) {
        .stock-derived-trend .stock-table-wrap,
        #stock-statement-content .stock-table-wrap {
          margin-right: 0;
          border-radius: 12px;
        }
        .stock-derived-trend .stock-table,
        #stock-statement-content .stock-table {
          min-width: 680px;
        }
      }
    `;
    document.head.appendChild(style);
  }

  function positionSectorDropdown(trigger, dropdown) {
    if (!trigger || !dropdown || window.innerWidth > 850) return;
    const r = trigger.getBoundingClientRect();
    dropdown.style.position = "fixed";
    dropdown.style.left = `${Math.max(8, r.left)}px`;
    dropdown.style.right = "auto";
    dropdown.style.top = `${Math.min(window.innerHeight - 20, r.bottom + 6)}px`;
    dropdown.style.width = `${Math.min(r.width, window.innerWidth - 16)}px`;
    dropdown.style.maxHeight = `${Math.max(180, Math.min(430, window.innerHeight - r.bottom - 28))}px`;
    dropdown.style.zIndex = "2147483000";
  }

  function hardenSectorTrigger() {
    const trigger = document.querySelector("#stock-selection-screen .stock-sector-picker .category-picker-trigger");
    const dropdown = document.querySelector("#stock-selection-screen .stock-sector-picker .category-picker-dropdown");
    if (!trigger || !dropdown || trigger.dataset.mobileFixInstalled === "1") return;
    trigger.dataset.mobileFixInstalled = "1";

    trigger.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopImmediatePropagation();
      const open = dropdown.hidden;
      dropdown.hidden = !open;
      trigger.setAttribute("aria-expanded", String(open));
      if (open) positionSectorDropdown(trigger, dropdown);
      else {
        dropdown.style.position = "";
        dropdown.style.left = "";
        dropdown.style.top = "";
        dropdown.style.width = "";
        dropdown.style.maxHeight = "";
        dropdown.style.zIndex = "";
      }
    }, true);

    window.addEventListener("resize", () => {
      if (!dropdown.hidden) positionSectorDropdown(trigger, dropdown);
    }, { passive: true });
    window.addEventListener("scroll", () => {
      if (!dropdown.hidden) positionSectorDropdown(trigger, dropdown);
    }, { passive: true });
  }

  function removeProviderNamesFromVisibleStockUi() {
    const root = document.getElementById("stock-analysis-screen") || document.getElementById("stock-selection-screen");
    if (!root) return;

    root.querySelectorAll(".stock-derived-analysis .stock-section-header span").forEach((el) => {
      if (/screener/i.test(el.textContent || "")) el.textContent = "Calculated metrics";
    });

    root.querySelectorAll(".stock-derived-explanation p").forEach((el) => {
      el.textContent = "These metrics use the annual income statement, balance sheet and cash-flow data available to the application. Definitions may differ from standard ratio conventions.";
    });

    root.querySelectorAll(".stock-warnings small").forEach((el) => {
      el.textContent = (el.textContent || "").replace(/\s*·\s*Source:\s*.*$/i, "");
    });

    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    nodes.forEach((node) => {
      if (/screener/i.test(node.nodeValue || "")) {
        node.nodeValue = node.nodeValue.replace(/screener/gi, "financial data");
      }
    });
  }

  function run() {
    // Table styles and UI cleanup must also run while the analysis screen is
    // active. The previous guard prevented the fix from running on that screen.
    installResponsiveTableStyles();
    if (isStockSelection()) hardenSectorTrigger();
    removeProviderNamesFromVisibleStockUi();
  }

  const observer = new MutationObserver(() => {
    window.clearTimeout(window.__stockMobileFixTimer);
    window.__stockMobileFixTimer = window.setTimeout(run, 0);
  });

  function boot() {
    run();
    observer.observe(document.getElementById("stock-analysis-content") || document.body, {
      childList: true,
      subtree: true,
    });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot, { once: true });
  else boot();
})();
