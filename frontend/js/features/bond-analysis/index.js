// Bond Analysis — production UI slice.
// Wires the page to the EXISTING bond APIs (no new backend, no client-side
// financial computation):
//   GET /api/bonds                       — list/search government bonds
//   GET /api/bonds/record/{record_id}    — government bond with no ISIN
//   GET /api/bonds/corporate             — list/search corporate bonds (CDSL)
//   GET /api/bonds/{isin}                — government bond by ISIN
//   GET /api/bonds/{isin}/market         — market observation
//   GET /api/bonds/{isin}/analytics      — computed analytics
//   GET /api/bonds/corporate/{isin}      — corporate bond by ISIN
//
// EVERY listed bond is selectable. Identity priority is ISIN first, then the
// backend's own source-scoped `record_id` for records that publish no ISIN
// (CCIL market-watch rows). No identifier is ever fabricated in the browser
// and no bond is disabled merely because it has no ISIN.
//
// Government and Corporate are SEPARATE lazy-loaded universes: only the
// active universe is ever requested, never both together.
//
// All financial values are rendered exactly as returned by the backend.
// Market YTM comes from the source/market observation; Calculated YTM comes
// from analytics. They are never substituted for one another.

import { api } from "../../core/api.js";
import { utils } from "../../core/utils.js";

const $ = (id) => document.getElementById(id);

const PAGE_SIZE = 12; // bonds per selector page (12–15 per spec)

const state = {
    searchSeq: 0,       // guards against out-of-order search responses
    loadSeq: 0,         // guards against out-of-order bond loads
    // Identity of the bond shown in the detail column: "isin:<ISIN>" or
    // "record:<record_id>" (source records that publish no ISIN). Never a
    // fabricated ISIN.
    selectedKey: null,
    universe: "government", // active universe: "government" | "corporate"
    universes: {            // per-universe pagination state (lazy-loaded)
        government: { page: 1, total: 0, visited: true },
        corporate:  { page: 1, total: 0, visited: false },
    },
    page: 1,            // 1-based selector page (ACTIVE universe)
    total: 0,           // total bonds matching the current query (ACTIVE universe)
    sortBy: "maturity_date",
    sortDir: "asc",
    // Range filter values (client-side). Defaults match the HTML slider ranges.
    rangeFilters: {
        couponMin: 0,     // percent
        couponMax: 20,    // percent
        yieldMin: 0,      // percent (corporate only — weighted_average_yield)
        yieldMax: 20,     // percent (corporate only — weighted_average_yield)
        maturityFrom: "", // ISO date string or empty
        maturityTo: "",   // ISO date string or empty
    },
    // Credit-rating selections (corporate-only, applied client-side).
    // Stored as an array of canonical rating keys; empty means no restriction.
    creditRatings: [],
};

// ---------------------------------------------------------------------------
// Formatting helpers (application conventions)
// ---------------------------------------------------------------------------

function escapeHtml(s) {
    if (s == null) return "";
    return String(s)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
}

function escapeAttr(s) {
    if (s == null) return "";
    return String(s).replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;");
}

function na(v) {
    return v === null || v === undefined || v === "" ? "N/A" : v;
}

function formatPct(value, decimals = 2) {
    if (value === null || value === undefined || !Number.isFinite(Number(value))) return "N/A";
    return `${Number(value).toFixed(decimals)}%`;
}

function formatNum(value, decimals = 2) {
    if (value === null || value === undefined || !Number.isFinite(Number(value))) return "N/A";
    return Number(value).toFixed(decimals);
}

// Application date convention: DD MMM YYYY (e.g. 11 May 2033).
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

function formatDate(value) {
    if (value === null || value === undefined || value === "") return "N/A";
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return String(value);
    return `${String(d.getDate()).padStart(2, "0")} ${MONTHS[d.getMonth()]} ${d.getFullYear()}`;
}

function couponFrequencyLabel(freq) {
    if (freq === null || freq === undefined) return "N/A";
    const map = { 1: "Annual", 2: "Semi-annual", 4: "Quarterly", 12: "Monthly" };
    return map[Number(freq)] || `${freq}/year`;
}

// ---------------------------------------------------------------------------
// Bond identity & endpoint selection
// ---------------------------------------------------------------------------
// Identity priority (never a fabricated identifier):
//   1. ISIN when the record publishes one
//   2. the backend's own source-scoped `record_id` otherwise
// The record_id comes straight from the API payload (the Bond model attaches
// it); the browser never derives or invents one.

function bondIdentity(bond) {
    const isin = bond && bond.isin ? String(bond.isin).trim() : "";
    const recordId = bond && bond.record_id ? String(bond.record_id).trim() : "";
    if (isin) return { kind: "isin", isin: isin, recordId: recordId };
    if (recordId) return { kind: "record", isin: "", recordId: recordId };
    return { kind: "none", isin: "", recordId: "" };
}

// Stable selection key for a bond record ("isin:…" / "record:…").
function bondSelectionKey(bond) {
    const identity = bondIdentity(bond);
    if (identity.kind === "isin") return "isin:" + identity.isin;
    if (identity.kind === "record") return "record:" + identity.recordId;
    return "";
}

// Endpoint plan mapping one identity onto the EXISTING API routes. Pure: it
// declares which existing endpoints a detail load needs and never invents an
// identifier. `analytics` is null when the analytics endpoints cannot serve
// the record (they are ISIN-based).
function bondDetailPlan(identity, universe, tradeDate) {
    const isCorporate = universe === "corporate";
    const kind = identity && identity.kind ? identity.kind : "none";
    const isin = identity && identity.isin ? identity.isin : "";
    const recordId = identity && identity.recordId ? identity.recordId : "";
    const dateQuery = isCorporate && tradeDate
        ? "?trade_date=" + encodeURIComponent(tradeDate)
        : "";

    if (kind === "isin") {
        const encoded = encodeURIComponent(isin);
        if (isCorporate) {
            return {
                key: "isin:" + isin,
                kind: "isin",
                label: "ISIN",
                detail: "/bonds/corporate/" + encoded + dateQuery,
                market: null,
                analytics: "/bonds/corporate/" + encoded + "/analytics" + dateQuery,
            };
        }
        return {
            key: "isin:" + isin,
            kind: "isin",
            label: "ISIN",
            detail: "/bonds/" + encoded,
            market: "/bonds/" + encoded + "/market",
            analytics: "/bonds/" + encoded + "/analytics",
        };
    }

    if (kind === "record") {
        return {
            key: "record:" + recordId,
            kind: "record",
            label: "Record ID",
            detail: "/bonds/record/" + encodeURIComponent(recordId),
            market: null,
            analytics: null,
        };
    }

    return null;
}

// Market indicator for a list row — backend-provided fields only
// (data_type / freshness_days). Returns null when there is nothing to show.
function bondMarketFlag(bond) {
    const dt = String((bond && bond.data_type) || "").toLowerCase();
    if (dt === "traded") return { label: "Traded", className: "is-traded" };
    if (dt === "indicative") return { label: "Indicative", className: "is-indicative" };
    const fresh = bond ? bond.freshness_days : null;
    if (typeof fresh === "number" && fresh > 7) {
        return { label: "Stale " + fresh + "d", className: "is-stale" };
    }
    return null;
}

// One selectable bond row. Pure (no DOM access) so the identity resolution,
// endpoint-agnostic rendering and the "no ISIN → Record ID" labelling are
// directly testable.
//
// Layout: name / identity (ISIN or Record ID) / instrument · issuer · maturity
//         with the headline yield and market flag on the right.
function renderBondListRow(bond, selectedKey, isCorporate) {
    const identity = bondIdentity(bond);
    const key = bondSelectionKey(bond);
    const name = (bond && bond.security_name) || identity.isin || identity.recordId || "Unnamed security";

    // Government rows keep using the market YTM exactly as before; corporate
    // (CDSL) rows may fall back to the weighted-average yield.
    const ytmValue = bond && bond.ytm != null
        ? bond.ytm
        : (isCorporate && bond && bond.weighted_average_yield != null ? bond.weighted_average_yield : null);
    const ytm = ytmValue != null ? formatPct(ytmValue) : "N/A";
    const flag = bondMarketFlag(bond);

    const identityHtml = identity.kind === "record"
        ? '<span class="ba-bond-id-label">Record ID</span><span class="ba-bond-meta-isin ba-bond-meta-record">' + escapeHtml(identity.recordId) + "</span>"
        : (identity.kind === "isin"
            ? '<span class="ba-bond-id-label">ISIN</span><span class="ba-bond-meta-isin">' + escapeHtml(identity.isin) + "</span>"
            : '<span class="ba-bond-id-label">No identifier</span>');

    const meta = [
        bond && bond.instrument_type ? escapeHtml(bond.instrument_type) : "",
        bond && bond.credit_rating ? '<span class="ba-bond-rating">' + escapeHtml(bond.credit_rating) + "</span>" : "",
        bond && bond.issuer ? escapeHtml(bond.issuer) : "",
        bond && bond.maturity_date ? "Matures " + escapeHtml(formatDate(bond.maturity_date)) : "",
    ].filter(Boolean).join('<span class="ba-bond-meta-sep" aria-hidden="true">&middot;</span>');

    const inner = '<span class="ba-bond-info">'
        + '<span class="ba-bond-name">' + escapeHtml(name) + "</span>"
        + '<span class="ba-bond-identity">' + identityHtml + "</span>"
        + '<span class="ba-bond-meta">' + meta + "</span>"
        + "</span>"
        + '<span class="ba-bond-quote">'
        + '<span class="ba-bond-yield">' + escapeHtml(ytm) + "</span>"
        + '<span class="ba-bond-yield-caption">YTM</span>'
        + (flag ? '<span class="ba-bond-flag ' + flag.className + '">' + escapeHtml(flag.label) + "</span>" : "")
        + "</span>";

    if (!key) {
        // Neither ISIN nor record_id was published, so there is genuinely no
        // endpoint that can load this record — the only case where a row is
        // rendered inert. No identifier is fabricated to make it clickable.
        return '<li class="ba-bond-row"><div class="ba-bond-item ba-bond-item-inert" aria-disabled="true"'
            + ' title="No identifier published for this record">' + inner + "</div></li>";
    }

    const selected = key === selectedKey;
    return '<li class="ba-bond-row">'
        + '<button type="button" class="ba-bond-item' + (selected ? " selected" : "") + '"'
        + ' data-isin="' + escapeAttr(identity.isin) + '"'
        + ' data-record-id="' + escapeAttr(identity.recordId) + '"'
        + ' aria-pressed="' + (selected ? "true" : "false") + '"'
        + ' title="' + escapeAttr("View details for " + name) + '">'
        + inner
        + '<span class="ba-bond-check" aria-hidden="true">'
        + '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>'
        + "</span>"
        + "</button></li>";
}

