import { api } from "../../../core/api.js";

const ROWS = [
    { key: "one_year_return", label: "1Y Return", type: "simple", higherBetter: true, unit: "percent" },
    { key: "three_year_cagr", label: "3Y CAGR", type: "cagr", higherBetter: true, unit: "percent" },
    { key: "five_year_cagr", label: "5Y CAGR", type: "cagr", higherBetter: true, unit: "percent" },
    { key: "ten_year_cagr", label: "10Y CAGR", type: "cagr", higherBetter: true, unit: "percent" },
    { key: "since_inception_cagr", label: "Since-Inception CAGR", type: "cagr", higherBetter: true, unit: "percent" },
];

export async function renderPerformanceSummary(container, enrichedFunds) {
    if (!container || !enrichedFunds || enrichedFunds.length < 2) return;

    container.innerHTML = "";

    const wrapper = document.createElement("div");
    wrapper.className = "comparison-chart-section";

    const header = document.createElement("div");
    header.className = "comparison-section-header";
    header.textContent = "Performance Summary";
    wrapper.appendChild(header);

    const description = document.createElement("p");
    description.className = "comparison-chart-description";
    description.textContent = "CAGR (Compound Annual Growth Rate) is shown for periods ≥ 1 year; 1Y figure is a simple period return. Since-Inception CAGR requires the full NAV history to be available.";
    wrapper.appendChild(description);

    const loadingEl = document.createElement("div");
    loadingEl.className = "comparison-chart-loading";
    loadingEl.textContent = "Loading inception history...";
    wrapper.appendChild(loadingEl);

    const tableWrapper = document.createElement("div");
    tableWrapper.className = "comparison-table-wrapper";
    tableWrapper.hidden = true;
    wrapper.appendChild(tableWrapper);

    container.appendChild(wrapper);

    const inceptionData = await fetchInceptionDataForAll(enrichedFunds);

    loadingEl.hidden = true;
    tableWrapper.hidden = false;

    buildTable(tableWrapper, enrichedFunds, inceptionData);
}

async function fetchInceptionDataForAll(enrichedFunds) {
    const promises = enrichedFunds.map(f =>
        api
            .get(`/mutual-funds/${f.scheme_code}/nav-history?years=10`)
            .catch(err => {
                console.error(`Failed to fetch NAV history for ${f.scheme_code}:`, err);
                return null;
            })
    );
    return await Promise.all(promises);
}

function buildTable(tableWrapper, enrichedFunds, navHistories) {
    const table = document.createElement("table");
    table.className = "comparison-table";

    const thead = document.createElement("thead");
    const headerRow = document.createElement("tr");
    headerRow.innerHTML = `<th>Metric</th>${enrichedFunds.map(f =>
        `<th class="fund-col"><div class="fund-col-name">${f.scheme_name}</div><div class="fund-col-meta">${f.amc || "—"} · ${f.scheme_code}</div></th>`
    ).join("")}`;
    thead.appendChild(headerRow);
    table.appendChild(thead);

    const tbody = document.createElement("tbody");

    ROWS.forEach(row => {
        const values = enrichedFunds.map((fund, i) => readValue(fund, row, navHistories[i]));
        const best = getBestIndices(values, row.higherBetter);

        const tr = document.createElement("tr");
        tr.innerHTML = `<td class="metric-label">${row.label}${row.type === "cagr" ? ' <span class="metric-kind">(CAGR)</span>' : ' <span class="metric-kind">(Return)</span>'}</td>${values.map((v, i) => {
            const isBest = best.has(i) && v != null;
            const display = formatValue(v, row.unit);
            return `<td class="metric-value${isBest ? " best" : ""}">${display}${isBest ? '<span class="best-indicator">●</span>' : ""}</td>`;
        }).join("")}`;
        tbody.appendChild(tr);
    });

    table.appendChild(tbody);
    tableWrapper.appendChild(table);
}

function readValue(fund, row, navHistory) {
    if (row.key === "since_inception_cagr") {
        return computeSinceInceptionCagr(fund, navHistory);
    }
    if (!fund._detail) return null;
    const v = fund._detail[row.key];
    if (v === "" || v === undefined) return null;
    return typeof v === "number" ? v : null;
}

function computeSinceInceptionCagr(fund, navHistory) {
    if (!navHistory || !Array.isArray(navHistory.dates) || navHistory.dates.length < 2) return null;
    if (!Array.isArray(navHistory.navs) || navHistory.navs.length !== navHistory.dates.length) return null;

    const firstNavDate = navHistory.dates[0];
    const firstNav = navHistory.navs[0];
    const lastNavDate = navHistory.dates[navHistory.dates.length - 1];
    const lastNav = navHistory.navs[navHistory.navs.length - 1];

    if (!firstNavDate || !lastNavDate || !Number.isFinite(firstNav) || !Number.isFinite(lastNav)) return null;
    if (firstNav <= 0 || lastNav <= 0) return null;

    const fundFirstDate = fund._detail?.first_nav_date;
    if (fundFirstDate && firstNavDate > fundFirstDate) return null;

    const years = yearsBetween(firstNavDate, lastNavDate);
    if (!Number.isFinite(years) || years <= 0) return null;

    const totalReturn = lastNav / firstNav - 1;
    if (totalReturn <= -1) return null;

    try {
        const cagr = Math.pow(1 + totalReturn, 1 / years) - 1;
        if (!Number.isFinite(cagr)) return null;
        return cagr;
    } catch {
        return null;
    }
}

function yearsBetween(startISO, endISO) {
    const start = new Date(startISO);
    const end = new Date(endISO);
    if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) return NaN;
    return (end.getTime() - start.getTime()) / (365.25 * 24 * 60 * 60 * 1000);
}

function getBestIndices(values, higherBetter) {
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
}

function formatValue(value, unit) {
    if (value == null) return "N/A";
    if (unit === "percent") return `${(value * 100).toFixed(2)}%`;
    if (unit === "ratio") return value.toFixed(2);
    return value.toFixed(2);
}