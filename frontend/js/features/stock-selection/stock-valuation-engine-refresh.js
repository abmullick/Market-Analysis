// Re-trigger the valuation engine when the single-stock detail panel is replaced.
// The stock detail UI is client-rendered, so the page itself is not reloaded between symbols.
let lastDetailSignature = "";

function refreshValuationEngine() {
  const details = document.querySelector("#stock-details");
  if (!details) return;
  const signature = `${details.querySelector(".stock-hero h1")?.textContent || ""}|${details.querySelector(".stock-eyebrow")?.textContent || ""}`;
  if (!signature || signature === lastDetailSignature) return;
  lastDetailSignature = signature;

  const host = document.querySelector("main");
  if (host) {
    delete host.dataset.valuationEngine;
    const marker = document.createElement("span");
    marker.hidden = true;
    marker.dataset.valuationRefresh = "1";
    host.appendChild(marker);
    marker.remove();
  }
}

const observer = new MutationObserver(refreshValuationEngine);
observer.observe(document.body, { childList: true, subtree: true });
document.addEventListener("DOMContentLoaded", refreshValuationEngine);
