import { api } from "../../core/api.js";
import { showLoading, hideLoading } from "../../components/loading.js";
import { openFundDetail } from "./fund-detail.js";
import { renderRiskReturnChart } from "./comparison/risk-return.js";
import { renderDrawdownChart } from "./comparison/drawdown.js";
import { renderRollingReturnsChart } from "./comparison/rolling-returns.js";
import { renderNavHistoryChart } from "./comparison/nav-history.js";
import { renderPerformanceSummary } from "./comparison/performance-summary.js";

const PRESETS = {
    best_overall: {
        label: "Best Overall",
        criteria: [
            { name: "1Y_return", weight: 25 },
            { name: "3Y_cagr", weight: 25 },
            { name: "sharpe_ratio", weight: 20 },
            { name: "sortino_ratio", weight: 15 },
            { name: "consistency", weight: 15 },
        ],
    },
    highest_returns: {
        label: "Highest Returns",
        criteria: [
            { name: "1Y_return", weight: 30 },
            { name: "3Y_cagr", weight: 30 },
            { name: "5Y_cagr", weight: 25 },
            { name: "10Y_cagr", weight: 15 },
        ],
    },
    lowest_risk: {
        label: "Lowest Risk",
        criteria: [
            { name: "volatility", weight: 30 },
            { name: "maximum_drawdown", weight: 25 },
            { name: "downside_deviation", weight: 25 },
            { name: "sharpe_ratio", weight: 20 },
        ],
    },
    best_consistency: {
        label: "Best Consistency",
        criteria: [
            { name: "consistency", weight: 40 },
            { name: "sharpe_ratio", weight: 25 },
            { name: "sortino_ratio", weight: 20 },
            { name: "3Y_cagr", weight: 15 },
        ],
    },
    custom: {
        label: "Custom",
        criteria: [
            { name: "1Y_return", weight: 33.3 },
            { name: "3Y_cagr", weight: 33.3 },
            { name: "sharpe_ratio", weight: 33.4 },
        ],
    },
};

const CRITERIA_META = {
    "1Y_return": {
        label: "1Y Return",
        direction: "higher",
        description: "Simple return over the past year",
        tooltip: "Actual = the fund's 1-year return (percentage). Score = its normalized 0–100 ranking score relative to other funds in this category.",
    },
    "3Y_cagr": {
        label: "3Y CAGR",
        direction: "higher",
        description: "3-year compound annual growth rate",
        tooltip: "Actual = annualized growth rate over 3 years (percentage). Score = its normalized 0–100 ranking score relative to other funds in this category.",
    },
    "5Y_cagr": {
        label: "5Y CAGR",
        direction: "higher",
        description: "5-year compound annual growth rate",
        tooltip: "Actual = annualized growth rate over 5 years (percentage). Score = its normalized 0–100 ranking score relative to other funds in this category.",
    },
    "10Y_cagr": {
        label: "10Y CAGR",
        direction: "higher",
        description: "10-year compound annual growth rate",
        tooltip: "Actual = annualized growth rate over 10 years (percentage). Score = its normalized 0–100 ranking score relative to other funds in this category.",
    },
    "sharpe_ratio": {
        label: "Sharpe Ratio",
        direction: "higher",
        description: "Risk-adjusted return (higher is better)",
        tooltip: "Actual = risk-adjusted return ratio (not a percentage). Higher means better return per unit of total risk. Score = its normalized 0–100 ranking score relative to other funds in this category.",
    },
    "sortino_ratio": {
        label: "Sortino Ratio",
        direction: "higher",
        description: "Return vs downside risk (higher is better)",
        tooltip: "Actual = return relative to downside risk only (not a percentage). Higher means better return per unit of downside risk. Score = its normalized 0–100 ranking score relative to other funds in this category.",
    },
    "volatility": {
        label: "Volatility",
        direction: "lower",
        description: "Annualized standard deviation (lower is better)",
        tooltip: "Actual = annualized volatility (percentage). Lower means more stable returns. Score = its normalized 0–100 ranking score (inverted: lower volatility gets a higher score).",
    },
    "maximum_drawdown": {
        label: "Max Drawdown",
        direction: "lower",
        description: "Largest peak-to-trough decline (lower is better)",
        tooltip: "Actual = largest peak-to-trough decline in NAV history (percentage). Lower means smaller losses from peaks. Score = its normalized 0–100 ranking score (inverted: smaller drawdown gets a higher score).",
    },
    "downside_deviation": {
        label: "Downside Deviation",
        direction: "lower",
        description: "Volatility of negative returns (lower is better)",
        tooltip: "Actual = volatility of negative returns only (percentage). Lower means fewer/smaller downside moves. Score = its normalized 0–100 ranking score (inverted: lower deviation gets a higher score).",
    },
    "consistency": {
        label: "Consistency",
        direction: "higher",
        description: "1Y rolling positive-period percentage (higher is better)",
        tooltip: "Actual = percentage of rolling 1-year windows with positive returns. Higher means more consistently positive returns. Score = its normalized 0–100 ranking score relative to other funds in this category.",
    },
};

const CRITERIA_HELP = {
    "1Y_return": "The fund's return over the past year. Higher is generally better.",
    "3Y_cagr": "The annualized return over three years. Higher is generally better.",
    "5Y_cagr": "The annualized return over five years. Higher is generally better.",
    "10Y_cagr": "The annualized return over ten years. Higher is generally better.",
    sharpe_ratio: "Measures return relative to volatility/risk. Higher generally means better risk-adjusted returns.",
    sortino_ratio: "Measures return relative to downside risk. Higher generally means better downside-risk-adjusted returns.",
    volatility: "Measures how much returns fluctuate. Lower generally means more stable returns.",
    maximum_drawdown: "The largest peak-to-trough decline in the fund's NAV history. A smaller drawdown is generally better.",
    downside_deviation: "Measures the variability of negative/downside returns. Lower generally indicates less downside variability.",
    consistency: "Percentage of 1-year rolling windows with positive returns. Higher means more consistently positive returns.",
};

const TOOLTIPS = {
    score: "Normalized ranking score from 0 to 100, based on this fund's metric value relative to all other eligible funds in the selected category.",
    overall_score: "Weighted combination of all selected metric scores (0–100), according to the active preset weights. Higher means better overall ranking.",
};

const FILTER_META = {
    overall_score: { label: "Overall Score", unit: "score", step: "1" },
    "1Y_return": { label: "1Y Return", unit: "percent", step: "0.1" },
    "3Y_cagr": { label: "3Y CAGR", unit: "percent", step: "0.1" },
    "5Y_cagr": { label: "5Y CAGR", unit: "percent", step: "0.1" },
    "10Y_cagr": { label: "10Y CAGR", unit: "percent", step: "0.1" },
    sharpe_ratio: { label: "Sharpe Ratio", unit: "ratio", step: "0.01" },
    sortino_ratio: { label: "Sortino Ratio", unit: "ratio", step: "0.01" },
    volatility: { label: "Volatility", unit: "percent", step: "0.1" },
    maximum_drawdown: { label: "Max Drawdown", unit: "percent", step: "0.1" },
    downside_deviation: { label: "Downside Deviation", unit: "percent", step: "0.1" },
    consistency: { label: "Consistency", unit: "percent", step: "0.1" },
    aum_cr: { label: "AUM (Cr)", unit: "currency", step: "100" },
    nav: { label: "Latest NAV", unit: "currency", step: "0.01" },
    data_points: { label: "Data Points", unit: "integer", step: "1" },
};

function getFilterValue(ranking, filterKey) {
    if (filterKey === "overall_score") {
        return ranking.overall_score;
    }
    if (filterKey === "aum_cr") {
        return ranking.aum_cr;
    }
    if (filterKey === "nav") {
        return ranking.nav;
    }
    if (filterKey === "data_points") {
        return ranking.data_points;
    }
    const cs = (ranking.criteria_scores || []).find(c => c.criterion === filterKey);
    return cs ? cs.raw_value : null;
}

function convertFilterInputToBackend(value, unit) {
    if (unit === "percent") {
        return value / 100;
    }
    return value;
}

let currentPreset = "best_overall";
let currentCategories = [];  // Changed from currentCategory to currentCategories (array)
let categories = [];
let currentRankings = [];
let filteredRankings = [];
let selectedFunds = new Set();
let isComparisonView = false;
let screeningFilters = [];

const MAX_COMPARE = 5;
const MIN_COMPARE = 2;

const SCREENER_FIELDS = [
    { key: "amc", label: "AMC", type: "categorical" },
    { key: "aum_cr", label: "AUM (Cr)", type: "numeric", unit: "Cr" },
    { key: "first_nav_date", label: "First NAV Date", type: "date" },
];

const SCREENER_OPERATORS = [
    { key: "gt", label: ">" },
    { key: "gte", label: "≥" },
    { key: "lt", label: "<" },
    { key: "lte", label: "≤" },
    { key: "between", label: "Between" },
];

const COMPARE_METRICS = [
    { key: "1Y_return", label: "1Y Return", unit: "percent", higherBetter: true },
    { key: "3Y_cagr", label: "3Y CAGR", unit: "percent", higherBetter: true },
    { key: "5Y_cagr", label: "5Y CAGR", unit: "percent", higherBetter: true },
    { key: "10Y_cagr", label: "10Y CAGR", unit: "percent", higherBetter: true },
    { key: "sharpe_ratio", label: "Sharpe Ratio", unit: "ratio", higherBetter: true },
    { key: "sortino_ratio", label: "Sortino Ratio", unit: "ratio", higherBetter: true },
    { key: "volatility", label: "Volatility", unit: "percent", higherBetter: false },
    { key: "maximum_drawdown", label: "Max Drawdown", unit: "percent", higherBetter: false },
    { key: "downside_deviation", label: "Downside Deviation", unit: "percent", higherBetter: false },
    { key: "consistency", label: "Consistency", unit: "percent", higherBetter: true },
];

export function initMutualFundAnalysis() {
    const container = document.getElementById("mutual-fund-content");
    if (!container) return;

    loadCategories();
}

async function loadCategories() {
    const filtersContainer = document.getElementById("ranking-filters");
    if (!filtersContainer) return;

    showLoading(filtersContainer, "Loading categories...");
    try {
        const response = await api.get("/mutual-funds/categories");
        categories = response.categories || [];
        hideLoading(filtersContainer);
        buildPageHeader();
        try {
            buildControls();
        } catch (e) {
            console.error("buildControls error:", e);
            filtersContainer.innerHTML = `<div class="empty-state"><p>Error building controls: ${e.message}</p></div>`;
        }
    } catch (error) {
        hideLoading(filtersContainer);
        filtersContainer.innerHTML = `<div class="empty-state"><p>Failed to load categories: ${error.message}</p></div>`;
    }
}

function buildPageHeader() {
    const container = document.getElementById("mutual-fund-content");
    if (!container) return;
    const existingHeader = container.querySelector(".mf-page-header");
    if (existingHeader) existingHeader.remove();
    const header = document.createElement("div");
    header.className = "mf-page-header";
    header.innerHTML = `
        <div class="mf-page-header-text">
            <h1 class="mf-page-title">Mutual Fund Screener</h1>
            <p class="mf-page-subtitle">Filter, score, and rank mutual funds using normalized multi-metric criteria. Select funds to compare side-by-side or open a fund to view its full research profile.</p>
        </div>
        <div class="mf-page-header-stat" id="mf-page-header-stat" hidden>
            <span class="mf-page-header-stat-value" id="mf-page-header-stat-value">0</span>
            <span class="mf-page-header-stat-label">funds matching current filters</span>
        </div>
    `;
    container.insertBefore(header, container.firstChild);
}

function updateMatchingFundsCount(count) {
    const stat = document.getElementById("mf-page-header-stat");
    const numberEl = document.getElementById("mf-page-header-stat-value");
    if (!stat || !numberEl) return;
    if (count == null || count === 0) {
        stat.hidden = true;
    } else {
        stat.hidden = false;
        numberEl.textContent = count.toLocaleString();
    }
}

