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
    "1Y_return": { label: "1Y Return", direction: "higher", description: "Simple return over the past year" },
    "3Y_cagr": { label: "3Y CAGR", direction: "higher", description: "3-year compound annual growth rate" },
    "5Y_cagr": { label: "5Y CAGR", direction: "higher", description: "5-year compound annual growth rate" },
    "10Y_cagr": { label: "10Y CAGR", direction: "higher", description: "10-year compound annual growth rate" },
    "sharpe_ratio": { label: "Sharpe Ratio", direction: "higher", description: "Risk-adjusted return (higher is better)" },
    "sortino_ratio": { label: "Sortino Ratio", direction: "higher", description: "Return vs downside risk (higher is better)" },
    "volatility": { label: "Volatility", direction: "lower", description: "Annualized standard deviation (lower is better)" },
    "maximum_drawdown": { label: "Max Drawdown", direction: "lower", description: "Largest peak-to-trough decline (lower is better)" },
    "downside_deviation": { label: "Downside Deviation", direction: "lower", description: "Volatility of negative returns (lower is better)" },
    "consistency": { label: "Consistency", direction: "higher", description: "1Y rolling positive-period percentage (higher is better)" },
};

let currentPreset = "best_overall";
let currentCategory = "";
let categories = [];

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
        buildControls();
    } catch (error) {
        filtersContainer.innerHTML = `<div class="empty-state"><p>Failed to load categories: ${error.message}</p></div>`;
    } finally {
        hideLoading(filtersContainer);
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
            <label for="category-select">Category</label>
            <select id="category-select">
                <option value="">Select a category</option>
                ${categories.map(c => `<option value="${c}">${c}</option>`).join("")}
            </select>
        </div>
    `;

    presetContainer.innerHTML = `
        <div class="filter-group">
            <label for="preset-select">Preset</label>
            <select id="preset-select">
                ${Object.entries(PRESETS).map(([key, preset]) => `<option value="${key}">${preset.label}</option>`).join("")}
            </select>
        </div>
    `;

    document.getElementById("category-select").addEventListener("change", (e) => {
        currentCategory = e.target.value;
    });

    document.getElementById("preset-select").addEventListener("change", (e) => {
        currentPreset = e.target.value;
        applyPreset(currentPreset);
    });

    buildCriteriaList(criteriaContainer);
    buildMethodology(methodologyContainer);

    document.getElementById("run-ranking").addEventListener("click", runRanking);

    applyPreset(currentPreset);
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
                <input type="range" id="range-${key}" min="0" max="100" step="1" value="0">
                <input type="number" id="num-${key}" min="0" max="100" step="1" value="0">
                <span>%</span>
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
        <h4>Methodology</h4>
        <ul>
            <li>Metrics computed from historical NAV data</li>
            <li>Min-max normalized to 0-100 scale</li>
            <li>Higher-is-better metrics ranked directly</li>
            <li>Lower-is-better metrics inverted</li>
            <li>Weights auto-renormalized to 100%</li>
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

        renderRankingResults(response.rankings, response.category);
    } catch (error) {
        resultsContainer.innerHTML = `<div class="empty-state"><p>Ranking failed: ${error.message}</p></div>`;
    } finally {
        hideLoading(resultsContainer);
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
    const summaryContainer = document.getElementById("ranking-summary");
    const tableContainer = document.getElementById("ranking-table-container");

    if (summaryContainer) {
        summaryContainer.innerHTML = `
            <div class="ranking-summary">
                <h3>${category} Rankings</h3>
                <span class="result-meta">${rankings.length} funds ranked</span>
            </div>
        `;
    }

    if (!tableContainer) return;

    if (!rankings.length) {
        tableContainer.innerHTML = `<div class="empty-state"><h3>No results</h3><p>No funds found for this category, or insufficient data to calculate metrics.</p></div>`;
        return;
    }

    const columns = [
        { key: "rank", label: "Rank" },
        { key: "scheme_name", label: "Fund Name" },
        { key: "amc", label: "AMC" },
        { key: "category", label: "Category" },
        { key: "overall_score", label: "Overall Score" },
        { key: "details", label: "" },
    ];

    const rows = rankings.map((r, index) => {
        const score = r.overall_score != null ? r.overall_score.toFixed(1) : "N/A";
        const scoreWidth = r.overall_score != null ? Math.max(0, Math.min(100, r.overall_score)) : 0;
        return {
            rank: index + 1,
            scheme_name: r.scheme_name,
            amc: r.amc || "—",
            category: r.category || "—",
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
        th.textContent = col.label;
        headerRow.appendChild(th);
    });
    thead.appendChild(headerRow);
    table.appendChild(thead);

    const tbody = document.createElement("tbody");
    rows.forEach((row, idx) => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td class="rank-cell">${row.rank}</td>
            <td><strong>${row.scheme_name}</strong></td>
            <td>${row.amc}</td>
            <td>${row.category}</td>
            <td class="score-cell">
                ${row.overall_score}
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
                renderDetailContent(content, rows[idx].details);
            }
        });
    });
}

function renderDetailContent(container, criteriaScores) {
    container.innerHTML = "";
    if (!criteriaScores || !criteriaScores.length) {
        container.innerHTML = `<div class="detail-item"><span class="detail-label">No criteria scores available</span></div>`;
        return;
    }

    criteriaScores.forEach(cs => {
        const meta = CRITERIA_META[cs.criterion] || { label: cs.criterion };
        const score = cs.score != null ? cs.score.toFixed(1) : "N/A";
        const scoreWidth = cs.score != null ? Math.max(0, Math.min(100, cs.score)) : 0;
        const raw = cs.raw_value != null ? formatRawValue(cs.criterion, cs.raw_value) : "N/A";

        const item = document.createElement("div");
        item.className = "detail-item";
        item.innerHTML = `
            <span class="detail-label">${meta.label}</span>
            <span class="detail-value">${score} <span style="font-weight:400;color:var(--color-text-light);font-size:0.8125rem;">/ 100</span></span>
            <div class="detail-bar-bg">
                <div class="detail-bar-fill" style="width: ${scoreWidth}%"></div>
            </div>
            <span class="detail-raw">Raw: ${raw}</span>
        `;
        container.appendChild(item);
    });
}

function formatRawValue(criterion, value) {
    if (value == null) return "N/A";
    if (typeof value !== "number") return String(value);

    switch (criterion) {
        case "1Y_return":
        case "3Y_cagr":
        case "5Y_cagr":
        case "10Y_cagr":
            return `${value.toFixed(2)}%`;
        case "sharpe_ratio":
        case "sortino_ratio":
            return value.toFixed(2);
        case "volatility":
        case "downside_deviation":
            return `${value.toFixed(2)}%`;
        case "maximum_drawdown":
            return `${(value * 100).toFixed(2)}%`;
        case "consistency":
            return `${value.toFixed(1)}%`;
        default:
            return value.toFixed(2);
    }
}
