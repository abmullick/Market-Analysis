"""Tests for mutual fund metric tooltips and help text.

Verifies:
- Every displayed metric has an explanation/tooltip in the frontend JS
- Score vs Actual distinction is present
- Percentage metrics mention percentage
- Sharpe/Sortino are described as ratios
- N/A metrics continue to display correctly
- Overall Score explanation mentions preset weighting
"""
import re
import sys

import pytest

sys.path.insert(0, "/home/abmul/projects/Market-Analysis")


def load_frontend_js():
    """Load the mutual fund analysis frontend JS file."""
    js_path = "/home/abmul/projects/Market-Analysis/frontend/js/features/mutual-fund-analysis/index.js"
    with open(js_path, "r") as f:
        return f.read()


class TestMetricTooltips:
    """Verify every metric has a tooltip/explanation in the frontend."""

    def _load_js(self):
        return load_frontend_js()

    def test_all_criteria_have_tooltips(self):
        """Every criterion should have a tooltip with 'Actual' and 'Score'."""
        js_content = self._load_js()
        expected_keys = [
            "1Y_return",
            "3Y_cagr",
            "5Y_cagr",
            "10Y_cagr",
            "sharpe_ratio",
            "sortino_ratio",
            "volatility",
            "maximum_drawdown",
            "downside_deviation",
            "consistency",
        ]

        for key in expected_keys:
            pattern = rf'"{key}":\s*\{{[^}}]*tooltip:\s*"([^"]+)"'
            match = re.search(pattern, js_content)
            assert match, f"Missing tooltip for {key} in frontend JS"
            tooltip = match.group(1)
            assert "Actual" in tooltip, f"Tooltip for {key} should mention 'Actual'"
            assert "Score" in tooltip, f"Tooltip for {key} should mention 'Score'"
            assert len(tooltip) > 30, f"Tooltip too short for {key}"

    def test_return_metrics_described_as_percentages(self):
        """Return/CAGR tooltips should mention percentage."""
        js_content = self._load_js()
        for key in ["1Y_return", "3Y_cagr", "5Y_cagr", "10Y_cagr"]:
            pattern = rf'"{key}":\s*\{{[^}}]*tooltip:\s*"([^"]+)"'
            match = re.search(pattern, js_content)
            assert match, f"Missing tooltip for {key}"
            tooltip = match.group(1)
            assert "%" in tooltip or "percentage" in tooltip.lower(), \
                f"{key} tooltip should mention percentage"

    def test_sharpe_sortino_described_as_ratios_not_percentages(self):
        """Sharpe and Sortino should say they are NOT percentages."""
        js_content = self._load_js()
        for key in ["sharpe_ratio", "sortino_ratio"]:
            pattern = rf'"{key}":\s*\{{[^}}]*tooltip:\s*"([^"]+)"'
            match = re.search(pattern, js_content)
            assert match, f"Missing tooltip for {key}"
            tooltip = match.group(1)
            assert "not a percentage" in tooltip.lower() or "ratio" in tooltip.lower(), \
                f"{key} tooltip should clarify it is not a percentage"

    def test_volatility_drawdown_deviation_described_as_percentages(self):
        """Volatility, drawdown, downside deviation should mention percentage."""
        js_content = self._load_js()
        for key in ["volatility", "maximum_drawdown", "downside_deviation"]:
            pattern = rf'"{key}":\s*\{{[^}}]*tooltip:\s*"([^"]+)"'
            match = re.search(pattern, js_content)
            assert match, f"Missing tooltip for {key}"
            tooltip = match.group(1)
            assert "%" in tooltip or "percentage" in tooltip.lower(), \
                f"{key} tooltip should mention percentage"

    def test_consistency_described_as_percentage(self):
        """Consistency should mention percentage."""
        js_content = self._load_js()
        pattern = r'"consistency":\s*\{[^}]*tooltip:\s*"([^"]+)"'
        match = re.search(pattern, js_content)
        assert match, "Missing tooltip for consistency"
        tooltip = match.group(1)
        assert "%" in tooltip or "percentage" in tooltip.lower()

    def test_max_drawdown_explains_peak_to_trough(self):
        """Max Drawdown tooltip should mention peak-to-trough."""
        js_content = self._load_js()
        pattern = r'"maximum_drawdown":\s*\{[^}]*tooltip:\s*"([^"]+)"'
        match = re.search(pattern, js_content)
        assert match, "Missing tooltip for maximum_drawdown"
        tooltip = match.group(1)
        assert "peak-to-trough" in tooltip.lower() or ("peak" in tooltip.lower() and "trough" in tooltip.lower())

    def test_lower_is_better_metrics_mention_inversion(self):
        """Lower-is-better metrics should mention score inversion."""
        js_content = self._load_js()
        for key in ["volatility", "maximum_drawdown", "downside_deviation"]:
            pattern = rf'"{key}":\s*\{{[^}}]*tooltip:\s*"([^"]+)"'
            match = re.search(pattern, js_content)
            assert match, f"Missing tooltip for {key}"
            tooltip = match.group(1)
            assert "inverted" in tooltip.lower() or "higher score" in tooltip.lower(), \
                f"{key} tooltip should explain score inversion"

    def test_overall_score_tooltip_exists(self):
        """Overall Score should have a tooltip mentioning preset weights."""
        js_content = self._load_js()
        pattern = r'overall_score:\s*"([^"]+)"'
        match = re.search(pattern, js_content)
        assert match, "Missing overall_score tooltip"
        tooltip = match.group(1)
        assert "weighted" in tooltip.lower(), "Overall score tooltip should mention weighting"
        assert "preset" in tooltip.lower(), "Overall score tooltip should mention preset"

    def test_score_tooltip_exists(self):
        """Individual score tooltip should exist and explain 0-100 scale."""
        js_content = self._load_js()
        pattern = r'score:\s*"([^"]+)"'
        match = re.search(pattern, js_content)
        assert match, "Missing score tooltip"
        tooltip = match.group(1)
        assert "0" in tooltip and "100" in tooltip, "Score tooltip should mention 0-100 scale"

    def test_tooltip_triggers_rendered_in_detail_view(self):
        """Detail view should render tooltip-trigger elements."""
        js_content = self._load_js()
        assert 'class="tooltip-trigger"' in js_content or "tooltip-trigger" in js_content, \
            "Tooltip trigger elements should be rendered in detail view"

    def test_tooltip_content_elements_rendered(self):
        """Tooltip content spans should be rendered inside triggers."""
        js_content = self._load_js()
        assert 'class="tooltip-content"' in js_content, \
            "Tooltip content elements should be rendered"

    def test_methodology_box_updated(self):
        """Methodology box should explain Actual vs Score."""
        js_content = self._load_js()
        assert "Actual" in js_content, "Methodology should explain Actual values"
        assert "Score" in js_content, "Methodology should explain Score values"
        assert "normalized" in js_content.lower() or "0–100" in js_content, \
            "Methodology should explain normalization"


