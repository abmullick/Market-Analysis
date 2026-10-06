(() => {
    if (window.__stockPortfolioDiagnosticInstalled) return;
    window.__stockPortfolioDiagnosticInstalled = true;

    const PREFIX = "[PORTFOLIO-DEBUG]";
    let fetchSequence = 0;
    const fundamentalCache = new Map();
    const fundamentalInflight = new Map();
    const chartCache = new Map();
    const chartInflight = new Map();

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
        const cache = isFundamentalRequest ? fundamentalCache : chartCache;
        const inflight = isFundamentalRequest ? fundamentalInflight : chartInflight;
        const type = isFundamentalRequest ? "fundamental" : "chart";
        log(`FETCH #${id} START`, symbol, url);
        console.trace(`${PREFIX} FETCH #${id} stack`);

        if (cache.has(url)) {
            log(`FETCH #${id} CACHE HIT`, symbol, { type, durationMs: 0 });
            const cached = cache.get(url);
            return new Response(JSON.stringify(cached.body), {
                status: cached.status,
                headers: { "Content-Type": "application/json" }
            });
        }

        if (inflight.has(url)) {
            log(`FETCH #${id} IN-FLIGHT REUSE`, symbol, { type });
            const cached = await inflight.get(url);
            log(`FETCH #${id} END`, symbol, {
                status: cached.status,
                ok: cached.ok,
                durationMs: Math.round(performance.now() - started),
                reused: true,
                type
            });
            return new Response(JSON.stringify(cached.body), {
                status: cached.status,
                headers: { "Content-Type": "application/json" }
            });
        }

        const requestPromise = (async () => {
            try {
                const response = await originalFetch(...args);
                if (response.ok) {
                    const body = await response.clone().json();
                    cache.set(url, { status: response.status, body });
                }
                return response;
            } finally {
                inflight.delete(url);
            }
        })();

        inflight.set(url, requestPromise.then(async response => ({
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
                cachedForReuse: response.ok,
                type
            });
            return response;
        } catch (error) {
            log(`FETCH #${id} ERROR`, symbol, {
                durationMs: Math.round(performance.now() - started),
                message: error?.message || String(error),
                type
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