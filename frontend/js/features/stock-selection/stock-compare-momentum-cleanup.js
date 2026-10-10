const isComparePage = () => new URLSearchParams(window.location.search).has("compare");

function removeIndividualMomentumFromCompare() {
  if (!isComparePage()) return;

  // The compare page has its own per-stock comparative decision lens.
  // Never leave the individual-analysis Momentum Index / Trend Timeline
  // mounted inside #stock-details, because it has no unambiguous stock owner.
  // In comparison mode, the individual-analysis panel has no single-stock owner.
  // Remove it wherever it appears; the comparison cards render one clearly named
  // Momentum Index and Trend Timeline per selected stock.
  document.querySelectorAll(
    "#stock-details .stock-fundamental-momentum, #stock-details .stock-fundamental-signals, " +
    ".stock-fundamental-momentum, .stock-fundamental-signals"
  ).forEach((el) => el.remove());
}

function init() {
  if (!isComparePage()) return;

  removeIndividualMomentumFromCompare();

  // Several comparison/analysis modules render asynchronously. Keep the
  // cleanup active until those modules have finished, without touching the
  // dedicated .stock-derived-comparison section.
  // Keep this guard active for the full comparison view. Analysis modules may
  // render or refresh asynchronously after the initial report has appeared.
  const observer = new MutationObserver(() => removeIndividualMomentumFromCompare());
  observer.observe(document.body, {
    childList: true,
    subtree: true,
  });
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init, { once: true });
} else {
  init();
}
