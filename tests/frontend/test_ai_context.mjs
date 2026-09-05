import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = await readFile(new URL("../../frontend/js/features/mutual-fund-analysis/ai-context.js", import.meta.url), "utf8");
const moduleUrl = `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`;
const { AI_CONTEXT_LIMITS, buildFundAIContext, serializeFundAIContext } = await import(moduleUrl);

const rankingConfiguration = {
    categories: ["Large Cap"],
    screening_filters: [{ field: "amc", operator: "contains", values: ["Axis"] }],
    criteria: [
        { name: "3Y_cagr", weight: 60 },
        { name: "sharpe_ratio", weight: 40 },
    ],
    auto_renormalize: true,
};

function makeDetail(overrides = {}) {
    return {
        scheme_code: "123456",
        scheme_name: "Example Growth Fund",
        category: "Large Cap",
        sub_category: "Large Cap",
        amc: "Example AMC",
        aum_cr: 1200,
        expense_ratio: 0.65,
        fund_age_years: 8.5,
        first_nav_date: "2018-01-01",
        one_year_return: 0.18,
        three_year_cagr: 0.14,
        five_year_cagr: 0.12,
        ten_year_cagr: 0.1,
        annualized_volatility: 0.16,
        sharpe_ratio: 0.91,
        sortino_ratio: 1.2,
        maximum_drawdown: -0.22,
        downside_deviation: 0.11,
        rolling_return_consistency: { "1Y": { positive_pct: 78, count: 84 } },
        asset_allocation: { equity: 95, cash: 5 },
        top_holdings: [{ name: "Example Holdings", weight: 8.4 }],
        nav: 123.45,
        nav_date: "2026-09-01",
        data_points: 2000,
        ...overrides,
    };
}

function makeRanking(overrides = {}) {
    return {
        rank: 4,
        total_funds: 42,
        percentile: 91,
        overall_score: 87.4,
        criteria_scores: [
            { criterion: "3Y_cagr", weight: 60, score: 90, raw_value: 0.14 },
            { criterion: "sharpe_ratio", weight: 40, score: 83, raw_value: 0.91 },
        ],
        ...overrides,
    };
}

test("includes selected fund metrics and exact ranking configuration", () => {
    const context = buildFundAIContext({
        detail: makeDetail(),
        ranking: makeRanking(),
        categoryAnalysis: {
            metrics: [{
                metric: "3Y_cagr",
                label: "3Y CAGR",
                fund_value: 0.14,
                percentile: 88,
                category_count: 42,
                higher_is_better: true,
                rank: 6,
            }],
        },
        rankingConfiguration,
    });

    assert.equal(context.selected_fund.scheme_name, "Example Growth Fund");
    assert.equal(context.selected_fund.performance.three_year_cagr, 0.14);
    assert.equal(context.selected_fund.risk.sharpe_ratio, 0.91);
    assert.deepEqual(context.ranking, {
        rank: 4,
        total_funds: 42,
        percentile: 91,
        overall_score: 87.4,
        metric_scores: makeRanking().criteria_scores,
    });
    assert.deepEqual(context.category_analysis.metrics[0], {
        metric: "3Y_cagr",
        label: "3Y CAGR",
        fund_value: 0.14,
        percentile: 88,
        category_count: 42,
        higher_is_better: true,
        rank: 6,
    });
    assert.deepEqual(context.user_preferences, rankingConfiguration);
    assert.ok(serializeFundAIContext(context).bytes <= AI_CONTEXT_LIMITS.targetBytes);
});

test("caps peers and excludes full peer objects and NAV history", () => {
    const fullPeer = {
        rank: 2,
        scheme_code: "999",
        scheme_name: "Peer Fund",
        overall_score: 92,
        top_holdings: [{ name: "Should not be sent", weight: 50 }],
        nav_history: Array.from({ length: 1000 }, (_, index) => ({ date: index, nav: index })),
    };
    const context = buildFundAIContext({
        detail: makeDetail({ nav_history: Array.from({ length: 1000 }, () => 1) }),
        ranking: makeRanking(),
        rankingConfiguration,
        peers: Array.from({ length: 20 }, () => fullPeer),
    });

    assert.equal(context.peers.length, AI_CONTEXT_LIMITS.maxPeers);
    assert.deepEqual(context.peers[0], { rank: 2, name: "Peer Fund", overall_score: 92 });
    assert.equal("scheme_code" in context.peers[0], false);
    assert.equal("nav_history" in context.selected_fund, false);
    assert.equal("top_holdings" in context.peers[0], false);
});

test("bounds optional portfolio information", () => {
    const context = buildFundAIContext({
        detail: makeDetail({
            asset_allocation: Object.fromEntries(Array.from({ length: 20 }, (_, index) => [`bucket_${index}`, index])),
            top_holdings: Array.from({ length: 20 }, (_, index) => ({ name: `Holding ${index}`, weight: index })),
        }),
        ranking: makeRanking(),
        rankingConfiguration,
    });

    assert.equal(Object.keys(context.selected_fund.portfolio.asset_allocation).length, 8);
    assert.equal(context.selected_fund.portfolio.top_holdings.length, 5);
});

test("removes optional data before failing an oversized core context", () => {
    const oversizedPreferences = {
        categories: ["Category ".repeat(5000)],
        screening_filters: [],
        criteria: [{ name: "3Y_cagr", weight: 100 }],
        auto_renormalize: true,
    };

    assert.throws(
        () => buildFundAIContext({
            detail: makeDetail(),
            ranking: makeRanking(),
            rankingConfiguration: oversizedPreferences,
            peers: Array.from({ length: 5 }, () => ({ rank: 1, name: "Peer", score: 90 })),
        }),
        /safety limit/
    );
});

test("handles missing optional data and remains JSON serializable", () => {
    const context = buildFundAIContext({
        detail: { scheme_name: "Minimal Fund" },
        ranking: { rank: 1 },
        rankingConfiguration,
    });

    const { serialized, bytes } = serializeFundAIContext(context);
    assert.equal(JSON.parse(serialized).selected_fund.scheme_name, "Minimal Fund");
    assert.ok(bytes <= AI_CONTEXT_LIMITS.maxBytes);
    assert.equal("performance" in context.selected_fund, false);
});