// Selection key carried by a rendered row button (same vocabulary as
// bondSelectionKey, read back from the DOM).
function elementSelectionKey(el) {
    const isin = el && el.dataset && el.dataset.isin ? el.dataset.isin : "";
    const recordId = el && el.dataset && el.dataset.recordId ? el.dataset.recordId : "";
    if (isin) return "isin:" + isin;
    if (recordId) return "record:" + recordId;
    return "";
}

// Reflect the selection on the already-rendered rows (no re-fetch, no
// re-render of the list): used on click so the selected state is immediate.
function markSelectedRow(key) {
    document.querySelectorAll(".ba-bond-item").forEach((el) => {
        const selected = Boolean(key) && elementSelectionKey(el) === key;
        el.classList.toggle("selected", selected);
        if (el.tagName === "BUTTON") el.setAttribute("aria-pressed", String(selected));
    });
}

// ---------------------------------------------------------------------------
// Bond search
// ---------------------------------------------------------------------------

// Corporate filter values (Trade Date | Issuer) — the corporate-only controls.
// Both map to supported GET /api/bonds/corporate parameters and are never sent
// to the government endpoint.
function readCorporateFilters() {
    const tradeDate = $("ba-corporate-trade-date");
    const issuer = $("ba-corporate-issuer");
    return {
        tradeDate: tradeDate ? tradeDate.value.trim() : "",
        issuer: issuer ? issuer.value.trim() : "",
        };
}

// Normalise a bond's credit_rating value into a canonical key that matches the
// CREDIT_RATING_OPTIONS vocabulary. null / undefined / empty / NA-like
// sentinels ("-", "--", "NA", "N/A") map to "Unknown" (rating unavailable —
// distinct from an explicit "Unrated"); the CDSL normalizer already collapses
// most of those sentinels to null, so this also covers them defensively.
// A literal "Unrated" string maps to "Unrated". Standard rating notation
// (AAA, AA+, A-, etc.) passes through upper-cased.
function getBondRatingKey(rating) {
    if (rating == null) return "Unknown";
    const s = String(rating).trim().toUpperCase();
    if (s === "" || s === "-" || s === "--" || s === "NA" || s === "N/A" || s === "UNKNOWN") return "Unknown";
    if (s === "UNRATED") return "Unrated";
    // Standard rating notation (AAA, AA+, A-, etc.) — pass through upper-cased.
    return s;
}

// True when the corporate credit-rating filter has at least one selection.
// Government bonds (T-Bills, G-Secs, SDLs) never carry a corporate rating, so
// the filter is a no-op outside the corporate universe.
function hasActiveCreditRatingFilter() {
    return state.universe === "corporate" && state.creditRatings.length > 0;
}

// Apply the client-side credit-rating filter (OR logic across selected
// ratings). A bond matches when its canonical rating key is one of the
// selected keys. Called as a post-step on the already range-filtered list so
// it composes cleanly with coupon / yield / maturity narrowing without adding
// any server requests. No active selection returns the list untouched.
function applyCreditRatingFilter(bonds) {
    if (!hasActiveCreditRatingFilter()) return bonds;
    const selected = new Set(state.creditRatings);
    return bonds.filter((bond) => selected.has(getBondRatingKey(bond.credit_rating)));
}


// Range filter slider bounds — must match the min/max attributes in the HTML.
const RANGE_MIN = 0;
const RANGE_MAX = 20;

// Credit rating options offered by the Advanced Bond Filters multi-select.
// Mirrors the back-end rating vocabulary (CDSL / Bond Central). The list is
// rendered once and filtered client-side by `credit_rating` on each bond
// record — no per-bond API calls are made. "Unknown" is the value stored for
// missing ratings and is displayed as "Rating unavailable".
const CREDIT_RATING_OPTIONS = [
    "AAA", "AA+", "AA", "AA-", "A+", "A", "A-",
    "BBB+", "BBB", "BBB-",
    "BB+", "BB", "BB-",
    "B+", "B", "B-", "C", "D",
    "Unrated", "Unknown",
];

// Display label for a rating option value. "Unknown" surfaces as
// "Rating unavailable"; every other value renders as itself.
function creditRatingLabel(rating) {
    return rating === "Unknown" ? "Rating unavailable" : rating;
}


// Read range filter values from the HTML controls. Values at the slider
// extremes mean "no bound on that side", matching the "Any" output labels.
function readRangeFilters() {
    const couponMinEl = $("ba-coupon-min");
    const couponMaxEl = $("ba-coupon-max");
    const yieldMinEl = $("ba-yield-min");
    const yieldMaxEl = $("ba-yield-max");
    const maturityFromEl = $("ba-maturity-from");
    const maturityToEl = $("ba-maturity-to");

    return {
        couponMin: couponMinEl ? parseFloat(couponMinEl.value) : RANGE_MIN,
        couponMax: couponMaxEl ? parseFloat(couponMaxEl.value) : RANGE_MAX,
        yieldMin: yieldMinEl ? parseFloat(yieldMinEl.value) : RANGE_MIN,
        yieldMax: yieldMaxEl ? parseFloat(yieldMaxEl.value) : RANGE_MAX,
        maturityFrom: maturityFromEl ? maturityFromEl.value : "",
        maturityTo: maturityToEl ? maturityToEl.value : "",
    };
}

// Check whether a range filter that APPLIES to the active universe is set.
// Coupon and maturity apply to both universes; yield applies to corporate only
// (so a pending corporate yield range never forces a full-universe download
// while the government universe is active).
function hasActiveRangeFilters() {
    const f = state.rangeFilters;
    if (f.couponMin !== RANGE_MIN || f.couponMax !== RANGE_MAX) return true;
    if (f.maturityFrom !== "" || f.maturityTo !== "") return true;
    if (state.universe === "corporate" &&
        (f.yieldMin !== RANGE_MIN || f.yieldMax !== RANGE_MAX)) return true;
    return false;
}

// Apply client-side range filtering to a list of bonds.
//
// The backend list endpoints (GET /api/bonds, GET /api/bonds/corporate) expose
// no range query parameters, so coupon / yield / maturity narrowing happens
// here, using only backend-provided field values:
//   coupon_rate              — both universes
//   ytm                      — government market YTM
//   weighted_average_yield   — corporate (CDSL) weighted average yield
//   maturity_date            — both universes
// A bound sitting at the slider extreme is treated as unbounded, so the
// default 0–20 positions never exclude bonds outside that numeric window.
function applyRangeFilters(bonds) {
    const f = state.rangeFilters;
    const isCorporate = state.universe === "corporate";

    // A bound at the slider extreme means "no bound on that side".
    const couponMin = f.couponMin > RANGE_MIN ? f.couponMin : null;
    const couponMax = f.couponMax < RANGE_MAX ? f.couponMax : null;
    const yieldMin = f.yieldMin > RANGE_MIN ? f.yieldMin : null;
    const yieldMax = f.yieldMax < RANGE_MAX ? f.yieldMax : null;
    const fromMs = f.maturityFrom ? new Date(f.maturityFrom).getTime() : null;
    const toMs = f.maturityTo ? new Date(f.maturityTo).getTime() : null;

    const couponConstrained = couponMin !== null || couponMax !== null;
    // The Weighted Average Yield control exists in the corporate universe only
    // (HTML: #ba-yield-range-group.ba-corporate-range-only), so a yield range
    // never narrows government results.
    const yieldConstrained = isCorporate && (yieldMin !== null || yieldMax !== null);
    const maturityConstrained = fromMs !== null || toMs !== null;

    return bonds.filter((bond) => {
        // Coupon rate — both universes.
        if (couponConstrained) {
            const coupon = toFiniteNumber(bond.coupon_rate);
            // A constrained field with no usable value cannot be verified, so
            // the record is excluded rather than assumed to be in range.
            if (coupon === null) return false;
            if (couponMin !== null && coupon < couponMin) return false;
            if (couponMax !== null && coupon > couponMax) return false;
        }

        // Yield — corporate uses the CDSL Weighted Average Yield (the backend
        // also mirrors that value into `ytm` for CDSL secondary rows, so the
        // fallback is the same figure); government uses the source market YTM.
        // The two universes are never substituted for one another.
        if (yieldConstrained) {
            const rawYield = isCorporate
                ? (bond.weighted_average_yield != null ? bond.weighted_average_yield : bond.ytm)
                : bond.ytm;
            const yieldValue = toFiniteNumber(rawYield);
            if (yieldValue === null) return false;
            if (yieldMin !== null && yieldValue < yieldMin) return false;
            if (yieldMax !== null && yieldValue > yieldMax) return false;
        }

        // Maturity date — both universes.
        if (maturityConstrained) {
            const maturityMs = toTimeMs(bond.maturity_date);
            if (maturityMs === null) return false;
            if (fromMs !== null && maturityMs < fromMs) return false;
            if (toMs !== null && maturityMs > toMs) return false;
        }

        return true;
    });
}

// The Weighted Average Yield group is corporate-only: the government bond
// payload carries a market YTM, not a weighted average yield.
function syncYieldControlsVisibility() {
    const yieldGroup = $("ba-yield-range-group");
    if (yieldGroup) yieldGroup.hidden = state.universe !== "corporate";
}

// Restore the range controls to their documented defaults — coupon 0–20,
// yield 0–20, blank maturity dates — and refresh the min/max output labels
// above each slider (the existing setupRangeOutputs listeners).
function setRangeControlsToDefaults() {
    [
        ["ba-coupon-min", RANGE_MIN],
        ["ba-coupon-max", RANGE_MAX],
        ["ba-yield-min", RANGE_MIN],
        ["ba-yield-max", RANGE_MAX],
    ].forEach(([id, value]) => {
        const el = $(id);
        if (!el) return;
        el.value = String(value);
        el.dispatchEvent(new Event("input", { bubbles: true }));
    });

    const from = $("ba-maturity-from");
    if (from) from.value = "";
    const to = $("ba-maturity-to");
    if (to) to.value = "";
}

// --- Safe field coercion -------------------------------------------------
// Backend list payloads are Bond records: coupon_rate / ytm /
// weighted_average_yield are numbers-or-null, maturity_date is an ISO date
// string-or-null. These helpers still accept string values defensively and
// return null for anything missing, empty or unparseable, so a constrained
// filter never silently includes an unverifiable record.

function toFiniteNumber(value) {
    if (value === null || value === undefined || value === "") return null;
    const n = typeof value === "number" ? value : Number(String(value).trim());
    return Number.isFinite(n) ? n : null;
}

function toTimeMs(value) {
    if (value === null || value === undefined || value === "") return null;
    const t = new Date(value).getTime();
    return Number.isFinite(t) ? t : null;
}

