import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";

const renderers = [
    "frontend/js/features/stock-selection/stock-ai-response.js",
    "frontend/js/features/mutual-fund-analysis/ai-response.js",
    "frontend/js/features/mutual-fund-analysis/ranking-ai-response.js",
    "frontend/js/features/portfolio-builder/ai-response.js",
];

test("all AI insight renderers use the shared speech controls", async () => {
    for (const path of renderers) {
        const source = await readFile(path, "utf8");
        assert.match(source, /import\s+\{\s*attachSpeechControls\s*\}\s+from\s+["']\.\.\/\.\.\/core\/ai-speech-controls\.js["']/,
            `${path} must import the shared speech controls`);
        assert.match(source, /attachSpeechControls\(container\)/,
            `${path} must attach speech controls after rendering the insight`);
    }
});

test("stock insight renderer is shared by individual and comparison workflows", async () => {
    const source = await readFile(renderers[0], "utf8");
    assert.match(source, /export function renderStockAIResponse/);
});