function buildControls() {
    const filtersContainer = document.getElementById("ranking-filters");
    const screenerContainer = document.getElementById("ranking-screener");
    const presetContainer = document.getElementById("ranking-preset");
    const criteriaContainer = document.getElementById("ranking-criteria");
    const methodologyContainer = document.getElementById("ranking-methodology");

    if (!filtersContainer || !screenerContainer || !presetContainer || !criteriaContainer || !methodologyContainer) {
        console.error("Missing containers:", {
            filters: !!filtersContainer,
            screener: !!screenerContainer,
            preset: !!presetContainer,
            criteria: !!criteriaContainer,
            methodology: !!methodologyContainer,
        });
        return;
    }

    try {
        filtersContainer.innerHTML = `
            <div class="screener-group">
                <div class="screener-group-heading">
                    <span class="screener-group-title">Fund</span>
                    <span class="screener-group-subtitle">Category &amp; AMC</span>
                </div>
                <div class="filter-group">
                    <label for="category-trigger">Category</label>
                    <div class="category-picker" id="category-picker">
                        <button type="button" class="category-picker-trigger" id="category-trigger" aria-haspopup="listbox" aria-expanded="false">
                            <span class="category-picker-value" id="category-value">All Categories</span>
                            <span class="category-picker-arrow">
                                <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5">
                                    <path d="M3 4.5L6 7.5L9 4.5"/>
                                </svg>
                            </span>
                        </button>
                        <div class="category-picker-dropdown" id="category-dropdown" role="listbox" hidden>
                            <div class="category-picker-search">
                                <svg class="category-picker-search-icon" width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5">
                                    <circle cx="6" cy="6" r="4.5"/>
                                    <path d="M9.5 9.5L13 13"/>
                                </svg>
                                <input type="text" class="category-picker-search-input" id="category-search" placeholder="Search categories..." autocomplete="off">
                                <button type="button" class="category-picker-search-clear" id="category-search-clear" hidden>
                                    <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5">
                                        <path d="M3 3L9 9M9 3L3 9"/>
                                    </svg>
                                </button>
                            </div>
                            <div class="category-picker-actions">
                                <button type="button" class="category-picker-action" id="category-select-all">Select All</button>
                                <button type="button" class="category-picker-action" id="category-clear-all">Clear</button>
                            </div>
                            <div class="category-picker-list" id="category-list"></div>
                            <div class="category-picker-footer">
                                <span class="category-picker-count" id="category-count">0 selected</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;

        presetContainer.innerHTML = `
            <div class="screener-group">
                <div class="screener-group-heading">
                    <span class="screener-group-title">Preset</span>
                    <span class="screener-group-subtitle">Quick weight profiles</span>
                </div>
                <div class="preset-grid" id="preset-grid"></div>
            </div>
        `;

        const presetGrid = document.getElementById("preset-grid");
        if (presetGrid) {
            const presetEntries = Object.entries(PRESETS);
            presetEntries.forEach(([key, preset]) => {
                const btn = document.createElement("button");
                btn.type = "button";
                btn.className = `preset-btn${key === currentPreset ? " active" : ""}${key === "custom" ? " preset-btn-wide" : ""}`;
                btn.dataset.preset = key;
                btn.textContent = preset.label;
                btn.addEventListener("click", () => {
                    currentPreset = key;
                    document.querySelectorAll(".preset-btn").forEach(b => b.classList.remove("active"));
                    btn.classList.add("active");
                    applyPreset(key);
                });
                presetGrid.appendChild(btn);
            });
        }

        initCategoryMultiSelect();

        buildScreener(screenerContainer);
        buildCriteriaList(criteriaContainer);
        buildMethodology(methodologyContainer);

        document.getElementById("run-ranking").addEventListener("click", runRanking);

        applyPreset(currentPreset);
    } catch (e) {
        console.error("buildControls error:", e);
        filtersContainer.innerHTML = `<div class="empty-state"><p>Error building controls: ${e.message}</p></div>`;
    }
}

function buildScreener(container) {
    if (!container) return;
    container.innerHTML = `
        <div class="screener screener-group">
            <div class="screener-group-heading screener-group-heading-row">
                <div>
                    <span class="screener-group-title">Fund Screener</span>
                    <span class="screener-group-subtitle">AUM, AMC &amp; inception filters</span>
                </div>
                <span class="screener-count" id="screener-count"></span>
            </div>
            <button type="button" class="screener-toggle" id="screener-toggle" aria-expanded="false">
                <span class="screener-toggle-label">${screeningFilters.length > 0 ? "Edit filters" : "Add filter"}</span>
                <span class="screener-toggle-icon">&#9662;</span>
            </button>
            <div class="screener-body" id="screener-body" hidden>
                <div class="screener-help">
                    <div class="screener-help-title">How to use these filters</div>
                    <ul>
                        <li><strong>AUM</strong> — Filters funds by total Assets Under Management. Example: AUM &ge; &#8377;20,000 Cr includes only funds with at least &#8377;20,000 Cr in total AUM.</li>
                        <li><strong>First NAV Date</strong> — Filters by the earliest available NAV date. Useful for finding funds with a longer history. Example: First NAV Date &ge; 2015 includes funds whose NAV history begins on or after 2015.</li>
                        <li><strong>AMC</strong> — Enter multiple AMC names separated by commas. Matching is case-insensitive and substring-based. Example: "SBI, Axis" matches AMC names containing "SBI" or "Axis".</li>
                    </ul>
                </div>
                <div class="screener-add">
                    <select id="screener-field" class="screener-select">
                        ${SCREENER_FIELDS.map(f => `<option value="${f.key}">${f.label}</option>`).join("")}
                    </select>
                    <button type="button" class="screener-add-btn" id="screener-add-btn">Add Filter</button>
                </div>
                <div class="screener-filters" id="screener-filters"></div>
                <div class="screener-footer">
                    <button type="button" class="btn-text" id="screener-clear">Clear All</button>
                    <span class="screener-result" id="screener-result"></span>
                </div>
            </div>
        </div>
    `;

    const toggle = document.getElementById("screener-toggle");
    const body = document.getElementById("screener-body");
    const toggleIcon = toggle ? toggle.querySelector(".screener-toggle-icon") : null;
    const addBtn = document.getElementById("screener-add-btn");
    const clearBtn = document.getElementById("screener-clear");

    if (toggle && body && toggleIcon) {
        toggle.addEventListener("click", () => {
            const isExpanded = !body.hidden;
            body.hidden = isExpanded;
            toggleIcon.style.transform = isExpanded ? "" : "rotate(180deg)";
        });
    }

    if (addBtn) {
        addBtn.addEventListener("click", () => {
            const fieldSelect = document.getElementById("screener-field");
            if (!fieldSelect) return;
            const fieldKey = fieldSelect.value;
            const field = SCREENER_FIELDS.find(f => f.key === fieldKey);
            if (!field) return;

            const filter = {
                field: fieldKey,
                operator: field.type === "categorical" ? "in" : "gte",
                value: field.type === "numeric" ? 0 : "",
                values: field.type === "categorical" ? [] : undefined,
            };
            screeningFilters.push(filter);
            renderScreenerFilters();
        });
    }

    if (clearBtn) {
        clearBtn.addEventListener("click", () => {
            screeningFilters = [];
            renderScreenerFilters();
        });
    }

    renderScreenerFilters();
}

function renderScreenerFilters() {
    const container = document.getElementById("screener-filters");
    if (!container) return;
    container.innerHTML = "";

    screeningFilters.forEach((filter, idx) => {
        const field = SCREENER_FIELDS.find(f => f.key === filter.field);
        if (!field) return;

        const row = document.createElement("div");
        row.className = "screener-filter-row";
        row.dataset.idx = idx;

        if (field.type === "categorical") {
            row.innerHTML = `
                <span class="screener-filter-label">${field.label}</span>
                <input type="text" class="screener-filter-input" placeholder="Enter values separated by commas" value="${(filter.values || []).join(", ")}">
                <button type="button" class="screener-filter-remove" data-idx="${idx}">&times;</button>
            `;
            const input = row.querySelector(".screener-filter-input");
            input.addEventListener("change", () => {
                filter.values = input.value.split(",").map(v => v.trim()).filter(v => v);
                updateScreenerResult();
            });
        } else if (field.type === "date") {
            row.innerHTML = `
                <span class="screener-filter-label">${field.label}</span>
                <select class="screener-filter-op">
                    ${SCREENER_OPERATORS.map(op => `<option value="${op.key}" ${op.key === filter.operator ? "selected" : ""}>${op.label}</option>`).join("")}
                </select>
                <input type="date" class="screener-filter-date" value="${filter.value || ""}">
                ${filter.operator === "between" ? `<input type="date" class="screener-filter-date-max" value="${filter.value_max || ""}">` : ""}
                <button type="button" class="screener-filter-remove" data-idx="${idx}">&times;</button>
            `;
            const opSelect = row.querySelector(".screener-filter-op");
            const dateInput = row.querySelector(".screener-filter-date");
            const dateMaxInput = row.querySelector(".screener-filter-date-max");

            opSelect.addEventListener("change", () => {
                filter.operator = opSelect.value;
                renderScreenerFilters();
            });

            dateInput.addEventListener("change", () => {
                filter.value = dateInput.value;
                updateScreenerResult();
            });

            if (dateMaxInput) {
                dateMaxInput.addEventListener("change", () => {
                    filter.value_max = dateMaxInput.value;
                    updateScreenerResult();
                });
            }
        } else {
            row.innerHTML = `
                <span class="screener-filter-label">${field.label}</span>
                <select class="screener-filter-op">
                    ${SCREENER_OPERATORS.map(op => `<option value="${op.key}" ${op.key === filter.operator ? "selected" : ""}>${op.label}</option>`).join("")}
                </select>
                <input type="number" class="screener-filter-value" value="${filter.value || ""}" step="0.01">
                ${filter.operator === "between" ? `<input type="number" class="screener-filter-value-max" value="${filter.value_max || ""}" step="0.01" placeholder="Max">` : ""}
                <span class="screener-filter-unit">${field.unit || ""}</span>
                <button type="button" class="screener-filter-remove" data-idx="${idx}">&times;</button>
            `;
            const opSelect = row.querySelector(".screener-filter-op");
            const valueInput = row.querySelector(".screener-filter-value");
            const valueMaxInput = row.querySelector(".screener-filter-value-max");

            opSelect.addEventListener("change", () => {
                filter.operator = opSelect.value;
                renderScreenerFilters();
            });

            valueInput.addEventListener("input", () => {
                filter.value = parseFloat(valueInput.value) || 0;
                updateScreenerResult();
            });

            if (valueMaxInput) {
                valueMaxInput.addEventListener("input", () => {
                    filter.value_max = parseFloat(valueMaxInput.value) || 0;
                    updateScreenerResult();
                });
            }
        }

        const removeBtn = row.querySelector(".screener-filter-remove");
        removeBtn.addEventListener("click", () => {
            screeningFilters.splice(idx, 1);
            renderScreenerFilters();
        });

        container.appendChild(row);
    });

    updateScreenerResult();
}

function updateScreenerResult() {
    const resultEl = document.getElementById("screener-result");
    const countEl = document.getElementById("screener-count");
    if (!resultEl) return;

    const activeCount = screeningFilters.length;
    if (activeCount === 0) {
        resultEl.textContent = "";
        if (countEl) countEl.textContent = "";
        return;
    }

    if (countEl) countEl.textContent = `${activeCount} filter${activeCount !== 1 ? "s" : ""}`;
    resultEl.textContent = "Filters will apply on Run Ranking";
}

function initCategoryMultiSelect() {
    const picker = document.getElementById("category-picker");
    const trigger = document.getElementById("category-trigger");
    const dropdown = document.getElementById("category-dropdown");
    const valueEl = document.getElementById("category-value");
    const searchInput = document.getElementById("category-search");
    const searchClear = document.getElementById("category-search-clear");
    const listContainer = document.getElementById("category-list");
    const selectAllBtn = document.getElementById("category-select-all");
    const clearAllBtn = document.getElementById("category-clear-all");
    const countEl = document.getElementById("category-count");

    if (!picker || !trigger || !dropdown || !listContainer) return;

    let isOpen = false;
    let searchText = "";

    // Derive category groups from category names
    function getCategoryGroups() {
        const groups = [];
        const groupMap = {};

        categories.forEach(cat => {
            let group = "Other";
            const lower = cat.toLowerCase();

            if (lower.includes("equity") || lower.includes("large cap") || lower.includes("mid cap") ||
                lower.includes("small cap") || lower.includes("flexi cap") || lower.includes("multi cap") ||
                lower.includes("focused") || lower.includes("elss") || lower.includes("value") ||
                lower.includes("contra") || lower.includes("dividend yield")) {
                group = "Equity";
            } else if (lower.includes("debt") || lower.includes("bond") || lower.includes("liquid") ||
                       lower.includes("money market") || lower.includes("overnight") || lower.includes("ultra short") ||
                       lower.includes("low duration") || lower.includes("short duration") || lower.includes("medium duration") ||
                       lower.includes("long duration") || lower.includes("dynamic bond") || lower.includes("gilt") ||
                       lower.includes("credit risk") || lower.includes("floater") || lower.includes("banking & psu")) {
                group = "Debt";
            } else if (lower.includes("hybrid") || lower.includes("aggressive hybrid") || lower.includes("balanced advantage") ||
                       lower.includes("equity savings") || lower.includes("conservative hybrid") || lower.includes("multi asset") ||
                       lower.includes("arbitrage")) {
                group = "Hybrid";
            } else if (lower.includes("other") || lower.includes("index") || lower.includes("etf") ||
                       lower.includes("fof") || lower.includes("gold")) {
                group = "Other";
            }

            if (!groupMap[group]) {
                groupMap[group] = [];
            }
            groupMap[group].push(cat);
        });

        // Sort groups in preferred order
        const groupOrder = ["Equity", "Debt", "Hybrid", "Other"];
        groupOrder.forEach(g => {
            if (groupMap[g]) {
                groups.push({ name: g, items: groupMap[g].sort() });
            }
        });

        return groups;
    }

    function renderList() {
        listContainer.innerHTML = "";
        const groups = getCategoryGroups();
        const filteredGroups = [];

        groups.forEach(group => {
            const filteredItems = group.items.filter(cat =>
                cat.toLowerCase().includes(searchText.toLowerCase())
            );
            if (filteredItems.length > 0) {
                filteredGroups.push({ name: group.name, items: filteredItems });
            }
        });

        if (filteredGroups.length === 0) {
            listContainer.innerHTML = '<div class="category-picker-empty">No categories found</div>';
            return;
        }

        filteredGroups.forEach(group => {
            const groupEl = document.createElement("div");
            groupEl.className = "category-picker-group";

            const header = document.createElement("div");
            header.className = "category-picker-group-header";
            header.textContent = group.name;
            groupEl.appendChild(header);

            group.items.forEach(cat => {
                const isSelected = currentCategories.includes(cat);
                const item = document.createElement("div");
                item.className = `category-picker-item${isSelected ? " selected" : ""}`;
                item.setAttribute("role", "option");
                item.setAttribute("aria-selected", isSelected);
                item.dataset.value = cat;

                const checkbox = document.createElement("span");
                checkbox.className = "category-picker-checkbox";
                checkbox.innerHTML = isSelected
                    ? '<svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor"><path d="M11.2 3.8L5.5 9.5 2.8 6.8l-.9.9L5.5 11.3 12.1 4.7l-.9-.9z"/></svg>'
                    : '';

                const label = document.createElement("span");
                label.className = "category-picker-item-label";
                label.textContent = cat;

                item.appendChild(checkbox);
                item.appendChild(label);

                item.addEventListener("click", (e) => {
                    e.stopPropagation();
                    toggleCategory(cat);
                });

                groupEl.appendChild(item);
            });

            listContainer.appendChild(groupEl);
        });
    }

    function toggleCategory(cat) {
        if (currentCategories.includes(cat)) {
            currentCategories = currentCategories.filter(c => c !== cat);
        } else {
            currentCategories.push(cat);
        }
        updateTrigger();
        renderList();
        updateCount();
    }

    function updateTrigger() {
        if (currentCategories.length === 0) {
            valueEl.textContent = "All Categories";
            valueEl.classList.remove("has-selection");
        } else if (currentCategories.length === 1) {
            valueEl.textContent = currentCategories[0];
            valueEl.classList.add("has-selection");
        } else if (currentCategories.length === categories.length) {
            valueEl.textContent = "All Categories";
            valueEl.classList.add("has-selection");
        } else {
            valueEl.textContent = `${currentCategories.length} categories selected`;
            valueEl.classList.add("has-selection");
        }
        trigger.setAttribute("aria-expanded", isOpen);
    }

    function updateCount() {
        if (countEl) {
            countEl.textContent = `${currentCategories.length} selected`;
        }
    }

    function open() {
        isOpen = true;
        dropdown.hidden = false;
        trigger.setAttribute("aria-expanded", "true");
        if (searchInput) {
            searchInput.focus();
        }
    }

    function close() {
        isOpen = false;
        dropdown.hidden = true;
        trigger.setAttribute("aria-expanded", "false");
    }

    function toggle() {
        if (isOpen) {
            close();
        } else {
            open();
        }
    }

    // Trigger click
    trigger.addEventListener("click", (e) => {
        e.stopPropagation();
        toggle();
    });

    // Close on outside click
    document.addEventListener("click", (e) => {
        if (!picker.contains(e.target)) {
            close();
        }
    });

    // Keyboard support
    trigger.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " " || e.key === "ArrowDown") {
            e.preventDefault();
            open();
        } else if (e.key === "Escape") {
            close();
        }
    });

    // Search functionality
    if (searchInput) {
        searchInput.addEventListener("input", () => {
            searchText = searchInput.value;
            if (searchClear) {
                searchClear.hidden = searchText.length === 0;
            }
            renderList();
        });

        searchInput.addEventListener("click", (e) => {
            e.stopPropagation();
        });

        searchInput.addEventListener("keydown", (e) => {
            if (e.key === "Escape") {
                close();
                trigger.focus();
            }
            e.stopPropagation();
        });
    }

    // Search clear
    if (searchClear) {
        searchClear.addEventListener("click", (e) => {
            e.stopPropagation();
            searchInput.value = "";
            searchText = "";
            searchClear.hidden = true;
            renderList();
            searchInput.focus();
        });
    }

    // Select All
    if (selectAllBtn) {
        selectAllBtn.addEventListener("click", (e) => {
            e.stopPropagation();
            // Select all categories (not just filtered)
            categories.forEach(cat => {
                if (!currentCategories.includes(cat)) {
                    currentCategories.push(cat);
                }
            });
            updateTrigger();
            renderList();
            updateCount();
        });
    }

    // Clear All
    if (clearAllBtn) {
        clearAllBtn.addEventListener("click", (e) => {
            e.stopPropagation();
            currentCategories = [];
            updateTrigger();
            renderList();
            updateCount();
        });
    }

    // Initialize
    renderList();
    updateTrigger();
    updateCount();
}

function initCombobox({ id, options, onSelect, selectedValue = "" }) {
    const combobox = document.getElementById(`${id}-combobox`);
    const input = document.getElementById(`${id}-input`);
    const dropdown = document.getElementById(`${id}-dropdown`);
    const hidden = document.getElementById(`${id}-value`);
    const toggle = combobox ? combobox.querySelector(".combobox-toggle") : null;

    if (!combobox || !input || !dropdown || !hidden || !toggle) {
        console.error(`Combobox ${id} elements missing`);
        return;
    }

    let filtered = options;
    let highlightedIndex = -1;
    let isOpen = false;

    function renderDropdown() {
        if (filtered.length === 0) {
            dropdown.innerHTML = '<div class="combobox-empty">No matches</div>';
            return;
        }
        dropdown.innerHTML = filtered.map((opt, idx) => `
            <div class="combobox-option${idx === highlightedIndex ? ' highlighted' : ''}" data-value="${opt.value}">
                ${highlightMatch(opt.label, input.value)}
            </div>
        `).join("");
        dropdown.querySelectorAll(".combobox-option").forEach(el => {
            el.addEventListener("mousedown", (e) => {
                e.preventDefault();
                selectOption(el.dataset.value);
            });
        });
    }

    function highlightMatch(text, query) {
        if (!query) return text;
        const idx = text.toLowerCase().indexOf(query.toLowerCase());
        if (idx === -1) return text;
        return `${text.slice(0, idx)}<strong>${text.slice(idx, idx + query.length)}</strong>${text.slice(idx + query.length)}`;
    }

    function selectOption(value) {
        const opt = options.find(o => o.value === value);
        input.value = opt ? opt.label : "";
        hidden.value = value;
        closeDropdown();
        onSelect(value);
    }

    function openDropdown() {
        isOpen = true;
        combobox.classList.add("open");
        filtered = options;
        highlightedIndex = -1;
        renderDropdown();
        dropdown.style.display = "block";
    }

    function closeDropdown() {
        isOpen = false;
        combobox.classList.remove("open");
        dropdown.style.display = "none";
    }

    function filterOptions(query) {
        const q = query.toLowerCase();
        filtered = options.filter(o => o.label.toLowerCase().includes(q));
        highlightedIndex = filtered.length > 0 ? 0 : -1;
        renderDropdown();
        if (!isOpen) {
            combobox.classList.add("open");
            dropdown.style.display = "block";
            isOpen = true;
        }
    }

    input.addEventListener("focus", () => { openDropdown(); });
    input.addEventListener("input", () => { filterOptions(input.value); });
    input.addEventListener("blur", () => { setTimeout(closeDropdown, 150); });
    input.addEventListener("keydown", (e) => {
        if (e.key === "ArrowDown") {
            e.preventDefault();
            if (!isOpen) openDropdown();
            highlightedIndex = Math.min(highlightedIndex + 1, filtered.length - 1);
            renderDropdown();
        } else if (e.key === "ArrowUp") {
            e.preventDefault();
            highlightedIndex = Math.max(highlightedIndex - 1, 0);
            renderDropdown();
        } else if (e.key === "Enter" && highlightedIndex >= 0) {
            e.preventDefault();
            selectOption(filtered[highlightedIndex].value);
        } else if (e.key === "Escape") {
            closeDropdown();
        }
    });

    toggle.addEventListener("mousedown", (e) => { e.preventDefault(); });
    toggle.addEventListener("click", () => {
        if (isOpen) closeDropdown();
        else { input.focus(); openDropdown(); }
    });

    if (selectedValue) {
        const opt = options.find(o => o.value === selectedValue);
        if (opt) {
            input.value = opt.label;
            hidden.value = selectedValue;
        }
    }
}

function buildCriteriaList(container) {
    container.innerHTML = `
        <div class="screener-group">
            <div class="screener-group-heading">
                <span class="screener-group-title">Criteria Weights</span>
                <span class="screener-group-subtitle">Customize scoring factors for ranking</span>
            </div>
            <div class="criteria-list" id="criteria-list"></div>
        </div>
    `;
    const list = document.getElementById("criteria-list");
    if (!list) return;

    Object.entries(CRITERIA_META).forEach(([key, meta]) => {
        const item = document.createElement("div");
        item.className = "criterion-item";
        item.dataset.criterion = key;

        item.innerHTML = `
            <div class="criterion-header">
                <input type="checkbox" id="cb-${key}" checked>
                <label for="cb-${key}">${meta.label}${CRITERIA_HELP[key] ? `<span class="tooltip-trigger" tabindex="0" role="button" aria-label="More information"><span class="tooltip-content">${CRITERIA_HELP[key]}</span>ⓘ</span>` : ""}</label>
                <span class="weight-value" id="weight-${key}">0%</span>
            </div>
            <div class="criterion-weight">
                <input type="range" id="range-${key}" min="0" max="100" step="1" value="0">
                <input type="number" id="num-${key}" min="0" max="100" step="1" value="0">
            </div>
        `;

        const checkbox = item.querySelector(`#cb-${key}`);
        const range = item.querySelector(`#range-${key}`);
        const number = item.querySelector(`#num-${key}`);
        const weightDisplay = item.querySelector(`#weight-${key}`);

        checkbox.addEventListener("change", () => {
            const enabled = checkbox.checked;
            item.classList.toggle("disabled", !enabled);
            range.disabled = !enabled;
            number.disabled = !enabled;
            if (!enabled) {
                range.value = 0;
                number.value = 0;
            }
            autoRenormalize();
        });

        range.addEventListener("input", () => {
            number.value = range.value;
            autoRenormalize();
        });

        number.addEventListener("input", () => {
            let val = parseFloat(number.value) || 0;
            val = Math.max(0, Math.min(100, val));
            range.value = val;
            number.value = val;
            autoRenormalize();
        });

        list.appendChild(item);
    });
}