// --- Full-universe retrieval ---------------------------------------------
// The documented backend maximum for the list `limit` parameter is 200
// (ge=1, le=200 on both GET /api/bonds and GET /api/bonds/corporate).

const MAX_PAGE_SIZE = 200;

// Download EVERY bond matching the server-side filters by paging at the
// documented maximum size until the result set is exhausted. The server's
// search / instrument_type / source / issuer / trade_date / sort parameters
// are all applied by the backend before anything reaches the browser.
async function fetchAllBonds(path, baseParams) {
    const bonds = [];
    let offset = 0;

    for (;;) {
        const params = new URLSearchParams(baseParams);
        params.set("limit", String(MAX_PAGE_SIZE));
        params.set("offset", String(offset));
        params.set("envelope", "true");

        const data = await api.get(`${path}?${params.toString()}`);
        const items = Array.isArray(data)
            ? data
            : (data && Array.isArray(data.items) ? data.items : []);
        const total = Array.isArray(data)
            ? items.length
            : (data && typeof data.total === "number" ? data.total : items.length);

        bonds.push(...items);
        offset += items.length;

        // Stop on an empty page, a short page (last page), or once the
        // reported total has been reached.
        if (items.length === 0 || items.length < MAX_PAGE_SIZE || bonds.length >= total) break;
    }

    return bonds;
}

// Cache of full server-filtered result sets keyed by filter signature, so
// range filtering and local pagination never re-download the universe. A
// request already in flight for the same signature is shared with any
// concurrent caller instead of being issued a second time. Keying by
// signature (rather than a single slot) means a slower earlier response can
// never overwrite the data for the filters currently on screen.
const UNIVERSE_CACHE_LIMIT = 8;
const universeCache = new Map();      // signature -> Bond[]
const universeInflight = new Map();   // signature -> Promise<Bond[]>

function buildFilterSignature(isCorporate, q, type, source, corp) {
    return JSON.stringify([
        isCorporate ? "corporate" : "government",
        q || "",
        type || "",
        source || "",
        corp.tradeDate || "",
        corp.issuer || "",
        state.sortBy || "",
        state.sortDir || "",
    ]);
}

async function getUniverseBonds(signature, path, baseParams) {
    if (universeCache.has(signature)) return universeCache.get(signature);
    if (universeInflight.has(signature)) return universeInflight.get(signature);

    const request = fetchAllBonds(path, baseParams)
        .then((bonds) => {
            universeCache.set(signature, bonds);
            // Bound the cache so repeated filter edits cannot grow it forever.
            while (universeCache.size > UNIVERSE_CACHE_LIMIT) {
                const oldest = universeCache.keys().next().value;
                universeCache.delete(oldest);
            }
            return bonds;
        })
        .finally(() => {
            universeInflight.delete(signature);
        });

    universeInflight.set(signature, request);
    return request;
}

async function searchBonds() {
    const seq = ++state.searchSeq;
    const q = $("ba-search-input").value.trim();
    const isCorporate = state.universe === "corporate";
    const type = isCorporate ? "" : $("ba-type-filter").value;
    // The data-source selector (All Sources | CCIL | NSE | RBI) is a
    // government-only control: "All Sources" (empty value) adds no parameter,
    // and the corporate universe never sends one.
    const sourceFilter = $("ba-source-filter");
    const source = isCorporate || !sourceFilter ? "" : sourceFilter.value;

    // Coupon / yield / maturity ranges AND the corporate credit-rating filter
    // are applied client-side: neither list endpoint accepts range or rating
    // query parameters, so the full server-filtered result set is downloaded
    // (paged at the documented maximum) and narrowed in the browser. With no
    // active local filter the original server-side pagination path is used
    // unchanged. The credit-rating filter is corporate-only and is never sent
    // to the backend (it reads bond.credit_rating from the loaded records).
    const rangeActive = hasActiveRangeFilters() || hasActiveCreditRatingFilter();

    // Server-side filters + sorting (backend-provided parameters only).
    const corpFilters = isCorporate ? readCorporateFilters() : { tradeDate: "", issuer: "" };
    const serverParams = new URLSearchParams();
    if (q) serverParams.set("search", q);
    if (type) serverParams.set("instrument_type", type);
    if (source) serverParams.set("source", source);
    if (isCorporate) {
        // The corporate universe is a separate CDSL endpoint: it accepts only
        // trade_date and issuer (plus search/sorting/pagination) and never the
        // government instrument_type/source filters.
        if (corpFilters.tradeDate) serverParams.set("trade_date", corpFilters.tradeDate);
        if (corpFilters.issuer) serverParams.set("issuer", corpFilters.issuer);
    }
    serverParams.set("sort_by", state.sortBy);
    serverParams.set("sort_dir", state.sortDir);

    const path = isCorporate ? "/bonds/corporate" : "/bonds";

    setSelectorStatus('<span class="pb-analysis-loading"><span class="pb-spinner" aria-hidden="true"></span><span>Searching bonds&hellip;</span></span>');
    $("ba-no-results").classList.add("hidden");
    setListLoading(true);

    let data;
    let universe = null;
    try {
        if (rangeActive) {
            // Range filtering needs the whole matching universe; the cache
            // prevents re-downloading it on every page change.
            const signature = buildFilterSignature(isCorporate, q, type, source, corpFilters);
            universe = await getUniverseBonds(signature, path, serverParams);
        } else {
            const pageParams = new URLSearchParams(serverParams);
            pageParams.set("limit", String(PAGE_SIZE));
            pageParams.set("offset", String((state.page - 1) * PAGE_SIZE));
            pageParams.set("envelope", "true");
            data = await api.get(`${path}?${pageParams.toString()}`);
        }
    } catch (err) {
        if (seq !== state.searchSeq) return;
        setSelectorStatus("");
        setListLoading(false);
        $("ba-no-results").classList.add("hidden");
        $("ba-bond-list").innerHTML = "";
        renderPagination(0);
        $("ba-range-chip").textContent = "";
        $("ba-result-count").textContent = "";
        showError(`Could not load bonds: ${err && err.message ? err.message : err}`);
        return;
    }

    if (seq !== state.searchSeq) return; // a newer search superseded this one
    setSelectorStatus("");
    setListLoading(false);
    hideError();

    // The server returns {items, total, limit, offset}; a plain array is also
    // accepted defensively, though the page always requests the envelope.
    //
    // With range filters active the cached full universe is narrowed locally
    // and paginated locally, and `total` reflects the FILTERED result set.
    // Otherwise the server already returned the requested page and its total.
    let list;
    if (rangeActive) {
        // Range filters narrow the cached full universe first, then the
        // corporate credit-rating filter (OR logic) applies client-side on
        // the result — no extra API requests are issued for ratings.
        const filtered = applyCreditRatingFilter(applyRangeFilters(universe || []));
        state.total = filtered.length;
        list = filtered.slice((state.page - 1) * PAGE_SIZE, state.page * PAGE_SIZE);
    } else {
        const fetched = Array.isArray(data) ? data : (data && Array.isArray(data.items) ? data.items : []);
        state.total = Array.isArray(data)
            ? fetched.length
            : (data && typeof data.total === "number" ? data.total : fetched.length);
        list = fetched;
    }

    // Header chip — the current page's slice of the result set, not always
    // the first page. Recomputed on every search so it stays in sync with
    // range filters, pagination, universe switches and server-side filters.
    if (state.total > 0) {
        const start = (state.page - 1) * PAGE_SIZE + 1;
        const end = Math.min(state.page * PAGE_SIZE, state.total);
        $("ba-range-chip").textContent = `Showing ${start}–${end} of ${state.total}`;
    } else {
        $("ba-range-chip").textContent = "";
    }
    $("ba-result-count").textContent = state.total
        ? `${state.total} bond${state.total === 1 ? "" : "s"}`
        : "";

    $("ba-no-results").classList.toggle("hidden", list.length > 0);

    // Zero bonds (e.g. after a trade-date/filter change): the previous
    // selection no longer matches this dataset. Clear it and hide the
    // detail panels so a stale bond does not stay visible next to the
    // "No bonds found" state.
    if (list.length === 0) {
        state.selectedKey = null;
        resetDetailPanel();
    }

    // EVERY row is selectable. Identity is the ISIN when the record
    // publishes one and the backend's own record_id otherwise (CCIL
    // market-watch rows) — see bondDetailPlan. A missing ISIN never
    // disables a bond.
    $("ba-bond-list").innerHTML = list.map(
        (b) => renderBondListRow(b, state.selectedKey, isCorporate)
    ).join("");

    renderPagination(state.total);
}

function setSelectorStatus(html) {
    const el = $("ba-selector-status");
    if (!el) return;
    el.innerHTML = html;
    el.classList.toggle("hidden", !html);
}

// Loading state for the selector list: the current rows stay visible (dimmed)
// while a new page/universe is in flight, and the busy state is exposed to
// assistive technology.
function setListLoading(loading) {
    const list = $("ba-bond-list");
    if (list) {
        list.classList.toggle("is-loading", Boolean(loading));
        list.setAttribute("aria-busy", loading ? "true" : "false");
    }
    const pagination = $("ba-pagination");
    if (pagination) pagination.classList.toggle("is-loading", Boolean(loading));
}

function showError(message) {
    const el = $("ba-error");
    if (!el) return;
    el.textContent = message;
    el.classList.remove("hidden");
}

function hideError() {
    const el = $("ba-error");
    if (el) el.classList.add("hidden");
}

// ---------------------------------------------------------------------------
// Universe switching — Government and Corporate are separate lazy-loaded
// datasets. Only the ACTIVE universe is ever requested; the inactive one is
// never fetched in the background.
// ---------------------------------------------------------------------------

function updateUniverseControls() {
    const isCorporate = state.universe === "corporate";
    const govBtn = $("ba-universe-government");
    const corpBtn = $("ba-universe-corporate");
    if (govBtn) {
        govBtn.classList.toggle("is-active", !isCorporate);
        govBtn.setAttribute("aria-pressed", String(!isCorporate));
    }
    if (corpBtn) {
        corpBtn.classList.toggle("is-active", isCorporate);
        corpBtn.setAttribute("aria-pressed", String(isCorporate));
    }
    // The instrument-type selector (All | G-Sec | SDL | T-Bill) is a
    // government-only control; corporate shows its own filter area instead.
    const govFilter = $("ba-type-filter");
    if (govFilter) govFilter.classList.toggle("hidden", isCorporate);
    // The corporate filter area (Trade Date | Issuer) is the corporate-only
    // counterpart of the controls above.
    const corpFilters = $("ba-corporate-filters");
    if (corpFilters) corpFilters.classList.toggle("hidden", !isCorporate);
    // The data-source selector (All Sources | CCIL | NSE | RBI) is likewise a
    // government-only control.
    const sourceFilter = $("ba-source-filter");
    if (sourceFilter) sourceFilter.classList.toggle("hidden", isCorporate);
    // The Weighted Average Yield range group is corporate-only.
    syncYieldControlsVisibility();
}

