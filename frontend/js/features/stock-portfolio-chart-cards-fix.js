/* Guard for the chart-card segregation layer.
 * The chart wrapper itself is marked after it has been moved into its card so
 * the parent MutationObserver cannot wrap the same visualization repeatedly.
 */
(function () {
    const SELECTORS = [
        ".portfolio-performance-chart-wrap",
        ".portfolio-performance-side",
        ".portfolio-benchmark-chart-wrap",
        ".portfolio-positioning-chart-wrap",
        ".portfolio-risk-chart-wrap"
    ];

    function mark() {
        const root = document.getElementById("stock-portfolio-analysis-content");
        if (!root) return;
        SELECTORS.forEach(selector => {
            root.querySelectorAll(`.stock-pb-chart-card > .stock-pb-chart-content > ${selector}`).forEach(el => {
                el.dataset.pbChartCard = "1";
            });
        });
    }

    function init() {
        const root = document.getElementById("stock-portfolio-analysis-content");
        if (!root) return;
        const observer = new MutationObserver(mark);
        observer.observe(root, { childList: true, subtree: true });
        mark();
    }

    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
    else init();
})();
