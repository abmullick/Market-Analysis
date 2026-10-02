// Stock Analysis navigation guard.
//
// Analysis and selection screens share one DOM document. Returning from a deep
// analysis view must not leave enhancement requests alive while a fresh
// selection page is loading. The guard handles the explicit Back button only.
// Browser-history navigation is intentionally left to stock-detail/index.js,
// which owns the stock analysis state machine.
(() => {
  if (window.__stockNavigationGuardInstalled) return;
  window.__stockNavigationGuardInstalled = true;

  const selectionUrl = () => `${window.location.origin}/stocks.html`;

  function returnToSelection(event) {
    const button = event.target?.closest?.("#stock-back-to-selection");
    if (!button) return;

    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();

    // Cancel all stock-analysis API work before replacing the document. This
    // prevents a slow analysis/chart/pedigree request from competing with the
    // new selection-page load.
    window.__stockApiAbortAll?.();
    window.location.replace(selectionUrl());
  }

  document.addEventListener("click", returnToSelection, true);
})();
