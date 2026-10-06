"""Diagnostic-only server instrumentation for stock analysis timing.

Loaded automatically by Python's site module when this repository is the
working directory. This intentionally keeps the application UI unchanged.
"""

import re
import threading
import time


def _install_screener_diagnostics() -> None:
    try:
        from backend.services.data.screener import ScreenerFinanceClient
    except Exception:
        return

    if getattr(ScreenerFinanceClient, "_diagnostic_timing_installed", False):
        return

    # Share the application's existing in-flight coordination across client
    # instances. The normal _fetch implementation remains responsible for the
    # actual deduplication.
    ScreenerFinanceClient._shared_fetch_inflight = {}
    ScreenerFinanceClient._shared_fetch_inflight_lock = threading.Lock()

    original_init = ScreenerFinanceClient.__init__

    def diagnostic_init(self):
        original_init(self)
        self._fetch_inflight = ScreenerFinanceClient._shared_fetch_inflight
        self._fetch_inflight_lock = ScreenerFinanceClient._shared_fetch_inflight_lock

        if getattr(self, "_diagnostic_http_installed", False):
            return

        original_get = self.session.get

        def diagnostic_get(url, *args, **kwargs):
            text_url = str(url)
            match = re.search(r"/company/([^/?#]+)", text_url)
            symbol = match.group(1).upper() if match else "?"
            started = time.perf_counter()
            print(
                f"[SCREENER-PERF] HTTP_START {symbol} thread={threading.current_thread().name}",
                flush=True,
            )
            try:
                response = original_get(url, *args, **kwargs)
                print(
                    f"[SCREENER-PERF] HTTP_COMPLETE {symbol} status={response.status_code} duration={time.perf_counter() - started:.3f}s",
                    flush=True,
                )
                return response
            except Exception as exc:
                print(
                    f"[SCREENER-PERF] HTTP_FAILED {symbol} duration={time.perf_counter() - started:.3f}s error={exc}",
                    flush=True,
                )
                raise

        self.session.get = diagnostic_get
        self._diagnostic_http_installed = True

    ScreenerFinanceClient.__init__ = diagnostic_init
    ScreenerFinanceClient._diagnostic_timing_installed = True
    print("[SCREENER-PERF] server diagnostics installed (actual HTTP + shared in-flight)", flush=True)


def _install_yahoo_diagnostics() -> None:
    try:
        from backend.services.data.yahoo import YahooFinanceClient
    except Exception:
        return

    if getattr(YahooFinanceClient, "_diagnostic_timing_installed", False):
        return

    def timed_method(name: str):
        original = getattr(YahooFinanceClient, name)

        def wrapped(self, symbol, *args, **kwargs):
            started = time.perf_counter()
            print(
                f"[STOCK-PROVIDER] START {name} {symbol} thread={threading.current_thread().name}",
                flush=True,
            )
            try:
                result = original(self, symbol, *args, **kwargs)
                print(
                    f"[STOCK-PROVIDER] END {name} {symbol} duration={time.perf_counter() - started:.3f}s",
                    flush=True,
                )
                return result
            except Exception as exc:
                print(
                    f"[STOCK-PROVIDER] FAILED {name} {symbol} duration={time.perf_counter() - started:.3f}s error={exc}",
                    flush=True,
                )
                raise

        return wrapped

    for method_name in ("quote_summary", "financial_history"):
        if hasattr(YahooFinanceClient, method_name):
            setattr(YahooFinanceClient, method_name, timed_method(method_name))

    YahooFinanceClient._diagnostic_timing_installed = True
    print("[STOCK-PROVIDER] Yahoo provider diagnostics installed", flush=True)


_install_screener_diagnostics()
_install_yahoo_diagnostics()
