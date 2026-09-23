// Bond Analysis bond-selection regression tests.
//
// Covers the government no-ISIN selection bug fix: every listed bond must be
// selectable with identity priority ISIN → record_id, no row may be disabled
// merely for lacking an ISIN, and the correct existing endpoint must be used
// for each identity type:
//
//   government + ISIN      → /bonds/{isin} (+ /market, /analytics)
//   government + record_id  → /bonds/record/{record_id} (no analytics)
//   corporate + ISIN        → /bonds/corporate/{isin} (+ /analytics)
//   corporate + record_id   → /bonds/record/{record_id} (no analytics)
//
// Pure helpers are extracted from the real feature module and executed in a
// sandbox (same technique as test_bond_range_filters.mjs); wire-up assertions
// match the shipped source and HTML.
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import vm from "node:vm";

const jsSource = await readFile("frontend/js/features/bond-analysis/index.js", "utf8");
const htmlSource = await readFile("frontend/html/bond-analysis.html", "utf8");

// Slice a top-level `function name(...) { ... }` declaration out of the source
// using brace matching (these helpers contain no unbalanced braces in strings).
function extractFunction(source, name) {
    const start = source.indexOf(`function ${name}(`);
    assert.notEqual(start, -1, `function ${name} not found in bond-analysis/index.js`);

    let depth = 0;
    let opened = false;
    for (let i = start; i < source.length; i += 1) {
        const ch = source[i];
        if (ch === "{") {
            depth += 1;
            opened = true;
        } else if (ch === "}") {
            depth -= 1;
            if (opened && depth === 0) return source.slice(start, i + 1);
        }
    }
    throw new Error(`unbalanced braces while extracting ${name}`);
}

// A real government list payload: CCIL market-watch record with no ISIN but a
// backend-issued record_id (matches the live GET /api/bonds response).
const CCIL_NO_ISIN = {
    isin: null,
    record_id: "ccil|g_sec|cb9b61b8bb97",
    security_name: "06.94 GS 2036",
    instrument_type: "G-Sec",
    issuer: null,
    source: "CCIL",
    data_type: "traded",
    ytm: 7.0367,
    clean_price: 99.32,
    maturity_date: "2036-05-11",
    coupon_rate: 6.94,
};

const GOV_ISIN = {
    isin: "IN0020220091",
    record_id: "ccil|g_sec|9e1a04c2d511",
    security_name: "07.10 GS 2034",
    instrument_type: "G-Sec",
    issuer: "Government of India",
    source: "CCIL",
    data_type: "traded",
    ytm: 6.54,
    clean_price: 101.25,
    maturity_date: "2034-04-15",
    coupon_rate: 7.1,
};

const CORP_ISIN = {
    isin: "INE296A07TC9",
    record_id: "cdsl|corporate_bond|e28534dd7084",
    security_name: "BAJAJ FINANCE LIMITED 8.12 NCD 10SP27 FVRS1LAC",
    instrument_type: "Corporate Bond",
    issuer: "BAJAJ FINANCE LIMITED",
    credit_rating: "AAA",
    source: "CDSL",
    data_type: "traded",
    ytm: 8.12,
    maturity_date: "2027-09-10",
    coupon_rate: 8.12,
    weighted_average_yield: 8.1,
};

// Build an isolated context holding the real identity/selection logic.
function buildSelectionSandbox() {
    const code = [
        'const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];',
        extractFunction(jsSource, "escapeHtml"),
        extractFunction(jsSource, "escapeAttr"),
        extractFunction(jsSource, "na"),
        extractFunction(jsSource, "formatPct"),
        extractFunction(jsSource, "formatNum"),
        extractFunction(jsSource, "formatDate"),
        extractFunction(jsSource, "bondIdentity"),
        extractFunction(jsSource, "bondSelectionKey"),
        extractFunction(jsSource, "bondMarketFlag"),
        extractFunction(jsSource, "bondDetailPlan"),
        extractFunction(jsSource, "elementSelectionKey"),
        extractFunction(jsSource, "renderBondListRow"),
    ].join("\n\n");

    const sandbox = {};
    vm.createContext(sandbox);
    vm.runInContext(code, sandbox);
    return sandbox;
}

const sandbox = buildSelectionSandbox();

