(() => {
    if (window.__stockPortfolioRequestCacheInstalled) return;
    window.__stockPortfolioRequestCacheInstalled = true;

    const fundamentalCache = new Map();
    const fundamentalInflight = new Map();
    const chartCache = new Map();
    const chartInflight = new Map();

    const originalFetch = window.fetch.bind(window);

    const toResponse = (cached) => new Response(cached.body == null ? null : JSON.stringify(cached.body), {
        status: cached.status,
        headers: { "Content-Type": "application/json" }
    });

    window.fetch = async (...args) => {
        const input = args[0];
        const url = typeof input === "string" ? input : input?.url || "";
        const match = url.match(/\/api\/stocks\/([^/]+)(?:\/charts)?(?:\?|$)/);
        if (!match) return originalFetch(...args);

        const isChartRequest = url.includes("/charts");
        const cache = isChartRequest ? chartCache : fundamentalCache;
        const inflight = isChartRequest ? chartInflight : fundamentalInflight;

        if (cache.has(url)) {
            return toResponse(cache.get(url));
        }

        if (inflight.has(url)) {
            return toResponse(await inflight.get(url));
        }

        const requestPromise = (async () => {
            const response = await originalFetch(...args);
            let body = null;
            try {
                body = await response.clone().json();
            } catch (_) {
                // Preserve status even when an error response is not JSON.
            }
            const result = {
                status: response.status,
                body,
                ok: response.ok
            };
            if (response.ok) cache.set(url, result);
            return result;
        })();

        inflight.set(url, requestPromise);
        try {
            return toResponse(await requestPromise);
        } finally {
            inflight.delete(url);
        }
    };
})();