function applyPreset(presetKey) {
    const preset = PRESETS[presetKey];
    if (!preset) return;

    preset.criteria.forEach(c => {
        const checkbox = document.getElementById(`cb-${c.name}`);
        const range = document.getElementById(`range-${c.name}`);
        const number = document.getElementById(`num-${c.name}`);
        const item = checkbox?.closest(".criterion-item");
        if (!checkbox || !range || !number || !item) return;

        checkbox.checked = true;
        range.value = c.weight;
        number.value = c.weight;
        item.classList.remove("disabled");
        range.disabled = false;
        number.disabled = false;
    });

    Object.keys(CRITERIA_META).forEach(key => {
        if (!preset.criteria.find(c => c.name === key)) {
            const checkbox = document.getElementById(`cb-${key}`);
            const range = document.getElementById(`range-${key}`);
            const number = document.getElementById(`num-${key}`);
            const item = checkbox?.closest(".criterion-item");
            if (!checkbox || !range || !number || !item) return;

            checkbox.checked = false;
            range.value = 0;
            number.value = 0;
            item.classList.add("disabled");
            range.disabled = true;
            number.disabled = true;
        }
    });

    autoRenormalize();
}

function autoRenormalize() {
    const checkboxes = document.querySelectorAll(".criteria-list input[type='checkbox']");
    let total = 0;
    const values = {};

    checkboxes.forEach(cb => {
        const key = cb.id.replace("cb-", "");
        const num = document.getElementById(`num-${key}`);
        const val = cb.checked ? (parseFloat(num?.value) || 0) : 0;
        values[key] = val;
        total += val;
    });

    if (total > 0) {
        Object.entries(values).forEach(([key, val]) => {
            const num = document.getElementById(`num-${key}`);
            const range = document.getElementById(`range-${key}`);
            const weightDisplay = document.getElementById(`weight-${key}`);
            if (num && range && values[key] > 0) {
                const normalized = (val / total) * 100;
                const rounded = Math.round(normalized * 10) / 10;
                num.value = rounded;
                range.value = rounded;
                if (weightDisplay) weightDisplay.textContent = `${rounded}%`;
            } else if (weightDisplay) {
                weightDisplay.textContent = `0%`;
            }
        });
    } else {
        Object.keys(values).forEach(key => {
            const weightDisplay = document.getElementById(`weight-${key}`);
            if (weightDisplay) weightDisplay.textContent = `0%`;
        });
    }

    refreshMethodologyBox();
}

function refreshMethodologyBox() {
    const container = document.getElementById("ranking-methodology");
    if (container) buildMethodology(container);
}

const PRESET_GROUPS = {
    best_overall: [
        { group: "Performance", weight: 50, criteria: ["1Y_return", "3Y_cagr"] },
        { group: "Risk-Adjusted", weight: 35, criteria: ["sharpe_ratio", "sortino_ratio"] },
        { group: "Risk", weight: 0, criteria: [] },
        { group: "Consistency", weight: 15, criteria: ["consistency"] },
    ],
    highest_returns: [
        { group: "Performance", weight: 100, criteria: ["1Y_return", "3Y_cagr", "5Y_cagr", "10Y_cagr"] },
        { group: "Risk-Adjusted", weight: 0, criteria: [] },
        { group: "Risk", weight: 0, criteria: [] },
        { group: "Consistency", weight: 0, criteria: [] },
    ],
    lowest_risk: [
        { group: "Performance", weight: 0, criteria: [] },
        { group: "Risk-Adjusted", weight: 20, criteria: ["sharpe_ratio"] },
        { group: "Risk", weight: 80, criteria: ["volatility", "maximum_drawdown", "downside_deviation"] },
        { group: "Consistency", weight: 0, criteria: [] },
    ],
    best_consistency: [
        { group: "Performance", weight: 15, criteria: ["3Y_cagr"] },
        { group: "Risk-Adjusted", weight: 45, criteria: ["sharpe_ratio", "sortino_ratio"] },
        { group: "Risk", weight: 0, criteria: [] },
        { group: "Consistency", weight: 40, criteria: ["consistency"] },
    ],
};

function getCurrentPresetGroups() {
    if (PRESET_GROUPS[currentPreset]) {
        return PRESET_GROUPS[currentPreset];
    }
    const criteria = getSelectedCriteria();
    const grouped = [
        { group: "Performance", weight: 0, criteria: [] },
        { group: "Risk-Adjusted", weight: 0, criteria: [] },
        { group: "Risk", weight: 0, criteria: [] },
        { group: "Consistency", weight: 0, criteria: [] },
    ];
    const bucket = (key) => {
        if (["1Y_return", "3Y_cagr", "5Y_cagr", "10Y_cagr"].includes(key)) return 0;
        if (["sharpe_ratio", "sortino_ratio"].includes(key)) return 1;
        if (["volatility", "maximum_drawdown", "downside_deviation"].includes(key)) return 2;
        if (key === "consistency") return 3;
        return null;
    };
    const total = criteria.reduce((s, c) => s + c.weight, 0) || 1;
    criteria.forEach(c => {
        const idx = bucket(c.name);
        if (idx == null) return;
        grouped[idx].weight += (c.weight / total) * 100;
        grouped[idx].criteria.push(c.name);
    });
    grouped.forEach(g => {
        g.weight = Math.round(g.weight * 10) / 10;
    });
    return grouped;
}

function buildMethodology(container) {
    const groups = getCurrentPresetGroups();
    const presetLabel = PRESETS[currentPreset]?.label || currentPreset;
    const totalActive = groups.reduce((s, g) => s + g.weight, 0);

    const groupsHtml = groups.map(g => {
        const active = g.weight > 0;
        const tooltip = g.criteria.length
            ? `Based on: ${g.criteria.map(c => CRITERIA_META[c]?.label || c).join(", ")}`
            : `No active criteria in this group for "${presetLabel}" preset.`;
        return `
            <div class="ranking-mw-group ${active ? "" : "is-inactive"}">
                <div class="ranking-mw-group-head">
                    <span class="ranking-mw-group-name">${g.group}</span>
                    <span class="ranking-mw-group-weight">${g.weight.toFixed(1)}%</span>
                </div>
                <div class="ranking-mw-group-bar"><div class="ranking-mw-group-fill" style="width: ${g.weight}%"></div></div>
                <div class="ranking-mw-group-hint">${g.criteria.length ? g.criteria.map(c => CRITERIA_META[c]?.label || c).join(" · ") : "Not used in this preset"}</div>
            </div>
        `;
    }).join("");

    container.innerHTML = `
        <h4>How ranking works</h4>
        <p class="ranking-mw-intro">Each fund is scored on up to 10 metrics. The overall score is a weighted blend of the <strong>${presetLabel}</strong> preset (renormalized to 100%).</p>
        <div class="ranking-mw-groups">${groupsHtml}</div>
        <ul class="ranking-mw-notes">
            <li><strong>Actual</strong> = the fund's real calculated metric (e.g., 18.00% return, 1.36 Sharpe ratio).</li>
            <li><strong>Score / 100</strong> = normalized ranking score relative to other funds in this category. 100 = best, 0 = worst.</li>
            <li><strong>Overall Score</strong> = weighted combination of individual scores per the selected preset.</li>
            <li>Lower-is-better metrics (volatility, drawdown, downside deviation) are inverted so higher score always means better.</li>
        </ul>
        <p class="ranking-mw-total">Total active weight: <strong>${totalActive.toFixed(1)}%</strong></p>
    `;
}

async function runRanking() {
    if (!currentCategories || currentCategories.length === 0) {
        alert("Please select at least one category first.");
        return;
    }

    const criteria = getSelectedCriteria();
    if (criteria.length === 0) {
        alert("Please select at least one criterion.");
        return;
    }

    const resultsContainer = document.getElementById("ranking-table-container");
    const summaryContainer = document.getElementById("ranking-summary");
    if (!resultsContainer) return;

    showLoading(resultsContainer, "Generating rankings...");
    if (summaryContainer) summaryContainer.innerHTML = "";

    try {
        // Build and validate screening filters
        const filters = buildScreeningFiltersPayload();
        if (filters === null) {
            // Validation failed, error already shown
            hideLoading(resultsContainer);
            return;
        }

        // Debug logging - show the actual payload being sent
        console.log("Ranking request payload:", {
            category: currentCategories,
            criteria: criteria,
            auto_renormalize: true,
            screening_filters: filters,
        });

        const response = await api.post("/mutual-funds/rank", {
            category: currentCategories,
            criteria: criteria,
            auto_renormalize: true,
            screening_filters: filters,
        });

        hideLoading(resultsContainer);
        renderRankingResults(response.rankings, response.category || currentCategories);

        if (response.meta?.screened_matching != null) {
            const summaryContainer = document.getElementById("ranking-summary");
            if (summaryContainer) {
                const existingInfo = summaryContainer.querySelector(".screener-info");
                if (existingInfo) existingInfo.remove();
                const info = document.createElement("div");
                info.className = "screener-info";
                const catCount = response.categories_count || currentCategories.length;
                info.textContent = `${response.meta.screened_matching} of ${response.meta.underlying_funds} funds across ${catCount} categor${catCount !== 1 ? "ies" : "y"} match your filters`;
                summaryContainer.appendChild(info);
            }
        }
    } catch (error) {
        hideLoading(resultsContainer);
        resultsContainer.innerHTML = `<div class="empty-state"><p>Ranking failed: ${error.message}</p></div>`;
    }
}

