// Coalesce identical lightweight stock-universe requests made by multiple
// Stock Analysis modules. The selection page has several enhancement modules,
// but the Nifty Total Market universe must be fetched only once per page load.
(() => {
  if (window.__stockApiCoalescerInstalled) return;
  window.__stockApiCoalescerInstalled = true;

  const nativeFetch = window.fetch.bind(window);
  const inflight = new Map();

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

  window.fetch = function(input, init) {
    const url = typeof input === "string" ? input : input?.url;
    if (!isLightweightUniverse(url, init)) return nativeFetch(input, init);

    const key = new URL(url, window.location.href).href;
    let pending = inflight.get(key);
    if (!pending) {
      pending = nativeFetch(input, init).then(async (response) => ({
        status: response.status,
        statusText: response.statusText,
        headers: [...response.headers.entries()],
        body: await response.text(),
      })).finally(() => inflight.delete(key));
      inflight.set(key, pending);
    }

    return pending.then((data) => new Response(data.body, {
      status: data.status,
      statusText: data.statusText,
      headers: data.headers,
    }));
  };
})();
