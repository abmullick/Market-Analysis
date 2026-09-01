export function renderRollingReturnsChart(container, enrichedFunds) {
    if (!container || !enrichedFunds || enrichedFunds.length < 2) return;

    const fundsWithData = enrichedFunds.filter(f => {
        return f._detail?.rolling_return_consistency != null;
    });

    if (fundsWithData.length === 0) {
        container.innerHTML = `<div class="empty-state"><h3>Not enough data</h3><p>No rolling return data available for the selected funds.</p></div>`;
        return;
    }

    const wrapper = document.createElement("div");
    wrapper.className = "comparison-chart-section";

    const header = document.createElement("div");
    header.className = "comparison-section-header";
    header.textContent = "Rolling Return Analysis";
    wrapper.appendChild(header);

    const description = document.createElement("p");
    description.className = "comparison-chart-description";
    description.textContent = "Positive Rolling Periods (%) shows the percentage of valid rolling windows that produced a positive return.";
    wrapper.appendChild(description);

    const table = document.createElement("table");
    table.className = "comparison-table";

    const thead = document.createElement("thead");
    const headerRow = document.createElement("tr");
    headerRow.innerHTML = `<th>Metric</th>${fundsWithData.map(f => `<th class="fund-col"><div class="fund-col-name">${f.scheme_name}</div><div class="fund-col-meta">${f.amc || "—"} · ${f.scheme_code}</div></th>`).join("")}`;
    thead.appendChild(headerRow);
    table.appendChild(thead);

    const tbody = document.createElement("tbody");

    const periods = [
        { label: "1Y Positive Rolling Periods (%)", key: "1Y", metric: "positive_pct", unit: "percentage" },
        { label: "3Y Positive Rolling Periods (%)", key: "3Y", metric: "positive_pct", unit: "percentage" },
        { label: "5Y Positive Rolling Periods (%)", key: "5Y", metric: "positive_pct", unit: "percentage" },
        { label: "Mean Rolling Return (1Y)", key: "1Y", metric: "mean_return", unit: "percent" },
    ];

    periods.forEach(period => {
        const values = fundsWithData.map(f => {
            const window = f._detail?.rolling_return_consistency?.[period.key];
            return window ? window[period.metric] : null;
        });
        const best = getBestIndices(values, true);
        const tr = document.createElement("tr");
        tr.innerHTML = `<td class="metric-label">${period.label}</td>${values.map((v, i) => {
            const isBest = best.has(i) && v != null;
            const display = formatValue(v, period.unit);
            return `<td class="metric-value${isBest ? " best" : ""}">${display}${isBest ? '<span class="best-indicator">●</span>' : ""}</td>`;
        }).join("")}`;
        tbody.appendChild(tr);
    });

    table.appendChild(tbody);
    wrapper.appendChild(table);
    container.appendChild(wrapper);
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
    if (value == null) return "Not available";
    if (unit === "percentage") return `${value.toFixed(2)}%`;
    if (unit === "percent") return `${(value * 100).toFixed(2)}%`;
    if (unit === "ratio") return value.toFixed(2);
    return value.toFixed(2);
}
