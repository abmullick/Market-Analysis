"""Portfolio-vs-Benchmark data provider (Phase 2E).

Retrieves legitimate free daily historical data for the three comparison series
and builds the rebased, date-aligned ``BenchmarkData`` payload consumed by the
Portfolio Analysis growth chart.

Sources (all FREE, server-side, cached):
- NIFTY 50 TRI : Nifty Indices Total Return Index (NOT the price index) via
  the same Nifty Indices ``/BackPage/getTotalReturnIndexString`` endpoint used
  by the ``jugaad-data`` package. The portfolio holds mutual funds, so the
  Total Return Index (which includes reinvested dividends) is the fair
  long-term benchmark; we never substitute the NIFTY 50 price index.
- S&P 500 TR   : Yahoo Finance ticker ``^SP500TR`` (explicitly the S&P 500
  Total Return series, not the price-only ``^GSPC``). Daily, USD.
- USD/INR      : Frankfurter v2 (ECB reference rates), daily. Used to convert
  the S&P 500 TR series into INR before comparison because the portfolio is an
  INR mutual-fund portfolio.

Design notes:
- Validation: only finite, positive values with parseable dates are kept.
- Alignment: series are intersected on their published dates (no
  interpolation / no forward-fill across long gaps), matching the portfolio
  convention. For S&P -> INR, the latest FX rate on-or-before each S&P date is
  used (weekends/holidays align to the last available reference rate).
- Resilience: any single failing source is omitted and reported in
  ``warnings``; the portfolio series is never modified. Nothing is fabricated.
"""

import bisect
import math
import threading
import time
from datetime import datetime
from typing import Any, Optional

import requests

from backend.models.portfolio import BenchmarkData, PortfolioSeriesPoint
from backend.utils.logging import logger

# ---------------------------------------------------------------------------
# Providers
# ---------------------------------------------------------------------------

# NIFTY 50 Total Return Index - Nifty Indices (same endpoint as jugaad-data).
NIFTY_TRI_URL = "https://niftyindices.com/BackPage/getTotalReturnIndexString"
NIFTY_HEADERS = {
    "Host": "niftyindices.com",
    "Referer": "niftyindices.com",
    "X-Requested-With": "XMLHttpRequest",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/134.0.6998.166 Safari/537.36"
    ),
    "Origin": "https://niftyindices.com",
    "Accept": "*/*",
    "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
    "Content-Type": "application/json; charset=UTF-8",
}
NIFTY_INDEX_NAME = "NIFTY 50"

# S&P 500 Total Return - Yahoo Finance chart API. ^SP500TR is the Total Return
# series (not the price-only ^GSPC).
SP500_YAHOO_SYMBOL = "^SP500TR"
YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/%5ESP500TR"
YAHOO_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
}

# USD/INR - Frankfurter v2 (ECB reference rates), no API key.
FRANKFURTER_RATES_URL = "https://api.frankfurter.dev/v2/rates"

# Smallest usable common period before we declare the comparison unavailable.
MIN_COMMON_OBSERVATIONS = 5

_TIMEOUT = (10, 45)


# ---------------------------------------------------------------------------
# Server-side caching (in-memory, TTL). Follows the project's cache pattern:
# a simple TTL dict guarded by a lock; expires rather than growing unbounded.
# ---------------------------------------------------------------------------

_CACHE_TTL_SECONDS = 24 * 60 * 60  # re-validate providers at most daily
_FAIL_TTL_SECONDS = 10 * 60  # after a provider failure, back off for 10 minutes
_STALE_MAX_AGE_SECONDS = 7 * 24 * 60 * 60  # stale cache usable for at most 7 days
_cache_lock = threading.Lock()
_cache: dict[str, tuple[dict[str, float], float]] = {}
_failures: dict[str, float] = {}


def _cache_get(key: str) -> Optional[dict[str, float]]:
    with _cache_lock:
        entry = _cache.get(key)
        if entry is None:
            return None
        data, expires = entry
        if time.time() > expires:
            return None  # kept in _cache for stale fallback; not served as fresh
        return data


def _cache_get_stale(key: str) -> Optional[dict[str, float]]:
    """Last-known-good data even if expired (within _STALE_MAX_AGE_SECONDS)."""
    with _cache_lock:
        entry = _cache.get(key)
        if entry is None:
            return None
        data, expires = entry
        fetched_at = expires - _CACHE_TTL_SECONDS
        if time.time() - fetched_at > _STALE_MAX_AGE_SECONDS:
            return None
        return data


