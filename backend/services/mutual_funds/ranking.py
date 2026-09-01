from typing import Any


def _get_field(fund: dict[str, Any], field: str) -> str | None:
    """Get a field value from a fund dict."""
    if isinstance(fund, dict):
        return fund.get(field)
    return getattr(fund, field, None)


def _get_metric_value(fund: dict[str, Any], field: str) -> float | None:
    """Get a metric value from a fund dict or object."""
    if field == "consistency_score":
        if isinstance(fund, dict):
            consistency = fund.get("rolling_return_consistency") or {}
        else:
            consistency = fund.rolling_return_consistency or {}
        one_y = consistency.get("1Y") or {}
        value = one_y.get("positive_pct")
        return float(value) if value is not None else None
    if isinstance(fund, dict):
        value = fund.get(field)
    else:
        value = getattr(fund, field, None)
    return float(value) if value is not None else None


class RankingEngine:
    CRITERIA = {
        "1Y_return": {"field": "one_year_return", "direction": "higher"},
        "3Y_cagr": {"field": "three_year_cagr", "direction": "higher"},
        "5Y_cagr": {"field": "five_year_cagr", "direction": "higher"},
        "10Y_cagr": {"field": "ten_year_cagr", "direction": "higher"},
        "sharpe_ratio": {"field": "sharpe_ratio", "direction": "higher"},
        "sortino_ratio": {"field": "sortino_ratio", "direction": "higher"},
        "volatility": {"field": "annualized_volatility", "direction": "lower"},
        "maximum_drawdown": {"field": "maximum_drawdown", "direction": "lower"},
        "downside_deviation": {"field": "downside_deviation", "direction": "lower"},
        "consistency": {"field": "consistency_score", "direction": "higher"},
    }

    LABELS = {
        "1Y_return": "1Y Return",
        "3Y_cagr": "3Y CAGR",
        "5Y_cagr": "5Y CAGR",
        "10Y_cagr": "10Y CAGR",
        "sharpe_ratio": "Sharpe Ratio",
        "sortino_ratio": "Sortino Ratio",
        "volatility": "Annualized Volatility",
        "maximum_drawdown": "Maximum Drawdown",
        "downside_deviation": "Downside Deviation",
        "consistency": "1Y Rolling Consistency",
    }

    def rank(self, funds: list[dict[str, Any]], criteria: list[dict[str, Any]], auto_renormalize: bool = True) -> list[dict[str, Any]]:
        if not funds or not criteria:
            return []

        selected = []
        for c in criteria:
            name = c["name"]
            weight = float(c["weight"])
            if name not in self.CRITERIA:
                raise ValueError(f"Unknown criterion: {name}")
            if weight < 0:
                raise ValueError(f"Weight must be non-negative for {name}")
            selected.append({"name": name, "weight": weight, **self.CRITERIA[name]})

        if auto_renormalize:
            total = sum(c["weight"] for c in selected)
            if total <= 0:
                raise ValueError("Sum of weights must be greater than zero")
            for c in selected:
                c["weight"] = c["weight"] / total * 100
        else:
            total = sum(c["weight"] for c in selected)
            if abs(total - 100.0) > 1e-6:
                raise ValueError(f"Weights must sum to 100 (got {total})")

        field_values: dict[str, list[float]] = {c["field"]: [] for c in selected}
        for fund in funds:
            for c in selected:
                value = _get_metric_value(fund, c["field"])
                if value is not None:
                    field_values[c["field"]].append(value)

        ranges: dict[str, tuple[float, float] | None] = {}
        for c in selected:
            values = field_values[c["field"]]
            if not values:
                ranges[c["field"]] = None
            else:
                min_v = min(values)
                max_v = max(values)
                ranges[c["field"]] = (min_v, max_v) if max_v > min_v else (min_v, min_v)

        results = []
        for fund in funds:
            criteria_scores = []
            overall = 0.0
            has_any = False

            for c in selected:
                raw = _get_metric_value(fund, c["field"])
                score = self._normalize(raw, ranges[c["field"]], c["direction"])
                criteria_scores.append({
                    "criterion": c["name"],
                    "weight": c["weight"],
                    "score": score,
                    "raw_value": raw,
                })
                if score is not None:
                    overall += (score / 100.0) * (c["weight"] / 100.0)
                    has_any = True

            results.append({
                "scheme_code": _get_field(fund, "scheme_code"),
                "scheme_name": _get_field(fund, "scheme_name"),
                "amc": _get_field(fund, "amc"),
                "category": _get_field(fund, "category"),
                "nav": _get_field(fund, "nav"),
                "nav_date": _get_field(fund, "nav_date"),
                "data_points": _get_field(fund, "data_points"),
                "overall_score": overall * 100 if has_any else None,
                "criteria_scores": criteria_scores,
            })

        results.sort(key=lambda x: x["overall_score"] if x["overall_score"] is not None else -float("inf"), reverse=True)
        for i, r in enumerate(results, start=1):
            r["rank"] = i if r["overall_score"] is not None else None

        return results

    def calculate_percentiles(self, funds: list[dict[str, Any]], criteria: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Calculate percentile ranks for each fund within the category for each criterion.

        Args:
            funds: List of fund dictionaries with metric values
            criteria: List of criterion dictionaries with name and direction

        Returns:
            List of dicts with metric name, fund value, percentile, and category count
        """
        if not funds or not criteria:
            return []

        selected = []
        for c in criteria:
            name = c["name"]
            if name not in self.CRITERIA:
                continue
            selected.append({"name": name, **self.CRITERIA[name]})

        field_values: dict[str, list[float]] = {c["field"]: [] for c in selected}
        for fund in funds:
            for c in selected:
                value = _get_metric_value(fund, c["field"])
                if value is not None:
                    field_values[c["field"]].append(value)

        results = []
        for fund in funds:
            scheme_code = _get_field(fund, "scheme_code")
            scheme_name = _get_field(fund, "scheme_name")

            for c in selected:
                field = c["field"]
                direction = c["direction"]
                raw = _get_metric_value(fund, field)
                values = field_values[field]
                category_count = len(values)

                if raw is None or category_count < 2:
                    results.append({
                        "scheme_code": scheme_code,
                        "scheme_name": scheme_name,
                        "metric": c["name"],
                        "label": self.LABELS.get(c["name"], c["name"]),
                        "fund_value": raw,
                        "percentile": None,
                        "category_count": category_count,
                        "higher_is_better": direction == "higher",
                    })
                    continue

                if direction == "higher":
                    percentile = (sum(1 for v in values if v <= raw) / category_count) * 100
                    rank = 1 + sum(1 for v in values if v > raw)
                else:
                    percentile = (sum(1 for v in values if v >= raw) / category_count) * 100
                    rank = 1 + sum(1 for v in values if v < raw)

                results.append({
                    "scheme_code": scheme_code,
                    "scheme_name": scheme_name,
                    "metric": c["name"],
                    "label": self.LABELS.get(c["name"], c["name"]),
                    "fund_value": raw,
                    "percentile": percentile,
                    "category_count": category_count,
                    "higher_is_better": direction == "higher",
                    "rank": rank,
                })

        return results

    def _normalize(self, value: float | None, min_max: tuple[float, float] | None, direction: str) -> float | None:
        if value is None or min_max is None:
            return None
        min_v, max_v = min_max
        if max_v == min_v:
            return 100.0
        normalized = (value - min_v) / (max_v - min_v) * 100
        if direction == "lower":
            normalized = 100.0 - normalized
        return max(0.0, min(100.0, normalized))
