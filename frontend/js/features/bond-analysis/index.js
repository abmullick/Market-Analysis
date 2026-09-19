// Bond Analysis — production UI slice.
// Wires the page to the EXISTING bond APIs (no new backend, no client-side
// financial computation):
//   GET /api/bonds                       — list/search government bonds
//   GET /api/bonds/corporate             — list/search corporate bonds (CDSL)
//   GET /api/bonds/{isin}                — government bond by ISIN
//   GET /api/bonds/{isin}/market         — market observation
//   GET /api/bonds/{isin}/analytics      — computed analytics
//   GET /api/bonds/corporate/{isin}      — corporate bond by ISIN
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
    selectedIsin: null,
    universe: "government", // active universe: "government" | "corporate"
    universes: {            // per-universe pagination state (lazy-loaded)
        government: { page: 1, total: 0, visited: true },
        corporate:  { page: 1, total: 0, visited: false },
    },
    page: 1,            // 1-based selector page (ACTIVE universe)
    total: 0,           // total bonds matching the current query (ACTIVE universe)
    sortBy: "maturity_date",
    sortDir: "asc",
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
    const isCorporate = state.universe === "corporate";
    const type = isCorporate ? "" : $("ba-type-filter").value;
    // The data-source selector (All Sources | CCIL | NSE | RBI) is a
    // government-only control: "All Sources" (empty value) adds no parameter,
    // and the corporate universe never sends one.
    const sourceFilter = $("ba-source-filter");
    const source = isCorporate || !sourceFilter ? "" : sourceFilter.value;

    // Server-side pagination + sorting (backend-provided values only). The
    // corporate universe is a separate CDSL endpoint and does not support the
    // government instrument_type/source filters, so they are never sent there.
    const params = new URLSearchParams();
    if (q) params.set("search", q);
    if (type) params.set("instrument_type", type);
    if (source) params.set("source", source);
    params.set("sort_by", state.sortBy);
    params.set("sort_dir", state.sortDir);
    params.set("limit", String(PAGE_SIZE));
    params.set("offset", String((state.page - 1) * PAGE_SIZE));
    params.set("envelope", "true");

    setSelectorStatus('<span class="pb-analysis-loading"><span class="pb-spinner" aria-hidden="true"></span><span>Searching bonds&hellip;</span></span>');
    $("ba-no-results").classList.add("hidden");

    let data;
    try {
        data = await api.get(`${isCorporate ? "/bonds/corporate" : "/bonds"}?${params.toString()}`);
    } catch (err) {
        if (seq !== state.searchSeq) return;
        setSelectorStatus("");
        $("ba-no-results").classList.add("hidden");
        $("ba-bond-list").innerHTML = "";
        renderPagination(0);
        $("ba-result-count").textContent = "";
        showError(`Could not load bonds: ${err && err.message ? err.message : err}`);
        return;
    }

    if (seq !== state.searchSeq) return; // a newer search superseded this one
    setSelectorStatus("");
    hideError();

    // Envelope response: {items, total, limit, offset}. A plain array is also
    // accepted defensively, though the page always requests the envelope.
    const list = Array.isArray(data) ? data : (data && Array.isArray(data.items) ? data.items : []);
    state.total = Array.isArray(data) ? list.length : (data && typeof data.total === "number" ? data.total : list.length);

    // Header chip — the universe size, not the page size.
    $("ba-range-chip").textContent = state.total
        ? `Showing 1–${Math.min(PAGE_SIZE, state.total)} of ${state.total}`
        : "";
    $("ba-result-count").textContent = state.total
        ? `${state.total} bond${state.total === 1 ? "" : "s"}`
        : "";

    $("ba-no-results").classList.toggle("hidden", list.length > 0);

    // Rows without an ISIN (some CCIL Market Watch entries) cannot be loaded
    // via /api/bonds/{isin}, so they are shown but not selectable.
    $("ba-bond-list").innerHTML = list.map((b) => {
        const isin = b.isin || "";
        const name = b.security_name || isin || "Unnamed security";
        // Government rows keep using the market YTM exactly as before;
        // corporate (CDSL) rows may fall back to the weighted-average yield.
        const ytmValue = b.ytm != null ? b.ytm
            : (isCorporate && b.weighted_average_yield != null ? b.weighted_average_yield : null);
        const ytm = ytmValue != null ? formatPct(ytmValue) : "N/A";
        const meta = [
            isin ? `<span class="ba-bond-meta-isin">${escapeHtml(isin)}</span>` : '<span>No ISIN reported</span>',
            b.instrument_type ? `<span>${escapeHtml(b.instrument_type)}</span>` : "",
            b.credit_rating ? `<span>${escapeHtml(b.credit_rating)}</span>` : "",
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
        const selected = isin === state.selectedIsin ? " selected" : "";
        return `<li><button type="button" class="ba-bond-item${selected}" data-isin="${escapeAttr(isin)}">${inner}</button></li>`;
    }).join("");

    renderPagination(state.total);
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
    const corpFilter = $("ba-corporate-type-filter");
    if (govFilter) govFilter.classList.toggle("hidden", isCorporate);
    if (corpFilter) corpFilter.classList.toggle("hidden", !isCorporate);
    // The data-source selector (All Sources | CCIL | NSE | RBI) is likewise a
    // government-only control.
    const sourceFilter = $("ba-source-filter");
    if (sourceFilter) sourceFilter.classList.toggle("hidden", isCorporate);
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
    state.selectedIsin = null;

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
    $("ba-section-header-badge").textContent = "";

    // Reset section collapse states when a new bond is selected
    const sections = document.querySelectorAll(".ba-section");
    sections.forEach((section) => {
        const toggle = section.querySelector(".ba-section-toggle");
        const body = section.querySelector(".ba-section-body");
        if (toggle && body) {
            // Bond Summary: OPEN by default, others: CLOSED by default
            const sectionId = section.getAttribute("data-section");
            if (sectionId === "summary") {
                toggle.setAttribute("aria-expanded", "true");
                body.classList.remove("collapsed");
                body.classList.add("expanded");
                if (toggle.querySelector(".ba-chevron")) {
                    toggle.querySelector(".ba-chevron").style.transform = "rotate(180deg)";
                }
            } else {
                toggle.setAttribute("aria-expanded", "false");
                body.classList.add("collapsed");
                body.classList.remove("expanded");
                if (toggle.querySelector(".ba-chevron")) {
                    toggle.querySelector(".ba-chevron").style.transform = "rotate(0deg)";
                }
            }
        }
    });

    // Market YTM (source observation) and Calculated YTM (analytics) come
    // from their own endpoints; the frontend never derives one from the other.
    // Government bonds use the three government endpoints. Corporate bonds
    // use the corporate detail endpoint plus the corporate analytics
    // endpoint (analytics computed server-side from CDSL-validated terms);
    // a failed analytics call degrades to the neutral N/A state.
    let bond, market, analytics;
    try {
        if (state.universe === "corporate") {
            bond = await api.get(`/bonds/corporate/${encodeURIComponent(isin)}`);
            market = null;
            analytics = {};
        } else {
            [bond, market, analytics] = await Promise.all([
                api.get(`/bonds/${encodeURIComponent(isin)}`),
                api.get(`/bonds/${encodeURIComponent(isin)}/market`),
                api.get(`/bonds/${encodeURIComponent(isin)}/analytics`),
            ]);
        }
        if (state.universe === "corporate") {
            try {
                analytics = await api.get(
                    `/bonds/corporate/${encodeURIComponent(isin)}/analytics`
                );
            } catch (_aErr) {
                analytics = {};
            }
        }
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

function renderBond(bond, analytics) {
    if (!bond) {
        $("ba-results").classList.add("hidden");
        $("ba-detail-empty").classList.remove("hidden");
        return;
    }

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

    // Corporate records (CDSL) render the fields the corporate endpoint
    // actually supplies — LTP/VWAP/weighted-average yield — using their real
    // names; the government rendering below is unchanged.
    const isCorporate = state.universe === "corporate";
    $("ba-summary-grid").innerHTML = isCorporate ? [
        detailItem("ISIN", bond.isin, true),
        detailItem("Instrument Type", bond.instrument_type),
        detailItem("Issuer", bond.issuer),
        detailItem("Credit Rating", bond.credit_rating),
        detailItem("Maturity Date", formatDate(bond.maturity_date)),
        detailItem("Coupon Rate", couponLabel),
        detailItem("LTP", formatNum(bond.last_traded_price != null ? bond.last_traded_price : bond.price)),
        detailItem("VWAP", formatNum(bond.weighted_average_price)),
        detailItem("Weighted Avg Yield", formatPct(bond.weighted_average_yield)),
    ].join("") : [
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
    renderCashFlows(analytics);

    // F. Details / methodology — government rows keep the analytics-backed
    // fields; corporate rows show the CDSL issuance/trade fields instead.
    // Analytics sections that cannot be populated for corporate records stay
    // at their neutral N/A/empty state (no client-side computation).
    $("ba-details-grid").innerHTML = isCorporate ? [
        detailItem("Trade Date", formatDate(bond.trade_date)),
        detailItem("Exchange", bond.exchange),
        detailItem("Issue Date", formatDate(bond.issue_date)),
        detailItem("Issue Size (Cr.)", formatNum(bond.issue_size)),
        detailItem("Issue Price", formatNum(bond.issue_price)),
        detailItem("Mode of Issuance", bond.mode_of_issuance),
        detailItem("Coupon Frequency", freqLabel),
    ].join("") : [
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

function kpiCard(key, label, value, muted, unavailableReason) {
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
    return `<div class="ba-kpi">
        <span class="ba-kpi-value${muted ? " is-muted" : ""}">${escapeHtml(na(value))}${naHtml}</span>
        <span class="ba-kpi-label">${escapeHtml(label)}${helpHtml}</span>
    </div>`;
}

function renderKpis(a) {
    const reasons = (a && a.unavailable_metrics) || {};
    $("ba-kpi-grid").innerHTML = [
        kpiCard("current_yield", "Current Yield", formatPct(a.current_yield), a.current_yield == null, reasons.current_yield),
        kpiCard("calculated_ytm", "Calculated YTM", formatPct(a.calculated_ytm), a.calculated_ytm == null, reasons.calculated_ytm),
        kpiCard("market_ytm", "Market YTM", formatPct(a.market_ytm), a.market_ytm == null, reasons.market_ytm),
        kpiCard("accrued_interest", "Accrued Interest", formatNum(a.accrued_interest), a.accrued_interest == null, reasons.accrued_interest),
        kpiCard("macaulay_duration", "Macaulay Duration", formatNum(a.macaulay_duration), a.macaulay_duration == null, reasons.macaulay_duration),
        kpiCard("modified_duration", "Modified Duration", formatNum(a.modified_duration), a.modified_duration == null, reasons.modified_duration),
        kpiCard("convexity", "Convexity", formatNum(a.convexity), a.convexity == null, reasons.convexity),
        kpiCard("dv01", "DV01", formatNum(a.dv01), a.dv01 == null, reasons.dv01),
    ].join("");
}

function renderCashFlows(analytics) {
    const wrap = $("ba-cashflow-wrap");
    const a = analytics || {};
    const rows = Array.isArray(a.cash_flows) ? a.cash_flows : [];
    if (!rows.length) {
        // Explain the empty state: which inputs are missing and, when known,
        // what additional data source would provide them.
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

    // Corporate filter area (currently "All" only — same shape as the
    // government filter for the future corporate filter controls).
    const corpFilter = $("ba-corporate-type-filter");
    if (corpFilter) {
        corpFilter.addEventListener("change", () => {
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
            const btn = e.target.closest(".ba-bond-item");
            if (btn && btn.dataset.isin) {
                selectBond(btn.dataset.isin);
            }
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

init();

