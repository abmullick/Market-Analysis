export function renderDrawdownChart(container, enrichedFunds) {
    if (!container || !enrichedFunds || enrichedFunds.length < 2) return;

    const fundsWithData = enrichedFunds.filter(f => {
        return f._detail?.maximum_drawdown != null || f._detail?.downside_deviation != null;
    });

    if (fundsWithData.length === 0) {
        container.innerHTML = `<div class="empty-state"><h3>Not enough data</h3><p>No drawdown data available for the selected funds.</p></div>`;
        return;
    }

    const wrapper = document.createElement("div");
    wrapper.className = "comparison-chart-section";

    const header = document.createElement("div");
    header.className = "comparison-section-header";
    header.textContent = "Drawdown Analysis";
    wrapper.appendChild(header);

    const table = document.createElement("table");
    table.className = "comparison-table";

    const thead = document.createElement("thead");
    const headerRow = document.createElement("tr");
    headerRow.innerHTML = `<th>Metric</th>${fundsWithData.map(f => `<th class="fund-col"><div class="fund-col-name">${f.scheme_name}</div><div class="fund-col-meta">${f.amc || "—"} · ${f.scheme_code}</div></th>`).join("")}`;
    thead.appendChild(headerRow);
    table.appendChild(thead);

    const tbody = document.createElement("tbody");

    const maxDrawdownValues = fundsWithData.map(f => f._detail?.maximum_drawdown);
    const bestMaxDrawdown = getBestIndices(maxDrawdownValues, false);

    const downsideValues = fundsWithData.map(f => f._detail?.downside_deviation);
    const bestDownside = getBestIndices(downsideValues, false);

    const metricRows = [
        { label: "Maximum Drawdown", values: maxDrawdownValues, best: bestMaxDrawdown, unit: "percent" },
        { label: "Downside Deviation", values: downsideValues, best: bestDownside, unit: "percent" },
    ];

    metricRows.forEach(row => {
        const tr = document.createElement("tr");
        tr.innerHTML = `<td class="metric-label">${row.label}</td>${row.values.map((v, i) => {
            const isBest = row.best.has(i) && v != null;
            const display = v != null ? `${(v * 100).toFixed(2)}%` : "Not available";
            return `<td class="metric-value${isBest ? " best" : ""}">${display}${isBest ? '<span class="best-indicator">●</span>' : ""}</td>`;
        }).join("")}`;
        tbody.appendChild(tr);
    });

    table.appendChild(tbody);
    wrapper.appendChild(table);
    container.appendChild(wrapper);
}

function getBestIndices(values, lowerBetter) {
    const valid = values.filter(v => v != null);
    if (valid.length < 2) return new Set();

    const best = new Set();
    let bestValue = lowerBetter ? Infinity : -Infinity;

    values.forEach((v, i) => {
        if (v == null) return;
        if (lowerBetter ? v < bestValue : v > bestValue) {
            bestValue = v;
            best.clear();
            best.add(i);
        } else if (v === bestValue) {
            best.add(i);
        }
    });

    return best;
}
