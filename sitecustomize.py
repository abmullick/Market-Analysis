"""Diagnostic-only server instrumentation for stock analysis timing.

Loaded automatically by Python's site module when this repository is the
working directory. This intentionally does not change application behavior.
"""

import re
import threading
import time
from concurrent.futures import Future


def _timed_call(label: str, func, *args, **kwargs):
    started = time.perf_counter()
    print(f"[STOCK-PERF] START {label}", flush=True)
    try:
        result = func(*args, **kwargs)
        print(f"[STOCK-PERF] END {label} duration={time.perf_counter() - started:.3f}s", flush=True)
        return result
    except Exception as exc:
        print(f"[STOCK-PERF] FAILED {label} duration={time.perf_counter() - started:.3f}s error={exc}", flush=True)
        raise


def _install_screener_diagnostics() -> None:
    try:
        from backend.services.data.screener import ScreenerFinanceClient
    except Exception:
        return

    if getattr(ScreenerFinanceClient, "_diagnostic_timing_installed", False):
        return

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
            print(f"[SCREENER-PERF] HTTP_START {symbol} thread={threading.current_thread().name}", flush=True)
            try:
                response = original_get(url, *args, **kwargs)
                print(f"[SCREENER-PERF] HTTP_COMPLETE {symbol} status={response.status_code} duration={time.perf_counter() - started:.3f}s", flush=True)
                return response
            except Exception as exc:
                print(f"[SCREENER-PERF] HTTP_FAILED {symbol} duration={time.perf_counter() - started:.3f}s error={exc}", flush=True)
                raise

        self.session.get = diagnostic_get
        self._diagnostic_http_installed = True

    ScreenerFinanceClient.__init__ = diagnostic_init
    ScreenerFinanceClient._diagnostic_timing_installed = True
    print("[SCREENER-PERF] server diagnostics installed (actual HTTP + shared in-flight)", flush=True)


def _install_screener_parse_cache() -> None:
    """Reuse CPU-parsed Screener structures when quote/history run together.

    The HTTP page is already cached/in-flight deduplicated in screener.py, but
    quote_summary() and financial_history() independently parse the same
    BeautifulSoup document. Cache the deterministic parse results too. This is
    diagnostic-branch only and deliberately leaves application source intact.
    """
    try:
        from backend.services.data.screener import ScreenerFinanceClient
    except Exception:
        return
    if getattr(ScreenerFinanceClient, "_parse_cache_installed", False):
        return

    lock = threading.Lock()
    caches = {
        "top_ratios": {},
        "growth": {},
        "table": {},
    }
    inflight: dict[tuple[str, int, str], Future] = {}
    ttl = getattr(ScreenerFinanceClient, "CACHE_TTL", 300)

    original_top_ratios = ScreenerFinanceClient._top_ratios
    original_growth = ScreenerFinanceClient._growth_tables
    original_table = ScreenerFinanceClient._table

    def cached_call(cache_name: str, soup, section: str, producer):
        now = time.time()
        key = (cache_name, id(soup), section)
        with lock:
            entry = caches[cache_name].get((id(soup), section))
            if entry is not None:
                cached_soup, created, value = entry
                if cached_soup is soup and now - created < ttl:
                    return value
                caches[cache_name].pop((id(soup), section), None)

            future = inflight.get(key)
            if future is None:
                future = Future()
                inflight[key] = future
                owner = True
            else:
                owner = False

        if not owner:
            return future.result()

        try:
            started = time.perf_counter()
            value = producer()
            with lock:
                caches[cache_name][(id(soup), section)] = (soup, time.time(), value)
                future.set_result(value)
            print(
                f"[SCREENER-PARSE] MISS {cache_name} section={section} "
                f"duration={time.perf_counter() - started:.3f}s",
                flush=True,
            )
            return value
        except BaseException as exc:
            with lock:
                if not future.done():
                    future.set_exception(exc if isinstance(exc, Exception) else Exception(str(exc)))
            raise
        finally:
            with lock:
                inflight.pop(key, None)
                cutoff = time.time() - ttl
                for name, cache in caches.items():
                    stale = [k for k, entry in cache.items() if entry[1] < cutoff]
                    for k in stale:
                        cache.pop(k, None)

    def cached_top_ratios(cls, soup):
        return cached_call("top_ratios", soup, "", lambda: original_top_ratios(soup))

    def cached_growth(cls, soup):
        return cached_call("growth", soup, "", lambda: original_growth(soup))

    def cached_table(cls, soup, section_id):
        return cached_call("table", soup, section_id, lambda: original_table(soup, section_id))

    ScreenerFinanceClient._top_ratios = classmethod(cached_top_ratios)
    ScreenerFinanceClient._growth_tables = classmethod(cached_growth)
    ScreenerFinanceClient._table = classmethod(cached_table)
    ScreenerFinanceClient._parse_cache_installed = True
    print("[SCREENER-PARSE] shared parsed-page cache installed", flush=True)


