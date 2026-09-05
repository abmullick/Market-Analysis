import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = await readFile("frontend/js/features/mutual-fund-analysis/ai-response.js", "utf8");
const { renderInsightError, renderInsightLoading, renderInsightResponse } = await import(
    `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`,
);

class FakeElement {
    constructor(ownerDocument, tagName) {
        this.ownerDocument = ownerDocument;
        this.tagName = tagName;
        this.children = [];
        this.textContent = "";
        this.attributes = {};
        this.listeners = {};
    }

    appendChild(child) {
        this.children.push(child);
        return child;
    }

    replaceChildren(...children) {
        this.children = children;
    }

    setAttribute(name, value) {
        this.attributes[name] = value;
    }

    addEventListener(name, handler) {
        this.listeners[name] = handler;
    }
}

class FakeDocument {
    createElement(tagName) {
        return new FakeElement(this, tagName);
    }
}

function textFrom(element) {
    return [element.textContent, ...element.children.map(textFrom)].join(" ");
}

function elementsByClass(element, className) {
    const matches = element.className === className ? [element] : [];
    return matches.concat(...element.children.map(child => elementsByClass(child, className)));
}

function makeContainer() {
    return new FakeElement(new FakeDocument(), "div");
}

test("renders every structured insight field as safe text", () => {
    const container = makeContainer();
    renderInsightResponse(container, {
        summary: "Summary <strong>must remain text</strong>",
        key_points: ["Point 1"],
        risks: ["Risk 1"],
        opportunities: ["Opportunity 1"],
        recommendation: "Recommendation 1",
    });

    const rendered = textFrom(container);
    assert.match(rendered, /Summary <strong>must remain text<\/strong>/);
    assert.match(rendered, /Point 1/);
    assert.match(rendered, /Risk 1/);
    assert.match(rendered, /Opportunity 1/);
    assert.match(rendered, /Recommendation 1/);
    assert.match(rendered, /AI interpretation based on the fund analysis/);
    assert.equal(elementsByClass(container, "fund-ai-insights-result-section").length, 5);
});

test("renders local loading and explicit retry error states", async () => {
    const container = makeContainer();
    renderInsightLoading(container);
    assert.equal(container.children[0].attributes.role, "status");
    assert.match(textFrom(container), /Generating AI Insights/);

    let retried = false;
    renderInsightError(container, () => {
        retried = true;
    });
    assert.match(textFrom(container), /could not be generated/);
    assert.equal(container.children[1].textContent, "Retry");
    await container.children[1].listeners.click();
    assert.equal(retried, true);
});

test("rejects malformed structured responses", () => {
    assert.throws(
        () => renderInsightResponse(makeContainer(), { summary: "Only summary" }),
        /Invalid AI insights response/,
    );
});