function buildScreeningFiltersPayload() {
    const filters = [];

    for (const f of screeningFilters) {
        const field = SCREENER_FIELDS.find(sf => sf.key === f.field);
        if (!field) continue;

        // Check for validation errors
        const row = document.querySelector(`.screener-filter-row[data-idx="${screeningFilters.indexOf(f)}"]`);
        const errorEl = row?.querySelector(".screener-filter-error");

        if (field.type === "categorical") {
            // Categorical filters: use values array
            const values = f.values || [];
            if (values.length === 0) {
                // Show validation error
                if (row) {
                    showFilterError(row, "Please enter at least one value");
                }
                return null;
            }
            filters.push({
                field: f.field,
                operator: f.operator,
                values: values,
            });
        } else if (field.type === "date") {
            // Date filters: send the ISO date string directly
            if (!f.value) {
                // Empty date = no filter, skip
                continue;
            }

            if (f.operator === "between") {
                if (!f.value_max) {
                    if (row) {
                        showFilterError(row, "Please enter a max date");
                    }
                    return null;
                }
                filters.push({
                    field: f.field,
                    operator: f.operator,
                    value: f.value,
                    value_min: f.value,
                    value_max: f.value_max,
                });
            } else {
                filters.push({
                    field: f.field,
                    operator: f.operator,
                    value: f.value,
                });
            }
        } else {
            // Numeric filters: ensure value is a valid number
            const numValue = parseFloat(f.value);
            if (isNaN(numValue) || f.value === "" || f.value === null) {
                if (row) {
                    showFilterError(row, "Please enter a valid number");
                }
                return null;
            }

            if (f.operator === "between") {
                const numMax = parseFloat(f.value_max);
                if (isNaN(numMax) || f.value_max === "" || f.value_max === null) {
                    if (row) {
                        showFilterError(row, "Please enter a valid max value");
                    }
                    return null;
                }
                filters.push({
                    field: f.field,
                    operator: f.operator,
                    value: numValue,
                    value_min: numValue,
                    value_max: numMax,
                });
            } else {
                filters.push({
                    field: f.field,
                    operator: f.operator,
                    value: numValue,
                });
            }
        }
    }

    return filters;
}

function showFilterError(row, message) {
    // Remove existing error
    const existing = row.querySelector(".screener-filter-error");
    if (existing) existing.remove();

    // Add error message
    const error = document.createElement("div");
    error.className = "screener-filter-error";
    error.textContent = message;
    row.appendChild(error);

    // Auto-remove after 3 seconds
    setTimeout(() => error.remove(), 3000);
}

function getSelectedCriteria() {
    const criteria = [];
    Object.keys(CRITERIA_META).forEach(key => {
        const checkbox = document.getElementById(`cb-${key}`);
        const number = document.getElementById(`num-${key}`);
        if (checkbox?.checked && number) {
            const weight = parseFloat(number.value) || 0;
            if (weight > 0) {
                criteria.push({ name: key, weight });
            }
        }
    });
    return criteria;
}

function toggleCategory(cat) {
    if (currentCategories.includes(cat)) {
        currentCategories = currentCategories.filter(c => c !== cat);
    } else {
        currentCategories.push(cat);
    }
    updateCategoryTriggerAndList();
}

function renderTop3Strip(top3, categories) {
    if (!top3 || top3.length === 0) return "";
    const order = [1, 0, 2];
    const podiumOrder = order.slice(0, top3.length);
    const podiumHtml = podiumOrder.map((idx, slot) => {
        const r = top3[idx];
        if (!r) return "";
        const place = idx + 1;
        const score = r.overall_score != null ? r.overall_score.toFixed(1) : "N/A";
        const category = r.category || (Array.isArray(categories) ? categories[0] : "") || "";
        const subline = r.amc ? r.amc : category;
        return `
            <div class="top3-card top3-place-${place}">
                <div class="top3-rank">#${place}</div>
                <div class="top3-name" data-scheme="${r.scheme_code}" data-name="${encodeURIComponent(r.scheme_name || "")}">${r.scheme_name || "—"}</div>
                <div class="top3-amc">${subline}</div>
                <div class="top3-score">
                    <span class="top3-score-value">${score}</span>
                    <span class="top3-score-suffix">/ 100</span>
                </div>
                <div class="top3-score-label">Overall</div>
                <button type="button" class="top3-why-btn" data-scheme="${r.scheme_code}">Why?</button>
            </div>
        `;
    }).join("");

    return `
        <div class="ranking-top3" aria-label="Top 3 ranked funds">
            <div class="ranking-top3-head">
                <h4>Top 3 ranked funds</h4>
                <span class="ranking-top3-sub">Across the current category and filters</span>
            </div>
            <div class="ranking-top3-grid top3-grid-${top3.length}">
                ${podiumHtml}
            </div>
        </div>
    `;
}

function attachTop3Handlers() {
    document.querySelectorAll(".top3-name").forEach(el => {
        el.addEventListener("click", () => {
            const code = el.dataset.scheme;
            const name = decodeURIComponent(el.dataset.name || "");
            if (code) openFundDetail(code, name);
        });
    });
    document.querySelectorAll(".top3-why-btn").forEach(btn => {
        btn.addEventListener("click", (e) => {
            e.stopPropagation();
            const code = btn.dataset.scheme;
            const fund = (currentRankings || []).find(r => String(r.scheme_code) === String(code));
            if (fund) {
                showFundWhyDialog(fund);
            }
        });
    });
}

function computeRankingFreshness(rankings) {
    if (!rankings || !rankings.length) return null;
    const dates = rankings.map(r => parseDateOnly(r.nav_date)).filter(Boolean);
    const firstDates = rankings.map(r => parseDateOnly(r.first_nav_date)).filter(Boolean);
    if (dates.length === 0 && firstDates.length === 0) return null;

    const latestData = dates.length ? new Date(Math.max(...dates.map(d => d.getTime()))) : null;
    const earliestInception = firstDates.length ? new Date(Math.min(...firstDates.map(d => d.getTime()))) : null;
    const latestInception = firstDates.length ? new Date(Math.max(...firstDates.map(d => d.getTime()))) : null;

    const latestStr = latestData ? formatDateHumanForComparison(latestData) : null;
    const earliestInceptionStr = earliestInception ? formatYearOnly(earliestInception) : null;
    const latestInceptionStr = latestInception ? formatYearOnly(latestInception) : null;

    const tooltipText = [
        "Based on each fund's latest available NAV record.",
        "Inception range is the spread between the youngest and oldest fund in this ranking.",
        "Ranking calculations use the same metrics regardless of how current each fund's NAV record is.",
    ].join(" ");

    return `
        <span class="ranking-freshness-dot" aria-hidden="true"></span>
        ${latestStr ? `<span class="ranking-freshness-item"><span class="ranking-freshness-label">Data as of</span> <span class="ranking-freshness-value">${latestStr}</span></span>` : ""}
        ${earliestInceptionStr && latestInceptionStr ? `<span class="ranking-freshness-item"><span class="ranking-freshness-label">Fund inception range</span> <span class="ranking-freshness-value">${earliestInceptionStr === latestInceptionStr ? latestInceptionStr : `${earliestInceptionStr} → ${latestInceptionStr}`}</span></span>` : ""}
        <span class="ranking-freshness-tooltip-trigger" tabindex="0" role="button" aria-label="Data freshness details">ⓘ
            <span class="ranking-freshness-tooltip-content">${tooltipText}</span>
        </span>
    `;
}

function deriveStrengthsWeaknesses(fund) {
    const cs = (fund.criteria_scores || []).filter(c => c.score != null && c.weight > 0);
    if (cs.length === 0) return { strengths: [], weaknesses: [], total: 0, rank: fund.rank, overall: fund.overall_score };
    const enriched = cs.map(c => ({
        key: c.criterion,
        label: CRITERIA_META[c.criterion]?.label || c.criterion,
        weight: c.weight,
        score: c.score,
        contribution: (c.score / 100) * (c.weight / 100) * 100,
        raw: c.raw_value,
    }));
    enriched.sort((a, b) => b.contribution - a.contribution);
    const strengths = enriched.slice(0, Math.min(2, enriched.length));
    const weaknesses = enriched.slice(-Math.min(2, enriched.length)).reverse();
    return {
        strengths,
        weaknesses,
        total: enriched.reduce((s, c) => s + c.contribution, 0),
        rank: fund.rank,
        overall: fund.overall_score,
    };
}

function formatStrengthsWeaknessesForRow(analysis) {
    if (!analysis || !analysis.strengths || !analysis.weaknesses) return "";
    const chip = (item, kind) => `
        <span class="ranking-sw-chip ranking-sw-chip-${kind}" title="${item.label}: score ${item.score.toFixed(1)}/100">
            <span class="ranking-sw-chip-dot" aria-hidden="true"></span>
            <span class="ranking-sw-chip-label">${item.label}</span>
        </span>
    `;
    return `
        <div class="ranking-sw-row">
            <div class="ranking-sw-pair ranking-sw-strengths">
                <span class="ranking-sw-pair-label">Strengths</span>
                <div class="ranking-sw-pair-chips">${analysis.strengths.map(s => chip(s, "strong")).join("")}</div>
            </div>
            <div class="ranking-sw-pair ranking-sw-weaknesses">
                <span class="ranking-sw-pair-label">Trade-offs</span>
                <div class="ranking-sw-pair-chips">${analysis.weaknesses.map(w => chip(w, "weak")).join("")}</div>
            </div>
        </div>
    `;
}

function showFundWhyDialog(fund) {
    const analysis = deriveStrengthsWeaknesses(fund);
    const dialog = document.createElement("div");
    dialog.className = "ranking-why-dialog";
    dialog.setAttribute("role", "dialog");
    dialog.setAttribute("aria-modal", "true");
    dialog.setAttribute("aria-label", "Why this fund ranks here");

    const overall = fund.overall_score != null ? fund.overall_score.toFixed(1) : "N/A";
    dialog.innerHTML = `
        <div class="ranking-why-backdrop"></div>
        <div class="ranking-why-card">
            <button type="button" class="ranking-why-close" aria-label="Close">×</button>
            <div class="ranking-why-eyebrow">Rank #${analysis.rank} · Overall ${overall} / 100</div>
            <h3 class="ranking-why-title">${fund.scheme_name || ""}</h3>
            <div class="ranking-why-amc">${fund.amc || ""} ${fund.category ? "· " + fund.category : ""}</div>

            <div class="ranking-why-section">
                <h4>Strengths</h4>
                <p class="ranking-why-section-help">Highest weighted contribution to the overall score.</p>
                <ul class="ranking-why-list ranking-why-list-strong">
                    ${analysis.strengths.map(s => `
                        <li>
                            <div class="ranking-why-list-row">
                                <span class="ranking-why-list-label">${s.label}</span>
                                <span class="ranking-why-list-value">Score ${s.score.toFixed(1)} · Weight ${s.weight.toFixed(1)}%</span>
                            </div>
                            <div class="ranking-why-list-bar"><div class="ranking-why-list-fill ranking-why-list-fill-strong" style="width: ${Math.max(0, Math.min(100, s.score))}%"></div></div>
                        </li>
                    `).join("")}
                </ul>
            </div>

            <div class="ranking-why-section">
                <h4>Trade-offs</h4>
                <p class="ranking-why-section-help">Lowest weighted contribution to the overall score.</p>
                <ul class="ranking-why-list ranking-why-list-weak">
                    ${analysis.weaknesses.map(s => `
                        <li>
                            <div class="ranking-why-list-row">
                                <span class="ranking-why-list-label">${s.label}</span>
                                <span class="ranking-why-list-value">Score ${s.score.toFixed(1)} · Weight ${s.weight.toFixed(1)}%</span>
                            </div>
                            <div class="ranking-why-list-bar"><div class="ranking-why-list-fill ranking-why-list-fill-weak" style="width: ${Math.max(0, Math.min(100, s.score))}%"></div></div>
                        </li>
                    `).join("")}
                </ul>
            </div>

            <div class="ranking-why-disclaimer">These strengths and trade-offs are derived directly from the fund's normalized ranking scores. They are not investment advice.</div>
        </div>
    `;
    document.body.appendChild(dialog);

    const close = () => {
        dialog.classList.add("ranking-why-closing");
        setTimeout(() => dialog.remove(), 160);
    };
    dialog.querySelector(".ranking-why-backdrop").addEventListener("click", close);
    dialog.querySelector(".ranking-why-close").addEventListener("click", close);
    document.addEventListener("keydown", function onKey(e) {
        if (e.key === "Escape") {
            close();
            document.removeEventListener("keydown", onKey);
        }
    });
}

