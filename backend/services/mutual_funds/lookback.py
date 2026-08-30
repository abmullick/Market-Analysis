from datetime import datetime, timedelta


CRITERIA_LOOKBACK_YEARS = {
    "1Y_return": 1,
    "3Y_cagr": 3,
    "5Y_cagr": 5,
    "10Y_cagr": 10,
    "sharpe_ratio": 1,
    "sortino_ratio": 1,
    "volatility": 1,
    "maximum_drawdown": 1,
    "downside_deviation": 1,
    "consistency": 1,
}

LOOKBACK_BUFFER_DAYS = 90


def get_required_lookback_years(criteria_names: list[str]) -> int:
    """Determine the maximum historical lookback needed for the given criteria."""
    max_years = 1
    for name in criteria_names:
        years = CRITERIA_LOOKBACK_YEARS.get(name, 1)
        max_years = max(max_years, years)
    return max_years


def get_date_range_for_lookback(lookback_years: int, end_date: datetime | None = None) -> tuple[datetime, datetime]:
    """Calculate start and end dates for fetching NAV history."""
    if end_date is None:
        end_date = datetime.now()
    buffer_days = LOOKBACK_BUFFER_DAYS
    total_days = int(lookback_years * 365.25) + buffer_days
    start_date = end_date - timedelta(days=total_days)
    return start_date, end_date
