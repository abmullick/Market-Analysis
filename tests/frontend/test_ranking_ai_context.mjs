import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = await readFile("frontend/js/features/mutual-fund-analysis/ranking-ai-context.js", "utf8");
const moduleUrl = `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`;
const { RANKING_AI_CONTEXT_LIMITS, buildRankingAIContext, serializeRankingAIContext } = await import(moduleUrl);

const rankingConfiguration = {
    categories: ["Equity - Large Cap"],
    screening_filters: [{ field: "amc", operator: "contains", values: ["Axis"] }],
    criteria: [
        { name: "1Y_return", weight: 40 },
        { name: "3Y_cagr", weight: 60 },
    ],
    auto_renormalize: true,
};

function makeFund(rank, extra = {}) {
    return {
        rank,
        scheme_code: `scheme-${rank}`,
        scheme_name: `Fund ${rank}`,
        category: "Large Cap",
        overall_score: 100 - rank,
        criteria_scores: [
            { criterion: "1Y_return", weight: 40, score: 90 - rank, raw_value: 0.1 },
            { criterion: "3Y_cagr", weight: 60, score: 80 - rank, raw_value: 0.12 },
        ],
        nav_history: Array.from({ length: 1000 }, () => ({ nav: rank })),
        ...extra,
    };
}

test("builds compact top and bottom ranking context", () => {
    const rankings = Array.from({ length: 30 }, (_, index) => makeFund(index + 1));
    const context = buildRankingAIContext({
        rankingConfiguration,
        rankings,
        metadata: { eligible_funds: 30, matching_funds: 28 },
    });

    assert.deepEqual(context.ranking_configuration, rankingConfiguration);
    assert.deepEqual(context.ranking_summary, {
        total_funds: 30,
        displayed_funds: 30,
        eligible_funds: 30,
        matching_funds: 28,
        categories: ["Equity - Large Cap"],
    });
    assert.equal(context.top_funds.length, RANKING_AI_CONTEXT_LIMITS.maxTopFunds);
    assert.equal(context.bottom_funds.length, RANKING_AI_CONTEXT_LIMITS.maxBottomFunds);
    assert.equal(context.top_funds[0].rank, 1);
    assert.equal(context.bottom_funds.at(-1).rank, 30);
    assert.equal("scheme_code" in context.top_funds[0], false);
    assert.equal("nav_history" in context.top_funds[0], false);
    assert.equal("currentRankings" in context, false);
});

test("retains metric evidence without full fund objects", () => {
    const context = buildRankingAIContext({ rankingConfiguration, rankings: [makeFund(1)] });
    assert.deepEqual(context.top_funds[0].metric_scores[0], {
        criterion: "1Y_return", weight: 40, score: 89, raw_value: 0.1,
    });
    assert.equal("criteria_scores" in context.top_funds[0], false);
});

test("reduces optional ranking evidence before failing the hard boundary", () => {
    const hugeMetric = "x".repeat(20000);
    const rankings = [makeFund(1, {
        criteria_scores: [{ criterion: hugeMetric, weight: 100, score: 1, raw_value: hugeMetric }],
    })];
    const context = buildRankingAIContext({ rankingConfiguration, rankings });
    assert.equal("metric_scores" in context.top_funds[0], false);
    assert.ok(serializeRankingAIContext(context).bytes <= RANKING_AI_CONTEXT_LIMITS.maxBytes);
});

test("fails instead of dropping oversized essential configuration", () => {
    assert.throws(
        () => buildRankingAIContext({
            rankingConfiguration: {
                categories: ["category ".repeat(5000)],
                screening_filters: [],
                criteria: [{ name: "1Y_return", weight: 100 }],
                auto_renormalize: true,
            },
            rankings: [makeFund(1)],
        }),
        /safety limit/,
    );
});

test("does not calculate ranking values", () => {
    const rankings = [makeFund(1, { rank: 7, overall_score: 42.25 })];
    const context = buildRankingAIContext({ rankingConfiguration, rankings });
    assert.equal(context.top_funds[0].rank, 7);
    assert.equal(context.top_funds[0].overall_score, 42.25);
});