function renderRankingResults(rankings, categories) {
    currentRankings = rankings;
    filteredRankings = rankings;

    const summaryContainer = document.getElementById("ranking-summary");
    const tableContainer = document.getElementById("ranking-table-container");

    // Format category display
    const categoryDisplay = Array.isArray(categories)
        ? (categories.length === 1 ? categories[0] : `${categories.length} categories`)
        : (categories || "Unknown");

    updateMatchingFundsCount(rankings.length);

    if (summaryContainer) {
        const top3 = rankings.filter(r => r.overall_score != null).slice(0, 3);
        const top3Html = renderTop3Strip(top3, categories);
        const freshness = computeRankingFreshness(rankings);
        summaryContainer.innerHTML = `
            <div class="ranking-summary">
                <div class="ranking-summary-titles">
                    <h3>${categoryDisplay} Rankings</h3>
                    <span class="result-meta" id="result-count">${rankings.length} ${rankings.length === 1 ? "fund" : "funds"} ranked</span>
                </div>
                <div class="ranking-summary-meta">
                    <span class="ranking-meta-item"><span class="ranking-meta-label">Preset</span> <span class="ranking-meta-value">${PRESETS[currentPreset]?.label || currentPreset}</span></span>
                    <span class="ranking-meta-item"><span class="ranking-meta-label">Sort</span> <span class="ranking-meta-value">Overall Score</span></span>
                </div>
            </div>
            <div class="ranking-summary-explanation">
                <p>Funds are scored on up to 10 metrics across <strong>Performance</strong>, <strong>Risk-Adjusted</strong>, <strong>Risk</strong> and <strong>Consistency</strong>. The <strong>${PRESETS[currentPreset]?.label || currentPreset}</strong> preset determines how each component contributes to the overall score.</p>
            </div>
            ${freshness ? `<div class="ranking-freshness-strip">${freshness}</div>` : ""}
            ${top3Html}
            <div class="active-filters-bar" id="active-filters-bar" hidden></div>
        `;
        renderActiveFilters();
        attachTop3Handlers();
    }

    if (!tableContainer) return;

    if (!rankings.length) {
        tableContainer.innerHTML = renderScreenerEmptyState();
        buildResultFilters([]);
        const clearBtn = tableContainer.querySelector("#empty-clear-categories");
        if (clearBtn) {
            clearBtn.addEventListener("click", () => {
                currentCategories = [];
                updateCategoryTriggerAndList();
                screeningFilters = [];
                renderScreenerFilters();
                renderActiveFilters();
                runRanking();
            });
        }
        return;
    }

    const existingBar = document.getElementById("comparison-bar");
    if (existingBar) existingBar.remove();

    const comparisonBar = document.createElement("div");
    comparisonBar.id = "comparison-bar";
    comparisonBar.className = "comparison-bar";
    comparisonBar.innerHTML = `
        <span class="comparison-bar-text" id="comparison-count">0 funds selected</span>
        <div class="comparison-bar-actions">
            <button class="btn-text" id="clear-selection">Clear</button>
            <button class="btn-primary btn-small" id="compare-btn" disabled>Compare Funds</button>
        </div>
    `;
    summaryContainer.appendChild(comparisonBar);

    document.getElementById("clear-selection").addEventListener("click", () => {
        selectedFunds.clear();
        updateComparisonBar();
        updateRowCheckboxes();
        const selectAll = document.querySelector(".compare-select-all");
        if (selectAll) selectAll.checked = false;
    });

    document.getElementById("compare-btn").addEventListener("click", showComparisonView);

    buildResultFilters(rankings);

    const columns = [
        { key: "select", label: "", width: 36 },
        { key: "rank", label: "Rank", width: 56 },
        { key: "scheme_name", label: "Fund", emphasize: true },
        { key: "category", label: "Category" },
        { key: "amc", label: "AMC" },
        { key: "nav", label: "Latest NAV", align: "right" },
        { key: "overall_score", label: "Overall Score", tooltip: TOOLTIPS.overall_score, emphasize: true },
        { key: "why", label: "Why" },
        { key: "details", label: "" },
    ];

    const rows = rankings.map((r, index) => {
        const score = r.overall_score != null ? r.overall_score.toFixed(1) : "N/A";
        const scoreWidth = r.overall_score != null ? Math.max(0, Math.min(100, r.overall_score)) : 0;
        const nav = r.nav != null ? formatNAV(r.nav) : "N/A";
        const scoreNum = r.overall_score != null ? r.overall_score : null;
        const analysis = deriveStrengthsWeaknesses(r);
        const categoryValue = r.category || (Array.isArray(categories) ? (categories.length === 1 ? categories[0] : categories.join(", ")) : (categories || "—"));
        return {
            rank: index + 1,
            rank_of: rankings.filter(x => x.overall_score != null).length,
            scheme_code: r.scheme_code || "—",
            scheme_name: r.scheme_name,
            amc: r.amc || "—",
            category: categoryValue,
            nav: nav,
            nav_raw: r.nav,
            nav_date: r.nav_date || "—",
            data_points: r.data_points != null ? r.data_points : null,
            aum_cr: r.aum_cr != null ? r.aum_cr : null,
            aum_quarter: r.aum_quarter || null,
            aum_quarter_end: r.aum_quarter_end || null,
            first_nav_date: r.first_nav_date || "—",
            overall_score: score,
            score_width: scoreWidth,
            score_num: scoreNum,
            analysis: analysis,
            details: r.criteria_scores || [],
            _raw: r,
        };
    });

    tableContainer.innerHTML = "";
    const table = document.createElement("table");
    table.className = "data-table screener-results-table";

    const thead = document.createElement("thead");
    const headerRow = document.createElement("tr");
    columns.forEach(col => {
        const th = document.createElement("th");
        if (col.emphasize) th.classList.add("data-table-th-emphasize");
        if (col.align === "right") th.classList.add("data-table-th-right");
        if (col.key === "select") {
            th.className = "select-cell";
            const selectAll = document.createElement("input");
            selectAll.type = "checkbox";
            selectAll.className = "compare-select-all";
            selectAll.setAttribute("aria-label", "Select all funds for comparison");
            selectAll.addEventListener("change", () => {
                const isChecked = selectAll.checked;
                if (isChecked) {
                    rows.forEach(row => {
                        if (selectedFunds.size < MAX_COMPARE) {
                            selectedFunds.add(row.scheme_code);
                        }
                    });
                } else {
                    rows.forEach(row => selectedFunds.delete(row.scheme_code));
                }
                updateComparisonBar();
                updateRowCheckboxes();
            });
            th.appendChild(selectAll);
        } else if (col.tooltip) {
            th.innerHTML = `${col.label} <span class="tooltip-trigger header-tooltip" tabindex="0" role="button" aria-label="Help"><span class="tooltip-content">${col.tooltip}</span>ⓘ</span>`;
        } else {
            th.textContent = col.label;
        }
        headerRow.appendChild(th);
    });
    thead.appendChild(headerRow);
    table.appendChild(thead);

    // Attach tooltip listeners to header tooltips
    thead.querySelectorAll(".tooltip-trigger").forEach(trigger => {
        const content = trigger.querySelector(".tooltip-content");
        if (!content) return;

        trigger.addEventListener("click", (e) => {
            e.stopPropagation();
            const isVisible = content.style.opacity === "1";
            document.querySelectorAll(".tooltip-content").forEach(t => {
                t.style.opacity = "0";
                t.style.visibility = "hidden";
            });
            if (!isVisible) {
                content.style.opacity = "1";
                content.style.visibility = "visible";
            }
        });
    });

    const tbody = document.createElement("tbody");
    rows.forEach((row, idx) => {
        const tr = document.createElement("tr");
        if (row.rank <= 3 && row.rank != null) {
            tr.classList.add("top-rank");
        }
        if (selectedFunds.has(row.scheme_code)) {
            tr.classList.add("row-selected");
        }
        const isSelected = selectedFunds.has(row.scheme_code);
        const rankClass = row.rank === 1 ? "rank-cell rank-pill rank-pill-1" :
                          row.rank === 2 ? "rank-cell rank-pill rank-pill-2" :
                          row.rank === 3 ? "rank-cell rank-pill rank-pill-3" :
                          "rank-cell rank-pill";
        const scoreTier = row.score_num == null ? "" :
                          row.score_num >= 75 ? "score-tier-top" :
                          row.score_num >= 50 ? "score-tier-mid" :
                          "score-tier-low";
        const totalScored = row.rank_of;
        const contextPct = totalScored > 0 && row.score_num != null
            ? Math.round(((totalScored - row.rank + 1) / totalScored) * 100)
            : null;
        const contextLabel = contextPct == null
            ? "—"
            : contextPct >= 80 ? "Top decile"
            : contextPct >= 60 ? "Upper third"
            : contextPct >= 40 ? "Mid range"
            : contextPct >= 20 ? "Lower third"
            : "Bottom quintile";
        const contextClass = contextPct == null ? "" :
                             contextPct >= 60 ? "context-upper" :
                             contextPct >= 40 ? "context-mid" :
                             "context-lower";
        const contextHtml = contextPct != null
            ? `<div class="rank-context ${contextClass}" title="Position within ${totalScored} ranked funds in current category">
                    <span class="rank-context-pct">${contextPct}<span class="rank-context-pct-suffix">%</span></span>
                    <span class="rank-context-label">${contextLabel}</span>
                </div>`
            : `<div class="rank-context rank-context-na">—</div>`;
        tr.innerHTML = `
            <td class="select-cell"><input type="checkbox" class="compare-cb" data-scheme="${row.scheme_code}" ${isSelected ? "checked" : ""} aria-label="Select ${row.scheme_name} for comparison"></td>
            <td>
                <div class="rank-cell-stack">
                    <span class="${rankClass}">${row.rank}</span>
                    ${contextHtml}
                </div>
            </td>
            <td class="fund-name-cell"><span class="fund-link" data-scheme="${row.scheme_code}" data-name="${encodeURIComponent(row.scheme_name)}">${row.scheme_name}</span>${formatStrengthsWeaknessesForRow(row.analysis)}</td>
            <td class="muted category-cell" title="${row.category}">${row.category}</td>
            <td class="muted amc-cell">${row.amc}</td>
            <td class="nav-cell">${row.nav}</td>
            <td class="score-cell ${scoreTier}">
                ${row.overall_score !== "N/A" ? `<span class="score-value">${row.overall_score}</span><span class="score-suffix">/ 100</span><div class="score-bar-bg"><div class="score-bar-fill" style="width: ${row.score_width}%"></div></div>` : `<span class="metric-na">N/A</span>`}
            </td>
            <td class="why-cell"><button type="button" class="why-btn" data-scheme="${row.scheme_code}" aria-label="Why this fund ranks here">Why?</button></td>
            <td><button class="expand-btn" data-idx="${idx}">Details</button></td>
        `;
        tbody.appendChild(tr);

        const detailTr = document.createElement("tr");
        detailTr.className = "details-row hidden";
        detailTr.dataset.idx = idx;
        detailTr.innerHTML = `<td colspan="${columns.length}"><div class="details-content"></div></td>`;
        tbody.appendChild(detailTr);
    });
    table.appendChild(tbody);
    tableContainer.appendChild(table);

    table.querySelectorAll(".fund-link").forEach(link => {
        link.addEventListener("click", () => {
            const schemeCode = link.dataset.scheme;
            const schemeName = decodeURIComponent(link.dataset.name);
            openFundDetail(schemeCode, schemeName);
        });
    });

    table.querySelectorAll(".why-btn").forEach(btn => {
        btn.addEventListener("click", (e) => {
            e.stopPropagation();
            const code = btn.dataset.scheme;
            const fund = rankings.find(r => String(r.scheme_code) === String(code));
            if (fund) showFundWhyDialog(fund);
        });
    });

    table.querySelectorAll(".compare-cb").forEach(cb => {
        cb.addEventListener("change", () => {
            const scheme = cb.dataset.scheme;
            if (cb.checked) {
                if (selectedFunds.size >= MAX_COMPARE) {
                    cb.checked = false;
                    return;
                }
                selectedFunds.add(scheme);
            } else {
                selectedFunds.delete(scheme);
            }
            updateComparisonBar();
            updateRowCheckboxes();
        });
    });

    table.querySelectorAll(".expand-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            const idx = parseInt(btn.dataset.idx, 10);
            const detailRow = table.querySelector(`tr.details-row[data-idx="${idx}"]`);
            const content = detailRow?.querySelector(".details-content");
            if (!content) return;

            const isHidden = detailRow.classList.contains("hidden");
            table.querySelectorAll(".details-row").forEach(r => r.classList.add("hidden"));
            table.querySelectorAll(".expand-btn").forEach(b => b.textContent = "Details");

            if (isHidden) {
                detailRow.classList.remove("hidden");
                btn.textContent = "Hide";
                renderDetailContent(content, rows[idx].details, {
                    nav_date: rows[idx].nav_date,
                    data_points: rows[idx].data_points,
                    category: rows[idx].category,
                    aum_cr: rows[idx].aum_cr,
                    aum_quarter: rows[idx].aum_quarter,
                    aum_quarter_end: rows[idx].aum_quarter_end,
                    first_nav_date: rows[idx].first_nav_date,
                });
            }
        });
    });
}

function renderScreenerEmptyState() {
    const hasCategories = currentCategories.length > 0;
    const hasScreenerFilters = screeningFilters.length > 0;
    const hasPreset = currentPreset;

    let explanation = "No funds match the current filter combination.";
    if (!hasCategories) {
        explanation = "Select at least one category to see matching funds.";
    } else if (hasScreenerFilters) {
        explanation = "The selected screener filters and category combination did not match any fund. Try relaxing a filter.";
    }

    return `
        <div class="screener-empty-state">
            <div class="screener-empty-state-icon" aria-hidden="true">
                <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                    <circle cx="11" cy="11" r="7"/>
                    <line x1="20" y1="20" x2="16.5" y2="16.5"/>
                </svg>
            </div>
            <h3 class="screener-empty-state-title">No funds match these filters</h3>
            <p class="screener-empty-state-text">${explanation}</p>
            <div class="screener-empty-state-actions">
                <button class="btn-primary btn-small" id="empty-clear-categories" type="button">Clear All Filters</button>
            </div>
        </div>
    `;
}

function renderActiveFilters() {
    const bar = document.getElementById("active-filters-bar");
    if (!bar) return;
    const chips = [];

    if (currentCategories.length > 0 && !(currentCategories.length === categories.length)) {
        currentCategories.forEach(cat => {
            chips.push({
                key: `cat:${cat}`,
                label: `Category: ${cat}`,
                onRemove: () => toggleCategory(cat),
            });
        });
    }

    screeningFilters.forEach((f, idx) => {
        const field = SCREENER_FIELDS.find(sf => sf.key === f.field);
        if (!field) return;
        const op = SCREENER_OPERATORS.find(o => o.key === f.operator);
        const opLabel = op ? op.label : "=";
        let valueLabel = "";
        if (field.type === "categorical") {
            valueLabel = (f.values && f.values.length) ? f.values.join(", ") : "any";
        } else if (f.operator === "between") {
            valueLabel = `${f.value} – ${f.value_max}`;
        } else {
            valueLabel = `${f.value}`;
        }
        chips.push({
            key: `screen:${idx}`,
            label: `${field.label} ${opLabel} ${valueLabel}`,
            onRemove: () => {
                screeningFilters.splice(idx, 1);
                renderScreenerFilters();
            },
        });
    });

    if (chips.length === 0) {
        bar.hidden = true;
        bar.innerHTML = "";
        return;
    }

    bar.hidden = false;
    bar.innerHTML = `
        <div class="active-filters-header">
            <span class="active-filters-title">Active Filters</span>
            <button type="button" class="btn-text" id="active-filters-clear">Clear All</button>
        </div>
        <div class="active-filters-chips">
            ${chips.map(chip => `
                <span class="active-filter-chip" data-key="${chip.key}">
                    <span class="active-filter-chip-label">${chip.label}</span>
                    <button type="button" class="active-filter-chip-remove" aria-label="Remove filter" data-key="${chip.key}">×</button>
                </span>
            `).join("")}
        </div>
    `;

    bar.querySelectorAll(".active-filter-chip-remove").forEach(btn => {
        btn.addEventListener("click", (e) => {
            e.stopPropagation();
            const key = btn.dataset.key;
            const chip = chips.find(c => c.key === key);
            if (chip && chip.onRemove) {
                chip.onRemove();
                renderActiveFilters();
            }
        });
    });

    const clearAllBtn = bar.querySelector("#active-filters-clear");
    if (clearAllBtn) {
        clearAllBtn.addEventListener("click", () => {
            currentCategories = [];
            updateCategoryTriggerAndList();
            screeningFilters = [];
            renderScreenerFilters();
            renderActiveFilters();
        });
    }
}

function updateCategoryTriggerAndList() {
    const valueEl = document.getElementById("category-value");
    const countEl = document.getElementById("category-count");
    const trigger = document.getElementById("category-trigger");
    if (valueEl) {
        if (currentCategories.length === 0) {
            valueEl.textContent = "All Categories";
            valueEl.classList.remove("has-selection");
        } else if (currentCategories.length === categories.length) {
            valueEl.textContent = "All Categories";
            valueEl.classList.add("has-selection");
        } else if (currentCategories.length === 1) {
            valueEl.textContent = currentCategories[0];
            valueEl.classList.add("has-selection");
        } else {
            valueEl.textContent = `${currentCategories.length} categories selected`;
            valueEl.classList.add("has-selection");
        }
    }
    if (countEl) {
        countEl.textContent = `${currentCategories.length} selected`;
    }
    if (trigger) {
        trigger.setAttribute("aria-expanded", "false");
    }
    const listContainer = document.getElementById("category-list");
    if (listContainer) {
        listContainer.querySelectorAll(".category-picker-item").forEach(item => {
            const v = item.dataset.value;
            const selected = currentCategories.includes(v);
            item.classList.toggle("selected", selected);
            item.setAttribute("aria-selected", selected);
            const checkbox = item.querySelector(".category-picker-checkbox");
            if (checkbox) {
                checkbox.innerHTML = selected
                    ? '<svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor"><path d="M11.2 3.8L5.5 9.5 2.8 6.8l-.9.9L5.5 11.3 12.1 4.7l-.9-.9z"/></svg>'
                    : '';
            }
        });
    }
}

function updateComparisonBar() {
    const bar = document.getElementById("comparison-bar");
    if (!bar) return;
    const count = selectedFunds.size;
    const countEl = document.getElementById("comparison-count");
    const compareBtn = document.getElementById("compare-btn");
    if (countEl) countEl.textContent = `${count} fund${count !== 1 ? "s" : ""} selected`;
    if (compareBtn) compareBtn.disabled = count < MIN_COMPARE;
    bar.classList.toggle("active", count > 0);
}

function updateSelectAllCheckbox() {
    const selectAll = document.querySelector(".compare-select-all");
    if (!selectAll) return;
    const checkboxes = document.querySelectorAll(".compare-cb");
    const allChecked = checkboxes.length > 0 && Array.from(checkboxes).every(cb => cb.checked);
    selectAll.checked = allChecked;
}

function updateRowCheckboxes() {
    document.querySelectorAll(".compare-cb").forEach(cb => {
        cb.checked = selectedFunds.has(cb.dataset.scheme);
    });
}

