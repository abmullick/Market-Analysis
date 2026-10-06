(() => {
    if (window.__stockPortfolioDiagnosticInstalled) return;
    window.__stockPortfolioDiagnosticInstalled = true;

    const PREFIX = "[PORTFOLIO-DEBUG]";
    let fetchSequence = 0;

    const stamp = () => new Date().toISOString();
    const log = (...args) => console.log(PREFIX, stamp(), ...args);

    log("diagnostic instrumentation installed");

    document.addEventListener("click", event => {
        const button = event.target?.closest?.("#portfolio-continue");
        if (!button) return;
        log("Continue click", {
            disabled: button.disabled,
            timestamp: performance.now().toFixed(1)
        });
        console.trace(`${PREFIX} Continue click stack`);
    }, true);

    document.addEventListener("click", event => {
        const button = event.target?.closest?.("#portfolio-analysis-back");
        if (!button) return;
        log("Back to builder click");
    }, true);

    const originalFetch = window.fetch.bind(window);
    window.fetch = async (...args) => {
        const input = args[0];
        const url = typeof input === "string" ? input : input?.url || "";
        const isPortfolioStockRequest = /\/api\/stocks\/[^/]+(?:\/charts)?(?:\?|$)/.test(url);
        if (!isPortfolioStockRequest) return originalFetch(...args);

        const id = ++fetchSequence;
        const started = performance.now();
        const symbol = decodeURIComponent(url.split("/api/stocks/")[1] || "").split("/")[0];
        log(`FETCH #${id} START`, symbol, url);
        console.trace(`${PREFIX} FETCH #${id} stack`);

        try {
            const response = await originalFetch(...args);
            log(`FETCH #${id} END`, symbol, {
                status: response.status,
                ok: response.ok,
                durationMs: Math.round(performance.now() - started)
            });
            return response;
        } catch (error) {
            log(`FETCH #${id} ERROR`, symbol, {
                durationMs: Math.round(performance.now() - started),
                message: error?.message || String(error)
            });
            throw error;
        }
    };

    const analysis = document.getElementById("stock-portfolio-analysis-content");
    if (analysis) {
        const observer = new MutationObserver(() => {
            log("Analysis visibility changed", { hidden: analysis.hidden });
        });
        observer.observe(analysis, { attributes: true, attributeFilter: ["hidden"] });
    }
})();
