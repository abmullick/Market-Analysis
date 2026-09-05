import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

async function loadModule(path) {
    const source = await readFile(path, "utf8");
    return import(`data:text/javascript;base64,${Buffer.from(source).toString("base64")}`);
}

const contextModule = await loadModule("frontend/js/features/mutual-fund-analysis/ai-context.js");
const requestSource = await readFile("frontend/js/features/mutual-fund-analysis/ai-request.js", "utf8");
globalThis.__aiContextModule = contextModule;
const requestModule = await import(`data:text/javascript;base64,${Buffer.from(
    requestSource.replace('import { serializeFundAIContext } from "./ai-context.js";', "const { serializeFundAIContext } = globalThis.__aiContextModule;"),
).toString("base64")}`);
const { AI_CONTEXT_LIMITS, buildFundAIContext } = contextModule;
const { requestFundAIInsights } = requestModule;

const detail = {
    scheme_name: "Example Growth Fund",
    category: "Large Cap",
    amc: "Example AMC",
    three_year_cagr: 0.14,
    sharpe_ratio: 0.91,
    nav_history: [{ date: "2026-01-01", nav: 100 }],
};
const ranking = {
    rank: 4,
    total_funds: 42,
    percentile: 91,
    overall_score: 87.4,
    criteria_scores: [{ criterion: "3Y_cagr", weight: 100, score: 90, raw_value: 0.14 }],
};
const rankingConfiguration = {
    categories: ["Large Cap"],
    screening_filters: [{ field: "amc", operator: "contains", values: ["Axis"] }],
    criteria: [{ name: "3Y_cagr", weight: 100 }],
    auto_renormalize: true,
};
const peers = Array.from({ length: 20 }, (_, index) => ({
    rank: index + 1,
    name: `Peer ${index + 1}`,
    score: 90 - index,
    top_holdings: [{ name: "Should not be sent" }],
}));

function createApiMock(response = { accepted: true }) {
    const calls = [];
    return {
        calls,
        post: async (path, body) => {
            calls.push({ path, body });
            return response;
        },
    };
}

test("posts the compact context to the scheme-specific insights endpoint", async () => {
    const apiClient = createApiMock();
    const response = await requestFundAIInsights({
        apiClient,
        buildContext: buildFundAIContext,
        schemeCode: "12/34",
        detail,
        ranking,
        categoryAnalysis: { metrics: [] },
        rankingConfiguration,
        peers,
    });

    assert.deepEqual(response, { accepted: true });
    assert.equal(apiClient.calls.length, 1);
    assert.equal(apiClient.calls[0].path, "/mutual-funds/12%2F34/insights");
    assert.deepEqual(apiClient.calls[0].body.user_preferences, rankingConfiguration);
    assert.equal(apiClient.calls[0].body.ranking.rank, 4);
    assert.equal(apiClient.calls[0].body.peers.length, AI_CONTEXT_LIMITS.maxPeers);
    assert.equal("currentRankings" in apiClient.calls[0].body, false);
    assert.equal("nav_history" in apiClient.calls[0].body.selected_fund, false);
    assert.equal("top_holdings" in apiClient.calls[0].body.peers[0], false);
    assert.ok(JSON.stringify(apiClient.calls[0].body).length < AI_CONTEXT_LIMITS.maxBytes);
});

test("propagates HTTP and network errors without making another request", async () => {
    const errors = [new Error("HTTP error 500"), new Error("Network unavailable")];
    for (const expected of errors) {
        let callCount = 0;
        const apiClient = {
            post: async () => {
                callCount += 1;
                throw expected;
            },
        };

        await assert.rejects(
            requestFundAIInsights({
                apiClient,
                buildContext: buildFundAIContext,
                schemeCode: "123456",
                detail,
                ranking,
                rankingConfiguration,
            }),
            expected,
        );
        assert.equal(callCount, 1);
    }
});

test("does not perform an additional fund-data request", async () => {
    const apiClient = createApiMock();
    let builderCalls = 0;
    await requestFundAIInsights({
        apiClient,
        buildContext: input => {
            builderCalls += 1;
            return buildFundAIContext(input);
        },
        schemeCode: "123456",
        detail,
        ranking,
        rankingConfiguration,
    });

    assert.equal(builderCalls, 1);
    assert.equal(apiClient.calls.length, 1);
});
