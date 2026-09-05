import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = await readFile("frontend/js/features/mutual-fund-analysis/ranking-ai-response.js", "utf8");
const { renderRankingAIError, renderRankingAILoading, renderRankingAIResponse } = await import(
    `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`,
);

class Element {
    constructor(document) { this.ownerDocument = document; this.children = []; this.textContent = ""; this.attributes = {}; this.listeners = {}; }
    appendChild(child) { this.children.push(child); return child; }
    replaceChildren(...children) { this.children = children; }
    setAttribute(name, value) { this.attributes[name] = value; }
    addEventListener(name, handler) { this.listeners[name] = handler; }
}
class Document { createElement() { return new Element(this); } }
function container() { return new Element(new Document()); }
function text(node) { return [node.textContent, ...node.children.map(text)].join(" "); }

test("renders ranking response sections and disclosure as text", () => {
    const root = container();
    renderRankingAIResponse(root, {
        summary: "Summary <b>text</b>",
        key_points: ["Driver"],
        risks: ["Trade-off"],
        opportunities: ["Opportunity"],
        recommendation: "Investigate",
    });
    const rendered = text(root);
    assert.match(rendered, /Summary <b>text<\/b>/);
    assert.match(rendered, /Drivers & Key Points/);
    assert.match(rendered, /Trade-offs & Risks/);
    assert.match(rendered, /Opportunities/);
    assert.match(rendered, /Recommendation/);
    assert.match(rendered, /does not recalculate the ranking/);
});

test("supports local loading, retry, and malformed-response handling", async () => {
    const root = container();
    renderRankingAILoading(root);
    assert.match(text(root), /Generating AI Ranking Insights/);
    let retried = false;
    renderRankingAIError(root, () => { retried = true; });
    await root.children[1].listeners.click();
    assert.equal(retried, true);
    assert.throws(() => renderRankingAIResponse(container(), { summary: "bad" }), /Invalid ranking insights response/);
});
