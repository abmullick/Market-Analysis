import bisect
from datetime import datetime, timedelta, timezone
from typing import Any

import math

from backend.models.mutual_fund import FundMetrics, NAVRecord


class MetricsCalculator:
    """Calculates quantitative metrics from historical NAV data.

    Formulas and assumptions:
    - Daily return: r_t = (NAV_t / NAV_{t-1}) - 1
    - Period return (1Y): simple return over the most recent ~365 calendar days
    - CAGR: (End/Start)^(1/years) - 1, where years = calendar_days / 365.25
    - Annualized volatility: sample_std(daily_returns) * sqrt(252)
      Uses 252 trading days per year for annualization.
    - Sharpe ratio: (annualized_geometric_return - risk_free_rate) / annualized_volatility
      Risk-free rate is assumed to be an annualized rate.
    - Sortino ratio: (annualized_geometric_return - risk_free_rate) / downside_deviation
      Downside deviation uses only negative daily returns with MAR = 0.
      Downside deviation = sqrt(sum(min(r_t, 0)^2) / N) * sqrt(252)
    - Maximum drawdown: max((peak - trough) / peak) over the series
    - Rolling-return consistency: for overlapping 1Y/3Y/5Y windows, reports
      count of positive returns, percentage positive, mean, and sample std deviation.
    """

    def __init__(self, scheme_code: str, nav_records: list[NAVRecord], risk_free_rate: float = 0.04):
        self._scheme_code = scheme_code
        self._navs = sorted(nav_records, key=lambda n: n.date)
        self._risk_free_rate = risk_free_rate

    def calculate(self) -> FundMetrics:
        if len(self._navs) < 2:
            return self._empty_metrics()

        navs = self._navs
        end_date = datetime.strptime(navs[-1].date, "%Y-%m-%d")
        start_date = datetime.strptime(navs[0].date, "%Y-%m-%d")
        years_available = (end_date - start_date).days / 365.25

        # Pre-parse dates once for all subsequent operations
        parsed_dates = [datetime.strptime(n.date, "%Y-%m-%d") for n in navs]

        one_year_navs = self._slice_navs(navs, 1.0, parsed_dates)
        three_year_navs = self._slice_navs(navs, 3.0, parsed_dates)
        five_year_navs = self._slice_navs(navs, 5.0, parsed_dates)
        ten_year_navs = self._slice_navs(navs, 10.0, parsed_dates)

        one_year_return = self._period_return(one_year_navs)
        three_year_cagr = self._cagr(three_year_navs)
        five_year_cagr = self._cagr(five_year_navs)
        ten_year_cagr = self._cagr(ten_year_navs)

        daily_returns = self._daily_returns(navs)
        annualized_volatility = self._annualized_volatility(daily_returns)

        one_year_volatility = self._annualized_volatility(self._daily_returns(one_year_navs))
        three_year_volatility = self._annualized_volatility(self._daily_returns(three_year_navs))
        five_year_volatility = self._annualized_volatility(self._daily_returns(five_year_navs))
        ten_year_volatility = self._annualized_volatility(self._daily_returns(ten_year_navs))

        total_return = navs[-1].nav / navs[0].nav - 1 if navs[0].nav > 0 else None
        annualized_return = self._annualize(total_return, years_available) if total_return is not None else None

        sharpe_ratio = self._sharpe(annualized_return, annualized_volatility)
        sortino_ratio = self._sortino(annualized_return, daily_returns)
        maximum_drawdown = self._max_drawdown(navs)
        downside_deviation = self._downside_deviation(daily_returns)
        rolling_consistency = self._rolling_consistency(navs, parsed_dates)

        return FundMetrics(
            scheme_code=self._scheme_code,
            calculated_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            data_start_date=navs[0].date,
            data_end_date=navs[-1].date,
            data_points=len(navs),
            years_available=years_available,
            one_year_return=one_year_return,
            three_year_cagr=three_year_cagr,
            five_year_cagr=five_year_cagr,
            ten_year_cagr=ten_year_cagr,
            annualized_volatility=annualized_volatility,
            one_year_volatility=one_year_volatility,
            three_year_volatility=three_year_volatility,
            five_year_volatility=five_year_volatility,
            ten_year_volatility=ten_year_volatility,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            maximum_drawdown=maximum_drawdown,
            downside_deviation=downside_deviation,
            rolling_return_consistency=rolling_consistency,
        )

    def _empty_metrics(self) -> FundMetrics:
        return FundMetrics(
            scheme_code=self._scheme_code,
            calculated_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        )

    def _slice_navs(self, navs: list[NAVRecord], years: float, parsed_dates: list[datetime] | None = None) -> list[NAVRecord]:
        if not navs:
            return []
        if parsed_dates is None:
            parsed_dates = [datetime.strptime(n.date, "%Y-%m-%d") for n in navs]
        start = parsed_dates[0]
        end = parsed_dates[-1]
        total_span = (end - start).days
        if total_span < int(years * 365.25):
            return []
        target_start = end - timedelta(days=int(years * 365.25))
        idx = bisect.bisect_left(parsed_dates, target_start)
        if idx < len(navs):
            return navs[idx:]
        return navs

    def _period_return(self, navs: list[NAVRecord]) -> float | None:
        if len(navs) < 2 or navs[0].nav <= 0:
            return None
        return navs[-1].nav / navs[0].nav - 1

    def _cagr(self, navs: list[NAVRecord]) -> float | None:
        if len(navs) < 2 or navs[0].nav <= 0:
            return None
        start = datetime.strptime(navs[0].date, "%Y-%m-%d")
        end = datetime.strptime(navs[-1].date, "%Y-%m-%d")
        years = (end - start).days / 365.25
        if years <= 0:
            return None
        total_return = navs[-1].nav / navs[0].nav - 1
        return self._annualize(total_return, years)

    def _annualize(self, total_return: float, years: float) -> float | None:
        if years <= 0 or total_return <= -1:
            return None
        try:
            result = (1 + total_return) ** (1 / years) - 1
            if not isinstance(result, (int, float)) or result != result:
                return None
            return result
        except (ZeroDivisionError, ValueError, OverflowError):
            return None

    def _daily_returns(self, navs: list[NAVRecord]) -> list[float]:
        returns = []
        for i in range(1, len(navs)):
            if navs[i - 1].nav > 0:
                returns.append(navs[i].nav / navs[i - 1].nav - 1)
        return returns

    def _annualized_volatility(self, daily_returns: list[float]) -> float | None:
        if len(daily_returns) < 2:
            return None
        mean = sum(daily_returns) / len(daily_returns)
        variance = sum((r - mean) ** 2 for r in daily_returns) / (len(daily_returns) - 1)
        return math.sqrt(variance) * math.sqrt(252)

    def _sharpe(
        self,
        annualized_return: float | None,
        annualized_volatility: float | None,
    ) -> float | None:
        if annualized_return is None or annualized_volatility is None or annualized_volatility == 0:
            return None
        return (annualized_return - self._risk_free_rate) / annualized_volatility

    def _sortino(self, annualized_return: float | None, daily_returns: list[float]) -> float | None:
        if annualized_return is None or not daily_returns:
            return None
        downside_dev = self._downside_deviation(daily_returns)
        if downside_dev is None or downside_dev == 0:
            return None
        return (annualized_return - self._risk_free_rate) / downside_dev

    def _max_drawdown(self, navs: list[NAVRecord]) -> float | None:
        positive_navs = [nav for nav in navs if nav.nav > 0]

        if len(positive_navs) < 2:
            return None

        peak = positive_navs[0].nav
        max_dd = 0.0
        for nav in positive_navs[1:]:
            if nav.nav > peak:
                peak = nav.nav
            dd = (peak - nav.nav) / peak
            if dd > max_dd:
                max_dd = dd
        return max_dd

    def _downside_deviation(self, daily_returns: list[float]) -> float | None:
        if not daily_returns:
            return None
        squared_downside = sum(min(r, 0) ** 2 for r in daily_returns)
        mean_squared_downside = squared_downside / len(daily_returns)
        if mean_squared_downside <= 0:
            return 0.0
        return math.sqrt(mean_squared_downside) * math.sqrt(252)

    def _rolling_returns(self, navs: list[NAVRecord], window_days: int) -> list[float]:
        if len(navs) < 2:
            return []

        parsed = [(datetime.strptime(n.date, "%Y-%m-%d"), n.nav) for n in navs]
        results = []
        start_idx = 0

        for i in range(1, len(parsed)):
            target_start = parsed[i][0] - timedelta(days=window_days)

            while start_idx + 1 < i and parsed[start_idx + 1][0] <= target_start:
                start_idx += 1

            if parsed[start_idx][0] <= target_start:
                start_nav = parsed[start_idx][1]
                if start_nav > 0:
                    results.append(parsed[i][1] / start_nav - 1)

        return results

    def _rolling_consistency(self, navs: list[NAVRecord], parsed_dates: list[datetime] | None = None) -> dict[str, Any] | None:
        windows = {
            "1Y": 365,
            "3Y": 1095,
            "5Y": 1825,
        }

        if len(navs) < 2:
            return None

        if parsed_dates is None:
            parsed_dates = [datetime.strptime(n.date, "%Y-%m-%d") for n in navs]

        parsed = [(d, n.nav) for d, n in zip(parsed_dates, navs)]
        n = len(parsed)

        start_indices = {label: 0 for label in windows}
        returns_by_window = {label: [] for label in windows}

        for i in range(1, n):
            date_i, nav_i = parsed[i]

            for label, window_days in windows.items():
                target_start = date_i - timedelta(days=window_days)
                si = start_indices[label]

                while si + 1 < i and parsed[si + 1][0] <= target_start:
                    si += 1
                start_indices[label] = si

                if parsed[si][0] <= target_start:
                    start_nav = parsed[si][1]
                    if start_nav > 0:
                        returns_by_window[label].append(nav_i / start_nav - 1)

        result = {}
        has_data = False

        for label in windows:
            returns = returns_by_window[label]
            if not returns:
                result[label] = None
                continue

            has_data = True
            positive_count = sum(1 for r in returns if r > 0)
            positive_pct = positive_count / len(returns) * 100
            mean_r = sum(returns) / len(returns)

            if len(returns) >= 2:
                variance = sum((r - mean_r) ** 2 for r in returns) / (len(returns) - 1)
                std_r = math.sqrt(variance)
            else:
                std_r = None

            sorted_returns = sorted(returns)
            mid = len(sorted_returns) // 2
            if len(sorted_returns) % 2 == 0:
                median_r = (sorted_returns[mid - 1] + sorted_returns[mid]) / 2
            else:
                median_r = sorted_returns[mid]

            min_r = min(returns)

            result[label] = {
                "windows": len(returns),
                "positive_pct": positive_pct,
                "mean_return": mean_r,
                "std_return": std_r,
                "median_return": median_r,
                "min_return": min_r,
            }

        return result if has_data else None

    def get_rolling_returns_series(self, window_years: int) -> dict[str, Any]:
        """Calculate rolling CAGR time series for a given window period.

        Uses the same date-alignment conventions as the existing metric
        calculator: for each observation, finds the closest NAV not later
        than approximately ``window_years`` calendar years earlier and
        computes CAGR over that span.

        Args:
            window_years: Rolling window period in years (1, 3, or 5).

        Returns:
            dict with:
                dates: ending dates of each rolling window.
                returns: rolling CAGR values as decimals.
                summary: count, avg, median, min, max, std_dev, positive_pct.
                insufficient_history: True when no valid windows exist.
        """
        if len(self._navs) < 2:
            return {
                "dates": [],
                "returns": [],
                "summary": None,
                "insufficient_history": True,
            }

        window_days = int(window_years * 365.25)
        parsed = [(datetime.strptime(n.date, "%Y-%m-%d"), n.nav) for n in self._navs]
        n = len(parsed)

        dates: list[str] = []
        returns: list[float] = []
        start_idx = 0

        for i in range(1, n):
            date_i, nav_i = parsed[i]
            target_start = date_i - timedelta(days=window_days)

            while start_idx + 1 < i and parsed[start_idx + 1][0] <= target_start:
                start_idx += 1

            if parsed[start_idx][0] <= target_start:
                start_nav = parsed[start_idx][1]
                if start_nav > 0:
                    total_return = nav_i / start_nav - 1
                    years_actual = (date_i - parsed[start_idx][0]).days / 365.25
                    if years_actual > 0:
                        cagr = (1 + total_return) ** (1 / years_actual) - 1
                        dates.append(date_i.strftime("%Y-%m-%d"))
                        returns.append(cagr)

        insufficient_history = len(returns) == 0
        summary = None

        if returns:
            positive_count = sum(1 for r in returns if r > 0)
            positive_pct = positive_count / len(returns) * 100
            avg_r = sum(returns) / len(returns)

            sorted_returns = sorted(returns)
            mid = len(sorted_returns) // 2
            if len(sorted_returns) % 2 == 0:
                median_r = (sorted_returns[mid - 1] + sorted_returns[mid]) / 2
            else:
                median_r = sorted_returns[mid]

            min_r = min(returns)
            max_r = max(returns)

            if len(returns) >= 2:
                variance = sum((r - avg_r) ** 2 for r in returns) / (len(returns) - 1)
                std_r = math.sqrt(variance)
            else:
                std_r = None

            summary = {
                "count": len(returns),
                "avg": avg_r,
                "median": median_r,
                "min": min_r,
                "max": max_r,
                "std_dev": std_r,
                "positive_pct": positive_pct,
            }

        return {
            "dates": dates,
            "returns": returns,
            "summary": summary,
            "insufficient_history": insufficient_history,
        }
