(() => {
    if (window.__stockPortfolioDiagnosticInstalled) return;
    window.__stockPortfolioDiagnosticInstalled = true;

    const PREFIX = "[PORTFOLIO-DEBUG]";
    let fetchSequence = 0;
    const fundamentalCache = new Map();
    const fundamentalInflight = new Map();

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
        const isFundamentalRequest = !url.includes("/charts");
        log(`FETCH #${id} START`, symbol, url);
        console.trace(`${PREFIX} FETCH #${id} stack`);

        if (isFundamentalRequest && fundamentalCache.has(url)) {
            log(`FETCH #${id} CACHE HIT`, symbol, { durationMs: 0 });
            const cached = fundamentalCache.get(url);
            return new Response(JSON.stringify(cached.body), {
                status: cached.status,
                headers: { "Content-Type": "application/json" }
            });
        }

        if (isFundamentalRequest && fundamentalInflight.has(url)) {
            log(`FETCH #${id} IN-FLIGHT REUSE`, symbol);
            const cached = await fundamentalInflight.get(url);
            log(`FETCH #${id} END`, symbol, { status: cached.status, ok: cached.ok, durationMs: Math.round(performance.now() - started), reused: true });
            return new Response(JSON.stringify(cached.body), {
                status: cached.status,
                headers: { "Content-Type": "application/json" }
            });
        }

        const requestPromise = (async () => {
            try {
                const response = await originalFetch(...args);
                if (isFundamentalRequest && response.ok) {
                    const body = await response.clone().json();
                    fundamentalCache.set(url, { status: response.status, body });
                }
                return response;
            } finally {
                if (isFundamentalRequest) fundamentalInflight.delete(url);
            }
        })();

        if (isFundamentalRequest) fundamentalInflight.set(url, requestPromise.then(async response => ({
            status: response.status,
            ok: response.ok,
            body: response.ok ? await response.clone().json() : null
        })));

        try {
            const response = await requestPromise;
            log(`FETCH #${id} END`, symbol, {
                status: response.status,
                ok: response.ok,
                durationMs: Math.round(performance.now() - started),
                cachedForReuse: isFundamentalRequest && response.ok
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