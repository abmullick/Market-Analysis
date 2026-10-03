const isComparePage = () => new URLSearchParams(window.location.search).has("compare");

function removeIndividualMomentumFromCompare() {
  if (!isComparePage()) return;

  // The compare page has its own per-stock comparative decision lens.
  // Never leave the individual-analysis Momentum Index / Trend Timeline
  // mounted inside #stock-details, because it has no unambiguous stock owner.
  document.querySelectorAll(
    "#stock-details .stock-fundamental-momentum, #stock-details .stock-fundamental-signals"
  ).forEach((el) => el.remove());
}

function init() {
  if (!isComparePage()) return;

  removeIndividualMomentumFromCompare();

  // Several comparison/analysis modules render asynchronously. Keep the
  // cleanup active until those modules have finished, without touching the
  // dedicated .stock-derived-comparison section.
  const observer = new MutationObserver(() => removeIndividualMomentumFromCompare());
  observer.observe(document.getElementById("stock-details") || document.body, {
    childList: true,
    subtree: true,
  });

  window.setTimeout(() => {
    observer.disconnect();
    removeIndividualMomentumFromCompare();
  }, 10000);
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init, { once: true });
} else {
  init();
}
