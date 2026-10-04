(() => {
  const OVERLAY_ID = "analysis-busy-overlay";
  let visible = false;
  let hideTimer = null;

  function ensureOverlay() {
    let overlay = document.getElementById(OVERLAY_ID);
    if (overlay) return overlay;
    overlay = document.createElement("div");
    overlay.id = OVERLAY_ID;
    overlay.className = "analysis-busy-overlay";
    overlay.setAttribute("aria-hidden", "true");
    overlay.innerHTML = `
      <div class="analysis-busy-card" role="status" aria-live="polite" aria-label="Processing">
        <div class="analysis-busy-spinner" aria-hidden="true"></div>
        <div class="analysis-busy-title">Processing…</div>
        <div class="analysis-busy-message">Fetching data and preparing the analysis. Please wait.</div>
      </div>`;
    document.body.appendChild(overlay);
    return overlay;
  }

  function show(message = "Fetching data and preparing the analysis. Please wait.") {
    const overlay = ensureOverlay();
    const msg = overlay.querySelector(".analysis-busy-message");
    if (msg) msg.textContent = message;
    overlay.classList.add("is-visible");
    overlay.setAttribute("aria-hidden", "false");
    visible = true;
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
    if (!button) return false;
    return Boolean(button.closest("#stock-selection-screen") && (
      button.matches("#stock-analyze-selected") ||
      button.matches(".stock-compare-action") ||
      button.matches(".stock-select-btn") && button.closest(".stock-selected-panel")
    ));
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
      return;
    }
    if (isStockAction(button)) {
      const compare = button.matches(".stock-compare-action");
      show(compare ? "Fetching comparison data. Please wait." : "Fetching stock data and preparing the analysis. Please wait.");
      scheduleSafetyHide();
    }
  }

  function observeCompletion() {
    const ranking = document.getElementById("ranking-table-container");
    const summary = document.getElementById("ranking-summary");
    const stockScreen = document.getElementById("stock-analysis-screen");
    const stockDetails = document.getElementById("stock-details");
    const status = document.getElementById("stock-analysis-status");
    if (!ranking && !summary && !stockScreen && !stockDetails && !status) return;

    const observer = new MutationObserver(() => {
      if (!visible) return;
      const rankingDone = Boolean(ranking && ranking.childElementCount) || Boolean(summary && summary.childElementCount && !ranking?.childElementCount);
      const stockDone = Boolean(stockScreen && !stockScreen.hidden && stockDetails && stockDetails.childElementCount && !/loading|fetching/i.test(status?.textContent || ""));
      if (rankingDone || stockDone) hide();
    });
    observer.observe(document.body, { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ["hidden", "class"] });
  }

  document.addEventListener("click", onClick, true);
  window.addEventListener("beforeunload", hide);
  document.addEventListener("DOMContentLoaded", () => { ensureOverlay(); observeCompletion(); });
  if (document.readyState !== "loading") { ensureOverlay(); observeCompletion(); }
})();
