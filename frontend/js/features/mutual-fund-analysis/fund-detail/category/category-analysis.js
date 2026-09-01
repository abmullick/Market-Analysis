export function renderCategoryAnalysis(container, detail, categoryData) {
    if (!container || !detail || !categoryData) return;

    const section = document.createElement("div");
    section.className = "fund-detail-section";

    const titleRow = document.createElement("div");
    titleRow.className = "section-title-row";

    const title = document.createElement("h3");
    title.className = "section-title";
    title.textContent = "Category Relative Analysis";
    titleRow.appendChild(title);

    const subtitle = document.createElement("span");
    subtitle.className = "section-subtitle";
    subtitle.textContent = `Compared with ${detail.category || "category"} funds`;
    titleRow.appendChild(subtitle);

    section.appendChild(titleRow);

    if (!categoryData.metrics || categoryData.metrics.length === 0) {
        const empty = document.createElement("div");
        empty.className = "empty-state";
        empty.innerHTML = `<p>Insufficient category data for comparison.</p>`;
        section.appendChild(empty);
        container.appendChild(section);
        return;
    }

    const table = document.createElement("table");
    table.className = "category-analysis-table";

    const thead = document.createElement("thead");
    const headerRow = document.createElement("tr");
    headerRow.innerHTML = `
        <th>Metric</th>
        <th>Fund Value</th>
        <th>Category Position</th>
    `;
    thead.appendChild(headerRow);
    table.appendChild(thead);

    const tbody = document.createElement("tbody");
    categoryData.metrics.forEach(m => {
        const tr = document.createElement("tr");

        const labelCell = document.createElement("td");
        labelCell.className = "metric-label";
        labelCell.textContent = m.label || m.metric;
        tr.appendChild(labelCell);

        const valueCell = document.createElement("td");
        valueCell.className = "metric-value";
        valueCell.textContent = formatMetricValue(m.fund_value, m.metric);
        tr.appendChild(valueCell);

        const positionCell = document.createElement("td");
        positionCell.className = "metric-value position-value";

        if (m.percentile != null && m.category_count > 0) {
            const pct = m.percentile;
            const rank = m.rank != null ? Math.round(m.rank) : null;
            const count = m.category_count;

            let pctLabel = "";
            if (pct >= 99) {
                pctLabel = "Top 1%";
            } else if (pct >= 95) {
                pctLabel = `Top ${Math.round(100 - pct + 1)}%`;
            } else if (pct >= 75) {
                pctLabel = "Above average";
            } else if (pct >= 25) {
                pctLabel = "Average";
            } else if (pct >= 5) {
                pctLabel = "Below average";
            } else if (pct >= 1) {
                pctLabel = `Bottom ${Math.round(pct)}%`;
            } else {
                pctLabel = "Bottom 1%";
            }

            let rankText = "";
            if (rank != null) {
                const suffix = rank % 10 === 1 && rank % 100 !== 11 ? "st" :
                               rank % 10 === 2 && rank % 100 !== 12 ? "nd" :
                               rank % 10 === 3 && rank % 100 !== 13 ? "rd" : "th";
                rankText = `${rank}${suffix} of ${count}`;
            }

            const pctText = `${pct.toFixed(1)}th percentile`;
            const detailText = [rankText, pctText].filter(Boolean).join(" · ");

            positionCell.innerHTML = `
                <div class="position-main">
                    <span class="position-label">${pctLabel}</span>
                    <span class="position-detail">${detailText}</span>
                </div>
                <div class="percentile-bar-container">
                    <div class="percentile-bar" style="width: ${Math.min(pct, 100)}%"></div>
                </div>
            `;

            if (pct >= 75) {
                positionCell.classList.add("position-high");
            } else if (pct <= 25) {
                positionCell.classList.add("position-low");
            } else {
                positionCell.classList.add("position-mid");
            }
        } else {
            positionCell.textContent = "Not available";
            positionCell.classList.add("position-na");
        }

        tr.appendChild(positionCell);
        tbody.appendChild(tr);
    });

    table.appendChild(tbody);
    section.appendChild(table);
    container.appendChild(section);
}

function formatMetricValue(value, metric) {
    if (value == null) return "Not available";

    if (["1Y_return", "3Y_cagr", "5Y_cagr", "10Y_cagr", "volatility", "maximum_drawdown", "downside_deviation"].includes(metric)) {
        return `${(value * 100).toFixed(2)}%`;
    }
    if (["sharpe_ratio", "sortino_ratio"].includes(metric)) {
        return value.toFixed(2);
    }
    if (metric === "consistency") {
        return `${value.toFixed(2)}%`;
    }
    return value.toFixed(2);
}
