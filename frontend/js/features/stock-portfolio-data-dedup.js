(() => {
    if (window.__stockPortfolioDataDedupInstalled) return;
    window.__stockPortfolioDataDedupInstalled = true;

    const originalFetch = window.fetch.bind(window);
    const cache = new Map();
    const inflight = new Map();
    const FUNDAMENTAL_RE = /^\/api\/stocks\/([^/?#]+)(?:\?.*)?$/;

    const makeResponse = entry => new Response(JSON.stringify(entry.body), {
        status: entry.status,
        statusText: entry.statusText || "",
        headers: { "Content-Type": "application/json" }
    });

    window.fetch = (input, init) => {
        const url = typeof input === "string" ? input : input?.url || "";
        const match = FUNDAMENTAL_RE.exec(url);
        if (!match) return originalFetch(input, init);

        const key = `/api/stocks/${decodeURIComponent(match[1]).toUpperCase()}`;
        const cached = cache.get(key);
        if (cached) return Promise.resolve(makeResponse(cached));

        const existing = inflight.get(key);
        if (existing) {
            return existing.then(makeResponse);
        }

        const promise = originalFetch(input, init).then(async response => {
            const body = await response.clone().json();
            const entry = {
                status: response.status,
                statusText: response.statusText,
                body
            };
            if (response.ok) cache.set(key, entry);
            return entry;
        }).finally(() => {
            inflight.delete(key);
        });

        inflight.set(key, promise);
        return promise.then(makeResponse);
    };
})();
