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

        one_year_navs = self._slice_navs(navs, 1.0)
        three_year_navs = self._slice_navs(navs, 3.0)
        five_year_navs = self._slice_navs(navs, 5.0)
        ten_year_navs = self._slice_navs(navs, 10.0)

        one_year_return = self._period_return(one_year_navs)
        three_year_cagr = self._cagr(three_year_navs)
        five_year_cagr = self._cagr(five_year_navs)
        ten_year_cagr = self._cagr(ten_year_navs)

        daily_returns = self._daily_returns(navs)
        annualized_volatility = self._annualized_volatility(daily_returns)

        total_return = navs[-1].nav / navs[0].nav - 1 if navs[0].nav > 0 else None
        annualized_return = self._annualize(total_return, years_available) if total_return is not None else None

        sharpe_ratio = self._sharpe(annualized_return, annualized_volatility)
        sortino_ratio = self._sortino(annualized_return, daily_returns)
        maximum_drawdown = self._max_drawdown(navs)
        downside_deviation = self._downside_deviation(daily_returns)
        rolling_consistency = self._rolling_consistency(navs)

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

    def _slice_navs(self, navs: list[NAVRecord], years: float) -> list[NAVRecord]:
        if not navs:
            return []
        start = datetime.strptime(navs[0].date, "%Y-%m-%d")
        end = datetime.strptime(navs[-1].date, "%Y-%m-%d")
        total_span = (end - start).days
        if total_span < int(years * 365.25):
            return []
        target_start = end - timedelta(days=int(years * 365.25))
        for i, nav in enumerate(navs):
            if datetime.strptime(nav.date, "%Y-%m-%d") >= target_start:
                return navs[i:]
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
        return (1 + total_return) ** (1 / years) - 1

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
        if len(navs) < 2:
            return None
        peak = navs[0].nav
        max_dd = 0.0
        for nav in navs[1:]:
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

    def _rolling_consistency(self, navs: list[NAVRecord]) -> dict[str, Any] | None:
        windows = {
            "1Y": 365,
            "3Y": 1095,
            "5Y": 1825,
        }
        result = {}
        has_data = False

        for label, days in windows.items():
            returns = self._rolling_returns(navs, days)
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

            result[label] = {
                "windows": len(returns),
                "positive_pct": positive_pct,
                "mean_return": mean_r,
                "std_return": std_r,
            }

        return result if has_data else None
