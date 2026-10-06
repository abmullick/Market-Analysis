(() => {
    if (window.__stockPortfolioRequestCacheInstalled) return;
    window.__stockPortfolioRequestCacheInstalled = true;

    const fundamentalCache = new Map();
    const fundamentalInflight = new Map();
    const chartCache = new Map();
    const chartInflight = new Map();

    const originalFetch = window.fetch.bind(window);

    const cloneCachedResponse = (cached) => new Response(JSON.stringify(cached.body), {
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
            return cloneCachedResponse(cache.get(url));
        }

        if (inflight.has(url)) {
            const cached = await inflight.get(url);
            return cloneCachedResponse(cached);
        }

        const requestPromise = (async () => {
            const response = await originalFetch(...args);
            if (!response.ok) return {
                status: response.status,
                body: null,
                ok: false
            };

            const body = await response.clone().json();
            const cached = {
                status: response.status,
                body,
                ok: true
            };
            cache.set(url, cached);
            return cached;
        })();

        inflight.set(url, requestPromise);
        try {
            const cached = await requestPromise;
            if (cached.ok) return cloneCachedResponse(cached);
            return originalFetch(...args);
        } finally {
            inflight.delete(url);
        }
    };
})();
