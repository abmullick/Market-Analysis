// Bond Analysis range-filter integration.
//
// Structure tests assert the wire-up (HTML ids preserved, Apply/Reset
// connected, paged full-universe retrieval). Behaviour tests extract the pure
// range-filter helpers from the feature module and run them against fixture
// bond records, so coercion and boundary handling are verified for real rather
// than only pattern-matched.
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import vm from "node:vm";

const jsSource = await readFile("frontend/js/features/bond-analysis/index.js", "utf8");
const htmlSource = await readFile("frontend/html/bond-analysis.html", "utf8");

// Slice a top-level `function name(...) { ... }` declaration out of the source
// using brace matching (comments/strings in these helpers contain no braces).
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

// Build an isolated context holding the real range-filter logic.
function buildRangeFilterSandbox() {
    const code = [
        "const RANGE_MIN = 0;",
        "const RANGE_MAX = 20;",
        extractFunction(jsSource, "toFiniteNumber"),
        extractFunction(jsSource, "toTimeMs"),
        extractFunction(jsSource, "applyRangeFilters"),
    ].join("\n\n");

    const sandbox = { state: { universe: "government", rangeFilters: {} } };
    vm.createContext(sandbox);
    vm.runInContext(code, sandbox);
    return sandbox;
}

function withRangeFilters(target, universe, overrides) {
    target.state.universe = universe;
    target.state.rangeFilters = {
        couponMin: 0,
        couponMax: 20,
        yieldMin: 0,
        yieldMax: 20,
        maturityFrom: "",
        maturityTo: "",
        ...overrides,
    };
}

const sandbox = buildRangeFilterSandbox();

// ---------------------------------------------------------------------------
// HTML contract
// ---------------------------------------------------------------------------

test("Bond Analysis - range panel keeps its original contract", () => {
    assert.match(htmlSource, /id="ba-range-panel"/);
    assert.match(htmlSource, /id="ba-range-content"/);
    assert.match(htmlSource, /id="ba-range-apply"/);
    assert.match(htmlSource, /id="ba-range-reset"/);
    assert.match(htmlSource, /id="ba-coupon-min"/);
    assert.match(htmlSource, /id="ba-coupon-max"/);
    assert.match(htmlSource, /id="ba-yield-min"/);
    assert.match(htmlSource, /id="ba-yield-max"/);
    assert.match(htmlSource, /id="ba-maturity-from"/);
    assert.match(htmlSource, /id="ba-maturity-to"/);
});

test("Bond Analysis - yield group stays corporate-only", () => {
    // The Weighted Average Yield fieldset is marked corporate-only and hidden
    // by default (the government universe has no weighted average yield).
    const yieldGroup = htmlSource.match(/<fieldset[\s\S]*?id="ba-yield-range-group"[\s\S]*?>/);
    assert.ok(yieldGroup, "yield range group not found");
    assert.match(yieldGroup[0], /ba-corporate-range-only/);
    assert.match(yieldGroup[0], /hidden/);
});

// ---------------------------------------------------------------------------
// JS wire-up
// ---------------------------------------------------------------------------

