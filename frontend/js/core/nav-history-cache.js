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

    const apiModule = await import("./api.js");
    const promise = apiModule.api
        .get(`/mutual-funds/${schemeCode}/nav-history?years=${years}`)
        .then((data) => {
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
