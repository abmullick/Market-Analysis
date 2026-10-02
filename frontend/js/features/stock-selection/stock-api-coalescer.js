// Coalesce identical lightweight stock-universe requests made by multiple
// Stock Analysis modules. The selection page has several enhancement modules,
// but the Nifty Total Market universe must be fetched only once per page load.
(() => {
  if (window.__stockApiCoalescerInstalled) return;
  window.__stockApiCoalescerInstalled = true;

  const nativeFetch = window.fetch.bind(window);
  const inflight = new Map();
  const CACHE_KEY = "market-analysis:stock-universe:v1";
  const CACHE_TTL_MS = 24 * 60 * 60 * 1000;
  const REQUEST_TIMEOUT_MS = 45 * 1000;

  function isLightweightUniverse(url, init) {
    if (init?.method && String(init.method).toUpperCase() !== "GET") return false;
    try {
      const u = new URL(url, window.location.href);
      return u.origin === window.location.origin &&
        u.pathname === "/api/stocks/universe" &&
        !u.search;
    } catch {
      return false;
    }
  }

  function makeResponse(data) {
    return new Response(data.body, {
      status: data.status,
      statusText: data.statusText,
      headers: data.headers,
    });
  }

  function readCachedResponse() {
    try {
      const raw = window.sessionStorage.getItem(CACHE_KEY);
      if (!raw) return null;
      const data = JSON.parse(raw);
      if (!data?.savedAt || Date.now() - data.savedAt > CACHE_TTL_MS) {
        window.sessionStorage.removeItem(CACHE_KEY);
        return null;
      }
      if (typeof data.body !== "string" || !Number.isFinite(Number(data.status))) return null;
      return data;
    } catch {
      return null;
    }
  }

  function writeCachedResponse(data) {
    try {
      window.sessionStorage.setItem(CACHE_KEY, JSON.stringify({
        ...data,
        savedAt: Date.now(),
      }));
    } catch {
      // Storage can be unavailable in private/restricted browser contexts.
    }
  }

  window.fetch = function(input, init) {
    const url = typeof input === "string" ? input : input?.url;
    if (!isLightweightUniverse(url, init)) return nativeFetch(input, init);

    const key = new URL(url, window.location.href).href;

    // Once the universe has loaded successfully, navigation back to stock
    // selection should be instant and must not depend on another network call.
    const cached = readCachedResponse();
    if (cached) return Promise.resolve(makeResponse(cached));

    let pending = inflight.get(key);
    if (!pending) {
      const controller = new AbortController();
      const timeoutId = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
      const requestInit = { ...(init || {}), signal: controller.signal };

      pending = nativeFetch(input, requestInit)
        .then(async (response) => ({
          status: response.status,
          statusText: response.statusText,
          headers: [...response.headers.entries()],
          body: await response.text(),
        }))
        .then((data) => {
          if (data.status >= 200 && data.status < 300) writeCachedResponse(data);
          return data;
        })
        .finally(() => {
          window.clearTimeout(timeoutId);
          inflight.delete(key);
        });

      inflight.set(key, pending);
    }

    return pending.then(makeResponse);
  };
})();
