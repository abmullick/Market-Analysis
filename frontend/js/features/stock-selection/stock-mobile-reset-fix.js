// Mobile stock-selection interaction and stale-analysis cleanup.
// This is intentionally isolated from the main selection/detail modules so it
// can harden the UI without coupling to their module-scoped state.

(function installStockMobileAndResetFix() {
  const isStockSelection = () => document.getElementById("stock-selection-screen");

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

  function clearAnalysisAndReturnToSelection() {
    const analysis = document.getElementById("stock-analysis-screen");
    const selection = document.getElementById("stock-selection-screen");
    const details = document.getElementById("stock-details");
    const status = document.getElementById("stock-analysis-status");
    if (!analysis || !selection) return;

    if (details) details.replaceChildren();
    if (status) status.textContent = "";

    analysis.hidden = true;
    selection.hidden = false;

    // Remove visual selection state without depending on the detail module's
    // private selectedStock variable.
    document.querySelectorAll("#stock-selection-screen .stock-picker-row.selected, #stock-selection-screen [aria-selected=\"true\"]")
      .forEach(el => {
        el.classList.remove("selected");
        el.removeAttribute("aria-selected");
      });
    document.querySelectorAll("#stock-selection-screen input[type=checkbox][data-stock-symbol]:checked")
      .forEach(el => { el.checked = false; });

    // The selection page is the root state; don't leave ?symbol=... behind.
    const cleanUrl = `${window.location.pathname}${window.location.hash || ""}`;
    if (window.location.href !== `${window.location.origin}${cleanUrl}`) {
      window.history.replaceState({}, "", cleanUrl);
    }
    window.scrollTo(0, 0);
  }

  function hardenSectorTrigger() {
    const trigger = document.querySelector("#stock-selection-screen .stock-sector-picker .category-picker-trigger");
    const dropdown = document.querySelector("#stock-selection-screen .stock-sector-picker .category-picker-dropdown");
    if (!trigger || !dropdown || trigger.dataset.mobileFixInstalled === "1") return;
    trigger.dataset.mobileFixInstalled = "1";

    // Capture phase deliberately supersedes the older bubble-phase handler.
    // This avoids mobile-browser touch/click quirks and gives the dropdown a
    // viewport-level position so it cannot be clipped by a card/container.
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

  function hardenBackButton() {
    const button = document.getElementById("stock-back-to-selection");
    if (!button || button.dataset.resetFixInstalled === "1") return;
    button.dataset.resetFixInstalled = "1";
    button.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopImmediatePropagation();
      clearAnalysisAndReturnToSelection();
    }, true);
  }

  function run() {
    if (!isStockSelection()) return;
    hardenSectorTrigger();
    hardenBackButton();
  }

  const observer = new MutationObserver(() => {
    window.clearTimeout(window.__stockMobileResetFixTimer);
    window.__stockMobileResetFixTimer = window.setTimeout(run, 0);
  });

  function boot() {
    run();
    const root = document.getElementById("stock-analysis-content") || document.body;
    observer.observe(root, { childList: true, subtree: true });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot, { once: true });
  else boot();
})();
