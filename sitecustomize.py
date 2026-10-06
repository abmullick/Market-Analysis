"""Diagnostic-only server instrumentation for Screener fetch timing.

Loaded automatically by Python's site module when this repository is the
working directory. This intentionally does not modify application behavior.
"""

import time


def _install_screener_diagnostics() -> None:
    try:
        from backend.services.data.screener import ScreenerFinanceClient
    except Exception:
        return

    if getattr(ScreenerFinanceClient, "_diagnostic_timing_installed", False):
        return

    original_fetch = ScreenerFinanceClient._fetch

    def timed_fetch(self, symbol):
        started = time.perf_counter()
        key = self._symbol(symbol)
        cached = self._cache.get(key)
        if cached and time.time() - cached[0] < self.CACHE_TTL:
            print(f"[SCREENER-PERF] {key} CACHE_HIT", flush=True)
            return original_fetch(self, symbol)

        with self._fetch_inflight_lock:
            is_inflight = key in self._fetch_inflight

        if is_inflight:
            print(f"[SCREENER-PERF] {key} IN_FLIGHT_REUSE", flush=True)
        else:
            print(f"[SCREENER-PERF] {key} NEW_REQUEST", flush=True)

        try:
            result = original_fetch(self, symbol)
            print(
                f"[SCREENER-PERF] {key} COMPLETE wait={time.perf_counter() - started:.3f}s",
                flush=True,
            )
            return result
        except Exception as exc:
            print(
                f"[SCREENER-PERF] {key} FAILED duration={time.perf_counter() - started:.3f}s error={exc}",
                flush=True,
            )
            raise

    ScreenerFinanceClient._fetch = timed_fetch
    ScreenerFinanceClient._diagnostic_timing_installed = True
    print("[SCREENER-PERF] server diagnostics installed", flush=True)


_install_screener_diagnostics()