// ---------------------------------------------------------------------------
// Identity resolution
// ---------------------------------------------------------------------------

test("Bond Analysis - ISIN wins over record_id when both are present", () => {
    const id = sandbox.bondIdentity(GOV_ISIN);
    assert.equal(id.kind, "isin");
    assert.equal(id.isin, "IN0020220091");
    assert.equal(sandbox.bondSelectionKey(GOV_ISIN), "isin:IN0020220091");
});

test("Bond Analysis - a no-ISIN government record resolves to its record_id", () => {
    const id = sandbox.bondIdentity(CCIL_NO_ISIN);
    assert.equal(id.kind, "record");
    assert.equal(id.isin, "");
    assert.equal(id.recordId, "ccil|g_sec|cb9b61b8bb97");
    assert.equal(sandbox.bondSelectionKey(CCIL_NO_ISIN), "record:ccil|g_sec|cb9b61b8bb97");
});

test("Bond Analysis - no record_id is ever fabricated", () => {
    const id = sandbox.bondIdentity({ security_name: "Mystery" });
    assert.equal(id.kind, "none");
    assert.equal(sandbox.bondSelectionKey({ security_name: "Mystery" }), "");
});

test("Bond Analysis - row buttons feed back the same selection key", () => {
    for (const bond of [GOV_ISIN, CCIL_NO_ISIN, CORP_ISIN]) {
        const html = sandbox.renderBondListRow(bond, null, false);
        const isin = (html.match(/data-isin="([^"]*)"/) || [])[1] ?? "";
        const recordId = (html.match(/data-record-id="([^"]*)"/) || [])[1] ?? "";
        assert.equal(
            sandbox.elementSelectionKey({ dataset: { isin, recordId } }),
            sandbox.bondSelectionKey(bond),
        );
    }
});

// ---------------------------------------------------------------------------
// Endpoint selection (existing routes only)
// ---------------------------------------------------------------------------

test("Bond Analysis - government ISIN uses the three ISIN endpoints", () => {
    const plan = sandbox.bondDetailPlan(
        { kind: "isin", isin: "IN0020220091", recordId: "ccil|g_sec|9e1a04c2d511" },
        "government",
        "",
    );
    assert.equal(plan.key, "isin:IN0020220091");
    assert.equal(plan.detail, "/bonds/IN0020220091");
    assert.equal(plan.market, "/bonds/IN0020220091/market");
    assert.equal(plan.analytics, "/bonds/IN0020220091/analytics");
});

test("Bond Analysis - government record_id uses the record route and no analytics", () => {
    const plan = sandbox.bondDetailPlan(
        { kind: "record", isin: "", recordId: "ccil|g_sec|cb9b61b8bb97" },
        "government",
        "",
    );
    assert.equal(plan.key, "record:ccil|g_sec|cb9b61b8bb97");
    assert.equal(plan.detail, "/bonds/record/ccil%7Cg_sec%7Ccb9b61b8bb97");
    assert.equal(plan.market, null);
    assert.equal(plan.analytics, null);
});

test("Bond Analysis - corporate ISIN uses the corporate endpoints", () => {
    const plan = sandbox.bondDetailPlan(
        { kind: "isin", isin: "INE296A07TC9", recordId: "" },
        "corporate",
        "",
    );
    assert.equal(plan.key, "isin:INE296A07TC9");
    assert.equal(plan.detail, "/bonds/corporate/INE296A07TC9");
    assert.equal(plan.analytics, "/bonds/corporate/INE296A07TC9/analytics");
});

test("Bond Analysis - corporate trade date pins both corporate requests", () => {
    const plan = sandbox.bondDetailPlan(
        { kind: "isin", isin: "INE296A07TC9", recordId: "" },
        "corporate",
        "2026-09-22",
    );
    assert.equal(plan.detail, "/bonds/corporate/INE296A07TC9?trade_date=2026-09-22");
    assert.equal(plan.analytics, "/bonds/corporate/INE296A07TC9/analytics?trade_date=2026-09-22");
});

test("Bond Analysis - a record with no identity has no endpoint plan", () => {
    assert.equal(sandbox.bondDetailPlan({ kind: "none", isin: "", recordId: "" }, "government", ""), null);
});

// ---------------------------------------------------------------------------
// Row rendering — no-ISIN rows are buttons, not disabled divs
// ---------------------------------------------------------------------------

