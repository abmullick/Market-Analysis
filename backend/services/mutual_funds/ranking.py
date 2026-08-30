from typing import Any

from backend.models.mutual_fund import FundMetrics


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

    def rank(self, funds: list[FundMetrics], criteria: list[dict[str, Any]], auto_renormalize: bool = True) -> list[dict[str, Any]]:
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
                value = self._get_metric_value(fund, c["field"])
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
                raw = self._get_metric_value(fund, c["field"])
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
                "scheme_code": fund.scheme_code,
                "scheme_name": fund.scheme_name,
                "category": fund.category,
                "overall_score": overall * 100 if has_any else None,
                "criteria_scores": criteria_scores,
            })

        results.sort(key=lambda x: x["overall_score"] if x["overall_score"] is not None else -float("inf"), reverse=True)
        for i, r in enumerate(results, start=1):
            r["rank"] = i if r["overall_score"] is not None else None

        return results

    def _get_metric_value(self, fund: FundMetrics, field: str) -> float | None:
        if field == "consistency_score":
            consistency = fund.rolling_return_consistency or {}
            one_y = consistency.get("1Y") or {}
            value = one_y.get("positive_pct")
            return float(value) if value is not None else None
        return getattr(fund, field, None)

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
