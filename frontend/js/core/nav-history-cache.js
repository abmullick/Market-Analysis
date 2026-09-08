/**
 * Shared in-memory cache for fund NAV history responses.
 *
 * Deduplicates concurrent requests for the same (scheme_code, years)
 * combination and caches completed responses to avoid duplicate
 * network calls within a single page lifecycle.
 *
 * - Cache key: `${scheme_code}:${years}`
 * - Concurrent requests share the same in-flight Promise.
 * - Failed requests are NOT cached; subsequent callers can retry.
 */

const cache = new Map();
const inflight = new Map();

// Very small browser-side cap: evict oldest entries (FIFO) so memory stays
// bounded during long sessions. Only responses the user explicitly requested
// are ever stored, and only in the browser.
const MAX_CACHE_ENTRIES = 25;

function makeKey(schemeCode, years) {
    return `${schemeCode}:${years}`;
}

export async function fetchNavHistory(schemeCode, years = 10) {
    const key = makeKey(schemeCode, years);

    if (cache.has(key)) {
        return cache.get(key);
    }

    if (inflight.has(key)) {
        return inflight.get(key);
    }

    // Register the in-flight promise synchronously (before any await) so that
    // concurrent callers reuse it instead of issuing duplicate HTTP requests.
    const promise = import("./api.js")
        .then((apiModule) =>
            apiModule.api.get(`/mutual-funds/${schemeCode}/nav-history?years=${years}`))
        .then((data) => {
            while (cache.size >= MAX_CACHE_ENTRIES) {
                const oldest = cache.keys().next().value;
                cache.delete(oldest);
            }
            cache.set(key, data);
            inflight.delete(key);
            return data;
        })
        .catch((err) => {
            inflight.delete(key);
            throw err;
        });

    inflight.set(key, promise);
    return promise;
}

export function clearNavHistoryCache() {
    cache.clear();
    inflight.clear();
}