function parseDateOnly(s) {
    if (!s) return null;
    if (typeof s !== "string") return null;
    const iso = s.match(/^(\d{4})-(\d{2})-(\d{2})/);
    if (iso) {
        return new Date(Date.UTC(+iso[1], +iso[2] - 1, +iso[3]));
    }
    const dmy = s.match(/^(\d{2})-([A-Za-z]{3})-(\d{4})/);
    if (dmy) {
        const months = { jan: 0, feb: 1, mar: 2, apr: 3, may: 4, jun: 5, jul: 6, aug: 7, sep: 8, oct: 9, nov: 10, dec: 11 };
        const m = months[dmy[2].toLowerCase()];
        if (m != null) return new Date(Date.UTC(+dmy[3], m, +dmy[1]));
    }
    return null;
}

function formatDateHumanForComparison(d) {
    if (!(d instanceof Date) || isNaN(d.getTime())) return null;
    return d.toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric", timeZone: "UTC" });
}

function formatYearOnly(d) {
    if (!(d instanceof Date) || isNaN(d.getTime())) return null;
    return String(d.getUTCFullYear());
}

function computeCommonComparisonPeriod(enrichedFunds) {
    const starts = [];
    const ends = [];
    enrichedFunds.forEach(f => {
        const d = f._detail || {};
        const s = parseDateOnly(d.data_start_date || d.first_nav_date);
        const e = parseDateOnly(d.data_end_date || d.nav_date);
        if (s) starts.push(s);
        if (e) ends.push(e);
    });
    if (starts.length === 0 || ends.length === 0) return null;

    const commonStart = new Date(Math.max(...starts.map(d => d.getTime())));
    const commonEnd = new Date(Math.min(...ends.map(d => d.getTime())));
    if (commonEnd <= commonStart) {
        return null;
    }

    const fundsWithFullRange = enrichedFunds.filter(f => {
        const s = parseDateOnly(f._detail?.data_start_date || f._detail?.first_nav_date);
        const e = parseDateOnly(f._detail?.data_end_date || f._detail?.nav_date);
        return s && e && s <= commonStart && e >= commonEnd;
    }).length;

    const earliest = new Date(Math.min(...starts.map(d => d.getTime())));
    const latest = new Date(Math.max(...ends.map(d => d.getTime())));

    const commonStartStr = formatDateHumanForComparison(commonStart);
    const commonEndStr = formatDateHumanForComparison(commonEnd);
    const earliestStr = formatDateHumanForComparison(earliest);
    const latestStr = formatDateHumanForComparison(latest);
    const commonStartYear = formatYearOnly(commonStart);
    const commonEndYear = formatYearOnly(commonEnd);

    const truncated = (earliestStr !== commonStartStr) || (latestStr !== commonEndStr);
    const tip = truncated
        ? `Common overlapping period used for comparable calculations. Individual fund histories: ${earliestStr} → ${latestStr}.`
        : "Common period used for comparable calculations across selected funds.";

    return `
        <span class="comparison-period-icon" aria-hidden="true">
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                <rect x="2" y="3" width="10" height="9" rx="1.5"/>
                <line x1="2" y1="6" x2="12" y2="6"/>
                <line x1="5" y1="1" x2="5" y2="3.5"/>
                <line x1="9" y1="1" x2="9" y2="3.5"/>
            </svg>
        </span>
        <span class="comparison-period-label">Comparison period</span>
        <span class="comparison-period-value">${commonStartStr} – ${commonEndStr} <span class="comparison-period-years">(${commonStartYear} → ${commonEndYear})</span></span>
        <span class="comparison-period-tooltip-trigger" tabindex="0" role="button" aria-label="Period details">ⓘ
            <span class="comparison-period-tooltip-content">${tip} ${fundsWithFullRange}/${enrichedFunds.length} funds cover the full common period.</span>
        </span>
        ${truncated ? `<span class="comparison-period-note">Some funds have shorter histories</span>` : ""}
    `;
}

async function showComparisonView() {
    if (selectedFunds.size < MIN_COMPARE) return;
    isComparisonView = true;
    const resultsContainer = document.querySelector(".ranking-results");
    if (!resultsContainer) return;

    const selected = filteredRankings.filter(r => selectedFunds.has(r.scheme_code));

    showLoading(resultsContainer, "Loading comparison data...");

    try {
        const detailPromises = selected.map(f =>
            api.get(`/mutual-funds/${f.scheme_code}/detail`).catch(err => {
                console.error(`Failed to fetch detail for ${f.scheme_code}:`, err);
                return null;
            })
        );

        const categoryAnalysisPromises = selected.map(f =>
            api.get(`/mutual-funds/${f.scheme_code}/category-analysis`).catch(err => {
                console.error(`Failed to fetch category analysis for ${f.scheme_code}:`, err);
                return null;
            })
        );

        const [details, categoryAnalyses] = await Promise.all([
            Promise.all(detailPromises),
            Promise.all(categoryAnalysisPromises),
        ]);

        const enriched = selected.map((fund, i) => ({
            ...fund,
            _detail: details[i],
            _categoryAnalysis: categoryAnalyses[i],
        }));

        resultsContainer.innerHTML = "";
        renderComparisonTable(resultsContainer, enriched);

        const summarySection = document.createElement("div");
        summarySection.className = "comparison-chart-module";
        resultsContainer.appendChild(summarySection);
        await renderPerformanceSummary(summarySection, enriched);

        const analysisContainer = document.createElement("div");
        analysisContainer.className = "comparison-analysis-sections";
        resultsContainer.appendChild(analysisContainer);

        const riskReturnSection = document.createElement("div");
        riskReturnSection.className = "comparison-chart-module";
        analysisContainer.appendChild(riskReturnSection);
        renderRiskReturnChart(riskReturnSection, enriched);

        const drawdownSection = document.createElement("div");
        drawdownSection.className = "comparison-chart-module";
        analysisContainer.appendChild(drawdownSection);
        renderDrawdownChart(drawdownSection, enriched);

        const rollingSection = document.createElement("div");
        rollingSection.className = "comparison-chart-module";
        analysisContainer.appendChild(rollingSection);
        renderRollingReturnsChart(rollingSection, enriched);

        const navSection = document.createElement("div");
        navSection.className = "comparison-chart-module";
        analysisContainer.appendChild(navSection);
        await renderNavHistoryChart(navSection, enriched);
    } catch (error) {
        resultsContainer.innerHTML = `<div class="empty-state"><h3>Comparison failed</h3><p>${error.message}</p></div>`;
    }
}

function hideComparisonView() {
    isComparisonView = false;
    const resultsContainer = document.querySelector(".ranking-results");
    if (!resultsContainer) return;
    resultsContainer.innerHTML = "";

    const summaryHtml = `
        <div id="ranking-summary">
            <div>
                <h3>${currentCategories.length === 1 ? currentCategories[0] : `${currentCategories.length} categories`} Rankings</h3>
                <span class="result-meta" id="result-count">${currentRankings.length} unique funds ranked</span>
            </div>
            <span class="result-meta">Preset: ${PRESETS[currentPreset]?.label || currentPreset}</span>
        </div>
        <div id="ranking-result-filters"></div>
    `;
    resultsContainer.innerHTML = summaryHtml;

    const tableContainer = document.createElement("div");
    tableContainer.id = "ranking-table-container";
    resultsContainer.appendChild(tableContainer);

    const existingBar = document.getElementById("comparison-bar");
    if (existingBar) existingBar.remove();

    const comparisonBar = document.createElement("div");
    comparisonBar.id = "comparison-bar";
    comparisonBar.className = `comparison-bar${selectedFunds.size > 0 ? " active" : ""}`;
    comparisonBar.innerHTML = `
        <span class="comparison-bar-text" id="comparison-count">${selectedFunds.size} fund${selectedFunds.size !== 1 ? "s" : ""} selected</span>
        <div class="comparison-bar-actions">
            <button class="btn-text" id="clear-selection">Clear</button>
            <button class="btn-primary btn-small" id="compare-btn" ${selectedFunds.size < MIN_COMPARE ? "disabled" : ""}>Compare Funds</button>
        </div>
    `;
    document.getElementById("ranking-summary").appendChild(comparisonBar);

    document.getElementById("clear-selection").addEventListener("click", () => {
        selectedFunds.clear();
        updateComparisonBar();
        updateRowCheckboxes();
        const selectAll = document.querySelector(".compare-select-all");
        if (selectAll) selectAll.checked = false;
    });

    document.getElementById("compare-btn").addEventListener("click", showComparisonView);

    buildResultFilters(filteredRankings);
    renderFilteredTable(filteredRankings);
    updateComparisonBar();
}

