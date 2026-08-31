import { api } from "../../core/api.js";
import { showLoading, hideLoading } from "../../components/loading.js";

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
let currentCategory = "";
let categories = [];
let currentRankings = [];
let filteredRankings = [];

export function initMutualFundAnalysis() {
    const container = document.getElementById("mutual-fund-content");
    if (!container) return;

    loadCategories();
}

async function loadCategories() {
    const filtersContainer = document.getElementById("ranking-filters");
    if (!filtersContainer) return;

    showLoading(filtersContainer);
    try {
        const response = await api.get("/mutual-funds/categories");
        categories = response.categories || [];
        hideLoading(filtersContainer);
        buildControls();
    } catch (error) {
        hideLoading(filtersContainer);
        filtersContainer.innerHTML = `<div class="empty-state"><p>Failed to load categories: ${error.message}</p></div>`;
    }
}

function buildControls() {
    const filtersContainer = document.getElementById("ranking-filters");
    const presetContainer = document.getElementById("ranking-preset");
    const criteriaContainer = document.getElementById("ranking-criteria");
    const methodologyContainer = document.getElementById("ranking-methodology");

    if (!filtersContainer || !presetContainer || !criteriaContainer || !methodologyContainer) return;

    filtersContainer.innerHTML = `
        <div class="filter-group">
            <label for="category-input">Category</label>
            <div class="combobox" id="category-combobox">
                <input type="text" id="category-input" class="combobox-input" placeholder="Search categories..." autocomplete="off">
                <button type="button" class="combobox-toggle" tabindex="-1">&#9662;</button>
                <div class="combobox-dropdown" id="category-dropdown"></div>
                <input type="hidden" id="category-value">
            </div>
        </div>
    `;

    presetContainer.innerHTML = `
        <div class="filter-group">
            <label for="preset-input">Preset</label>
            <div class="combobox" id="preset-combobox">
                <input type="text" id="preset-input" class="combobox-input" placeholder="Search presets..." autocomplete="off">
                <button type="button" class="combobox-toggle" tabindex="-1">&#9662;</button>
                <div class="combobox-dropdown" id="preset-dropdown"></div>
                <input type="hidden" id="preset-value">
            </div>
        </div>
    `;

    initCombobox({
        id: "category",
        options: categories.map(c => ({ value: c, label: c })),
        onSelect: (value) => { currentCategory = value; },
    });

    initCombobox({
        id: "preset",
        options: Object.entries(PRESETS).map(([key, preset]) => ({ value: key, label: preset.label })),
        onSelect: (value) => {
            currentPreset = value;
            applyPreset(currentPreset);
        },
        selectedValue: currentPreset,
    });

    buildCriteriaList(criteriaContainer);
    buildMethodology(methodologyContainer);

    document.getElementById("run-ranking").addEventListener("click", runRanking);

    applyPreset(currentPreset);
}

function initCombobox({ id, options, onSelect, selectedValue = "" }) {
    const combobox = document.getElementById(`${id}-combobox`);
    const input = document.getElementById(`${id}-input`);
    const dropdown = document.getElementById(`${id}-dropdown`);
    const hidden = document.getElementById(`${id}-value`);
    const toggle = combobox.querySelector(".combobox-toggle");

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
    container.innerHTML = `<div class="criteria-list" id="criteria-list"></div>`;
    const list = document.getElementById("criteria-list");
    if (!list) return;

    Object.entries(CRITERIA_META).forEach(([key, meta]) => {
        const item = document.createElement("div");
        item.className = "criterion-item";
        item.dataset.criterion = key;

        item.innerHTML = `
            <div class="criterion-header">
                <input type="checkbox" id="cb-${key}" checked>
                <label for="cb-${key}">${meta.label}</label>
            </div>
            <div class="criterion-weight">
                <span class="weight-label">Weight:</span>
                <input type="range" id="range-${key}" min="0" max="100" step="1" value="0">
                <input type="number" id="num-${key}" min="0" max="100" step="1" value="0">
                <span class="weight-unit">%</span>
            </div>
        `;

        const checkbox = item.querySelector(`#cb-${key}`);
        const range = item.querySelector(`#range-${key}`);
        const number = item.querySelector(`#num-${key}`);

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
            if (num && range && values[key] > 0) {
                const normalized = (val / total) * 100;
                const rounded = Math.round(normalized * 10) / 10;
                num.value = rounded;
                range.value = rounded;
            }
        });
    }
}

