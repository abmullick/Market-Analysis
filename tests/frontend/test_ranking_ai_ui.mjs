import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = await readFile("frontend/js/features/mutual-fund-analysis/index.js", "utf8");
const fundSource = await readFile("frontend/js/features/mutual-fund-analysis/fund-detail.js", "utf8");
const css = await readFile("frontend/css/features/mutual-fund-analysis.css", "utf8");

test("ranking action is explicit, guarded, and uses shared AI styling", () => {
    assert.match(source, /✨ AI Ranking Insights/);
    assert.match(source, /button\.addEventListener\("click", requestInsights\)/);
    assert.match(source, /if \(isRequesting\) return/);
    assert.match(source, /lastRankingAIContext = buildRankingAIContext/);
    assert.match(source, /requestRankingAIInsights/);
    assert.match(source, /ranking-ai-module/);
    assert.match(fundSource, /className = "ai-action ai-action-compact fund-ai-insights-button"/);
    assert.match(css, /\.ai-action\s*\{/);
});
