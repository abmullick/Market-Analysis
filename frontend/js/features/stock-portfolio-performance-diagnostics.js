/* Diagnostic-only. No UI changes; logs portfolio request orchestration and timing. */
(() => {
    if (window.__stockPortfolioPerformanceDiagnostics) return;
    window.__stockPortfolioPerformanceDiagnostics = true;

    const state = {
        started: null,
        active: 0,
        maxActive: 0,
        requests: [],
    };

    const now = () => performance.now();
    const label = url => {
        try {
            const u = new URL(url, location.href);
            return `${u.pathname}${u.search}`;
        } catch (_) {
            return String(url);
        }
    };

    const originalFetch = window.fetch.bind(window);
    window.fetch = async (input, init) => {
        const url = typeof input === "string" ? input : input?.url || String(input);
        const path = label(url);
        const isApi = path.startsWith("/api/");
        if (!isApi) return originalFetch(input, init);

        const id = state.requests.length + 1;
        const started = now();
        state.active += 1;
        state.maxActive = Math.max(state.maxActive, state.active);
        console.log(`[PORTFOLIO-PERF] REQUEST_START #${id} active=${state.active} ${path}`);

        try {
            const response = await originalFetch(input, init);
            const elapsed = now() - started;
            state.requests.push({ id, path, elapsed, status: response.status });
            console.log(`[PORTFOLIO-PERF] REQUEST_END #${id} active=${state.active} status=${response.status} duration=${(elapsed / 1000).toFixed(3)}s ${path}`);
            return response;
        } catch (error) {
            const elapsed = now() - started;
            console.log(`[PORTFOLIO-PERF] REQUEST_FAIL #${id} active=${state.active} duration=${(elapsed / 1000).toFixed(3)}s ${path}`, error);
            throw error;
        } finally {
            state.active -= 1;
        }
    };

    const continueButton = document.getElementById("portfolio-continue");
    continueButton?.addEventListener("click", () => {
        state.started = now();
        state.requests = [];
        state.active = 0;
        state.maxActive = 0;
        console.log("[PORTFOLIO-PERF] CONTINUE_CLICK");
    }, true);

    const results = document.getElementById("portfolio-analysis-results");
    if (results) {
        const observer = new MutationObserver(() => {
            if (!state.started) return;
            const elapsed = now() - state.started;
            if (results.children.length) {
                console.log(`[PORTFOLIO-PERF] ANALYSIS_RENDERED duration=${(elapsed / 1000).toFixed(3)}s requests=${state.requests.length} maxConcurrent=${state.maxActive}`);
                state.started = null;
            }
        });
        observer.observe(results, { childList: true, subtree: true });
    }

    window.addEventListener("load", () => {
        const entries = performance.getEntriesByType("resource").filter(e => e.name.includes("/api/"));
        console.log(`[PORTFOLIO-PERF] PAGE_API_RESOURCES count=${entries.length}`);
        entries.forEach(e => console.log(`[PORTFOLIO-PERF] RESOURCE ${e.name} duration=${(e.duration / 1000).toFixed(3)}s start=${(e.startTime / 1000).toFixed(3)}s`));
    });

    console.log("[PORTFOLIO-PERF] browser diagnostics installed");
})();
