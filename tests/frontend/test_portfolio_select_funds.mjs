import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const jsSource = await readFile("frontend/js/features/portfolio-select-funds/index.js", "utf8");
const htmlSource = await readFile("frontend/html/portfolio-select-funds.html", "utf8");
const cssSource = await readFile("frontend/css/features/portfolio-select-funds.css", "utf8");

test("Portfolio Select Funds - Filter controls exist in HTML", () => {
    assert.match(htmlSource, /id="pfs-fund-age-filter"/);
    assert.match(htmlSource, /id="pfs-fund-status-filter"/);
    assert.match(htmlSource, /Fund age filter/);
    assert.match(htmlSource, /Fund status filter/);
    assert.match(htmlSource, /Any age/);
    assert.match(htmlSource, /1\+ years/);
    assert.match(htmlSource, /3\+ years/);
    assert.match(htmlSource, /5\+ years/);
    assert.match(htmlSource, /10\+ years/);
    assert.match(htmlSource, /All/);
    assert.match(htmlSource, /Active/);
    assert.match(htmlSource, /Inactive/);
});

test("Portfolio Select Funds - Filter state variables exist in JS", () => {
    assert.match(jsSource, /fundAge\s*:/);
    assert.match(jsSource, /fundStatus\s*:/);
    assert.match(jsSource, /state\.fundAge/);
    assert.match(jsSource, /state\.fundStatus/);
});

test("Portfolio Select Funds - Filter event listeners exist in JS", () => {
    assert.match(jsSource, /pfs-fund-age-filter/);
    assert.match(jsSource, /pfs-fund-status-filter/);
    assert.match(jsSource, /addEventListener.*change/);
    assert.match(jsSource, /renderResults/);
});

test("Portfolio Select Funds - Search request includes limit parameter", () => {
    assert.match(jsSource, /params\.append\(['"]limit['"]\s*,\s*['"]5000['"]\)/);
});

test("Portfolio Select Funds - Filter logic in renderResults", () => {
    assert.match(jsSource, /filteredResults.*state\.results\.filter/);
    assert.match(jsSource, /state\.fundAge\s*!==\s*['"]any['"]/);
    assert.match(jsSource, /state\.fundStatus\s*!==\s*['"]all['"]/);
    assert.match(jsSource, /fund\.first_nav_date/);
    assert.match(jsSource, /fund\.is_active/);
    assert.match(jsSource, /ageInYears/);
    assert.match(jsSource, /!fund\.is_active/);
});

test("Portfolio Select Funds - Result metadata displays age and status", () => {
    assert.match(jsSource, /first_nav_date/);
    assert.match(jsSource, /is_active/);
    assert.match(jsSource, /Since/);
    assert.match(jsSource, /Active/);
    assert.match(jsSource, /Inactive/);
    assert.match(jsSource, /pfs-fund-meta-item/);
});

test("Portfolio Select Funds - CSS styles for filter dropdowns", () => {
    assert.match(cssSource, /pfs-filter-select/);
    assert.match(cssSource, /margin-left: 12px/);
    assert.match(cssSource, /padding: 8px 12px/);
    assert.match(cssSource, /border: 1px solid var\(--color-border\)/);
    assert.match(cssSource, /border-radius: var\(--radius-md\)/);
    assert.match(cssSource, /background: var\(--color-surface\)/);
    assert.match(cssSource, /color: var\(--color-text\)/);
    assert.match(cssSource, /font-size: 0\.875rem/);
    assert.match(cssSource, /cursor: pointer/);
    assert.match(cssSource, /transition: border-color 0\.2s ease/);
});

test("Portfolio Select Funds - Search status shows total count when truncated", () => {
    assert.match(jsSource, /data\\.total\\s*!={1,2}\\s*undefined/);
    assert.match(jsSource, /status\.textContent\s*\=\s*['"]Showing\s+/);
});

test("Portfolio Select Funds - No API request per fund for filters", () => {
    // Ensure there's no loop over results making individual API calls
    assert.doesNotMatch(jsSource, /for\s*\([^)]*\)\s*{\s*[^}]*api\.get/);
    assert.doesNotMatch(jsSource, /\/\*[^*]*\*\/.*api\.get.*\*\//);
});

test("Portfolio Select Funds - Filter changes trigger re-render without new API request", () => {
    assert.match(jsSource, /state\.fundAge\s*=/);
    assert.match(jsSource, /state\.fundStatus\s*=/);
    assert.match(jsSource, /renderResults/);
    // Filter changes should call renderResults, not performSearch
    assert.doesNotMatch(jsSource, /fundAge.*=.*performSearch/);
    assert.doesNotMatch(jsSource, /fundStatus.*=.*performSearch/);
});
