// Bond Analysis — first production UI slice.
// Wires the page to the EXISTING bond APIs (no new backend, no client-side
// financial computation):
//   GET /api/bonds                    — list/search bonds
//   GET /api/bonds/{isin}             — bond by ISIN
//   GET /api/bonds/{isin}/market      — market observation
//   GET /api/bonds/{isin}/analytics   — computed analytics
//
// All financial values are rendered exactly as returned by the backend.
// Market YTM comes from the source/market observation; Calculated YTM comes
// from analytics. They are never substituted for one another.

import { api } from "../../core/api.js";
import { utils } from "../../core/utils.js";

const $ = (id) => document.getElementById(id);

const state = {
    searchSeq: 0,   // guards against out-of-order search responses
    loadSeq: 0,     // guards against out-of-order bond loads
    selectedIsin: null,
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
// Bond search
// ---------------------------------------------------------------------------

async function searchBonds() {
    const seq = ++state.searchSeq;
    const q = $("ba-search-input").value.trim();
    const type = $("ba-type-filter").value;

    const params = new URLSearchParams();
    if (q) params.set("search", q);
    if (type) params.set("instrument_type", type);
    params.set("limit", "50");

    setSelectorStatus('<span class="pb-analysis-loading"><span class="pb-spinner" aria-hidden="true"></span><span>Searching bonds&hellip;</span></span>');
    $("ba-no-results").classList.add("hidden");

    let bonds;
    try {
        bonds = await api.get(`/bonds?${params.toString()}`);
    } catch (err) {
        if (seq !== state.searchSeq) return;
        setSelectorStatus("");
        $("ba-no-results").classList.add("hidden");
        $("ba-bond-list").innerHTML = "";
        $("ba-result-count").textContent = "";
        showError(`Could not load bonds: ${err && err.message ? err.message : err}`);
        return;
    }

    if (seq !== state.searchSeq) return; // a newer search superseded this one
    setSelectorStatus("");
    hideError();

    const list = Array.isArray(bonds) ? bonds : [];
    $("ba-result-count").textContent = list.length ? `${list.length} result${list.length === 1 ? "" : "s"}` : "";
    $("ba-no-results").classList.toggle("hidden", list.length > 0);

    // Rows without an ISIN (some CCIL Market Watch entries) cannot be loaded
    // via /api/bonds/{isin}, so they are shown but not selectable.
    $("ba-bond-list").innerHTML = list.map((b) => {
        const isin = b.isin || "";
        const name = b.security_name || isin || "Unnamed security";
        const ytm = b.ytm != null ? formatPct(b.ytm) : "N/A";
        const meta = [
            isin ? `<span class="ba-bond-meta-isin">${escapeHtml(isin)}</span>` : '<span>No ISIN reported</span>',
            b.instrument_type ? `<span>${escapeHtml(b.instrument_type)}</span>` : "",
            b.issuer ? `<span>${escapeHtml(b.issuer)}</span>` : "",
            b.maturity_date ? `<span>Matures ${escapeHtml(formatDate(b.maturity_date))}</span>` : "",
        ].join("");
        const inner = `<span class="ba-bond-info">
                <span class="ba-bond-name">${escapeHtml(name)}</span>
                <span class="ba-bond-meta">${meta}</span>
            </span>
            <span class="ba-bond-yield">${escapeHtml(ytm)}</span>`;
        if (!isin) {
            return `<li><div class="ba-bond-item" aria-disabled="true" title="Details unavailable — this source entry has no ISIN">${inner}</div></li>`;
        }
        return `<li><button type="button" class="ba-bond-item" data-isin="${escapeAttr(isin)}">${inner}</button></li>`;
    }).join("");
}

function setSelectorStatus(html) {
    const el = $("ba-selector-status");
    if (!el) return;
    el.innerHTML = html;
    el.classList.toggle("hidden", !html);
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
// Selected bond load — /{isin}, /{isin}/market and /{isin}/analytics
// ---------------------------------------------------------------------------

async function selectBond(isin) {
    if (!isin) return;
    const seq = ++state.loadSeq;
    state.selectedIsin = isin;

    document.querySelectorAll(".ba-bond-item").forEach((btn) => {
        btn.classList.toggle("selected", btn.dataset.isin === isin);
    });

    $("ba-detail-empty").classList.add("hidden");
    $("ba-error").classList.add("hidden");
    $("ba-results").classList.remove("hidden");
    $("ba-summary-name").textContent = "Loading bond…";
    $("ba-summary-meta").innerHTML = "";
    $("ba-summary-grid").innerHTML = "";
    $("ba-kpi-grid").innerHTML = '<div class="pb-analysis-loading"><span class="pb-spinner" aria-hidden="true"></span><span>Loading analytics&hellip;</span></div>';
    $("ba-cashflow-wrap").innerHTML = "";
    $("ba-details-grid").innerHTML = "";
    $("ba-notes").innerHTML = "";
    $("ba-source-badge").textContent = "";

    // Market YTM (source observation) and Calculated YTM (analytics) come
    // from their own endpoints; the frontend never derives one from the other.
    let bond, market, analytics;
    try {
        [bond, market, analytics] = await Promise.all([
            api.get(`/bonds/${encodeURIComponent(isin)}`),
            api.get(`/bonds/${encodeURIComponent(isin)}/market`),
            api.get(`/bonds/${encodeURIComponent(isin)}/analytics`),
        ]);
    } catch (err) {
        if (seq !== state.loadSeq) return;
        $("ba-results").classList.add("hidden");
        $("ba-detail-empty").classList.remove("hidden");
        showError(`Could not load bond data: ${err && err.message ? err.message : err}`);
        return;
    }
    if (seq !== state.loadSeq) return;

    // /{isin}/market returns the same normalized record with emphasis on the
    // observation fields; prefer it for market-specific values when present.
    const merged = Object.assign({}, bond || {}, pickMarketFields(market));
    renderBond(merged, analytics || {});
}

// Only market-observation fields are taken from the market endpoint; master
// data (name, ISIN, coupon, maturity…) stays authoritative from /{isin}.
const MARKET_FIELDS = [
    "price", "clean_price", "dirty_price", "ytm",
    "bid_price", "bid_yield", "offer_price", "offer_yield",
    "last_traded_price", "last_traded_yield",
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

function renderBond(bond, analytics) {
    if (!bond) {
        $("ba-results").classList.add("hidden");
        $("ba-detail-empty").classList.remove("hidden");
        return;
    }

    // Source indicator (backend-provided source/freshness only)
    const badge = $("ba-source-badge");
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

    // C. Summary card
    $("ba-summary-name").textContent = bond.security_name || bond.isin || "Unnamed security";
    $("ba-summary-meta").innerHTML = [
        bond.instrument_type ? `<span>${escapeHtml(bond.instrument_type)}</span>` : "",
        bond.issuer ? `<span>${escapeHtml(bond.issuer)}</span>` : "",
    ].join("");

    // T-Bills are zero-coupon: coupon/frequency shown as neutral N/A values.
    const isTBill = (bond.instrument_type || "").toUpperCase() === "T-BILL";
    const couponLabel = isTBill ? "N/A (zero-coupon)" : formatPct(bond.coupon_rate);
    const freqLabel = isTBill ? "N/A (zero-coupon)" : couponFrequencyLabel(bond.coupon_frequency);

    $("ba-summary-grid").innerHTML = [
        detailItem("ISIN", bond.isin, true),
        detailItem("Instrument Type", bond.instrument_type),
        detailItem("Issuer", bond.issuer),
        detailItem("Maturity Date", formatDate(bond.maturity_date)),
        detailItem("Coupon Rate", couponLabel),
        detailItem("Coupon Frequency", freqLabel),
        detailItem("Clean Price", formatNum(bond.clean_price != null ? bond.clean_price : bond.price)),
        detailItem("Market YTM", formatPct(bond.ytm)),
    ].join("");

    // D. Analytics KPIs
    renderKpis(analytics);

    // E. Cash flows
    renderCashFlows(analytics.cash_flows);

    // F. Details / methodology
    $("ba-details-grid").innerHTML = [
        detailItem("Settlement Date", formatDate(analytics.settlement_date)),
        detailItem("Day-Count Convention", analytics.day_count_convention),
        detailItem("Coupon Frequency", freqLabel),
        detailItem("Face Value", formatNum(bond.face_value)),
        detailItem("Callable", bond.callable === true ? "Yes" : (bond.callable === false ? "No" : "N/A")),
        detailItem("Puttable", bond.puttable === true ? "Yes" : (bond.puttable === false ? "No" : "N/A")),
    ].join("");

    const notes = Array.isArray(analytics.notes) ? analytics.notes : [];
    $("ba-notes").innerHTML = notes.length
        ? notes.map((n) => `<li>${escapeHtml(n)}</li>`).join("")
        : "";
}


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

function kpiCard(key, label, value, muted) {
    const help = KPI_HELP[key] || "";
    const helpHtml = help
        ? `<span class="tooltip-trigger" tabindex="0" role="button" aria-label="More information about ${escapeAttr(label)}"><span class="tooltip-content">${escapeHtml(help)}</span>ⓘ</span>`
        : "";
    return `<div class="ba-kpi">
        <span class="ba-kpi-value${muted ? " is-muted" : ""}">${escapeHtml(na(value))}</span>
        <span class="ba-kpi-label">${escapeHtml(label)}${helpHtml}</span>
    </div>`;
}

function renderKpis(a) {
    $("ba-kpi-grid").innerHTML = [
        kpiCard("current_yield", "Current Yield", formatPct(a.current_yield), a.current_yield == null),
        kpiCard("calculated_ytm", "Calculated YTM", formatPct(a.calculated_ytm), a.calculated_ytm == null),
        kpiCard("market_ytm", "Market YTM", formatPct(a.market_ytm), a.market_ytm == null),
        kpiCard("accrued_interest", "Accrued Interest", formatNum(a.accrued_interest), a.accrued_interest == null),
        kpiCard("macaulay_duration", "Macaulay Duration", formatNum(a.macaulay_duration), a.macaulay_duration == null),
        kpiCard("modified_duration", "Modified Duration", formatNum(a.modified_duration), a.modified_duration == null),
        kpiCard("convexity", "Convexity", formatNum(a.convexity), a.convexity == null),
        kpiCard("dv01", "DV01", formatNum(a.dv01), a.dv01 == null),
    ].join("");
}

function renderCashFlows(cashFlows) {
    const wrap = $("ba-cashflow-wrap");
    const rows = Array.isArray(cashFlows) ? cashFlows : [];
    if (!rows.length) {
        wrap.innerHTML = '<p class="ba-section-sub">No cash-flow schedule available for this bond.</p>';
        return;
    }

    // Values are rendered exactly as returned by the analytics endpoint;
    // nothing is recomputed in the browser.
    wrap.innerHTML = `<table class="ba-table">
        <thead>
            <tr>
                <th>Payment Date</th>
                <th class="ba-num">Coupon</th>
                <th class="ba-num">Principal</th>
                <th class="ba-num">Total Cash Flow</th>
            </tr>
        </thead>
        <tbody>
            ${rows.map((r) => `<tr>
                <td>${escapeHtml(formatDate(r.date))}</td>
                <td class="ba-num">${escapeHtml(formatNum(r.coupon))}</td>
                <td class="ba-num">${escapeHtml(formatNum(r.principal))}</td>
                <td class="ba-num">${escapeHtml(formatNum(r.total))}</td>
            </tr>`).join("")}
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
// Event wiring & init
// ---------------------------------------------------------------------------

function init() {
    // Initial/empty state before a bond is selected.
    $("ba-detail-empty").classList.remove("hidden");

    const searchInput = $("ba-search-input");
    const typeFilter = $("ba-type-filter");
    const bondList = $("ba-bond-list");

    if (searchInput && typeFilter) {
        // Debounced free-text search (shared core/utils debounce).
        const debouncedSearch = utils.debounce(searchBonds, 300);
        searchInput.addEventListener("input", debouncedSearch);
        typeFilter.addEventListener("change", searchBonds);
    }

    if (bondList) {
        bondList.addEventListener("click", (e) => {
            const btn = e.target.closest(".ba-bond-item");
            if (btn && btn.dataset.isin) {
                selectBond(btn.dataset.isin);
            }
        });
    }

    searchBonds();
}

init();