def _cache_put(key: str, data: dict[str, float]) -> None:
    with _cache_lock:
        _cache[key] = (data, time.time() + _CACHE_TTL_SECONDS)
        _failures.pop(key, None)


def _recent_failure(key: str) -> bool:
    """True while the provider is in a short back-off after a failed attempt.

    Prevents hammering a rate-limiting (HTTP 429) provider on every user
    request; the provider is retried after _FAIL_TTL_SECONDS.
    """
    with _cache_lock:
        failed_at = _failures.get(key)
        if failed_at is None:
            return False
        if time.time() - failed_at > _FAIL_TTL_SECONDS:
            del _failures[key]
            return False
        return True


def _mark_failure(key: str) -> None:
    with _cache_lock:
        _failures[key] = time.time()


def _fetch_cached(key: str, fetch: Any, label: str) -> dict[str, float]:
    """Fresh cache -> single provider attempt -> stale cache -> error.

    A provider failure never triggers synchronous retries; at most one outbound
    request is made per cache window (plus a short negative-cache back-off), so
    a rate-limited provider never slows the user's request by more than one
    attempt.
    """
    fresh = _cache_get(key)
    if fresh is not None:
        return fresh
    if _recent_failure(key):
        stale = _cache_get_stale(key)
        if stale is not None:
            logger.info("%s: provider in back-off, using stale cached data.", label)
            return stale
        raise BenchmarkProviderError(
            f"{label} is temporarily unavailable (provider rate-limited)."
        )
    try:
        data = fetch()
    except Exception as exc:
        _mark_failure(key)
        logger.warning("%s fetch failed: %s", label, exc)
        stale = _cache_get_stale(key)
        if stale is not None:
            logger.info("%s: using stale cached data after provider failure.", label)
            return stale
        raise BenchmarkProviderError(f"{label} is temporarily unavailable.") from exc
    _cache_put(key, data)
    return data


class BenchmarkProviderError(Exception):
    """Raised when a benchmark source is unavailable or returns invalid data."""


# ---------------------------------------------------------------------------
# Low-level fetchers (each returns a dict date-ISO -> float, cached)
# ---------------------------------------------------------------------------


