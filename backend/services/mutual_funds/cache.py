import time
from typing import Any
from threading import Lock


class MetricsCache:
    def __init__(self, ttl_seconds: int = 86400):
        self._cache: dict[str, tuple[dict[str, Any], float]] = {}
        self._failures: dict[str, float] = {}
        self._ttl = ttl_seconds
        self._lock = Lock()
        self._hits = 0
        self._misses = 0

    def _make_key(self, scheme_code: str, lookback_years: int) -> str:
        return f"{scheme_code}:{lookback_years}"

    def get(self, scheme_code: str, lookback_years: int) -> dict[str, Any] | None:
        key = self._make_key(scheme_code, lookback_years)
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                self._misses += 1
                return None
            metrics, expires = entry
            if time.time() > expires:
                del self._cache[key]
                self._misses += 1
                return None
            self._hits += 1
            return metrics

    def put(self, scheme_code: str, lookback_years: int, metrics: dict[str, Any]) -> None:
        key = self._make_key(scheme_code, lookback_years)
        expires = time.time() + self._ttl
        with self._lock:
            self._cache[key] = (metrics, expires)

    def is_failed(self, scheme_code: str, lookback_years: int) -> bool:
        key = self._make_key(scheme_code, lookback_years)
        with self._lock:
            expires = self._failures.get(key)
            if expires is None:
                return False
            if time.time() > expires:
                del self._failures[key]
                return False
            return True

    def put_failure(self, scheme_code: str, lookback_years: int) -> None:
        key = self._make_key(scheme_code, lookback_years)
        expires = time.time() + self._ttl
        with self._lock:
            self._failures[key] = expires

    def invalidate(self, scheme_code: str | None = None) -> None:
        with self._lock:
            if scheme_code is None:
                self._cache.clear()
                self._failures.clear()
            else:
                keys_to_remove = [k for k in self._cache if k.startswith(f"{scheme_code}:")]
                for k in keys_to_remove:
                    del self._cache[k]
                keys_to_remove = [k for k in self._failures if k.startswith(f"{scheme_code}:")]
                for k in keys_to_remove:
                    del self._failures[k]

    def stats(self) -> dict[str, int]:
        with self._lock:
            return {
                "size": len(self._cache),
                "failures": len(self._failures),
                "hits": self._hits,
                "misses": self._misses,
            }


metrics_cache = MetricsCache(ttl_seconds=86400)
category_analysis_cache: dict[str, tuple[dict[str, Any], float]] = {}
_category_analysis_lock = Lock()


def get_category_analysis(category: str) -> dict[str, Any] | None:
    key = f"category:{category}"
    with _category_analysis_lock:
        entry = category_analysis_cache.get(key)
        if entry is None:
            return None
        data, expires = entry
        if time.time() > expires:
            del category_analysis_cache[key]
            return None
        return data


def put_category_analysis(category: str, data: dict[str, Any], ttl_seconds: int = 86400) -> None:
    key = f"category:{category}"
    expires = time.time() + ttl_seconds
    with _category_analysis_lock:
        category_analysis_cache[key] = (data, expires)