test("Bond Analysis - range state is tracked", () => {
    assert.match(jsSource, /rangeFilters\s*:\s*\{/);
    for (const key of [
        "couponMin",
        "couponMax",
        "yieldMin",
        "yieldMax",
        "maturityFrom",
        "maturityTo",
    ]) {
        assert.match(jsSource, new RegExp(`${key}\\s*:`), `missing rangeFilters.${key}`);
    }
});

test("Bond Analysis - full universe is paged, not fetched with one huge limit", () => {
    // The backend caps `limit` at 200; the helper loops with limit/offset.
    assert.match(jsSource, /const MAX_PAGE_SIZE = 200;/);
    assert.match(jsSource, /async function fetchAllBonds\(/);
    assert.match(jsSource, /params\.set\("limit", String\(MAX_PAGE_SIZE\)\)/);
    assert.match(jsSource, /params\.set\("offset", String\(offset\)\)/);
    assert.match(jsSource, /bonds\.push\(\.\.\.items\)/);
    assert.match(jsSource, /offset \+= items\.length/);
});

test("Bond Analysis - no invented range query parameters are sent", () => {
    assert.doesNotMatch(
        jsSource,
        /(serverParams|params|pageParams)\.set\(\s*"(coupon|yield|maturity)[a-z_]*"/,
    );
});

test("Bond Analysis - universe downloads are cached and de-duplicated", () => {
    assert.match(jsSource, /const universeCache = new Map\(\)/);
    assert.match(jsSource, /const universeInflight = new Map\(\)/);
    assert.match(jsSource, /function buildFilterSignature\(/);
    assert.match(jsSource, /async function getUniverseBonds\(/);
    assert.match(jsSource, /if \(universeCache\.has\(signature\)\) return universeCache\.get\(signature\);/);
    assert.match(jsSource, /if \(universeInflight\.has\(signature\)\) return universeInflight\.get\(signature\);/);
    // The cache is bounded so repeated filter edits cannot grow it forever.
    assert.match(jsSource, /UNIVERSE_CACHE_LIMIT/);
});

test("Bond Analysis - Apply reloads the universe from page 1", () => {
    const applyBlock = jsSource.slice(jsSource.indexOf('const rangeApply = $("ba-range-apply")'));
    assert.match(applyBlock, /addEventListener\("click"/);
    assert.match(applyBlock, /state\.rangeFilters = readRangeFilters\(\)/);
    assert.match(applyBlock, /state\.page = 1/);
    assert.match(applyBlock, /searchBonds\(\)/);
});

test("Bond Analysis - Reset restores defaults and server-side pagination", () => {
    const resetBlock = jsSource.slice(jsSource.indexOf('const rangeReset = $("ba-range-reset")'));
    assert.match(resetBlock, /addEventListener\("click"/);
    assert.match(resetBlock, /setRangeControlsToDefaults\(\)/);
    assert.match(resetBlock, /state\.rangeFilters = readRangeFilters\(\)/);
    assert.match(resetBlock, /state\.page = 1/);
    assert.match(resetBlock, /searchBonds\(\)/);

    // Defaults: coupon 0-20, yield 0-20, blank maturity dates.
    const defaults = jsSource.slice(jsSource.indexOf("function setRangeControlsToDefaults()"));
    assert.match(defaults, /\["ba-coupon-min", RANGE_MIN\]/);
    assert.match(defaults, /\["ba-coupon-max", RANGE_MAX\]/);
    assert.match(defaults, /\["ba-yield-min", RANGE_MIN\]/);
    assert.match(defaults, /\["ba-yield-max", RANGE_MAX\]/);
    assert.match(defaults, /ba-maturity-from/);
    assert.match(defaults, /ba-maturity-to/);
});

test("Bond Analysis - server-side filters are applied before client-side ranges", () => {
    assert.match(jsSource, /serverParams\.set\("search", q\)/);
    assert.match(jsSource, /serverParams\.set\("instrument_type", type\)/);
    assert.match(jsSource, /serverParams\.set\("source", source\)/);
    assert.match(jsSource, /serverParams\.set\("trade_date", corpFilters\.tradeDate\)/);
    assert.match(jsSource, /serverParams\.set\("issuer", corpFilters\.issuer\)/);
    assert.match(jsSource, /serverParams\.set\("sort_by", state\.sortBy\)/);
    assert.match(jsSource, /serverParams\.set\("sort_dir", state\.sortDir\)/);
    assert.match(jsSource, /applyRangeFilters\(universe \|\| \[\]\)/);
});

test("Bond Analysis - filtered total drives local pagination", () => {
    assert.match(jsSource, /state\.total = filtered\.length/);
    assert.match(
        jsSource,
        /filtered\.slice\(\(state\.page - 1\) \* PAGE_SIZE, state\.page \* PAGE_SIZE\)/,
    );
});


// ---------------------------------------------------------------------------
// Behaviour - coercion and range semantics
// ---------------------------------------------------------------------------

test("Bond Analysis - default slider extremes apply no coupon constraint", () => {
    withRangeFilters(sandbox, "government", {});
    const bonds = [{ coupon_rate: 25 }, { coupon_rate: 0 }, { coupon_rate: null }];
    assert.equal(sandbox.applyRangeFilters(bonds).length, 3);
});

test("Bond Analysis - coupon range includes bounds and rejects unusable values", () => {
    withRangeFilters(sandbox, "government", { couponMin: 6, couponMax: 8 });
    const input = [
        { id: "in-low", coupon_rate: 7.15 },
        { id: "at-min", coupon_rate: 6 },
        { id: "at-max", coupon_rate: 8 },
        { id: "string", coupon_rate: "7.5" },
        { id: "too-low", coupon_rate: 5.9 },
        { id: "too-high", coupon_rate: 8.1 },
        { id: "null", coupon_rate: null },
        { id: "missing" },
        { id: "blank", coupon_rate: "" },
        { id: "invalid", coupon_rate: "n/a" },
    ];
    const kept = sandbox.applyRangeFilters(input).map((b) => b.id);
    assert.deepEqual(kept, ["in-low", "at-min", "at-max", "string"]);
});

test("Bond Analysis - government yield uses market ytm only", () => {
    withRangeFilters(sandbox, "government", { yieldMin: 7, yieldMax: 8 });
    const input = [
        { id: "ytm-in", ytm: 7.5, weighted_average_yield: 99 },
        { id: "way-only", ytm: null, weighted_average_yield: 7.5 },
        { id: "ytm-out", ytm: 9 },
        { id: "ytm-missing" },
    ];
    // weighted_average_yield is never consulted for government bonds.
    assert.deepEqual(sandbox.applyRangeFilters(input).map((b) => b.id), ["ytm-in"]);
});

test("Bond Analysis - corporate yield uses weighted average yield with ytm fallback", () => {
    withRangeFilters(sandbox, "corporate", { yieldMin: 7, yieldMax: 8 });
    const input = [
        { id: "way-in", weighted_average_yield: 7.5 },
        { id: "way-out", weighted_average_yield: 9 },
        { id: "fallback", weighted_average_yield: null, ytm: 7.25 },
        { id: "none", weighted_average_yield: null, ytm: null },
    ];
    assert.deepEqual(
        sandbox.applyRangeFilters(input).map((b) => b.id),
        ["way-in", "fallback"],
    );
});

test("Bond Analysis - corporate yield range never narrows government results", () => {
    // A pending corporate yield range must be inert for the government universe.
    withRangeFilters(sandbox, "government", { yieldMin: 15, yieldMax: 16 });
    const input = [{ ytm: 7.0 }, { ytm: null }];
    assert.equal(sandbox.applyRangeFilters(input).length, 2);
});

test("Bond Analysis - maturity range is inclusive and rejects unusable dates", () => {
    withRangeFilters(sandbox, "government", {
        maturityFrom: "2030-01-01",
        maturityTo: "2035-12-31",
    });
    const input = [
        { id: "at-from", maturity_date: "2030-01-01" },
        { id: "inside", maturity_date: "2032-06-15" },
        { id: "at-to", maturity_date: "2035-12-31" },
        { id: "too-early", maturity_date: "2029-12-31" },
        { id: "too-late", maturity_date: "2036-01-01" },
        { id: "null", maturity_date: null },
        { id: "missing" },
        { id: "invalid", maturity_date: "not-a-date" },
    ];
    assert.deepEqual(
        sandbox.applyRangeFilters(input).map((b) => b.id),
        ["at-from", "inside", "at-to"],
    );
});

test("Bond Analysis - open-ended ranges constrain only the given side", () => {
    withRangeFilters(sandbox, "government", { couponMin: 7 });
    assert.equal(
        sandbox.applyRangeFilters([{ coupon_rate: 7 }, { coupon_rate: 19 }, { coupon_rate: 6.9 }]).length,
        2,
    );

    withRangeFilters(sandbox, "government", { couponMax: 7 });
    assert.equal(
        sandbox.applyRangeFilters([{ coupon_rate: 7 }, { coupon_rate: 19 }, { coupon_rate: 6.9 }]).length,
        2,
    );

    withRangeFilters(sandbox, "government", { maturityFrom: "2030-01-01" });
    assert.equal(
        sandbox.applyRangeFilters([
            { maturity_date: "2029-01-01" },
            { maturity_date: "2040-01-01" },
        ]).length,
        1,
    );

    withRangeFilters(sandbox, "government", { maturityTo: "2030-01-01" });
    assert.equal(
        sandbox.applyRangeFilters([
            { maturity_date: "2029-01-01" },
            { maturity_date: "2040-01-01" },
        ]).length,
        1,
    );
});

test("Bond Analysis - combined filters are ANDed", () => {
    withRangeFilters(sandbox, "corporate", {
        couponMin: 8,
        couponMax: 10,
        yieldMin: 8,
        yieldMax: 9,
        maturityFrom: "2030-01-01",
        maturityTo: "2032-12-31",
    });
    const input = [
        { id: "all-match", coupon_rate: 9, weighted_average_yield: 8.5, maturity_date: "2031-05-05" },
        { id: "coupon-fail", coupon_rate: 7, weighted_average_yield: 8.5, maturity_date: "2031-05-05" },
        { id: "yield-fail", coupon_rate: 9, weighted_average_yield: 11, maturity_date: "2031-05-05" },
        { id: "maturity-fail", coupon_rate: 9, weighted_average_yield: 8.5, maturity_date: "2039-05-05" },
    ];
    assert.deepEqual(sandbox.applyRangeFilters(input).map((b) => b.id), ["all-match"]);
});