function buildMethodology(container) {
    container.innerHTML = `
        <h4>How to read the results</h4>
        <ul>
            <li><strong>Actual</strong> = the fund's real calculated metric (e.g., 18.00% return, 1.36 Sharpe ratio).</li>
            <li><strong>Score / 100</strong> = normalized ranking score relative to other funds in this category. 100 = best, 0 = worst.</li>
            <li><strong>Overall Score</strong> = weighted combination of individual scores per the selected preset.</li>
            <li>Lower-is-better metrics (volatility, drawdown, downside deviation) are inverted so higher score always means better.</li>
        </ul>
    `;
}

async function runRanking() {
    if (!currentCategory) {
        alert("Please select a category first.");
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

    showLoading(resultsContainer);
    if (summaryContainer) summaryContainer.innerHTML = "";

    try {
        const response = await api.post("/mutual-funds/rank", {
            category: currentCategory,
            criteria: criteria,
            auto_renormalize: true,
        });

        hideLoading(resultsContainer);
        renderRankingResults(response.rankings, response.category);
    } catch (error) {
        hideLoading(resultsContainer);
        resultsContainer.innerHTML = `<div class="empty-state"><p>Ranking failed: ${error.message}</p></div>`;
    }
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

function renderRankingResults(rankings, category) {
    currentRankings = rankings;
    filteredRankings = rankings;

    const summaryContainer = document.getElementById("ranking-summary");
    const tableContainer = document.getElementById("ranking-table-container");

    if (summaryContainer) {
        summaryContainer.innerHTML = `
            <div class="ranking-summary">
                <div>
                    <h3>${category} Rankings</h3>
                    <span class="result-meta" id="result-count">${rankings.length} unique funds ranked</span>
                </div>
                <span class="result-meta">Preset: ${PRESETS[currentPreset]?.label || currentPreset}</span>
            </div>
        `;
    }

    if (!tableContainer) return;

    if (!rankings.length) {
        tableContainer.innerHTML = `<div class="empty-state"><h3>No results</h3><p>No funds found for this category, or insufficient data to calculate metrics.</p></div>`;
        buildResultFilters([]);
        return;
    }

    buildResultFilters(rankings);

    const columns = [
        { key: "rank", label: "Rank" },
        { key: "scheme_name", label: "Fund Name" },
        { key: "amc", label: "AMC" },
        { key: "category", label: "Category" },
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
            scheme_name: r.scheme_name,
            amc: r.amc || "—",
            category: r.category || "—",
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

    tableContainer.innerHTML = "";
    const table = document.createElement("table");
    table.className = "data-table";

    const thead = document.createElement("thead");
    const headerRow = document.createElement("tr");
    columns.forEach(col => {
        const th = document.createElement("th");
        if (col.tooltip) {
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
        tr.innerHTML = `
            <td class="rank-cell">${row.rank}</td>
            <td><strong>${row.scheme_name}</strong></td>
            <td>${row.amc}</td>
            <td>${row.category}</td>
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
        { key: "rank", label: "Rank" },
        { key: "scheme_name", label: "Fund Name" },
        { key: "amc", label: "AMC" },
        { key: "category", label: "Category" },
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
            scheme_name: r.scheme_name,
            amc: r.amc || "—",
            category: r.category || "—",
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
        if (col.tooltip) {
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
        tr.innerHTML = `
            <td class="rank-cell">${row.rank}</td>
            <td><strong>${row.scheme_name}</strong></td>
            <td>${row.amc}</td>
            <td>${row.category}</td>
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
    tableContainer.innerHTML = "";
    tableContainer.appendChild(table);

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
