import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = await readFile("frontend/js/features/mutual-fund-analysis/ranking-ai-request.js", "utf8");
const contextSource = await readFile("frontend/js/features/mutual-fund-analysis/ranking-ai-context.js", "utf8");
globalThis.__rankingContext = await import(`data:text/javascript;base64,${Buffer.from(contextSource).toString("base64")}`);
const module = await import(`data:text/javascript;base64,${Buffer.from(
    source.replace('import { serializeRankingAIContext } from "./ranking-ai-context.js";', "const { serializeRankingAIContext } = globalThis.__rankingContext;"),
).toString("base64")}`);
const { requestRankingAIInsights } = module;

const context = {
    ranking_configuration: {
        categories: ["Large Cap"],
        screening_filters: [],
        criteria: [{ name: "3Y_cagr", weight: 100 }],
        auto_renormalize: true,
    },
    ranking_summary: { total_funds: 2, displayed_funds: 2, categories: ["Large Cap"] },
    top_funds: [{ rank: 1, scheme_name: "Fund A", overall_score: 95 }],
    bottom_funds: [{ rank: 2, scheme_name: "Fund B", overall_score: 40 }],
};

test("posts exact compact ranking context once to the dedicated endpoint", async () => {
    const calls = [];
    const result = await requestRankingAIInsights({
        apiClient: { post: async (...args) => { calls.push(args); return { summary: "ok" }; } },
        context,
    });

    assert.deepEqual(result, { summary: "ok" });
    assert.equal(calls.length, 1);
    assert.equal(calls[0][0], "/mutual-funds/ranking-insights");
    assert.deepEqual(calls[0][1], context);
    assert.equal("currentRankings" in calls[0][1], false);
});
