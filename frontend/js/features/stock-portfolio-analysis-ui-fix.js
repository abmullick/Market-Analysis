/* Keep the semantic class used by the existing positioning/benchmark/risk
   features after the presentation layer wraps sections into PB cards. */
(function () {
    function restoreHooks() {
        document.querySelectorAll("#portfolio-analysis-results .stock-portfolio-collapsible-card, #portfolio-rebalancing .stock-portfolio-collapsible-card, #portfolio-action-view .stock-portfolio-collapsible-card").forEach(card => {
            card.classList.add("portfolio-analysis-section");
        });
    }
    function init() {
        const analysis = document.getElementById("stock-portfolio-analysis-content");
        if (!analysis) return;
        const observer = new MutationObserver(() => restoreHooks());
        observer.observe(analysis, { childList: true, subtree: true });
        restoreHooks();
    }
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
})();