def _install_provider_path_diagnostics() -> None:
    try:
        from backend.services.data.yahoo import YahooFinanceClient
    except Exception:
        return
    if getattr(YahooFinanceClient, "_diagnostic_provider_path_installed", False):
        return

    def timed_internal(name: str):
        original = getattr(YahooFinanceClient, name)

        def wrapped(self, symbol, *args, **kwargs):
            started = time.perf_counter()
            provider = "SCREENER" if name.startswith("_screener_") else "YAHOO"
            print(
                f"[STOCK-SOURCE] START {name} symbol={symbol} provider={provider} "
                f"thread={threading.current_thread().name}",
                flush=True,
            )
            try:
                result = original(self, symbol, *args, **kwargs)
                print(
                    f"[STOCK-SOURCE] END {name} symbol={symbol} provider={provider} "
                    f"duration={time.perf_counter() - started:.3f}s",
                    flush=True,
                )
                return result
            except Exception as exc:
                print(
                    f"[STOCK-SOURCE] FAILED {name} symbol={symbol} provider={provider} "
                    f"duration={time.perf_counter() - started:.3f}s error={exc}",
                    flush=True,
                )
                raise

        return wrapped

    for method_name in ("_screener_quote_summary", "_screener_history"):
        if hasattr(YahooFinanceClient, method_name):
            setattr(YahooFinanceClient, method_name, timed_internal(method_name))

    original_get_json = YahooFinanceClient._get_json

    def timed_get_json(self, path, params=None):
        started = time.perf_counter()
        print(
            f"[STOCK-SOURCE] YAHOO_HTTP_START path={path} thread={threading.current_thread().name}",
            flush=True,
        )
        try:
            result = original_get_json(self, path, params)
            print(
                f"[STOCK-SOURCE] YAHOO_HTTP_END path={path} "
                f"duration={time.perf_counter() - started:.3f}s",
                flush=True,
            )
            return result
        except Exception as exc:
            print(
                f"[STOCK-SOURCE] YAHOO_HTTP_FAILED path={path} "
                f"duration={time.perf_counter() - started:.3f}s error={exc}",
                flush=True,
            )
            raise

    YahooFinanceClient._get_json = timed_get_json
    YahooFinanceClient._diagnostic_provider_path_installed = True
    print("[STOCK-SOURCE] provider-path diagnostics installed", flush=True)


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
            print(f"[STOCK-PROVIDER] START {name} {symbol} thread={threading.current_thread().name}", flush=True)
            try:
                result = original(self, symbol, *args, **kwargs)
                print(f"[STOCK-PROVIDER] END {name} {symbol} duration={time.perf_counter() - started:.3f}s", flush=True)
                return result
            except Exception as exc:
                print(f"[STOCK-PROVIDER] FAILED {name} {symbol} duration={time.perf_counter() - started:.3f}s error={exc}", flush=True)
                raise
        return wrapped

    for method_name in ("quote_summary", "financial_history"):
        if hasattr(YahooFinanceClient, method_name):
            setattr(YahooFinanceClient, method_name, timed_method(method_name))
    YahooFinanceClient._diagnostic_timing_installed = True
    print("[STOCK-PROVIDER] Yahoo provider diagnostics installed", flush=True)


def _install_fundamental_pipeline_diagnostics() -> None:
    try:
        import backend.services.data.fundamentals as fundamentals
        from backend.services.stocks.screener import ScreenerEngine
    except Exception:
        return
    if getattr(fundamentals, "_diagnostic_pipeline_installed", False):
        return

    original_analysis = fundamentals.get_stock_analysis
    original_normalize = fundamentals.normalize
    original_derive = ScreenerEngine.derive_fundamental_metrics

    def timed_analysis(client, symbol):
        return _timed_call(f"ANALYSIS {symbol}", original_analysis, client, symbol)

    def timed_normalize(symbol, raw, history):
        return _timed_call(f"NORMALIZE {symbol}", original_normalize, symbol, raw, history)

    def timed_derive(self, data):
        symbol = (data.get("fundamentals") or {}).get("symbol", "?")
        return _timed_call(f"DERIVE_METRICS {symbol}", original_derive, self, data)

    fundamentals.get_stock_analysis = timed_analysis
    fundamentals.normalize = timed_normalize
    ScreenerEngine.derive_fundamental_metrics = timed_derive
    fundamentals._diagnostic_pipeline_installed = True
    print("[STOCK-PERF] fundamental pipeline diagnostics installed", flush=True)


def _install_chart_diagnostics() -> None:
    try:
        import backend.services.data.stock_charts as charts
    except Exception:
        return
    if getattr(charts, "_diagnostic_charts_installed", False):
        return

    original_prices = charts.yahoo_annual_prices
    original_build = charts.build_stock_charts

    def timed_prices(symbol, *args, **kwargs):
        return _timed_call(f"CHART_PRICE_HISTORY {symbol}", original_prices, symbol, *args, **kwargs)

    def timed_build(*args, **kwargs):
        return _timed_call("CHART_BUILD", original_build, *args, **kwargs)

    charts.yahoo_annual_prices = timed_prices
    charts.build_stock_charts = timed_build
    charts._diagnostic_charts_installed = True
    print("[STOCK-PERF] chart pipeline diagnostics installed", flush=True)


_install_screener_diagnostics()
_install_screener_parse_cache()
_install_provider_path_diagnostics()
_install_yahoo_diagnostics()
_install_fundamental_pipeline_diagnostics()
_install_chart_diagnostics()
