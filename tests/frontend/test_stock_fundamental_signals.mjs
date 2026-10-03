import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = await readFile("frontend/js/features/stock-selection/stock-fundamental-signals.js", "utf8");
const { buildFundamentalSignals } = await import(
    `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`,
);

function series(values) {
    return values.map((value, index) => ({ year: String(index), value }));
}

test("classifies multi-period improving and deteriorating fundamentals", () => {
    const signals = buildFundamentalSignals({
        trends: {
            roe: series([10, 11, 13]),
            roce: series([12, 13, 15]),
            operating_margin: series([20, 18, 16]),
            revenue_growth: series([5, 8, 12]),
            profit_growth: series([15, 9, 2]),
            eps_growth: series([7, 4, -1]),
            debt: series([100, 90, 70]),
            debt_equity: series([1.2, 1, 0.8]),
            cash_conversion: series([110, 120, 125]),
            promoter_holding: series([50, 50.2, 50.5]),
            fii_holding: series([10, 11, 12]),
            dii_holding: series([8, 8, 9]),
        },
        earnings_quality: {
            fcf: series([100, 105, 110]),
            fcf_growth: series([2, 8, 15]),
            net_profit: series([100, 120, 150]),
        },
        dilution: {
            share_count_cagr_5y: 0.04,
            profit_vs_eps_cagr_gap_5y: 0.05,
        },
    });

    assert.deepEqual(signals.positive, [
        "ROE improving",
        "ROCE improving",
        "Revenue growth strengthening",
        "FCF improving",
        "Strong cash conversion",
        "Debt/Equity declining",
        "Debt declining",
        "Promoter holding stable/increasing",
        "FII/DII holding increasing",
    ]);
    assert.deepEqual(signals.watch, [
        "Operating margin declining",
        "Profit growth deteriorating",
        "EPS growth deteriorating",
        "Share count increasing materially",
        "Profit growth materially exceeds EPS growth",
    ]);
});

test("flags weak cash conversion and FCF deterioration alongside profit growth", () => {
    const signals = buildFundamentalSignals({
        trends: {
            cash_conversion: series([25, 40, 35]),
            debt: series([100, 115, 140]),
            debt_equity: series([0.8, 0.9, 1]),
            promoter_holding: series([50, 49, 47]),
            fii_holding: series([10, 9, 8]),
            dii_holding: series([9, 9, 8]),
        },
        earnings_quality: {
            fcf: series([100, 80, 60]),
            net_profit: series([100, 130, 160]),
        },
    });

    assert.deepEqual(signals.positive, []);
    assert.deepEqual(signals.watch, [
        "FCF deteriorating while profit grows",
        "CFO / Net Profit persistently weak",
        "Debt/Equity increasing",
        "Debt increasing materially",
        "Promoter holding declining",
        "FII/DII holding declining",
    ]);
});

test("does not emit signals for missing, short, or insignificant history", () => {
    const signals = buildFundamentalSignals({
        trends: {
            roe: series([10, 10.5]),
            revenue_growth: series([4, 4.5]),
            debt: series([100, 99, 98]),
        },
    });

    assert.deepEqual(signals, { positive: [], watch: [] });
    assert.deepEqual(buildFundamentalSignals({}), { positive: [], watch: [] });
});