test("Bond Analysis - no-ISIN government record renders as a real button", () => {
    const html = sandbox.renderBondListRow(CCIL_NO_ISIN, null, false);
    assert.match(html, /^<li class="ba-bond-row"><button type="button" class="ba-bond-item"/);
    assert.match(html, /data-record-id="ccil\|g_sec\|cb9b61b8bb97"/);
    assert.match(html, />Record ID</);
    assert.match(html, /06\.94 GS 2036/);
    assert.doesNotMatch(html, /aria-disabled/);
});

test("Bond Analysis - ISIN records keep rendering with data-isin", () => {
    const gov = sandbox.renderBondListRow(GOV_ISIN, null, false);
    assert.match(gov, /^<li class="ba-bond-row"><button type="button" class="ba-bond-item"/);
    assert.match(gov, /data-isin="IN0020220091"/);
    assert.match(gov, />ISIN</);

    const corp = sandbox.renderBondListRow(CORP_ISIN, null, true);
    assert.match(corp, /data-isin="INE296A07TC9"/);
    assert.match(corp, /BAJAJ FINANCE LIMITED/);
});

test("Bond Analysis - selected row carries the selected state", () => {
    const key = sandbox.bondSelectionKey(CCIL_NO_ISIN);
    const html = sandbox.renderBondListRow(CCIL_NO_ISIN, key, false);
    assert.match(html, /class="ba-bond-item selected"/);
    assert.match(html, /aria-pressed="true"/);
});

test("Bond Analysis - only a record with no identifier at all is inert", () => {
    const html = sandbox.renderBondListRow({ security_name: "Mystery" }, null, false);
    assert.match(html, /ba-bond-item-inert/);
    assert.match(html, /aria-disabled="true"/);
    assert.doesNotMatch(html, /<button/);
});

// ---------------------------------------------------------------------------
// Wire-up — the shipped module resolves identity from the row and executes
// the planned endpoints.
// ---------------------------------------------------------------------------

test("Bond Analysis - click handler resolves identity (not ISIN-only)", () => {
    const click = jsSource.slice(jsSource.indexOf('bondList.addEventListener("click"'));
    assert.match(click, /closest\("\.ba-bond-item"\)/);
    assert.match(click, /tagName !== "BUTTON"/);
    assert.match(click, /dataset\.isin/);
    assert.match(click, /dataset\.recordId/);
    assert.match(click, /selectBond\(\{/);
});

test("Bond Analysis - detail load executes the identity endpoint plan", () => {
    const select = jsSource.slice(jsSource.indexOf("async function selectBond("));
    assert.match(select, /bondDetailPlan\(identity, state\.universe/);
    assert.match(select, /api\.get\(plan\.detail\)/);
    assert.match(select, /api\.get\(plan\.market\)/);
    assert.match(select, /api\.get\(plan\.analytics\)/);
    assert.match(select, /markSelectedRow\(plan\.key\)/);
});

test("Bond Analysis - list render delegates to the identity-aware row builder", () => {
    assert.match(jsSource, /renderBondListRow\(b, state\.selectedKey, isCorporate\)/);
    assert.doesNotMatch(jsSource, /Details unavailable — this source entry has no ISIN/);
});

test("Bond Analysis - record identity and selection hooks exist in the page", () => {
    assert.match(htmlSource, /id="ba-summary-hero"/);
    assert.match(htmlSource, /id="ba-source-status-list"/);
    assert.match(htmlSource, /data-source="CCIL"/);
    assert.match(htmlSource, /data-source="NSE"/);
    assert.match(htmlSource, /data-source="RBI"/);
});

test("Bond Analysis - empty state invites selection with research context", () => {
    const empty = htmlSource.slice(htmlSource.indexOf('id="ba-detail-empty"'));
    assert.match(empty, /Select a bond to begin/);
    assert.match(empty, /Select a bond from the list to view market data and analytics/);
});

test("Bond Analysis - no-ISIN records show an explicit analytics-unavailable state", () => {
    assert.match(jsSource, /ANALYTICS_UNAVAILABLE_REASON/);
    assert.match(jsSource, /renderKpis\(analytics, bond, analyticsAvailable\)/);
    assert.match(jsSource, /renderCashFlows\(analytics, analyticsAvailable\)/);
});