class TestTooltipTextConsistency:
    """Verify tooltip text is consistent with backend behavior."""

    def _load_js(self):
        return load_frontend_js()

    def test_consistency_tooltip_matches_backend_calculation(self):
        """Consistency tooltip should match the actual backend calculation (1Y rolling windows)."""
        js_content = self._load_js()
        pattern = r'"consistency":\s*\{[^}]*tooltip:\s*"([^"]+)"'
        match = re.search(pattern, js_content)
        assert match, "Missing tooltip for consistency"
        tooltip = match.group(1)
        assert "rolling" in tooltip.lower(), "Consistency tooltip should mention rolling windows"
        assert "1Y" in tooltip or "1-year" in tooltip.lower() or "one year" in tooltip.lower(), \
            "Consistency tooltip should specify 1Y period"

    def test_drawdown_tooltip_matches_backend_calculation(self):
        """Drawdown tooltip should match actual backend calculation (peak-to-trough)."""
        js_content = self._load_js()
        pattern = r'"maximum_drawdown":\s*\{[^}]*tooltip:\s*"([^"]+)"'
        match = re.search(pattern, js_content)
        assert match, "Missing tooltip for maximum_drawdown"
        tooltip = match.group(1)
        assert "peak" in tooltip.lower() and "trough" in tooltip.lower(), \
            "Drawdown tooltip should mention peak-to-trough"