function resetDetailPanel() {
    $("ba-results").classList.add("hidden");
    $("ba-detail-empty").classList.remove("hidden");
    $("ba-error").classList.add("hidden");
}

function setUniverse(next) {
    if (!next || next === state.universe || !state.universes[next]) return;

    // Preserve the outgoing universe's pagination state.
    state.universes[state.universe].page = state.page;
    state.universes[state.universe].total = state.total;

    state.universe = next;
    const target = state.universes[next];
    // A universe starts at page 1 on its FIRST visit only; its page is
    // preserved on later visits.
    if (!target.visited) {
        target.page = 1;
        target.visited = true;
    }
    state.page = target.page;
    state.total = target.total;

    // Invalidate any in-flight search/bond load from the previous universe
    // (stale-response protection) and clear the selection, which belonged to
    // the previous universe's dataset.
    state.searchSeq++;
    state.loadSeq++;
    state.selectedKey = null;

    updateUniverseControls();
    resetDetailPanel();
    $("ba-range-chip").textContent = "";
    $("ba-result-count").textContent = "";

    searchBonds();
}

// ---------------------------------------------------------------------------
// Pagination controls (client state only — data pages come from the API)
// ---------------------------------------------------------------------------

// Page-number list with ellipsis windows: 1 … (p-1) p (p+1) … N
function pageNumbers(current, count) {
    if (count <= 7) {
        return Array.from({ length: count }, (_, i) => i + 1);
    }
    const pages = [1];
    const start = Math.max(2, current - 1);
    const end = Math.min(count - 1, current + 1);
    if (start > 2) pages.push("gap");
    for (let p = start; p <= end; p++) pages.push(p);
    if (end < count - 1) pages.push("gap");
    pages.push(count);
    return pages;
}

function renderPagination(total) {
    const el = $("ba-pagination");
    if (!el) return;

    const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));
    state.page = Math.min(Math.max(1, state.page), pageCount);

    if (total <= 0) {
        el.classList.add("hidden");
        el.innerHTML = "";
        return;
    }
    el.classList.remove("hidden");

    const start = (state.page - 1) * PAGE_SIZE + 1;
    const end = Math.min(total, state.page * PAGE_SIZE);
    const atFirst = state.page <= 1;
    const atLast = state.page >= pageCount;

    const buttons = pageNumbers(state.page, pageCount).map((p) => {
        if (p === "gap") return '<span class="ba-page-btn ba-page-gap" aria-hidden="true">&hellip;</span>';
        const active = p === state.page ? " is-active" : "";
        const aria = p === state.page ? ' aria-current="page"' : "";
        return `<button type="button" class="ba-page-btn${active}" data-page="${p}"${aria} aria-label="Page ${p}">${p}</button>`;
    }).join("");

    el.innerHTML = `<span class="ba-page-info">Showing ${start}&ndash;${end} of ${total}</span>`
        + `<button type="button" class="ba-page-btn ba-page-nav" data-page="prev" aria-label="Previous page"${atFirst ? " disabled" : ""}>&lsaquo; Prev</button>`
        + buttons
        + `<button type="button" class="ba-page-btn ba-page-nav" data-page="next" aria-label="Next page"${atLast ? " disabled" : ""}>Next &rsaquo;</button>`;
}

function goToPage(page) {
    const pageCount = Math.max(1, Math.ceil(state.total / PAGE_SIZE));
    const next = Math.min(Math.max(1, page), pageCount);
    if (next === state.page) return;
    state.page = next;
    searchBonds();
}


// ---------------------------------------------------------------------------
// Selected bond load — ISIN records use /{isin} (+/market, /analytics);
// records with no ISIN use the existing /record/{record_id} route; corporate
// records use /bonds/corporate/{isin}. The endpoint choice is made by
// bondDetailPlan() — this function only executes the plan.
// ---------------------------------------------------------------------------

// Section collapse states applied when a bond is selected: Bond Summary and
// Analytics are open (the analytical headline), Cash Flows and Details start
// collapsed.
const DEFAULT_OPEN_SECTIONS = ["summary", "analytics"];

function resetSectionStates() {
    document.querySelectorAll(".ba-section").forEach((section) => {
        const toggle = section.querySelector(".ba-section-toggle");
        const body = section.querySelector(".ba-section-body");
        if (!toggle || !body) return;
        const sectionId = section.getAttribute("data-section");
        const open = DEFAULT_OPEN_SECTIONS.indexOf(sectionId) !== -1;
        toggle.setAttribute("aria-expanded", open ? "true" : "false");
        body.classList.toggle("collapsed", !open);
        body.classList.toggle("expanded", open);
        const chevron = toggle.querySelector(".ba-chevron");
        if (chevron) chevron.style.transform = open ? "rotate(180deg)" : "rotate(0deg)";
    });
}

async function selectBond(bondRef) {
    // Identity comes from the row (ISIN when present, otherwise the
    // backend's record_id). Both are carried by the list payload.
    const identity = bondIdentity({
        isin: bondRef && bondRef.isin ? bondRef.isin : "",
        record_id: bondRef && bondRef.recordId ? bondRef.recordId : "",
    });
    if (identity.kind === "none") return;

    // Corporate detail/analytics default to the current report date; the
    // Trade Date filter pins the same CDSL report the list was filtered by.
    const corpTradeDate = state.universe === "corporate"
        ? readCorporateFilters().tradeDate : "";
    const plan = bondDetailPlan(identity, state.universe, corpTradeDate);
    if (!plan) return;

    const seq = ++state.loadSeq;
    state.selectedKey = plan.key;
    markSelectedRow(plan.key);

    $("ba-detail-empty").classList.add("hidden");
    $("ba-error").classList.add("hidden");
    $("ba-results").classList.remove("hidden");
    $("ba-results").classList.add("is-loading");
    $("ba-summary-name").textContent = "Loading bond…";
    $("ba-summary-meta").innerHTML = "";
    $("ba-summary-hero").innerHTML = "";
    $("ba-summary-grid").innerHTML = "";
    $("ba-kpi-grid").innerHTML = '<div class="pb-analysis-loading"><span class="pb-spinner" aria-hidden="true"></span><span>Loading analytics&hellip;</span></div>';
    $("ba-cashflow-wrap").innerHTML = "";
    $("ba-details-grid").innerHTML = "";
    $("ba-notes").innerHTML = "";
    $("ba-section-header-badge").textContent = "";
    $("ba-section-header-badge2").textContent = "";

    resetSectionStates();

    // Market YTM (source observation) and Calculated YTM (analytics) come
    // from their own endpoints; the frontend never derives one from the other.
    let bond = null;
    let market = null;
    let analytics = null;
    try {
        if (plan.market && plan.analytics) {
            // Government ISIN records: master + market observation + analytics.
            [bond, market, analytics] = await Promise.all([
                api.get(plan.detail),
                api.get(plan.market),
                api.get(plan.analytics),
            ]);
        } else {
            // Records with no ISIN (record_id) and corporate (CDSL) records:
            // the detail route is authoritative; analytics are requested only
            // when the identity supports them (they are ISIN-based).
            bond = await api.get(plan.detail);
            if (plan.analytics) {
                try {
                    analytics = await api.get(plan.analytics);
                } catch (_aErr) {
                    // Analytics unavailable for this record: the detail view
                    // stays useful and the metric cards show unavailable.
                    analytics = null;
                }
            }
        }
    } catch (err) {
        if (seq !== state.loadSeq) return;
        $("ba-results").classList.add("hidden");
        $("ba-results").classList.remove("is-loading");
        $("ba-detail-empty").classList.remove("hidden");
        state.selectedKey = null;
        markSelectedRow(null);
        showError(`Could not load bond data: ${err && err.message ? err.message : err}`);
        return;
    }
    if (seq !== state.loadSeq) return;

    // /{isin}/market returns the same normalized record with emphasis on the
    // observation fields; prefer it for market-specific values when present.
    const merged = Object.assign({}, bond || {}, pickMarketFields(market));
    $("ba-results").classList.remove("is-loading");
    renderBond(merged, analytics || {}, {
        // false → the analytics endpoints cannot serve this record (no ISIN).
        analyticsAvailable: plan.analytics !== null,
        identityKind: plan.kind,
    });
}

// Only market-observation fields are taken from the market endpoint; master
// data (name, ISIN, coupon, maturity…) stays authoritative from /{isin}.
const MARKET_FIELDS = [
    "price", "clean_price", "dirty_price", "ytm",
    "bid_price", "bid_yield", "offer_price", "offer_yield",
    "last_traded_price", "last_traded_yield",
    "weighted_average_price", "weighted_average_yield",
    "traded_value", "traded_quantity", "trade_count",
    "trade_date", "trade_time", "source", "as_of",
    "retrieved_at", "data_type", "freshness_days",
];

function pickMarketFields(m) {
    const out = {};
    if (!m || typeof m !== "object") return out;
    for (const key of MARKET_FIELDS) {
        if (m[key] !== undefined && m[key] !== null) out[key] = m[key];
    }
    return out;
}


// ---------------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------------

function detailItem(label, value, mono) {
    return `<div class="ba-detail-item">
        <span class="ba-detail-label">${escapeHtml(label)}</span>
        <span class="ba-detail-value${mono ? " ba-value-mono" : ""}">${escapeHtml(na(value))}</span>
    </div>`;
}

// Credit rating for the existing summary card. An authoritative rating
// (e.g. from the CDSL record) always wins; a Bond Central rating is used
// only when no authoritative rating is present. Government securities,
// T-Bills and SDLs are not CRA-rated and always show N/A. Never throws:
// null/undefined bonds and non-array `credit_ratings` render N/A.
function summaryCreditRating(bond, isCorporate) {
    if (!isCorporate || !bond) return "N/A";
    if (bond.credit_rating) return bond.credit_rating;
    const ratings = Array.isArray(bond.credit_ratings) ? bond.credit_ratings : [];
    const fallback = ratings.find((r) => r && r.credit_rating);
    return fallback ? fallback.credit_rating : "N/A";
}

