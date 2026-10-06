import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger("market_analysis.performance")


class PerformanceLoggingMiddleware(BaseHTTPMiddleware):
    """Diagnostic-only request timing for the stock portfolio performance test.

    This middleware does not alter request concurrency, caching, provider calls,
    response payloads, or application calculations. It only records elapsed
    server time for API requests so the slow stage can be identified safely.
    """

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if not path.startswith("/api/stocks/"):
            return await call_next(request)

        started = time.perf_counter()
        started_wall = time.strftime("%H:%M:%S")
        try:
            response = await call_next(request)
            return response
        finally:
            elapsed_ms = (time.perf_counter() - started) * 1000
            logger.warning(
                "[PORTFOLIO-PERF] %s %s duration=%.0fms started=%s status=%s",
                request.method,
                path,
                elapsed_ms,
                started_wall,
                getattr(locals().get("response"), "status_code", "unknown"),
            )