def _valid_value(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        value = float(v)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(value) or value <= 0:
        return None
    return value


def _iso(date_str: str) -> Optional[str]:
    """Parse a value into an ISO 'YYYY-MM-DD' string, or None if invalid."""
    s = str(date_str).strip()
    formats = ("%d %b %Y", "%Y-%m-%d", "%d-%b-%Y")
    for fmt in formats:
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def fetch_nifty50_tri(from_date: str, to_date: str) -> dict[str, float]:
    """NIFTY 50 Total Return Index (TRI), daily, Nifty Indices.

    Returns a mapping {date-ISO: TRI value}. Raises BenchmarkProviderError if
    the source cannot be reached or returns no usable rows.
    """
    cache_key = f"nifty_tri:{from_date}:{to_date}"

    def _fetch() -> dict[str, float]:
        start = datetime.strptime(from_date, "%Y-%m-%d")
        end = datetime.strptime(to_date, "%Y-%m-%d")
        cinfo = {
            "name": NIFTY_INDEX_NAME,
            "startDate": start.strftime("%d-%b-%Y"),
            "endDate": end.strftime("%d-%b-%Y"),
            "indexName": NIFTY_INDEX_NAME,
        }
        payload = {"cinfo": str(cinfo).replace('"', "'")}
        response = requests.post(
            NIFTY_TRI_URL, json=payload, headers=NIFTY_HEADERS, timeout=_TIMEOUT
        )
        response.raise_for_status()
        rows = response.json()
        if not isinstance(rows, list):
            raise ValueError(
                f"unexpected payload (type {type(rows).__name__})"
            )

        series: dict[str, float] = {}
        for row in rows:
            if not isinstance(row, dict):
                continue
            day = _iso(row.get("Date"))
            value = _valid_value(row.get("TotalReturnsIndex"))
            if day and value is not None:
                series[day] = value
        series = {d: series[d] for d in sorted(series)}

        if len(series) < MIN_COMMON_OBSERVATIONS:
            raise ValueError(f"no usable data for {from_date}..{to_date}")
        logger.info(
            "NIFTY 50 TRI: %d observations (%s..%s)",
            len(series), min(series), max(series),
        )
        return series

    return _fetch_cached(cache_key, _fetch, "NIFTY 50 TRI")


def fetch_sp500_total_return(from_date: str, to_date: str) -> dict[str, float]:
    """S&P 500 Total Return Index (USD), daily, Yahoo Finance ticker ^SP500TR.

    Returns a mapping {date-ISO: USD total-return index value}. Raises
    BenchmarkProviderError if Yahoo is unreachable (e.g. rate-limited) or the
    payload cannot be parsed.
    """
    cache_key = f"sp500_tr:{from_date}:{to_date}"

    def _fetch() -> dict[str, float]:
        period1 = int(datetime.strptime(from_date, "%Y-%m-%d").timestamp())
        period2 = int(datetime.strptime(to_date, "%Y-%m-%d").timestamp())
        params = {
            "period1": period1,
            "period2": period2,
            "interval": "1d",
            "events": "history",
        }
        response = requests.get(
            YAHOO_CHART_URL, headers=YAHOO_HEADERS, params=params, timeout=_TIMEOUT
        )
        response.raise_for_status()
        data = response.json()

        try:
            result = (data.get("chart") or {}).get("result") or []
            meta_result = result[0]
            timestamps = meta_result.get("timestamp") or []
            quotes = (meta_result.get("indicators") or {}).get("quote") or [{}]
            closes = quotes[0].get("close") or []
        except (IndexError, AttributeError):
            raise ValueError("malformed chart payload")

        if len(timestamps) != len(closes):
            raise ValueError("timestamp/close length mismatch")

        series: dict[str, float] = {}
        for ts, close in zip(timestamps, closes):
            try:
                epoch = float(ts)
                if epoch > 1e12:  # milliseconds -> seconds
                    epoch /= 1000.0
                day = datetime.utcfromtimestamp(epoch).strftime("%Y-%m-%d")
            except (ValueError, OverflowError, OSError):
                continue
            value = _valid_value(close)
            if day and value is not None:
                series[day] = value
        series = {d: series[d] for d in sorted(series)}

        if len(series) < MIN_COMMON_OBSERVATIONS:
            raise ValueError(f"no usable data for {from_date}..{to_date}")
        logger.info(
            "S&P 500 TR: %d observations (%s..%s)",
            len(series), min(series), max(series),
        )
        return series

    return _fetch_cached(cache_key, _fetch, "S&P 500 TR")


def fetch_usd_inr(from_date: str, to_date: str) -> dict[str, float]:
    """Daily USD/INR reference rate, Frankfurter v2 (ECB)."""
    cache_key = f"usd_inr:{from_date}:{to_date}"

    def _fetch() -> dict[str, float]:
        params = {
            "base": "usd",
            "quotes": "inr",
            "from": from_date,
            "to": to_date,
        }
        response = requests.get(FRANKFURTER_RATES_URL, params=params, timeout=_TIMEOUT)
        response.raise_for_status()
        rows = response.json()

        series: dict[str, float] = {}
        if isinstance(rows, dict) and isinstance(rows.get("rates"), dict):
            for day, rate in rows["rates"].items():
                value = _valid_value(rate)
                iso = _iso(day)
                if iso and value is not None:
                    series[iso] = value
        elif isinstance(rows, list):
            for row in rows:
                if not isinstance(row, dict):
                    continue
                iso = _iso(row.get("date"))
                value = _valid_value(row.get("rate"))
                if iso and value is not None:
                    series[iso] = value
        series = {d: series[d] for d in sorted(series)}

        if len(series) < MIN_COMMON_OBSERVATIONS:
            raise ValueError(f"no usable data for {from_date}..{to_date}")
        logger.info(
            "USD/INR: %d observations (%s..%s)",
            len(series), min(series), max(series),
        )
        return series

    return _fetch_cached(cache_key, _fetch, "USD/INR")


# ---------------------------------------------------------------------------
# Alignment + BenchmarkData construction
# ---------------------------------------------------------------------------


def _convert_usd_to_inr(sp500: dict[str, float], fx: dict[str, float]) -> dict[str, float]:
    """Convert the USD S&P series into INR using the latest FX rate <= date.

    Reuses only real published observations; no FX values are invented. If no
    prior FX rate exists for a date (should not happen for 2013+), that S&P
    observation is dropped.
    """
    if not sp500 or not fx:
        return {}
    fx_days = sorted(fx)
    fx_values = [fx[d] for d in fx_days]
    converted: dict[str, float] = {}
    for day in sorted(sp500):
        idx = bisect.bisect_right(fx_days, day) - 1
        if idx < 0:
            continue
        converted[day] = sp500[day] * fx_values[idx]
    return converted


def _cagr(values: list[float], years: float) -> Optional[float]:
    if not values or years <= 0 or values[0] <= 0 or values[-1] <= 0:
        return None
    return (values[-1] / values[0]) ** (1.0 / years) - 1.0


def build_benchmark_data(portfolio_series: list[PortfolioSeriesPoint]) -> BenchmarkData:
    """Build the rebased, date-aligned benchmark comparison payload.

    The portfolio growth series is used as-is for the Portfolio line; the common
    period is the intersection of valid published dates across the portfolio and
    each available benchmark. All three lines are rebased to 100 at the first
    common date. A failing source is omitted (with a warning) -- never faked.
    """
    if not portfolio_series or len(portfolio_series) < 2:
        return BenchmarkData(warnings=["Insufficient portfolio history for benchmark comparison."])

    portfolio = {p.date: p.value for p in portfolio_series}
    portfolio_dates = [p.date for p in portfolio_series]
    start, end = portfolio_dates[0], portfolio_dates[-1]

    warnings: list[str] = []

    nifty: dict[str, float] = {}
    try:
        nifty = fetch_nifty50_tri(start, end)
    except BenchmarkProviderError as exc:
        logger.warning("NIFTY 50 TRI unavailable: %s", exc)
        warnings.append("NIFTY 50 TRI data temporarily unavailable.")
    except Exception as exc:  # defensively never break the portfolio chart
        logger.warning("NIFTY 50 TRI unavailable: %s", exc)
        warnings.append("NIFTY 50 TRI data temporarily unavailable.")

    sp500_inr: dict[str, float] = {}
    try:
        sp500 = fetch_sp500_total_return(start, end)
        fx = fetch_usd_inr(start, end)
        sp500_inr = _convert_usd_to_inr(sp500, fx)
    except BenchmarkProviderError as exc:
        logger.warning("S&P 500 TR unavailable: %s", exc)
        warnings.append(
            "S&P 500 Total Return temporarily unavailable — the benchmark data "
            "provider temporarily limited the request. Portfolio and NIFTY 50 "
            "comparison remain unaffected."
        )
    except Exception as exc:
        logger.warning("S&P 500 TR unavailable: %s", exc)
        warnings.append(
            "S&P 500 Total Return temporarily unavailable — the benchmark data "
            "provider temporarily limited the request. Portfolio and NIFTY 50 "
            "comparison remain unaffected."
        )

    nifty_ok = bool(nifty)
    sp500_ok = bool(sp500_inr)

    if not nifty_ok and not sp500_ok:
        return BenchmarkData(available=False, warnings=warnings or ["Benchmark data unavailable."])

    common = set(portfolio_dates)
    if nifty_ok:
        common &= set(nifty)
    if sp500_ok:
        common &= set(sp500_inr)
    common = sorted(common)

    if len(common) < MIN_COMMON_OBSERVATIONS:
        return BenchmarkData(
            available=False,
            warnings=warnings or ["Benchmark data does not sufficiently overlap the portfolio period."],
        )

    common_start, common_end = common[0], common[-1]
    observations = len(common)

    # Rebase every series to 100 at the first common date.
    portfolio0 = portfolio[common_start]
    portfolio_reb = [portfolio[d] / portfolio0 * 100.0 for d in common]
    nifty_reb = [nifty[d] / nifty[common_start] * 100.0 for d in common] if nifty_ok else []
    sp500_reb = [sp500_inr[d] / sp500_inr[common_start] * 100.0 for d in common] if sp500_ok else []

    try:
        start_dt = datetime.strptime(common_start, "%Y-%m-%d")
        end_dt = datetime.strptime(common_end, "%Y-%m-%d")
        years = (end_dt - start_dt).days / 365.25
    except ValueError:
        years = 0.0

    portfolio_cagr = _cagr(portfolio_reb, years)
    nifty_cagr = _cagr(nifty_reb, years) if nifty_ok else None
    sp500_cagr = _cagr(sp500_reb, years) if sp500_ok else None

    nifty_outperf = (
        portfolio_cagr - nifty_cagr
        if portfolio_cagr is not None and nifty_cagr is not None
        else None
    )
    sp500_outperf = (
        portfolio_cagr - sp500_cagr
        if portfolio_cagr is not None and sp500_cagr is not None
        else None
    )

    return BenchmarkData(
        available=True,
        nifty50_tri_available=nifty_ok,
        sp500_available=sp500_ok,
        common_start=common_start,
        common_end=common_end,
        observations=observations,
        dates=common,
        portfolio=portfolio_reb,
        nifty50_tri=nifty_reb,
        sp500_total_return_inr=sp500_reb,
        portfolio_cagr=portfolio_cagr,
        nifty50_tri_cagr=nifty_cagr,
        sp500_total_return_cagr=sp500_cagr,
        nifty50_outperformance=nifty_outperf,
        sp500_outperformance=sp500_outperf,
        warnings=warnings,
    )