// Credit ratings from Bond Central (corporate bonds only). Government
// securities, T-Bills and SDLs are not CRA-rated, so they always render the
// neutral N/A credit-rating row instead of a corporate CRA rating.
// Multiple ratings are preserved and each rating date is shown exactly as
// published, so a historical rating is never presented as current. Never
// throws: null/undefined bonds and non-array `credit_ratings` render N/A.
function creditRatingItems(bond, isCorporate) {
    const ratings = (bond && Array.isArray(bond.credit_ratings)) ? bond.credit_ratings : [];
    const rows = isCorporate
        ? ratings.filter((r) => r && (
            r.credit_rating || r.credit_rating_agency_name
            || r.date_of_credit_rating || r.ratings_watch || r.ratings_outlook
        ))
        : [];

    if (rows.length === 0) {
        return detailItem("Credit Rating", "N/A");
    }

    return rows.map((r) => [
        detailItem("Rating", r.credit_rating),
        detailItem("Agency", r.credit_rating_agency_name),
        detailItem("Rating date", r.date_of_credit_rating),
        detailItem("Source", r.source || "Bond Central"),
        r.ratings_outlook ? detailItem("Outlook", r.ratings_outlook) : "",
        r.ratings_watch ? detailItem("Watch", r.ratings_watch) : "",
    ].join("")).join("");
}

// Data-consistency warning: a maturity date that has passed while the source
// still reports the security as ACTIVE requires verification. The stored
// status is never changed automatically — this is a display-only warning.
function maturityStatusWarning(bond) {
    if (!bond || !bond.maturity_date) return "";
    const maturity = new Date(bond.maturity_date);
    if (Number.isNaN(maturity.getTime())) return "";
    const status = String(bond.security_status || "").trim().toUpperCase();
    if (status !== "ACTIVE") return "";
    return maturity.getTime() < Date.now()
        ? "Maturity date has passed; current security status requires verification."
        : "";
}

// Emphasis tile for the headline numbers (price / yield), kept distinct from
// the compact metadata tiles so the important figures read first.
function heroMetric(label, value, caption) {
    const shown = value === null || value === undefined || value === "" ? "N/A" : value;
    const muted = shown === "N/A";
    return `<div class="ba-hero-metric${muted ? " is-muted" : ""}">
        <span class="ba-hero-value">${escapeHtml(shown)}</span>
        <span class="ba-hero-label">${escapeHtml(label)}</span>
        ${caption ? `<span class="ba-hero-caption">${escapeHtml(caption)}</span>` : ""}
    </div>`;
}

// Compact metadata tile (label above value) for the summary metric grid.
function metricTile(label, value, options) {
    const opts = options || {};
    const missing = value === null || value === undefined || value === "";
    return `<div class="ba-metric${missing ? " is-missing" : ""}${opts.emphasis ? " is-emphasis" : ""}">
        <span class="ba-metric-label">${escapeHtml(label)}</span>
        <span class="ba-metric-value">${escapeHtml(na(value))}</span>
    </div>`;
}

function renderBond(bond, analytics, options) {
    const opts = options || {};
    const isCorporate = state.universe === "corporate";
    // false when the record publishes no ISIN and the ISIN-based analytics
    // endpoints cannot serve it — the analytics sections then render a clean
    // unavailable state instead of an unexplained blank.
    const analyticsAvailable = opts.analyticsAvailable !== false;

    if (!bond) {
        $("ba-results").classList.add("hidden");
        $("ba-detail-empty").classList.remove("hidden");
        return;
    }

    const identity = bondIdentity(bond);

    // Source indicator (backend-provided source/freshness only)
    const badge = $("ba-section-header-badge");
    const dt = (bond.data_type || "").toLowerCase();
    const stale = typeof bond.freshness_days === "number" && bond.freshness_days > 7;
    badge.textContent = [
        bond.source ? `Source: ${bond.source}` : "",
        dt ? bond.data_type.charAt(0).toUpperCase() + dt.slice(1) : "",
        bond.as_of ? `As of ${formatDate(bond.as_of)}` : "",
        stale ? `Freshness: ${bond.freshness_days}d` : "",
    ].filter(Boolean).join(" · ") || "Data availability unknown";
    badge.classList.toggle("is-traded", dt === "traded");
    badge.classList.toggle("is-stale", stale);

    // Analytics provenance: the engine's settlement date when it ran,
    // otherwise an explicit reason instead of a silent blank.
    const analyticsBadge = $("ba-section-header-badge2");
    if (analyticsBadge) {
        analyticsBadge.textContent = analyticsAvailable
            ? (analytics.settlement_date
                ? `Settlement ${formatDate(analytics.settlement_date)}`
                : "Computed by the analytics engine")
            : "Unavailable — no ISIN on this record";
        analyticsBadge.classList.toggle("is-unavailable", !analyticsAvailable);
    }

    // C. Summary — prominent name, compact identity/metadata chips, then the
    // headline price/yield metrics and the metric grid.
    $("ba-summary-name").textContent = bond.security_name || identity.isin || identity.recordId || "Unnamed security";

    const identityChip = identity.kind === "record"
        ? `<span class="ba-bond-meta-chip"><span class="ba-bond-id-label">Record ID</span>${escapeHtml(identity.recordId)}</span>`
        : (identity.kind === "isin"
            ? `<span class="ba-bond-meta-chip"><span class="ba-bond-id-label">ISIN</span><span class="ba-bond-meta-isin">${escapeHtml(identity.isin)}</span></span>`
            : "");
    $("ba-summary-meta").innerHTML = [
        identityChip,
        bond.instrument_type ? `<span class="ba-bond-meta-chip">${escapeHtml(bond.instrument_type)}</span>` : "",
        bond.issuer ? `<span class="ba-bond-meta-chip">${escapeHtml(bond.issuer)}</span>` : "",
        bond.maturity_date ? `<span class="ba-bond-meta-chip">Matures ${escapeHtml(formatDate(bond.maturity_date))}</span>` : "",
    ].filter(Boolean).join("");

    // T-Bills are zero-coupon: coupon/frequency shown as neutral N/A values.
    const isTBill = (bond.instrument_type || "").toUpperCase() === "T-BILL";
    const couponLabel = isTBill ? "N/A (zero-coupon)" : formatPct(bond.coupon_rate);
    const freqLabel = isTBill ? "N/A (zero-coupon)" : couponFrequencyLabel(bond.coupon_frequency);

    // Corporate records (CDSL) render the fields the corporate endpoint
    // actually supplies — LTP / VWAP / weighted-average yield — using their
    // real names; the government rendering is unchanged.
    $("ba-summary-hero").innerHTML = (isCorporate ? [
        heroMetric("LTP", formatNum(bond.last_traded_price != null ? bond.last_traded_price : bond.price), "Last traded price"),
        heroMetric("Market YTM", formatPct(bond.ytm), "As reported by the source"),
        heroMetric("Weighted Avg Yield", formatPct(bond.weighted_average_yield), "CDSL trade-weighted yield"),
    ] : [
        heroMetric("Clean Price", formatNum(bond.clean_price != null ? bond.clean_price : bond.price), "Per ₹100 face value"),
        heroMetric("Market YTM", formatPct(bond.ytm), "As reported by the source"),
        heroMetric("Coupon Rate", isTBill ? "N/A" : formatPct(bond.coupon_rate), isTBill ? "Zero-coupon instrument" : "Annual coupon"),
    ]).join("");

    $("ba-summary-grid").innerHTML = (isCorporate ? [
        metricTile("Credit Rating", summaryCreditRating(bond, isCorporate), { emphasis: true }),
        metricTile("Maturity Date", formatDate(bond.maturity_date)),
        metricTile("Coupon Rate", couponLabel),
        metricTile("VWAP", formatNum(bond.weighted_average_price)),
        metricTile("Trade Date", formatDate(bond.trade_date)),
        metricTile("Instrument Type", bond.instrument_type),
    ] : [
        metricTile("Credit Rating", summaryCreditRating(bond, isCorporate)),
        metricTile("Maturity Date", formatDate(bond.maturity_date), { emphasis: true }),
        metricTile("Coupon Rate", couponLabel),
        metricTile("Coupon Frequency", freqLabel),
        metricTile("Instrument Type", bond.instrument_type),
        metricTile("Issuer", bond.issuer),
    ]).join("");

    // D. Analytics KPIs
    renderKpis(analytics, bond, analyticsAvailable);

    // E. Cash flows
    renderCashFlows(analytics, analyticsAvailable);

    // F. Details / methodology — government rows keep the analytics-backed
    // fields; corporate rows show the CDSL issuance/trade fields instead.
    // Analytics sections that cannot be populated for corporate records stay
    // at their neutral N/A/empty state (no client-side computation).
    // The identity row shows the ISIN when the record publishes one and the
    // backend's own Record ID otherwise (never a fabricated value).
    const identityDetail = identity.kind === "record"
        ? detailItem("Record ID", identity.recordId, true)
        : detailItem("ISIN", identity.isin, true);

    const detailRows = isCorporate ? [
        identityDetail,
        detailItem("Trade Date", formatDate(bond.trade_date)),
        detailItem("Exchange", bond.exchange),
        detailItem("Issue Date", formatDate(bond.issue_date)),
        detailItem("Issue Size (Cr.)", formatNum(bond.issue_size)),
        detailItem("Issue Price", formatNum(bond.issue_price)),
        detailItem("Mode of Issuance", bond.mode_of_issuance),
        detailItem("Coupon Frequency", freqLabel),
    ] : [
        identityDetail,
        detailItem("Settlement Date", formatDate(analytics.settlement_date)),
        detailItem("Day-Count Convention", analytics.day_count_convention),
        detailItem("Coupon Frequency", freqLabel),
        detailItem("Face Value", formatNum(bond.face_value)),
        detailItem("Callable", bond.callable === true ? "Yes" : (bond.callable === false ? "No" : "N/A")),
        detailItem("Puttable", bond.puttable === true ? "Yes" : (bond.puttable === false ? "No" : "N/A")),
    ];

    // Credit ratings (Bond Central) are corporate-only; government securities,
    // T-Bills and SDLs render the neutral N/A credit-rating row instead.
    $("ba-details-grid").innerHTML = detailRows.join("") + creditRatingItems(bond, isCorporate);

    const notes = Array.isArray(analytics.notes) ? analytics.notes : [];
    const noteItems = notes.map((n) => `<li>${escapeHtml(n)}</li>`);
    // Records with no ISIN cannot be served by the ISIN-based analytics
    // endpoints: state that plainly instead of leaving a silent gap.
    if (!analyticsAvailable) {
        noteItems.push(`<li>${escapeHtml(ANALYTICS_UNAVAILABLE_REASON)}</li>`);
    }
    // Display-only warning; the stored security status is never changed.
    const statusWarning = maturityStatusWarning(bond);
    if (statusWarning) noteItems.push(`<li>${escapeHtml(statusWarning)}</li>`);
    $("ba-notes").innerHTML = noteItems.join("");
}


// Shown wherever the analytics engine cannot produce metrics for the selected
// record (its endpoints are ISIN-based; some source records publish no ISIN).
const ANALYTICS_UNAVAILABLE_REASON = "Analytics unavailable for this record: the analytics engine requires an ISIN and this source record publishes none. The bond details and the source-reported market values are shown as published.";

