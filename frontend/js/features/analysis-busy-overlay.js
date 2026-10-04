(() => {
  const OVERLAY_ID = "analysis-busy-overlay";
  let visible = false;
  let hideTimer = null;
  let shownAt = 0;

  function ensureOverlay() {
    let overlay = document.getElementById(OVERLAY_ID);
    if (overlay) return overlay;
    overlay = document.createElement("div");
    overlay.id = OVERLAY_ID;
    overlay.className = "analysis-busy-overlay";
    overlay.setAttribute("aria-hidden", "true");
    overlay.innerHTML = `<div class="analysis-busy-card" role="status" aria-live="polite" aria-label="Processing"><div class="analysis-busy-spinner" aria-hidden="true"></div><div class="analysis-busy-title">Processing…</div><div class="analysis-busy-message">Fetching data and preparing the analysis. Please wait.</div></div>`;
    document.body.appendChild(overlay);
    return overlay;
  }

  function show(message) {
    const overlay = ensureOverlay();
    overlay.querySelector(".analysis-busy-message").textContent = message;
    overlay.classList.add("is-visible");
    overlay.setAttribute("aria-hidden", "false");
    visible = true;
    shownAt = Date.now();
    if (hideTimer) clearTimeout(hideTimer);
  }

  function hide() {
    const overlay = document.getElementById(OVERLAY_ID);
    if (!overlay) return;
    overlay.classList.remove("is-visible");
    overlay.setAttribute("aria-hidden", "true");
    visible = false;
  }

  function scheduleSafetyHide(ms = 120000) {
    if (hideTimer) clearTimeout(hideTimer);
    hideTimer = setTimeout(hide, ms);
  }

  function isStockAction(button) {
    return Boolean(button?.closest("#stock-selection-screen") && (button.matches("#stock-analyze-selected") || button.matches(".stock-compare-action")));
  }

  function isRankingAction(button) {
    return Boolean(button?.matches("#run-ranking"));
  }

  function onClick(event) {
    const button = event.target.closest?.("button");
    if (!button || button.disabled) return;
    if (isRankingAction(button)) {
      show("Running ranking and fetching mutual fund data. Please wait.");
      scheduleSafetyHide();
    } else if (isStockAction(button)) {
      show(button.matches(".stock-compare-action") ? "Fetching comparison data. Please wait." : "Fetching stock data and preparing the analysis. Please wait.");
      scheduleSafetyHide();
    }
  }

  function completionCheck() {
    if (!visible || Date.now() - shownAt < 700) return;
    const ranking = document.getElementById("ranking-table-container");
    const summary = document.getElementById("ranking-summary");
    const rankingBusy = document.querySelector("#ranking-results .loading, #ranking-results [aria-busy='true'], #ranking-results .spinner");
    const stockScreen = document.getElementById("stock-analysis-screen");
    const stockDetails = document.getElementById("stock-details");
    const status = document.getElementById("stock-analysis-status");
    const stockLoading = /loading|fetching|analy[sz]ing/i.test(status?.textContent || "") || Boolean(stockDetails?.querySelector(".stock-loading"));
    const rankingDone = !rankingBusy && Boolean(ranking?.childElementCount || summary?.childElementCount);
    const stockDone = Boolean(stockScreen && !stockScreen.hidden && stockDetails?.childElementCount && !stockLoading);
    if (rankingDone || stockDone) hide();
  }

  function observeCompletion() {
    const observer = new MutationObserver(completionCheck);
    observer.observe(document.body, { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ["hidden", "class", "aria-busy"] });
    window.setInterval(completionCheck, 400);
  }

  document.addEventListener("click", onClick, true);
  window.addEventListener("beforeunload", hide);
  document.addEventListener("DOMContentLoaded", () => { ensureOverlay(); observeCompletion(); });
  if (document.readyState !== "loading") { ensureOverlay(); observeCompletion(); }
})();