function renderComparisonTable(container, enrichedFunds) {
    if (!enrichedFunds || enrichedFunds.length < MIN_COMPARE) {
        container.innerHTML = `<div class="empty-state"><h3>Not enough funds selected</h3><p>Select at least ${MIN_COMPARE} funds to compare.</p></div>`;
        return;
    }

    const formatValue = (value, unit) => {
        if (value == null) return "Not available";
        if (unit === "percent") return `${(value * 100).toFixed(2)}%`;
        if (unit === "percentage") return `${value.toFixed(2)}%`;
        if (unit === "ratio") return value.toFixed(2);
        if (unit === "integer") return Math.round(value).toLocaleString();
        if (unit === "currency") return `₹${value.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
        return value.toFixed(2);
    };

    const getDetailValue = (fund, key) => {
        if (!fund._detail) return null;
        const val = fund._detail[key];
        if (val === "" || val === undefined) return null;
        return val;
    };

    const getMetricValue = (fund, key) => {
        if (key === "overall_score") return fund.overall_score;

        const detailKey = key === "1Y_return" ? "one_year_return" :
                         key === "3Y_cagr" ? "three_year_cagr" :
                         key === "5Y_cagr" ? "five_year_cagr" :
                         key === "10Y_cagr" ? "ten_year_cagr" :
                         key === "sharpe_ratio" ? "sharpe_ratio" :
                         key === "sortino_ratio" ? "sortino_ratio" :
                         key === "volatility" ? "annualized_volatility" :
                         key === "maximum_drawdown" ? "maximum_drawdown" :
                         key === "downside_deviation" ? "downside_deviation" :
                         key === "consistency" ? null : key;

        if (detailKey) {
            const val = getDetailValue(fund, detailKey);
            if (val != null) return val;
        }

        const cs = (fund.criteria_scores || []).find(c => c.criterion === key);
        return cs ? cs.raw_value : null;
    };

    const getRollingValue = (fund, period, metric) => {
        if (!fund._detail) return null;
        const rolling = fund._detail.rolling_return_consistency;
        if (!rolling) return null;
        const window = rolling[period];
        if (!window) return null;
        return window[metric];
    };

    const isHigherBetter = (key) => {
        const meta = COMPARE_METRICS.find(m => m.key === key);
        return meta ? meta.higherBetter : true;
    };

    const getBestIndices = (values, higherBetter) => {
        const valid = values.filter(v => v != null);
        if (valid.length < 2) return new Set();

        const best = new Set();
        let bestValue = higherBetter ? -Infinity : Infinity;

        values.forEach((v, i) => {
            if (v == null) return;
            if (higherBetter ? v > bestValue : v < bestValue) {
                bestValue = v;
                best.clear();
                best.add(i);
            } else if (v === bestValue) {
                best.add(i);
            }
        });

        return best;
    };

    const sectionHeader = (label) => {
        const tr = document.createElement("tr");
        tr.innerHTML = `<td class="comparison-section-header" colspan="${enrichedFunds.length + 1}">${label}</td>`;
        return tr;
    };

    const wrapper = document.createElement("div");
    wrapper.className = "comparison-view";

    const header = document.createElement("div");
    header.className = "comparison-header";
    const periodInfo = computeCommonComparisonPeriod(enrichedFunds);
    header.innerHTML = `
        <div class="comparison-header-top">
            <button class="btn-back" id="back-to-rankings">← Back to Rankings</button>
            <div class="comparison-header-titles">
                <h3 class="comparison-title">Fund Comparison</h3>
                <p class="comparison-subtitle">${enrichedFunds.length} funds selected for side-by-side analysis</p>
            </div>
        </div>
        ${periodInfo ? `<div class="comparison-period-strip">${periodInfo}</div>` : ""}
    `;
    wrapper.appendChild(header);

    const identitySection = document.createElement("div");
    identitySection.className = "comparison-identity-grid";
    enrichedFunds.forEach((fund, i) => {
        const amc = fund.amc || fund._detail?.amc || "AMC not available";
        const category = fund._categoryAnalysis?.category
            || fund.category
            || fund._detail?.category
            || "Category not available";
        const colorIndex = i % 5;
        const card = document.createElement("div");
        card.className = `fund-identity-card fund-color-${colorIndex}`;
        card.innerHTML = `
            <div class="fund-identity-accent"></div>
            <div class="fund-identity-body">
                <div class="fund-identity-name"><span class="fund-link" data-scheme="${fund.scheme_code}" data-name="${encodeURIComponent(fund.scheme_name)}">${fund.scheme_name}</span></div>
                <div class="fund-identity-meta">
                    <span class="fund-identity-amc">${amc}</span>
                    <span class="fund-identity-sep">·</span>
                    <span class="fund-identity-category">${category}</span>
                </div>
            </div>
        `;
        identitySection.appendChild(card);
    });
    wrapper.appendChild(identitySection);

    const kpiSection = document.createElement("div");
    kpiSection.className = "comparison-kpi-section";
    const kpiTitleRow = document.createElement("div");
    kpiTitleRow.className = "comparison-kpi-title-row";
    const kpiLegend = document.createElement("div");
    kpiLegend.className = "comparison-kpi-legend";
    enrichedFunds.forEach((f, i) => {
        const chip = document.createElement("span");
        chip.className = `comparison-legend-chip fund-color-${i % 5}`;
        chip.innerHTML = `<span class="comparison-legend-swatch"></span><span class="comparison-legend-label">F${i + 1}</span><span class="comparison-legend-name">${f.scheme_name}</span>`;
        kpiLegend.appendChild(chip);
    });
    kpiTitleRow.innerHTML = `
        <h4 class="comparison-kpi-title">Key Metrics at a Glance</h4>
        <p class="comparison-kpi-subtitle">Best value per metric is highlighted across the selected funds.</p>
    `;
    kpiSection.appendChild(kpiTitleRow);
    kpiSection.appendChild(kpiLegend);
    const kpiGrid = document.createElement("div");
    kpiGrid.className = "comparison-kpi-grid";
    kpiSection.appendChild(kpiGrid);
    wrapper.appendChild(kpiSection);

    const KPI_METRICS = [
        { key: "3Y_cagr", label: "3Y CAGR", unit: "percent", higherBetter: true, semantic: "positive" },
        { key: "5Y_cagr", label: "5Y CAGR", unit: "percent", higherBetter: true, semantic: "positive" },
        { key: "volatility", label: "Annualized Volatility", unit: "percent", higherBetter: false, semantic: "risk" },
        { key: "sharpe_ratio", label: "Sharpe Ratio", unit: "ratio", higherBetter: true, semantic: "positive" },
        { key: "sortino_ratio", label: "Sortino Ratio", unit: "ratio", higherBetter: true, semantic: "positive" },
        { key: "maximum_drawdown", label: "Maximum Drawdown", unit: "percent", higherBetter: false, semantic: "risk" },
    ];

    const kpiValuesByMetric = KPI_METRICS.map(m => enrichedFunds.map(f => getMetricValue(f, m.key)));
    const kpiBestByMetric = KPI_METRICS.map((m, i) => getBestIndices(kpiValuesByMetric[i], m.higherBetter));

    KPI_METRICS.forEach((m, mi) => {
        const values = kpiValuesByMetric[mi];
        const best = kpiBestByMetric[mi];
        const card = document.createElement("div");
        card.className = `kpi-card kpi-${m.semantic}`;
        let row = `<div class="kpi-card-header"><span class="kpi-card-label">${m.label}</span></div>`;
        row += `<div class="kpi-card-values">`;
        values.forEach((v, fi) => {
            const isBest = best.has(fi) && v != null;
            const display = formatValue(v, m.unit);
            row += `<div class="kpi-cell${isBest ? " kpi-best" : ""}"><span class="kpi-cell-value">${display}</span><span class="kpi-cell-fund">F${fi + 1}</span></div>`;
        });
        row += `</div>`;
        card.innerHTML = row;
        kpiGrid.appendChild(card);
    });

    const tableWrapper = document.createElement("div");
    tableWrapper.className = "comparison-table-wrapper";

    const table = document.createElement("table");
    table.className = "comparison-table";

    const thead = document.createElement("thead");
    const headerRow = document.createElement("tr");
    headerRow.innerHTML = `<th>Metric</th>${enrichedFunds.map((f, i) => `<th class="fund-col fund-color-${i % 5}"><div class="fund-col-tag">F${i + 1}</div><div class="fund-col-name"><span class="fund-link" data-scheme="${f.scheme_code}" data-name="${encodeURIComponent(f.scheme_name)}">${f.scheme_name}</span></div><div class="fund-col-meta">${f.amc || "—"} · ${f.scheme_code}</div></th>`).join("")}`;
    thead.appendChild(headerRow);
    table.appendChild(thead);

    const tbody = document.createElement("tbody");

    const fundInfoRows = [
        { label: "AMC", key: "amc", fallback: (f) => f.amc || "Not available" },
        { label: "Scheme Code", key: "scheme_code", fallback: (f) => f.scheme_code || "Not available" },
        { label: "Category", key: "category", fallback: (f) => f.category || "Not available" },
        { label: "Plan", key: "plan", fallback: (f) => f._detail?.plan || "Not available" },
        { label: "Option", key: "option", fallback: (f) => f._detail?.option || "Not available" },
        { label: "Fund Inception", key: "first_nav_date", fallback: (f) => f.first_nav_date || "Not available" },
        { label: "Fund Age", key: "fund_age_years", fallback: (f) => f._detail?.fund_age_years != null ? `${f._detail.fund_age_years.toFixed(2)} years` : "Not available" },
        { label: "Total AUM", key: "total_aum_cr", fallback: (f) => f._detail?.total_aum_cr != null ? `₹${f._detail.total_aum_cr.toLocaleString()} Cr` : (f.aum_cr != null ? `₹${f.aum_cr.toLocaleString()} Cr` : "Not available") },
        { label: "Overall Score", key: null, fallback: (f) => f.overall_score != null ? `${f.overall_score.toFixed(1)} / 100` : "Not available" },
    ];

    tbody.appendChild(sectionHeader("Fund Information"));

    fundInfoRows.forEach(row => {
        const values = enrichedFunds.map(f => {
            const val = getDetailValue(f, row.key);
            if (val != null) return row.key === "aum_cr" ? `₹${val.toLocaleString()} Cr` : String(val);
            return row.fallback(f);
        });
        const tr = document.createElement("tr");
        tr.innerHTML = `<td class="metric-label">${row.label}</td>${values.map(v => `<td class="metric-value">${v}</td>`).join("")}`;
        tbody.appendChild(tr);
    });

    tbody.appendChild(sectionHeader("Category Context"));

    const getCategoryAnalysis = (f) => f._categoryAnalysis || null;

    const getAveragePercentile = (analysis) => {
        if (!analysis || !analysis.metrics || analysis.metrics.length === 0) return null;
        const validPercentiles = analysis.metrics
            .map(m => m.percentile)
            .filter(p => p != null);
        if (validPercentiles.length === 0) return null;
        return validPercentiles.reduce((sum, p) => sum + p, 0) / validPercentiles.length;
    };

    const getCategoryCount = (analysis) => {
        if (!analysis || !analysis.metrics || analysis.metrics.length === 0) return null;
        const counts = analysis.metrics
            .map(m => m.category_count)
            .filter(c => c != null);
        if (counts.length === 0) return null;
        return Math.max(...counts);
    };

    const getEstimatedRank = (avgPercentile, categoryCount) => {
        if (avgPercentile == null || categoryCount == null) return null;
        return Math.max(1, Math.min(categoryCount, Math.round((100 - avgPercentile) / 100 * categoryCount) + 1));
    };

    const allSameCategory = enrichedFunds.length >= 2 &&
        enrichedFunds.every(f => {
            const analysis = getCategoryAnalysis(f);
            return analysis && analysis.category && analysis.category === enrichedFunds[0]._categoryAnalysis?.category;
        });

    const firstCategory = (() => {
        const analysis = getCategoryAnalysis(enrichedFunds[0]);
        return analysis?.category || enrichedFunds[0].category || enrichedFunds[0]._detail?.category || null;
    })();

    if (allSameCategory && firstCategory) {
        const noteTr = document.createElement("tr");
        noteTr.innerHTML = `<td colspan="${enrichedFunds.length + 1}" class="category-context-note">All selected funds belong to the <strong>${firstCategory}</strong> category.</td>`;
        tbody.appendChild(noteTr);
    } else if (enrichedFunds.length >= 2) {
        const noteTr = document.createElement("tr");
        noteTr.innerHTML = `<td colspan="${enrichedFunds.length + 1}" class="category-context-note">Selected funds belong to different categories. Ranks shown are within each fund's own category.</td>`;
        tbody.appendChild(noteTr);
    }

    const categoryContextRows = [
        {
            label: "Category",
            getValue: (f) => {
                const analysis = getCategoryAnalysis(f);
                return analysis?.category || f.category || f._detail?.category || null;
            },
            format: (v) => v != null ? String(v) : null,
        },
        {
            label: "Category Rank",
            getValue: (f) => {
                const analysis = getCategoryAnalysis(f);
                const avgPercentile = getAveragePercentile(analysis);
                const categoryCount = getCategoryCount(analysis);
                return getEstimatedRank(avgPercentile, categoryCount);
            },
            format: (v, f) => {
                if (v == null) return null;
                const analysis = getCategoryAnalysis(f);
                const categoryCount = getCategoryCount(analysis);
                return categoryCount != null ? `${v} / ${categoryCount}` : `${v}`;
            },
        },
        {
            label: "Category Percentile",
            getValue: (f) => {
                const analysis = getCategoryAnalysis(f);
                return getAveragePercentile(analysis);
            },
            format: (v) => v != null ? `${Math.round(v)}th` : null,
        },
    ];

    categoryContextRows.forEach(row => {
        const values = enrichedFunds.map(f => {
            const raw = row.getValue(f);
            return row.format(raw, f);
        });
        const tr = document.createElement("tr");
        tr.innerHTML = `<td class="metric-label">${row.label}</td>${values.map(v => {
            const display = v != null ? v : "Not available";
            return `<td class="metric-value">${display}</td>`;
        }).join("")}`;
        tbody.appendChild(tr);
    });

    tbody.appendChild(sectionHeader("Data Period"));

    const dataPeriods = enrichedFunds.map(f => {
        if (f._detail && f._detail.data_start_date && f._detail.data_end_date) {
            const points = f._detail.data_points != null ? ` (${f._detail.data_points.toLocaleString()} points)` : "";
            return `${f._detail.data_start_date} to ${f._detail.data_end_date}${points}`;
        }
        return "Not available";
    });

    const periodTr = document.createElement("tr");
    periodTr.innerHTML = `<td class="metric-label">Period</td>${dataPeriods.map(v => `<td class="metric-value comparison-data-period">${v}</td>`).join("")}`;
    tbody.appendChild(periodTr);

    tbody.appendChild(sectionHeader("Performance"));

    const performanceMetrics = [
        { key: "1Y_return", label: "1Y Return", unit: "percent" },
        { key: "3Y_cagr", label: "3Y CAGR", unit: "percent" },
        { key: "5Y_cagr", label: "5Y CAGR", unit: "percent" },
        { key: "10Y_cagr", label: "10Y CAGR", unit: "percent" },
    ];

    performanceMetrics.forEach(metric => {
        const values = enrichedFunds.map(f => getMetricValue(f, metric.key));
        const bestIndices = getBestIndices(values, true);
        const tr = document.createElement("tr");
        tr.innerHTML = `<td class="metric-label">${metric.label}</td>${values.map((v, i) => {
            const isBest = bestIndices.has(i) && v != null;
            return `<td class="metric-value${isBest ? " best" : ""}">${formatValue(v, metric.unit)}${isBest ? '<span class="best-indicator">●</span>' : ""}</td>`;
        }).join("")}`;
        tbody.appendChild(tr);
    });

    tbody.appendChild(sectionHeader("Risk"));

    const riskMetrics = [
        { key: "volatility", label: "Annualized Volatility", unit: "percent" },
        { key: "sharpe_ratio", label: "Sharpe Ratio", unit: "ratio" },
        { key: "sortino_ratio", label: "Sortino Ratio", unit: "ratio" },
        { key: "maximum_drawdown", label: "Maximum Drawdown", unit: "percent" },
        { key: "downside_deviation", label: "Downside Deviation", unit: "percent" },
    ];

    riskMetrics.forEach(metric => {
        const values = enrichedFunds.map(f => getMetricValue(f, metric.key));
        const bestIndices = getBestIndices(values, isHigherBetter(metric.key));
        const tr = document.createElement("tr");
        tr.innerHTML = `<td class="metric-label">${metric.label}</td>${values.map((v, i) => {
            const isBest = bestIndices.has(i) && v != null;
            return `<td class="metric-value${isBest ? " best" : ""}">${formatValue(v, metric.unit)}${isBest ? '<span class="best-indicator">●</span>' : ""}</td>`;
        }).join("")}`;
        tbody.appendChild(tr);
    });

    tbody.appendChild(sectionHeader("Risk & Risk-Adjusted Performance"));

    const riskAdjustedMetrics = [
        { key: "volatility", label: "Annualized Volatility", unit: "percent", available: true },
        { key: "sharpe_ratio", label: "Sharpe Ratio", unit: "ratio", available: true },
        { key: "sortino_ratio", label: "Sortino Ratio", unit: "ratio", available: true },
        { key: "maximum_drawdown", label: "Maximum Drawdown", unit: "percent", available: true },
        { key: "beta", label: "Beta", unit: "ratio", available: false },
        { key: "alpha", label: "Alpha", unit: "percent", available: false },
    ];

    riskAdjustedMetrics.forEach(metric => {
        const values = metric.available
            ? enrichedFunds.map(f => getMetricValue(f, metric.key))
            : enrichedFunds.map(() => null);
        const bestIndices = metric.available ? getBestIndices(values, isHigherBetter(metric.key)) : new Set();
        const tr = document.createElement("tr");
        tr.innerHTML = `<td class="metric-label">${metric.label}${metric.available ? "" : ' <span class="metric-na-note">(N/A)</span>'}</td>${values.map((v, i) => {
            const isBest = bestIndices.has(i) && v != null;
            const display = formatValue(v, metric.unit);
            const isNa = v == null;
            return `<td class="metric-value${isBest ? " best" : ""}${isNa ? " na" : ""}">${display}${isBest ? '<span class="best-indicator">●</span>' : ""}</td>`;
        }).join("")}`;
        tbody.appendChild(tr);
    });

    tbody.appendChild(sectionHeader("Consistency"));

    const rollingRows = [
        { label: "1Y Positive Rolling Periods (%)", period: "1Y", metric: "positive_pct", unit: "percentage" },
        { label: "3Y Positive Rolling Periods (%)", period: "3Y", metric: "positive_pct", unit: "percentage" },
        { label: "5Y Positive Rolling Periods (%)", period: "5Y", metric: "positive_pct", unit: "percentage" },
        { label: "Mean Rolling Return (1Y)", period: "1Y", metric: "mean_return", unit: "percent" },
        { label: "Median Rolling Return (1Y)", period: "1Y", metric: "median_return", unit: "percent" },
        { label: "Worst Rolling Return (1Y)", period: "1Y", metric: "min_return", unit: "percent" },
    ];

    rollingRows.forEach(row => {
        const values = enrichedFunds.map(f => getRollingValue(f, row.period, row.metric));
        const bestIndices = row.metric === "positive_pct" ? getBestIndices(values, true) : getBestIndices(values, true);
        const tr = document.createElement("tr");
        tr.innerHTML = `<td class="metric-label">${row.label}</td>${values.map((v, i) => {
            const isBest = bestIndices.has(i) && v != null;
            return `<td class="metric-value${isBest ? " best" : ""}">${formatValue(v, row.unit)}${isBest ? '<span class="best-indicator">●</span>' : ""}</td>`;
        }).join("")}`;
        tbody.appendChild(tr);
    });

    table.appendChild(tbody);
    tableWrapper.appendChild(table);
    wrapper.appendChild(tableWrapper);
    container.appendChild(wrapper);

    document.getElementById("back-to-rankings").addEventListener("click", hideComparisonView);

    wrapper.querySelectorAll(".fund-link").forEach(link => {
        link.addEventListener("click", () => {
            const schemeCode = link.dataset.scheme;
            const schemeName = decodeURIComponent(link.dataset.name);
            openFundDetail(schemeCode, schemeName);
        });
    });
}