// KPI metadata — concise hover/help text, following the application's
// .tooltip-trigger pattern (no tooltip library).
const KPI_HELP = {
    current_yield: "Annual coupon divided by the current clean price, shown as a percentage.",
    calculated_ytm: "Yield to maturity computed by the analytics engine from the bond's price and cash flows — independent of the market-reported YTM.",
    market_ytm: "Yield to maturity as reported by the market data source. Kept separate from the calculated YTM.",
    accrued_interest: "Interest accumulated since the last coupon date, per 100 of face value. Reported separately from the clean price.",
    macaulay_duration: "Weighted average time (in years) to receive the bond's cash flows.",
    modified_duration: "Approximate percentage price change for a 1% change in yield.",
    convexity: "Second-order sensitivity capturing how duration changes as yield changes.",
    dv01: "Dollar value of one basis point — price change for a 0.01% yield move, per 100 of face value.",
};

// One analytics metric card. `emphasis` promotes the headline price/yield
// metrics; `unavailableReason` explains a muted N/A value via the existing
// tooltip pattern.
function kpiCard(key, label, value, muted, unavailableReason, emphasis) {
    const help = KPI_HELP[key] || "";
    const helpHtml = help
        ? `<span class="tooltip-trigger" tabindex="0" role="button" aria-label="More information about ${escapeAttr(label)}"><span class="tooltip-content">${escapeHtml(help)}</span>ⓘ</span>`
        : "";
    // When a metric is unavailable, the N/A value itself carries a tooltip
    // explaining exactly why (missing source terms etc.) instead of an
    // unexplained N/A.
    const naHtml = muted && unavailableReason
        ? `<span class="tooltip-trigger" tabindex="0" role="button" aria-label="Why is ${escapeAttr(label)} unavailable?"><span class="tooltip-content">${escapeHtml(unavailableReason)}</span>ⓘ</span>`
        : "";
    return `<div class="ba-kpi${emphasis ? " is-emphasis" : ""}${muted ? " is-muted" : ""}">
        <span class="ba-kpi-value${muted ? " is-muted" : ""}">${escapeHtml(na(value))}${naHtml}</span>
        <span class="ba-kpi-label">${escapeHtml(label)}${helpHtml}</span>
    </div>`;
}

// Analytics metric grid. `analyticsAvailable === false` renders the eight
// metric cards in their unavailable state with a single explicit reason and
// keeps the source-reported Market YTM visible (a backend value from the
// record itself — nothing is computed in the browser).
function renderKpis(a, bond, analyticsAvailable) {
    const available = analyticsAvailable !== false;
    const analytics = a || {};
    const reasons = analytics.unavailable_metrics || {};
    const reasonFor = (key) => (available ? reasons[key] : ANALYTICS_UNAVAILABLE_REASON);

    // Market YTM is reported by the source observation, so it survives even
    // when the analytics engine cannot run for the record.
    const marketYtm = available
        ? analytics.market_ytm
        : (bond && bond.ytm != null ? bond.ytm : null);

    $("ba-kpi-grid").innerHTML = [
        available ? "" : `<p class="ba-kpi-notice">Analytics unavailable for this record <span class="ba-kpi-notice-detail">— ${escapeHtml(ANALYTICS_UNAVAILABLE_REASON)}</span></p>`,
        kpiCard("current_yield", "Current Yield", available ? analytics.current_yield : null, !available || analytics.current_yield == null, reasonFor("current_yield"), true),
        kpiCard("market_ytm", "Market YTM", marketYtm, marketYtm == null, reasonFor("market_ytm"), true),
        kpiCard("calculated_ytm", "Calculated YTM", available ? analytics.calculated_ytm : null, !available || analytics.calculated_ytm == null, reasonFor("calculated_ytm"), true),
        kpiCard("accrued_interest", "Accrued Interest", available ? analytics.accrued_interest : null, !available || analytics.accrued_interest == null, reasonFor("accrued_interest")),
        kpiCard("macaulay_duration", "Macaulay Duration", available ? analytics.macaulay_duration : null, !available || analytics.macaulay_duration == null, reasonFor("macaulay_duration")),
        kpiCard("modified_duration", "Modified Duration", available ? analytics.modified_duration : null, !available || analytics.modified_duration == null, reasonFor("modified_duration")),
        kpiCard("convexity", "Convexity", available ? analytics.convexity : null, !available || analytics.convexity == null, reasonFor("convexity")),
        kpiCard("dv01", "DV01", available ? analytics.dv01 : null, !available || analytics.dv01 == null, reasonFor("dv01")),
    ].join("");
}

function renderCashFlows(analytics, analyticsAvailable) {
    const wrap = $("ba-cashflow-wrap");
    const a = analytics || {};
    const available = analyticsAvailable !== false;
    const rows = Array.isArray(a.cash_flows) ? a.cash_flows : [];
    if (!rows.length) {
        // Explain the empty state: which inputs are missing and, when known,
        // what additional data source would provide them. A record without an
        // ISIN cannot reach the analytics engine at all, so say that first.
        if (!available) {
            wrap.innerHTML = `
            <p class="ba-section-sub"><strong>Cash-flow schedule unavailable.</strong> ${escapeHtml(ANALYTICS_UNAVAILABLE_REASON)}</p>
            <p class="ba-section-sub">A payment schedule is shown only when the bond's coupon rate, coupon frequency, interest start date and redemption/maturity date are all published by the source (CDSL). For government securities the coupon calendar is derived from the published maturity date.</p>`;
            return;
        }
        const reasons = a.unavailable_metrics || {};
        const reason = a.unavailable_metrics && a.unavailable_metrics.cash_flows
            ? a.unavailable_metrics.cash_flows
            : "Cash-flow data unavailable for this bond.";
        const missing = Object.values(reasons)
            .filter((r) => r && r !== reason)
            .slice(0, 3);
        wrap.innerHTML = `
            <p class="ba-section-sub"><strong>Cash-flow data unavailable.</strong> ${escapeHtml(reason)}</p>
            ${missing.length ? `<ul class="ba-notes">${missing.map((m) => `<li>${escapeHtml(m)}</li>`).join("")}</ul>` : ""}
            <p class="ba-section-sub">A payment schedule is shown only when the bond's coupon rate, coupon frequency, interest start date and redemption/maturity date are all published by the source (CDSL). For government securities the coupon calendar is derived from the published maturity date.</p>`;
        return;
    }

    // Distinguish source-published schedules from schedules calculated from
    // source-validated terms; values are rendered exactly as returned by the
    // analytics endpoint — nothing is recomputed in the browser.
    const sourceLabel = a.cash_flow_source === "source"
        ? "Source-provided schedule (CDSL)"
        : "Calculated from source-validated terms (per ₹100 face value)";
    const hasSourceRows = rows.some((r) => r && r.source === "cdsl");
    const badge = hasSourceRows
        ? "Source-provided schedule (CDSL)"
        : sourceLabel;

    wrap.innerHTML = `<p class="ba-section-sub">${escapeHtml(badge)}</p>
    <table class="ba-table">
        <thead>
            <tr>
                <th>Payment Date</th>
                <th class="ba-num">Coupon</th>
                <th class="ba-num">Principal</th>
                <th class="ba-num">Total Cash Flow</th>
            </tr>
        </thead>
        <tbody>
            ${rows.map((r, i) => {
                const isFinal = i === rows.length - 1;
                const principal = toFiniteNumber(r.principal);
                // The final row is the redemption only when the backend
                // actually reports principal on it — never assumed.
                const isRedemption = isFinal && principal !== null && principal > 0;
                const rowClass = isRedemption ? "is-redemption"
                    : (isFinal ? "is-final" : (i % 2 === 1 ? "is-alt" : ""));
                return `<tr${rowClass ? ` class="${rowClass}"` : ""}>
                <td>${escapeHtml(formatDate(r.date))}${isRedemption ? '<span class="ba-cf-tag">Redemption</span>' : ""}</td>
                <td class="ba-num">${escapeHtml(formatNum(r.coupon))}</td>
                <td class="ba-num">${escapeHtml(formatNum(r.principal))}</td>
                <td class="ba-num">${escapeHtml(formatNum(r.total))}</td>
            </tr>`;
            }).join("")}
        </tbody>
    </table>`;
}


// ---------------------------------------------------------------------------
// Tooltips — same fixed-position pattern as Mutual Fund Analysis
// (the shared .tooltip-trigger CSS is defined in bond-analysis.css).
// ---------------------------------------------------------------------------

function positionTooltip(trigger) {
    const content = trigger.querySelector(".tooltip-content");
    if (!content) return;

    const triggerRect = trigger.getBoundingClientRect();
    const contentRect = content.getBoundingClientRect();

    const viewportWidth = window.innerWidth;
    const contentWidth = contentRect.width || 260;

    let left = triggerRect.left + (triggerRect.width / 2) - (contentWidth / 2);
    left = Math.max(8, Math.min(left, viewportWidth - contentWidth - 8));

    const top = triggerRect.bottom;

    content.style.setProperty("top", `${top}px`);
    content.style.setProperty("left", `${left}px`);
}

document.addEventListener("mouseover", (e) => {
    const trigger = e.target.closest(".tooltip-trigger");
    if (trigger) {
        positionTooltip(trigger);
    }
});

document.addEventListener("focusin", (e) => {
    const trigger = e.target.closest(".tooltip-trigger");
    if (trigger) {
        positionTooltip(trigger);
    }
});


// ---------------------------------------------------------------------------
// Credit Rating multi-select (Advanced Bond Filters — corporate only)
// ---------------------------------------------------------------------------
// The rating list is rendered ONCE from CREDIT_RATING_OPTIONS and narrowed by
// the in-dropdown search. Selections live on the option elements themselves
// (aria-selected), so filtering the visible list never drops a selection.
// Nothing is fetched per rating: the chosen keys are matched client-side
// against bond.credit_rating by applyCreditRatingFilter().

// Index (within the currently visible options) of the roving tab stop.
let creditRatingActiveIdx = -1;

// Render the full option list. Options are never removed on search — they are
// hidden — so a selection survives an in-dropdown search. The "Unknown" value
// is labelled "Rating unavailable" while its data-rating stays "Unknown" so
// it matches getBondRatingKey() output.
function renderCreditRatingOptions() {
    const list = $("ba-credit-rating-listbox");
    if (!list) return;
    list.innerHTML = CREDIT_RATING_OPTIONS.map((rating, index) => `
        <li role="option"
            id="ba-credit-rating-option-${index}"
            class="ba-multiselect-option"
            data-rating="${escapeHtml(rating)}"
            aria-selected="false"
            tabindex="-1">
            <span class="ba-multiselect-checkbox" aria-hidden="true"></span>
            <span class="ba-multiselect-option-label">${escapeHtml(creditRatingLabel(rating))}</span>
        </li>
    `).join("");
}

