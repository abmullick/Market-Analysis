// Stock Analysis navigation guard.
//
// The analysis and selection screens share one DOM document. Returning from a
// deep analysis view used to leave asynchronous analysis/selection work alive,
// which could result in both screens being visible and the selection screen
// waiting on a second universe request. The back action is a navigation
// boundary, so use a clean page navigation rather than trying to reconcile two
// independently-rendered screens in place.
//
// The lightweight universe fetch is session-cached by stock-api-coalescer.js,
// so a clean return to /stocks.html remains fast after the first load.
(() => {
  if (window.__stockNavigationGuardInstalled) return;
  window.__stockNavigationGuardInstalled = true;

  const selectionUrl = () => `${window.location.origin}/stocks.html`;

  function returnToSelection(event) {
    const button = event.target?.closest?.("#stock-back-to-selection");
    if (!button) return;

    // Run during capture so the older bubble-phase handler in stock-detail
    // cannot start another universe request or alter the two-screen state.
    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();

    window.location.replace(selectionUrl());
  }

  document.addEventListener("click", returnToSelection, true);

  // Browser Back from /stocks.html?symbol=... has the same lifecycle problem.
  // Replace the deep URL with a clean selection-page load instead of allowing
  // the old analysis DOM and pending requests to survive the transition.
  window.addEventListener("popstate", () => {
    const params = new URLSearchParams(window.location.search);
    if (!params.has("symbol") && !params.has("compare")) return;
    window.location.replace(selectionUrl());
  });
})();
