// Coalesce Stock Analysis API requests made by multiple frontend modules.
//
// A single analysis page can have several enhancement modules requesting the
// same analysis/charts/pedigree payload. Keep one in-flight request per exact
// URL and reuse successful responses for the lifetime of this page. This avoids
// duplicate backend work and prevents the enhancement modules from turning one
// stock selection into a request storm.
(() => {
  if (window.__stockApiCoalescerInstalled) return;
  window.__stockApiCoalescerInstalled = true;

  const nativeFetch = window.fetch.bind(window);
  const inflight = new Map();
  const responseCache = new Map();
  const controllers = new Set();
  const CACHE_TTL_MS = 60 * 1000;
  const REQUEST_TIMEOUT_MS = 45 * 1000;
  const UNIVERSE_CACHE_KEY = "market-analysis:stock-universe:v2";
  const UNIVERSE_CACHE_TTL_MS = 24 * 60 * 60 * 1000;

  function stockApiKey(url, init) {
    if (init?.method && String(init.method).toUpperCase() !== "GET") return null;
    if (init?.headers) {
      const headers = new Headers(init.headers);
      if (headers.get("X-Stock-Core-Request") === "comparison") return null;
    }
    try {
      const u = new URL(url, window.location.href);
      if (u.origin !== window.location.origin || !u.pathname.startsWith("/api/stocks")) return null;
      return u.href;
    } catch {
      return null;
    }
  }

  function makeResponse(data) {
    return new Response(data.body, {
      status: data.status,
      statusText: data.statusText,
      headers: data.headers,
    });
  }

  function readUniverseCache(key) {
    if (key !== `${window.location.origin}/api/stocks/universe`) return null;
    try {
      const raw = window.sessionStorage.getItem(UNIVERSE_CACHE_KEY);
      if (!raw) return null;
      const data = JSON.parse(raw);
      if (!data?.savedAt || Date.now() - data.savedAt > UNIVERSE_CACHE_TTL_MS) {
        window.sessionStorage.removeItem(UNIVERSE_CACHE_KEY);
        return null;
      }
      if (typeof data.body !== "string" || !Number.isFinite(Number(data.status))) return null;
      return data;
    } catch {
      return null;
    }
  }

  function writeUniverseCache(key, data) {
    if (key !== `${window.location.origin}/api/stocks/universe`) return;
    try {
      window.sessionStorage.setItem(UNIVERSE_CACHE_KEY, JSON.stringify({ ...data, savedAt: Date.now() }));
    } catch {
      // Storage may be unavailable in private/restricted browser contexts.
    }
  }

  function readMemoryCache(key) {
    const entry = responseCache.get(key);
    if (!entry) return null;
    if (Date.now() - entry.savedAt > CACHE_TTL_MS) {
      responseCache.delete(key);
      return null;
    }
    return entry.data;
  }

  function abortAll() {
    controllers.forEach((controller) => controller.abort());
    controllers.clear();
    inflight.clear();
  }

  window.__stockApiAbortAll = abortAll;
  window.addEventListener("pagehide", abortAll, { once: true });

  window.fetch = function(input, init) {
    const url = typeof input === "string" ? input : input?.url;
    const key = stockApiKey(url, init);
    if (!key) return nativeFetch(input, init);

    const universe = readUniverseCache(key);
    if (universe) return Promise.resolve(makeResponse(universe));

    const cached = readMemoryCache(key);
    if (cached) return Promise.resolve(makeResponse(cached));

    const pending = inflight.get(key);
    if (pending) return pending.then(makeResponse);

    const controller = new AbortController();
    controllers.add(controller);
    const timeoutId = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
    const requestInit = { ...(init || {}), signal: controller.signal };

    const promise = nativeFetch(input, requestInit)
      .then(async (response) => ({
        status: response.status,
        statusText: response.statusText,
        headers: [...response.headers.entries()],
        body: await response.text(),
      }))
      .then((data) => {
        if (data.status >= 200 && data.status < 300) {
          responseCache.set(key, { savedAt: Date.now(), data });
          writeUniverseCache(key, data);
        }
        return data;
      })
      .finally(() => {
        window.clearTimeout(timeoutId);
        controllers.delete(controller);
        inflight.delete(key);
      });

    inflight.set(key, promise);
    return promise.then(makeResponse);
  };
})();