function buildResultFilters(rankings) {
    const container = document.getElementById("ranking-result-filters");
    if (!container) return;

    const availableFilters = [];
    if (rankings.some(r => r.overall_score != null)) {
        availableFilters.push("overall_score");
    }
    const criteriaKeys = Object.keys(FILTER_META).filter(k => k !== "overall_score" && k !== "nav" && k !== "data_points");
    for (const key of criteriaKeys) {
        if (rankings.some(r => getFilterValue(r, key) != null)) {
            availableFilters.push(key);
        }
    }
    if (rankings.some(r => r.nav != null)) {
        availableFilters.push("nav");
    }
    if (rankings.some(r => r.data_points != null)) {
        availableFilters.push("data_points");
    }

    if (!availableFilters.length) {
        container.innerHTML = "";
        return;
    }

    const filterRows = availableFilters.map(filterKey => {
        const meta = FILTER_META[filterKey];
        const unitLabel = meta.unit === "percent" ? "%" : meta.unit === "currency" ? "₹" : "";
        return `
            <div class="filter-chip" data-filter="${filterKey}">
                <span class="filter-chip-label">${meta.label}</span>
                <div class="filter-chip-controls">
                    <select class="filter-op" id="${filterKey}-op-ge" aria-label="${meta.label} min operator">
                        <option value=">=">&ge;</option>
                        <option value="<=">&le;</option>
                    </select>
                    <input type="number" class="filter-input" id="filter-${filterKey}-ge" placeholder="Min" step="${meta.step}" ${meta.unit === "integer" ? 'min="0"' : ''}>
                    <span class="filter-to">to</span>
                    <select class="filter-op" id="${filterKey}-op-le" aria-label="${meta.label} max operator">
                        <option value="<=">&le;</option>
                        <option value=">=">&ge;</option>
                    </select>
                    <input type="number" class="filter-input" id="filter-${filterKey}-le" placeholder="Max" step="${meta.step}" ${meta.unit === "integer" ? 'min="0"' : ''}>
                    ${unitLabel ? `<span class="filter-unit">${unitLabel}</span>` : ""}
                </div>
            </div>
        `;
    }).join("");

    container.innerHTML = `
        <div class="filter-panel">
            <button type="button" class="filter-toggle" id="filter-toggle">
                <span class="filter-toggle-icon">&#9662;</span>
                <span class="filter-toggle-label">Filter Results</span>
                <span class="filter-toggle-count" id="filter-toggle-count">${rankings.length} funds</span>
            </button>
            <div class="filter-body" id="filter-body" hidden>
                <div class="filter-grid">
                    ${filterRows}
                </div>
                <div class="filter-footer">
                    <button type="button" id="clear-filters" class="btn-text">Clear all</button>
                    <span class="filter-result-count" id="filtered-count">Showing ${rankings.length} of ${rankings.length}</span>
                </div>
            </div>
        </div>
    `;

    const toggle = document.getElementById("filter-toggle");
    const body = document.getElementById("filter-body");
    const toggleIcon = toggle.querySelector(".filter-toggle-icon");
    const toggleCount = document.getElementById("filter-toggle-count");
    const countSpan = document.getElementById("filtered-count");

    toggle.addEventListener("click", () => {
        const isExpanded = !body.hidden;
        body.hidden = isExpanded;
        toggleIcon.style.transform = isExpanded ? "" : "rotate(180deg)";
    });

    function applyFilters() {
        filteredRankings = currentRankings.filter(r => {
            for (const filterKey of availableFilters) {
                const meta = FILTER_META[filterKey];
                const geInput = document.getElementById(`filter-${filterKey}-ge`);
                const leInput = document.getElementById(`filter-${filterKey}-le`);
                const geOpSelect = document.getElementById(`${filterKey}-op-ge`);
                const leOpSelect = document.getElementById(`${filterKey}-op-le`);

                const rawValue = getFilterValue(r, filterKey);
                if (rawValue == null) return false;

                if (geInput && geInput.value !== "") {
                    const inputVal = parseFloat(geInput.value);
                    if (!isNaN(inputVal)) {
                        const backendVal = convertFilterInputToBackend(inputVal, meta.unit);
                        const op = geOpSelect ? geOpSelect.value : ">=";
                        if (op === ">=" && rawValue < backendVal) return false;
                        if (op === "<=" && rawValue > backendVal) return false;
                    }
                }
                if (leInput && leInput.value !== "") {
                    const inputVal = parseFloat(leInput.value);
                    if (!isNaN(inputVal)) {
                        const backendVal = convertFilterInputToBackend(inputVal, meta.unit);
                        const op = leOpSelect ? leOpSelect.value : "<=";
                        if (op === "<=" && rawValue > backendVal) return false;
                        if (op === ">=" && rawValue < backendVal) return false;
                    }
                }
            }
            return true;
        });

        const showCount = filteredRankings.length;
        const totalCount = currentRankings.length;
        countSpan.textContent = `Showing ${showCount} of ${totalCount}`;
        toggleCount.textContent = `${showCount} of ${totalCount} funds`;
        renderFilteredTable(filteredRankings);
    }

    for (const filterKey of availableFilters) {
        const geInput = document.getElementById(`filter-${filterKey}-ge`);
        const leInput = document.getElementById(`filter-${filterKey}-le`);
        if (geInput) geInput.addEventListener("input", applyFilters);
        if (leInput) leInput.addEventListener("input", applyFilters);
    }

    document.getElementById("clear-filters").addEventListener("click", () => {
        for (const filterKey of availableFilters) {
            const geInput = document.getElementById(`filter-${filterKey}-ge`);
            const leInput = document.getElementById(`filter-${filterKey}-le`);
            if (geInput) geInput.value = "";
            if (leInput) leInput.value = "";
        }
        filteredRankings = currentRankings;
        countSpan.textContent = `Showing ${filteredRankings.length} of ${currentRankings.length}`;
        toggleCount.textContent = `${filteredRankings.length} of ${currentRankings.length} funds`;
        renderFilteredTable(filteredRankings);
    });
}

function renderFilteredTable(rankings) {
    const tableContainer = document.getElementById("ranking-table-container");
    if (!tableContainer) return;

    if (!rankings.length) {
        tableContainer.innerHTML = `<div class="empty-state"><h3>No results</h3><p>No funds match the current filters.</p></div>`;
        return;
    }

    const columns = [
        { key: "select", label: "" },
        { key: "rank", label: "Rank" },
        { key: "scheme_name", label: "Fund Name" },
        { key: "amc", label: "AMC" },
        { key: "scheme_code", label: "Scheme Code" },
        { key: "nav", label: "Latest NAV" },
        { key: "overall_score", label: "Overall Score", tooltip: TOOLTIPS.overall_score },
        { key: "details", label: "" },
    ];

    const rows = rankings.map((r, index) => {
        const score = r.overall_score != null ? r.overall_score.toFixed(1) : "N/A";
        const scoreWidth = r.overall_score != null ? Math.max(0, Math.min(100, r.overall_score)) : 0;
        const nav = r.nav != null ? formatNAV(r.nav) : "N/A";
        return {
            rank: index + 1,
            scheme_code: r.scheme_code || "—",
            scheme_name: r.scheme_name,
            amc: r.amc || "—",
            nav: nav,
            nav_raw: r.nav,
            nav_date: r.nav_date || "—",
            data_points: r.data_points != null ? r.data_points : null,
            aum_cr: r.aum_cr != null ? r.aum_cr : null,
            aum_quarter: r.aum_quarter || null,
            aum_quarter_end: r.aum_quarter_end || null,
            first_nav_date: r.first_nav_date || "—",
            overall_score: score,
            score_width: scoreWidth,
            details: r.criteria_scores || [],
            _raw: r,
        };
    });

    const table = document.createElement("table");
    table.className = "data-table";

    const thead = document.createElement("thead");
    const headerRow = document.createElement("tr");
    columns.forEach(col => {
        const th = document.createElement("th");
        if (col.key === "select") {
            th.className = "select-cell";
            const selectAll = document.createElement("input");
            selectAll.type = "checkbox";
            selectAll.className = "compare-select-all";
            selectAll.addEventListener("change", () => {
                const isChecked = selectAll.checked;
                if (isChecked) {
                    rows.forEach(row => {
                        if (selectedFunds.size < MAX_COMPARE) {
                            selectedFunds.add(row.scheme_code);
                        }
                    });
                } else {
                    rows.forEach(row => selectedFunds.delete(row.scheme_code));
                }
                updateComparisonBar();
                updateRowCheckboxes();
            });
            th.appendChild(selectAll);
        } else if (col.tooltip) {
            th.innerHTML = `${col.label} <span class="tooltip-trigger header-tooltip" tabindex="0" role="button" aria-label="Help"><span class="tooltip-content">${col.tooltip}</span>ⓘ</span>`;
        } else {
            th.textContent = col.label;
        }
        headerRow.appendChild(th);
    });
    thead.appendChild(headerRow);
    table.appendChild(thead);

    thead.querySelectorAll(".tooltip-trigger").forEach(trigger => {
        const content = trigger.querySelector(".tooltip-content");
        if (!content) return;
        trigger.addEventListener("click", (e) => {
            e.stopPropagation();
            const isVisible = content.style.opacity === "1";
            document.querySelectorAll(".tooltip-content").forEach(t => {
                t.style.opacity = "0";
                t.style.visibility = "hidden";
            });
            if (!isVisible) {
                content.style.opacity = "1";
                content.style.visibility = "visible";
            }
        });
    });

    const tbody = document.createElement("tbody");
    rows.forEach((row, idx) => {
        const tr = document.createElement("tr");
        if (row.rank <= 3 && row.rank != null) {
            tr.classList.add("top-rank");
        }
        const isSelected = selectedFunds.has(row.scheme_code);
        tr.innerHTML = `
            <td class="select-cell"><input type="checkbox" class="compare-cb" data-scheme="${row.scheme_code}" ${isSelected ? "checked" : ""}></td>
            <td class="rank-cell">${row.rank}</td>
            <td><strong><span class="fund-link" data-scheme="${row.scheme_code}" data-name="${encodeURIComponent(row.scheme_name)}">${row.scheme_name}</span></strong></td>
            <td class="muted">${row.amc}</td>
            <td class="muted">${row.scheme_code}</td>
            <td class="nav-cell">${row.nav}</td>
            <td class="score-cell">
                ${row.overall_score !== "N/A" ? `<span class="score-label">Score</span> ${row.overall_score} <span style="font-weight:400;color:var(--color-text-light);font-size:0.8125rem;">/ 100</span>` : "N/A"}
                <div class="score-bar-bg">
                    <div class="score-bar-fill" style="width: ${row.score_width}%"></div>
                </div>
            </td>
            <td><button class="expand-btn" data-idx="${idx}">Details</button></td>
        `;
        tbody.appendChild(tr);

        const detailTr = document.createElement("tr");
        detailTr.className = "details-row hidden";
        detailTr.dataset.idx = idx;
        detailTr.innerHTML = `<td colspan="${columns.length}"><div class="details-content"></div></td>`;
        tbody.appendChild(detailTr);
    });
    table.appendChild(tbody);
    tableContainer.appendChild(table);


    table.querySelectorAll(".fund-link").forEach(link => {
        link.addEventListener("click", () => {
            const schemeCode = link.dataset.scheme;
            const schemeName = decodeURIComponent(link.dataset.name);
            openFundDetail(schemeCode, schemeName);
        });
    });
    table.querySelectorAll(".compare-cb").forEach(cb => {
        cb.addEventListener("change", () => {
            const scheme = cb.dataset.scheme;
            if (cb.checked) {
                if (selectedFunds.size >= MAX_COMPARE) {
                    cb.checked = false;
                    return;
                }
                selectedFunds.add(scheme);
            } else {
                selectedFunds.delete(scheme);
            }
            updateComparisonBar();
            updateSelectAllCheckbox();
        });
    });

    table.querySelectorAll(".expand-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            const idx = parseInt(btn.dataset.idx, 10);
            const detailRow = table.querySelector(`tr.details-row[data-idx="${idx}"]`);
            const content = detailRow?.querySelector(".details-content");
            if (!content) return;

            const isHidden = detailRow.classList.contains("hidden");
            table.querySelectorAll(".details-row").forEach(r => r.classList.add("hidden"));
            table.querySelectorAll(".expand-btn").forEach(b => b.textContent = "Details");

            if (isHidden) {
                detailRow.classList.remove("hidden");
                btn.textContent = "Hide";
                renderDetailContent(content, rows[idx].details, {
                    nav_date: rows[idx].nav_date,
                    data_points: rows[idx].data_points,
                    category: rows[idx].category,
                    aum_cr: rows[idx].aum_cr,
                    aum_quarter: rows[idx].aum_quarter,
                    aum_quarter_end: rows[idx].aum_quarter_end,
                    first_nav_date: rows[idx].first_nav_date,
                });
            }
        });
    });
}

function renderDetailContent(container, criteriaScores, meta = {}) {
    container.innerHTML = "";
    if (!criteriaScores || !criteriaScores.length) {
        container.innerHTML = `<div class="detail-item"><span class="detail-label">No criteria scores available</span></div>`;
        return;
    }

    const metaSection = document.createElement("div");
    metaSection.className = "detail-meta";
    if (meta.nav_date && meta.nav_date !== "—") {
        const navDateItem = document.createElement("div");
        navDateItem.className = "detail-item";
        navDateItem.innerHTML = `
            <span class="detail-label">NAV Date</span>
            <span class="detail-value">${meta.nav_date}</span>
        `;
        metaSection.appendChild(navDateItem);
    }
    if (meta.data_points != null) {
        const dataPointsItem = document.createElement("div");
        dataPointsItem.className = "detail-item";
        dataPointsItem.innerHTML = `
            <span class="detail-label">Data Points</span>
            <span class="detail-value">${meta.data_points.toLocaleString()}</span>
        `;
        metaSection.appendChild(dataPointsItem);
    }
    if (meta.category && meta.category !== "—") {
        const categoryItem = document.createElement("div");
        categoryItem.className = "detail-item";
        categoryItem.innerHTML = `
            <span class="detail-label">Category</span>
            <span class="detail-value">${meta.category}</span>
        `;
        metaSection.appendChild(categoryItem);
    }
    if (meta.aum_cr != null) {
        const aumItem = document.createElement("div");
        aumItem.className = "detail-item";
        aumItem.innerHTML = `
            <span class="detail-label">AUM (AAUM)</span>
            <span class="detail-value">₹${meta.aum_cr.toLocaleString(undefined, {minimumFractionDigits: 0, maximumFractionDigits: 0})} Cr</span>
        `;
        metaSection.appendChild(aumItem);
    }
    if (meta.aum_quarter_end) {
        const aumDateItem = document.createElement("div");
        aumDateItem.className = "detail-item";
        aumDateItem.innerHTML = `
            <span class="detail-label">AUM As Of</span>
            <span class="detail-value">${meta.aum_quarter_end}</span>
        `;
        metaSection.appendChild(aumDateItem);
    }
    if (meta.first_nav_date && meta.first_nav_date !== "—") {
        const firstNavItem = document.createElement("div");
        firstNavItem.className = "detail-item";
        firstNavItem.innerHTML = `
            <span class="detail-label">First NAV Date</span>
            <span class="detail-value">${meta.first_nav_date}</span>
        `;
        metaSection.appendChild(firstNavItem);
    }
    if (metaSection.children.length) {
        container.appendChild(metaSection);
    }

    criteriaScores.forEach(cs => {
        const meta = CRITERIA_META[cs.criterion] || { label: cs.criterion };
        const score = cs.score != null ? cs.score.toFixed(1) : "N/A";
        const scoreWidth = cs.score != null ? Math.max(0, Math.min(100, cs.score)) : 0;
        const raw = cs.raw_value != null ? formatRawValue(cs.criterion, cs.raw_value) : "N/A";
        const tooltipText = meta.tooltip || meta.description || "";

        const item = document.createElement("div");
        item.className = "detail-item";
        item.innerHTML = `
            <div class="detail-header">
                <span class="detail-label">${meta.label}</span>
                ${tooltipText ? `<span class="tooltip-trigger" tabindex="0" role="button" aria-label="Help"><span class="tooltip-content">${tooltipText}</span>ⓘ</span>` : ""}
            </div>
            <span class="detail-value">Score: ${score} <span style="font-weight:400;color:var(--color-text-light);font-size:0.8125rem;">/ 100</span></span>
            <div class="detail-bar-bg">
                <div class="detail-bar-fill" style="width: ${scoreWidth}%"></div>
            </div>
            <span class="detail-raw">Actual: ${raw}</span>
        `;
        container.appendChild(item);
    });

    container.querySelectorAll(".tooltip-trigger").forEach(trigger => {
        const content = trigger.querySelector(".tooltip-content");
        if (!content) return;

        trigger.addEventListener("click", (e) => {
            e.stopPropagation();
            const isVisible = content.style.opacity === "1";
            document.querySelectorAll(".tooltip-content").forEach(t => {
                t.style.opacity = "0";
                t.style.visibility = "hidden";
            });
            if (!isVisible) {
                content.style.opacity = "1";
                content.style.visibility = "visible";
            }
        });
    });
}

function formatNAV(value) {
    if (value === null || value === undefined) return "N/A";
    const num = Number(value);
    if (isNaN(num)) return "N/A";
    return num.toFixed(2);
}

function formatRawValue(criterion, value) {
    if (value == null) return "N/A";
    if (typeof value !== "number") return String(value);

    switch (criterion) {
        case "1Y_return":
        case "3Y_cagr":
        case "5Y_cagr":
        case "10Y_cagr":
            return `${(value * 100).toFixed(2)}%`;
        case "sharpe_ratio":
        case "sortino_ratio":
            return value.toFixed(2);
        case "volatility":
        case "downside_deviation":
            return `${(value * 100).toFixed(2)}%`;
        case "maximum_drawdown":
            return `${(value * 100).toFixed(2)}%`;
        case "consistency":
            return `${value.toFixed(1)}%`;
        default:
            return value.toFixed(2);
    }
}

document.addEventListener("click", (e) => {
    if (!e.target.closest(".tooltip-trigger")) {
        document.querySelectorAll(".tooltip-content").forEach(t => {
            t.style.opacity = "0";
            t.style.visibility = "hidden";
        });
    }
});
