/* Keep the semantic hooks used by the existing portfolio analysis modules
   and place Data Notes after What-If / Action View at the true page bottom. */
(function () {
    function restoreHooks() {
        document.querySelectorAll("#portfolio-analysis-results .stock-portfolio-collapsible-card, #portfolio-rebalancing .stock-portfolio-collapsible-card, #portfolio-action-view .stock-portfolio-collapsible-card").forEach(card => {
            card.classList.add("portfolio-analysis-section");
        });
    }

    function moveDataNotes() {
        const analysis = document.getElementById("stock-portfolio-analysis-content");
        if (!analysis) return;
        const notes = [...analysis.querySelectorAll("section")].find(section =>
            String(section.querySelector("h2")?.textContent || "").trim().toLowerCase() === "data notes"
        );
        if (!notes) return;
        notes.dataset.pbNotes = "1";
        if (notes.parentElement !== analysis || notes !== analysis.lastElementChild) analysis.appendChild(notes);
    }

    function refresh() {
        restoreHooks();
        moveDataNotes();
    }

    function init() {
        const analysis = document.getElementById("stock-portfolio-analysis-content");
        if (!analysis) return;
        let timer = null;
        const observer = new MutationObserver(() => {
            clearTimeout(timer);
            timer = setTimeout(refresh, 80);
        });
        observer.observe(analysis, { childList: true, subtree: true });
        refresh();
    }

    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
})();