// Currently visible (unfiltered) options, in document order.
function visibleCreditRatingOptions() {
    const list = $("ba-credit-rating-listbox");
    if (!list) return [];
    return Array.from(list.querySelectorAll('[role="option"]'))
        .filter((el) => !el.classList.contains("hidden"));
}

// The pending selection, read straight from the option elements.
function readCreditRatingState() {
    const list = $("ba-credit-rating-listbox");
    if (!list) return [];
    return Array.from(list.querySelectorAll('[role="option"][aria-selected="true"]'))
        .map((el) => el.getAttribute("data-rating"))
        .filter(Boolean);
}

// Move the roving tab stop to the given visible option index and focus it.
function focusCreditRatingOption(index) {
    const options = visibleCreditRatingOptions();
    if (!options.length) return;
    const clamped = Math.max(0, Math.min(index, options.length - 1));
    options.forEach((el) => el.setAttribute("tabindex", "-1"));
    creditRatingActiveIdx = clamped;
    const target = options[clamped];
    target.setAttribute("tabindex", "0");
    target.focus();
}

// Show/hide options by the in-dropdown search term and reset the tab stop.
// Matching runs against both the stored value and its display label, so
// typing "unavailable" still finds the "Rating unavailable" option.
function filterCreditRatingOptions(query) {
    const list = $("ba-credit-rating-listbox");
    if (!list) return;
    const q = String(query || "").trim().toLowerCase();
    Array.from(list.querySelectorAll('[role="option"]')).forEach((el) => {
        const rating = (el.getAttribute("data-rating") || "").toLowerCase();
        const label = creditRatingLabel(el.getAttribute("data-rating") || "").toLowerCase();
        el.classList.toggle("hidden", Boolean(q) && !rating.includes(q) && !label.includes(q));
    });

    const options = visibleCreditRatingOptions();
    Array.from(list.querySelectorAll('[role="option"]')).forEach((el) => {
        el.setAttribute("tabindex", "-1");
    });
    if (options.length) options[0].setAttribute("tabindex", "0");
    creditRatingActiveIdx = options.length ? 0 : -1;

    const field = $("ba-credit-rating");
    if (field && field.dataset.state === "open") positionCreditRatingDropdown();
}

// Selected ratings surface as compact chips (up to three), otherwise a count.
// The "Unknown" value renders as "Rating unavailable".
function renderCreditRatingDisplay() {
    const display = $("ba-credit-rating-display");
    if (!display) return;
    const selected = readCreditRatingState();
    if (!selected.length) {
        display.innerHTML = '<span class="ba-multiselect-summary">Select ratings&hellip;</span>';
        return;
    }
    if (selected.length <= 3) {
        display.innerHTML = selected
            .map((rating) => `<span class="ba-multiselect-chip">${escapeHtml(creditRatingLabel(rating))}</span>`)
            .join("");
        return;
    }
    display.innerHTML = `<span class="ba-multiselect-summary">${selected.length} ratings selected</span>`;
}

// Commit the pending (DOM) rating selection into state and immediately
// re-run the search so a toggle filters the corporate list at once.
function commitCreditRatingSelection() {
    state.creditRatings = readCreditRatingState();
    state.page = 1;
    searchBonds();
}

function toggleCreditRatingOption(optionEl) {
    if (!optionEl) return;
    const next = optionEl.getAttribute("aria-selected") !== "true";
    optionEl.setAttribute("aria-selected", next ? "true" : "false");
    renderCreditRatingDisplay();
    commitCreditRatingSelection();
}

function clearCreditRatingSelections() {
    const list = $("ba-credit-rating-listbox");
    if (!list) return;
    Array.from(list.querySelectorAll('[role="option"]')).forEach((el) => {
        el.setAttribute("aria-selected", "false");
    });
    renderCreditRatingDisplay();
}

// Position the fixed-position panel against the trigger. The panel uses
// position: fixed so it is not clipped by the overflow: hidden filter card;
// it flips above the trigger when there is not enough room below.
function positionCreditRatingDropdown() {
    const trigger = $("ba-credit-rating-trigger");
    const dropdown = $("ba-credit-rating-dropdown");
    if (!trigger || !dropdown) return;

    const rect = trigger.getBoundingClientRect();
    const gap = 4;
    const panelHeight = Math.min(dropdown.getBoundingClientRect().height || 288, 288);
    const roomBelow = window.innerHeight - rect.bottom;
    const flipUp = roomBelow < panelHeight + gap && rect.top > panelHeight + gap;

    dropdown.style.top = flipUp
        ? `${Math.round(rect.top - panelHeight - gap)}px`
        : `${Math.round(rect.bottom + gap)}px`;
    dropdown.style.left = `${Math.round(rect.left)}px`;
    dropdown.style.width = `${Math.round(rect.width)}px`;
}

function openCreditRatingDropdown() {
    const field = $("ba-credit-rating");
    const dropdown = $("ba-credit-rating-dropdown");
    const trigger = $("ba-credit-rating-trigger");
    const search = $("ba-credit-rating-search");
    if (!field || !dropdown || !trigger) return;

    field.dataset.state = "open";
    dropdown.classList.remove("hidden");
    dropdown.setAttribute("aria-hidden", "false");
    trigger.setAttribute("aria-expanded", "true");
    if (search) {
        search.value = "";
        filterCreditRatingOptions("");
    }
    // Measure/position only once the panel is visible.
    positionCreditRatingDropdown();
    if (search) search.focus();
}

function closeCreditRatingDropdown() {
    const field = $("ba-credit-rating");
    const dropdown = $("ba-credit-rating-dropdown");
    const trigger = $("ba-credit-rating-trigger");
    if (!field || !dropdown || !trigger) return;

    field.dataset.state = "closed";
    dropdown.classList.add("hidden");
    dropdown.setAttribute("aria-hidden", "true");
    trigger.setAttribute("aria-expanded", "false");
}

// Reset clears every rating selection plus the in-dropdown search term.
function resetCreditRatingFilter() {
    clearCreditRatingSelections();
    const search = $("ba-credit-rating-search");
    if (search) search.value = "";
    filterCreditRatingOptions("");
}

function setupCreditRatingFilter() {
    const field = $("ba-credit-rating");
    const trigger = $("ba-credit-rating-trigger");
    const dropdown = $("ba-credit-rating-dropdown");
    const search = $("ba-credit-rating-search");
    const list = $("ba-credit-rating-listbox");
    const clearBtn = $("ba-credit-rating-clear");
    if (!field || !trigger || !list) return;

    renderCreditRatingOptions();
    filterCreditRatingOptions("");
    renderCreditRatingDisplay();

    // Trigger — click or Down/Up arrow opens the dropdown (search focused).
    trigger.addEventListener("click", () => {
        if (field.dataset.state === "open") closeCreditRatingDropdown();
        else openCreditRatingDropdown();
    });
    trigger.addEventListener("keydown", (e) => {
        if (e.key === "ArrowDown" || e.key === "ArrowUp") {
            e.preventDefault();
            openCreditRatingDropdown();
        }
    });

    // In-dropdown search narrows the visible options.
    if (search) {
        search.addEventListener("input", () => filterCreditRatingOptions(search.value));
        search.addEventListener("keydown", (e) => {
            if (e.key === "ArrowDown") {
                e.preventDefault();
                focusCreditRatingOption(0);
            } else if (e.key === "Escape") {
                e.preventDefault();
                closeCreditRatingDropdown();
                trigger.focus();
            }
        });
    }

    // Option selection (delegated) + keyboard navigation.
    list.addEventListener("click", (e) => {
        const option = e.target.closest('[role="option"]');
        if (!option) return;
        e.preventDefault();
        toggleCreditRatingOption(option);
    });
    list.addEventListener("keydown", (e) => {
        const option = e.target.closest('[role="option"]');
        if (!option) return;
        if (e.key === "ArrowDown") {
            e.preventDefault();
            focusCreditRatingOption(creditRatingActiveIdx + 1);
        } else if (e.key === "ArrowUp") {
            e.preventDefault();
            focusCreditRatingOption(creditRatingActiveIdx - 1);
        } else if (e.key === "Home") {
            e.preventDefault();
            focusCreditRatingOption(0);
        } else if (e.key === "End") {
            e.preventDefault();
            focusCreditRatingOption(visibleCreditRatingOptions().length - 1);
        } else if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            toggleCreditRatingOption(option);
        } else if (e.key === "Escape") {
            e.preventDefault();
            closeCreditRatingDropdown();
            trigger.focus();
        }
    });

    // Clear every selection without leaving the dropdown. Commits immediately
    // so the list reverts to unfiltered without waiting for Apply.
    if (clearBtn) {
        clearBtn.addEventListener("click", (e) => {
            e.preventDefault();
            clearCreditRatingSelections();
            if (search) {
                search.value = "";
                filterCreditRatingOptions("");
                search.focus();
            }
            commitCreditRatingSelection();
        });
    }

    // Escape closes the dropdown from anywhere inside the field.
    field.addEventListener("keydown", (e) => {
        if (e.key === "Escape" && field.dataset.state === "open") {
            e.preventDefault();
            closeCreditRatingDropdown();
            trigger.focus();
        }
    });

    // A click outside the field closes the dropdown.
    document.addEventListener("click", (e) => {
        if (!field.contains(e.target)) closeCreditRatingDropdown();
    });

    // The panel is position: fixed, so it would detach from the trigger on a
    // scroll or resize — close it instead (scrolls inside the panel are kept).
    window.addEventListener("resize", () => {
        if (field.dataset.state === "open") closeCreditRatingDropdown();
    });
    window.addEventListener("scroll", (e) => {
        if (field.dataset.state !== "open") return;
        if (dropdown && dropdown.contains(e.target)) return;
        closeCreditRatingDropdown();
    }, true);

    // Keep the panel anchored to the field while open.
    if (dropdown) {
        dropdown.addEventListener("click", (e) => e.stopPropagation());
    }
}

// ---------------------------------------------------------------------------
// Range filter output labels
// ---------------------------------------------------------------------------

function setupRangeOutput(inputId, outputId, label, anyAtLimit = false) {
    const input = $(inputId);
    const output = $(outputId);

    if (!input || !output) return;

    const updateOutput = () => {
        const value = Number(input.value);
        const min = Number(input.min);
        const max = Number(input.max);

        const isAny =
            anyAtLimit &&
            ((label === "Min" && value === min) ||
             (label === "Max" && value === max));

        output.textContent = isAny
            ? `${label}: Any`
            : `${label}: ${value.toFixed(2).replace(/\.?0+$/, "")}%`;
    };

    input.addEventListener("input", updateOutput);
    updateOutput();
}

function setupRangeOutputs() {
    setupRangeOutput("ba-coupon-min", "ba-coupon-min-value", "Min", true);
    setupRangeOutput("ba-coupon-max", "ba-coupon-max-value", "Max", true);
    setupRangeOutput("ba-yield-min", "ba-yield-min-value", "Min", true);
    setupRangeOutput("ba-yield-max", "ba-yield-max-value", "Max", true);
}

// ---------------------------------------------------------------------------
// Event wiring & init
// ---------------------------------------------------------------------------

function init() {
    setupRangeOutputs();
    // Credit-rating multi-select (corporate-only, client-side filter).
    setupCreditRatingFilter();

    // Initial/empty state before a bond is selected.
    $("ba-detail-empty").classList.remove("hidden");

    const searchInput = $("ba-search-input");
    const typeFilter = $("ba-type-filter");
    const bondList = $("ba-bond-list");

    if (searchInput && typeFilter) {
        // Debounced free-text search (shared core/utils debounce).
        const debouncedSearch = utils.debounce(searchBonds, 300);
        searchInput.addEventListener("input", debouncedSearch);
        typeFilter.addEventListener("change", () => {
            state.page = 1;
            searchBonds();
        });
    }

    // Data-source filter (All Sources | CCIL | NSE | RBI) — government-only;
    // a change restarts the search from the first page, like the other
    // filter controls.
    const sourceFilter = $("ba-source-filter");
    if (sourceFilter) {
        sourceFilter.addEventListener("change", () => {
            state.page = 1;
            searchBonds();
        });
    }

    // Corporate filter area — Trade Date (CDSL report date) and Issuer. Both
    // map to supported GET /api/bonds/corporate parameters; a change restarts
    // the search from the first page, like the other filter controls.
    const corpTradeDate = $("ba-corporate-trade-date");
    if (corpTradeDate) {
        corpTradeDate.addEventListener("change", () => {
            state.page = 1;
            searchBonds();
        });
    }
    const corpIssuer = $("ba-corporate-issuer");
    if (corpIssuer) {
        // Debounced like the shared search box (same 300 ms convention).
        corpIssuer.addEventListener("input", utils.debounce(() => {
            state.page = 1;
            searchBonds();
        }, 300));
    }

    // Range filters (coupon / yield / maturity). The sliders and date inputs
    // only change the PENDING values: nothing is requested until Apply, which
    // reloads the active universe from page 1 using every selected filter
    // (search, instrument type, source, corporate trade date/issuer, sort,
    // and the ranges themselves).
    const rangeApply = $("ba-range-apply");
    if (rangeApply) {
        rangeApply.addEventListener("click", () => {
            state.rangeFilters = readRangeFilters();
            // Commit pending credit-rating selections (corporate-only).
            state.creditRatings = readCreditRatingState();
            state.page = 1;
            searchBonds();
        });
    }

    // Reset restores the documented defaults, clears the active range filters,
    // AND clears credit-rating selections, then reloads the current universe
    // from the first page.
    const rangeReset = $("ba-range-reset");
    if (rangeReset) {
        rangeReset.addEventListener("click", () => {
            setRangeControlsToDefaults();
            state.rangeFilters = readRangeFilters();
            resetCreditRatingFilter();
            state.creditRatings = [];
            state.page = 1;
            searchBonds();
        });
    }

    // Universe switch — Government (default) | Corporate. Each universe is
    // loaded independently and lazily; the inactive one is never requested.
    const universeSwitch = $("ba-universe-switch");
    if (universeSwitch) {
        universeSwitch.addEventListener("click", (e) => {
            const btn = e.target.closest(".ba-universe-btn");
            if (btn) setUniverse(btn.dataset.universe);
        });
    }

    const sortSelect = $("ba-sort-select");
    const sortDirBtn = $("ba-sort-dir");
    if (sortSelect) {
        sortSelect.addEventListener("change", () => {
            state.sortBy = sortSelect.value;
            state.page = 1;
            searchBonds();
        });
    }
    if (sortDirBtn) {
        sortDirBtn.addEventListener("click", () => {
            const next = state.sortDir === "asc" ? "desc" : "asc";
            state.sortDir = next;
            sortDirBtn.setAttribute("aria-label", next === "asc" ? "Sort ascending" : "Sort descending");
            sortDirBtn.setAttribute("title", next === "asc" ? "Sort ascending" : "Sort descending");
            sortDirBtn.innerHTML = next === "asc" ? "&uarr;" : "&darr;";
            state.page = 1;
            searchBonds();
        });
    }

    if (bondList) {
        bondList.addEventListener("click", (e) => {
            const item = e.target.closest(".ba-bond-item");
            // Only real buttons are selectable. The single inert fallback row
            // (a record with no published identifier at all) is a div.
            if (!item || item.tagName !== "BUTTON") return;
            // Identity: ISIN when present, otherwise the backend-issued
            // record_id. Never a fabricated ISIN.
            selectBond({
                isin: item.dataset.isin ? item.dataset.isin : "",
                recordId: item.dataset.recordId ? item.dataset.recordId : "",
            });
        });
    }

// Section collapsible toggle
    const sectionToggles = document.querySelectorAll(".ba-section-toggle");
    sectionToggles.forEach((toggle) => {
        toggle.addEventListener("click", () => {
            const section = toggle.closest(".ba-section");
            const isOpen = toggle.getAttribute("aria-expanded") === "true";
            const body = section.querySelector(".ba-section-body");
            const chevron = toggle.querySelector(".ba-chevron");

            // Toggle state
            const newOpen = !isOpen;
            toggle.setAttribute("aria-expanded", newOpen);
            if (chevron) {
                chevron.style.transform = newOpen ? "rotate(180deg)" : "rotate(0deg)";
            }

            // Toggle content visibility
            if (body) {
                body.classList.toggle("collapsed", !newOpen);
                body.classList.toggle("expanded", newOpen);
            }
        });
    });

    // Pagination event delegation
    const paginationEl = $("ba-pagination");
    if (paginationEl) {
        paginationEl.addEventListener("click", (e) => {
            const btn = e.target.closest(".ba-page-btn");
            if (!btn) return;

            const page = btn.getAttribute("data-page");
            if (page === "prev") {
                // Prev is handled by going to page - 1, but we need to ensure we don't go below 1
                if (state.page > 1) {
                    state.page--;
                    searchBonds();
                }
            } else if (page === "next") {
                const pageCount = Math.max(1, Math.ceil(state.total / PAGE_SIZE));
                if (state.page < pageCount) {
                    state.page++;
                    searchBonds();
                }
            } else {
                // Page number button
                const requestedPage = parseInt(page, 10);
                if (!isNaN(requestedPage) && requestedPage !== state.page) {
                    state.page = requestedPage;
                    searchBonds();
                }
            }
        });
    }

    // Initialization always starts in the government universe; the initial
    // search below is the existing government search and /api/bonds/corporate
    // is never called during init.
    state.universe = "government";
    updateUniverseControls();
    searchBonds();
}


// ---------------------------------------------------------------------------
// Data Source Status — GET /api/bonds/sources/status
// ---------------------------------------------------------------------------
const BA_SOURCE_ORDER = ["CCIL", "NSE", "RBI"];
function baSourceStatusLabel(status) {
    const s = String(status || "not_loaded").toLowerCase();
    if (s === "success") return "Success";
    if (s === "error") return "Error";
    return "Not Loaded";
}
function baSourceStatusClass(status) {
    const s = String(status || "not_loaded").toLowerCase();
    if (s === "success") return "is-success";
    if (s === "error") return "is-error";
    return "is-neutral";
}
function renderBondSourceStatus(payload) {
    const list = $("ba-source-status-list");
    if (!list) return;
    const items = Array.isArray(payload) ? payload : (payload && Array.isArray(payload.sources) ? payload.sources : []);
    const bySource = {};
    items.forEach((entry) => {
        if (!entry || !entry.source) return;
        bySource[String(entry.source).toUpperCase()] = entry;
    });
    let okCount = 0;
    BA_SOURCE_ORDER.forEach((name) => {
        const row = list.querySelector(`[data-source="${name}"]`);
        if (!row) return;
        const entry = bySource[name] || { status: "not_loaded", record_count: 0, error: null };
        const status = String(entry.status || "not_loaded").toLowerCase();
        if (status === "success") okCount++;
        const badge = row.querySelector(".ba-source-badge");
        if (badge) {
            badge.textContent = baSourceStatusLabel(status);
            badge.classList.remove("is-success", "is-error", "is-neutral");
            badge.classList.add(baSourceStatusClass(status));
        }
        const count = row.querySelector(".ba-source-count");
        if (count) {
            const n = Number(entry.record_count);
            const safe = Number.isFinite(n) && n >= 0 ? n : 0;
            count.textContent = `${safe} record${safe === 1 ? "" : "s"}`;
        }
        let err = row.querySelector(".ba-source-error");
        const msg = status === "error" && entry.error ? String(entry.error) : "";
        if (msg) {
            if (!err) {
                err = document.createElement("span");
                err.className = "ba-source-error";
                err.setAttribute("role", "alert");
                row.appendChild(err);
            }
            err.textContent = msg;
        } else if (err) {
            err.remove();
        }
    });
    const total = $("ba-source-status-count");
    if (total) total.textContent = `${okCount}/${BA_SOURCE_ORDER.length} healthy`;
}
async function refreshBondSourceStatus() {
    try {
        const payload = await api.get("/bonds/sources/status");
        renderBondSourceStatus(payload);
    } catch (err) {
        renderBondSourceStatus({ sources: [] });
        const total = $("ba-source-status-count");
        if (total) total.textContent = "Status unavailable";
    }
}
// Refresh source status after every bond data refresh completes.
if (typeof searchBonds === "function" && !searchBonds.__baStatusWrapped) {
    const _baBaseSearchBonds = searchBonds;
    searchBonds = async function (...args) {
        try {
            return await _baBaseSearchBonds.apply(this, args);
        } finally {
            refreshBondSourceStatus();
        }
    };
    searchBonds.__baStatusWrapped = true;
}

// Sync aria-expanded for the range filter toggle for accessibility.
(function () {
    const rangePanel = document.getElementById('ba-range-panel');
    if (!rangePanel) return;
    const toggleBtn = rangePanel.querySelector('.ba-range-toggle');
    const summary = rangePanel.querySelector('.ba-range-summary');
    const syncAria = () => {
        const isOpen = rangePanel.hasAttribute('open');
        if (toggleBtn) toggleBtn.setAttribute('aria-expanded', String(isOpen));
        if (summary) summary.setAttribute('aria-expanded', String(isOpen));
    };
    // Initial sync
    syncAria();
    // Update on toggle via native <details> event
    rangePanel.addEventListener('toggle', syncAria);
    // Also handle clicks on the summary for browsers that may not fire toggle
    if (summary) {
        summary.addEventListener('click', syncAria);
    }
})();

init();


