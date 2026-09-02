import { api } from "../../core/api.js";
import { showLoading, hideLoading } from "../../components/loading.js";
import { renderDrawdownAnalysis } from "./fund-detail/drawdown.js";
import { renderCategoryAnalysis } from "./fund-detail/category/category-analysis.js";

let navChart = null;
let rollingChart = null;
let lastFocusedElement = null;
let escapeHandler = null;
let backdropHandler = null;

export async function openFundDetail(schemeCode, schemeName) {
    const modalContainer = document.getElementById("fund-detail-modal");
    if (!modalContainer) return;

    lastFocusedElement = document.activeElement;

    showLoading(modalContainer, "Loading fund details...");

    try {
        const [detail, navHistory, categoryAnalysis] = await Promise.all([
            api.get(`/mutual-funds/${schemeCode}/detail`),
            api.get(`/mutual-funds/${schemeCode}/nav-history?years=10`),
            api.get(`/mutual-funds/${schemeCode}/category-analysis`).catch(() => null),
        ]);

        hideLoading(modalContainer);
        renderFundModal(detail, navHistory, schemeCode, categoryAnalysis);
    } catch (error) {
        hideLoading(modalContainer);
        renderErrorModal(error, schemeCode, schemeName);
    }
}

function renderFundModal(detail, navHistory, schemeCode, categoryAnalysis) {
    const modalContainer = document.getElementById("fund-detail-modal");
    if (!modalContainer) return;

    modalContainer.innerHTML = "";

    const overlay = document.createElement("div");
    overlay.className = "modal-overlay";

    const dialog = document.createElement("div");
    dialog.className = "modal modal-large";
    dialog.setAttribute("role", "dialog");
    dialog.setAttribute("aria-modal", "true");
    dialog.setAttribute("aria-label", detail.scheme_name || "Fund Details");

    const header = document.createElement("div");
    header.className = "modal-header";

    const titleEl = document.createElement("h2");
    titleEl.className = "modal-title";
    titleEl.textContent = detail.scheme_name;
    header.appendChild(titleEl);

    const closeBtn = document.createElement("button");
    closeBtn.className = "modal-close";
    closeBtn.innerHTML = "&times;";
    closeBtn.setAttribute("aria-label", "Close fund details");
    closeBtn.addEventListener("click", closeFundDetail);
    header.appendChild(closeBtn);

    const content = document.createElement("div");
    content.className = "fund-detail-content";

    content.appendChild(createFundIdentitySection(detail, schemeCode));
    content.appendChild(createKpiSection(detail));
    content.appendChild(createPerformanceSummarySection(detail, navHistory));
    content.appendChild(createChartSection(detail, navHistory));

    const riskSection = document.createElement("div");
    riskSection.className = "fund-detail-section fund-risk-section";
    const riskHeading = document.createElement("div");
    riskHeading.className = "fund-section-heading";
    riskHeading.innerHTML = `
        <h3 class="fund-section-title">Risk &amp; Risk-Adjusted Performance</h3>
        <p class="fund-section-subtitle">Volatility, drawdown behavior, and where Sharpe/Sortino place the fund within its category.</p>
    `;
    riskSection.appendChild(riskHeading);
    content.appendChild(riskSection);
    renderDrawdownAnalysis(riskSection, detail, navHistory);
    if (categoryAnalysis) {
        renderCategoryAnalysis(riskSection, detail, categoryAnalysis);
    }

    const rollingSectionSchemeCode = schemeCode || detail.scheme_code;
    console.log("[RollingReturns] renderFundModal calling createRollingReturnsSection with:", rollingSectionSchemeCode, "schemeCode:", schemeCode, "detail.scheme_code:", detail.scheme_code);
    content.appendChild(createRollingReturnsSection(rollingSectionSchemeCode));

    content.appendChild(createPortfolioSection(detail));
    content.appendChild(createMetadataSection(detail));

    dialog.appendChild(header);
    dialog.appendChild(content);
    overlay.appendChild(dialog);
    modalContainer.appendChild(overlay);

    lockBodyScroll();

    escapeHandler = (e) => {
        if (e.key === "Escape") {
            closeFundDetail();
        }
    };
    document.addEventListener("keydown", escapeHandler);

    backdropHandler = (e) => {
        if (e.target === overlay) {
            closeFundDetail();
        }
    };
    overlay.addEventListener("click", backdropHandler);

    requestAnimationFrame(() => {
        closeBtn.focus();
    });

    setTimeout(() => {
        initNavChart(navHistory, "10Y");
    }, 100);
}

function createFundIdentitySection(detail, schemeCode) {
    const section = document.createElement("div");
    section.className = "fund-identity-section";

    const badgesRow = document.createElement("div");
    badgesRow.className = "fund-identity-badges";

    const addBadge = (text, className) => {
        if (!text) return;
        const b = document.createElement("span");
        b.className = `fund-badge ${className || ""}`;
        b.textContent = text;
        badgesRow.appendChild(b);
    };
    addBadge(detail.amc, "fund-badge-amc");
    addBadge(detail.category, "fund-badge-category");
    addBadge(detail.plan, `fund-badge-plan ${(detail.plan || "").toLowerCase()}`);
    addBadge(detail.option, "fund-badge-option");

    if (badgesRow.children.length > 0) {
        section.appendChild(badgesRow);
    }

    const metaRow = document.createElement("div");
    metaRow.className = "fund-identity-meta";

    const inception = detail.first_nav_date || "Not available";
    const fundAge = detail.fund_age_years != null ? `${detail.fund_age_years.toFixed(1)} years` : "Not available";
    const dataRange = (detail.data_start_date && detail.data_end_date)
        ? `${detail.data_start_date} – ${detail.data_end_date}`
        : "Not available";
    const dataPoints = detail.data_points != null ? `${detail.data_points.toLocaleString()} points` : null;

    const metaItems = [
        { label: "Inception", value: inception },
        { label: "Fund Age", value: fundAge },
        { label: "Data Range", value: dataRange },
    ];
    if (dataPoints) {
        metaItems.push({ label: "Data Points", value: dataPoints });
    }

    metaItems.forEach(item => {
        const cell = document.createElement("div");
        cell.className = "fund-identity-meta-item";
        const labelEl = document.createElement("span");
        labelEl.className = "fund-identity-meta-label";
        labelEl.textContent = item.label;
        const valueEl = document.createElement("span");
        valueEl.className = "fund-identity-meta-value";
        valueEl.textContent = item.value;
        cell.appendChild(labelEl);
        cell.appendChild(valueEl);
        metaRow.appendChild(cell);
    });
    section.appendChild(metaRow);

    return section;
}

function createKpiSection(detail) {
    const section = document.createElement("div");
    section.className = "fund-detail-section fund-kpi-section";

    const heading = document.createElement("div");
    heading.className = "fund-section-heading";
    heading.innerHTML = `
        <h3 class="fund-section-title">At a Glance</h3>
        <p class="fund-section-subtitle">Key performance and risk-adjusted metrics from the fund's history.</p>
    `;
    section.appendChild(heading);

    const grid = document.createElement("div");
    grid.className = "fund-kpi-grid";

    const kpis = [
        { key: "3y", label: "3Y CAGR", value: detail.three_year_cagr, kind: "cagr-positive" },
        { key: "5y", label: "5Y CAGR", value: detail.five_year_cagr, kind: "cagr-positive" },
        { key: "vol", label: "Volatility", value: detail.annualized_volatility, kind: "risk" },
        { key: "sharpe", label: "Sharpe Ratio", value: detail.sharpe_ratio, kind: "ratio-positive" },
        { key: "sortino", label: "Sortino Ratio", value: detail.sortino_ratio, kind: "ratio-positive" },
        { key: "mdd", label: "Max Drawdown", value: detail.maximum_drawdown, kind: "risk" },
    ];

    kpis.forEach(kpi => {
        const card = document.createElement("div");
        card.className = `fund-kpi-card fund-kpi-${kpi.kind}`;

        const labelEl = document.createElement("div");
        labelEl.className = "fund-kpi-label";
        labelEl.textContent = kpi.label;

        const valueEl = document.createElement("div");
        valueEl.className = "fund-kpi-value";
        if (kpi.value == null) {
            valueEl.textContent = "Not available";
            valueEl.classList.add("fund-kpi-na");
        } else if (kpi.kind === "cagr-positive" || kpi.kind === "risk") {
            const pct = kpi.value * 100;
            valueEl.textContent = `${pct >= 0 ? "" : ""}${pct.toFixed(2)}%`;
            if (kpi.kind === "cagr-positive") {
                valueEl.classList.add(pct >= 0 ? "fund-kpi-positive" : "fund-kpi-negative");
            } else {
                valueEl.classList.add("fund-kpi-risk-neutral");
            }
        } else {
            valueEl.textContent = kpi.value.toFixed(2);
            if (kpi.value > 1) valueEl.classList.add("fund-kpi-positive");
            else if (kpi.value > 0) valueEl.classList.add("fund-kpi-amber");
            else valueEl.classList.add("fund-kpi-negative");
        }

        card.appendChild(labelEl);
        card.appendChild(valueEl);
        grid.appendChild(card);
    });

    section.appendChild(grid);
    return section;
}

function createPerformanceSummarySection(detail, navHistory) {
    const section = document.createElement("div");
    section.className = "fund-detail-section";

    const heading = document.createElement("div");
    heading.className = "fund-section-heading";
    heading.innerHTML = `
        <h3 class="fund-section-title">Performance Summary</h3>
        <p class="fund-section-subtitle">Simple period return for 1Y; CAGR for multi-year periods.</p>
    `;
    section.appendChild(heading);

    const table = document.createElement("table");
    table.className = "fund-perf-table";

    const thead = document.createElement("thead");
    const headerRow = document.createElement("tr");
    headerRow.innerHTML = `
        <th class="fund-perf-period-col">Period</th>
        <th class="fund-perf-kind-col">Type</th>
        <th class="fund-perf-value-col">Return</th>
    `;
    thead.appendChild(headerRow);
    table.appendChild(thead);

    const tbody = document.createElement("tbody");

    const sinceInceptionCagr = computeSinceInceptionCagr(detail, navHistory);

    const rows = [
        { period: "1Y", kind: "Simple Return", value: detail.one_year_return, kindClass: "perf-kind-simple" },
        { period: "3Y", kind: "CAGR", value: detail.three_year_cagr, kindClass: "perf-kind-cagr" },
        { period: "5Y", kind: "CAGR", value: detail.five_year_cagr, kindClass: "perf-kind-cagr" },
        { period: "10Y", kind: "CAGR", value: detail.ten_year_cagr, kindClass: "perf-kind-cagr" },
        { period: "Since Inception", kind: "CAGR", value: sinceInceptionCagr, kindClass: "perf-kind-cagr" },
    ];

    rows.forEach(row => {
        const tr = document.createElement("tr");
        const periodCell = document.createElement("td");
        periodCell.className = "fund-perf-period";
        periodCell.textContent = row.period;
        tr.appendChild(periodCell);

        const kindCell = document.createElement("td");
        kindCell.className = `fund-perf-kind ${row.kindClass}`;
        kindCell.textContent = row.kind;
        tr.appendChild(kindCell);

        const valueCell = document.createElement("td");
        valueCell.className = "fund-perf-value";
        if (row.value == null) {
            valueCell.textContent = "Not available";
            valueCell.classList.add("fund-perf-na");
        } else {
            const pct = row.value * 100;
            valueCell.textContent = `${pct.toFixed(2)}%`;
            if (pct >= 0) valueCell.classList.add("fund-perf-positive");
            else valueCell.classList.add("fund-perf-negative");
        }
        tr.appendChild(valueCell);

        tbody.appendChild(tr);
    });

    table.appendChild(tbody);
    section.appendChild(table);
    return section;
}

function computeSinceInceptionCagr(detail, navHistory) {
    if (!navHistory || !Array.isArray(navHistory.dates) || navHistory.dates.length < 2) return null;
    if (!Array.isArray(navHistory.navs) || navHistory.navs.length !== navHistory.dates.length) return null;

    const firstDate = navHistory.dates[0];
    const firstNav = navHistory.navs[0];
    const lastDate = navHistory.dates[navHistory.dates.length - 1];
    const lastNav = navHistory.navs[navHistory.navs.length - 1];

    if (!firstDate || !lastDate || !Number.isFinite(firstNav) || !Number.isFinite(lastNav)) return null;
    if (firstNav <= 0 || lastNav <= 0) return null;

    const fundFirstDate = detail.first_nav_date;
    if (fundFirstDate && firstDate > fundFirstDate) return null;

    const years = yearsBetween(firstDate, lastDate);
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

function createChartSection(detail, navHistory) {
    const section = document.createElement("div");
    section.className = "fund-detail-section fund-chart-section is-chart";

    const titleRow = document.createElement("div");
    titleRow.className = "section-title-row";

    const heading = document.createElement("div");
    heading.className = "fund-section-heading fund-section-heading-row";
    heading.innerHTML = `
        <h3 class="fund-section-title">Historical NAV</h3>
        <p class="fund-section-subtitle">Fund NAV over the selected period. Toggle to change the time window.</p>
    `;
    titleRow.appendChild(heading);

    const buttons = document.createElement("div");
    buttons.className = "chart-period-buttons";

    const periods = ["1Y", "3Y", "5Y", "10Y", "Max"];
    periods.forEach(period => {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = `chart-period-btn${period === "10Y" ? " active" : ""}`;
        btn.textContent = period;
        btn.addEventListener("click", () => {
            buttons.querySelectorAll(".chart-period-btn").forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            updateNavChart(navHistory, period);
        });
        buttons.appendChild(btn);
    });

    titleRow.appendChild(buttons);
    section.appendChild(titleRow);

    const chartContainer = document.createElement("div");
    chartContainer.className = "chart-container fund-nav-chart";

    const canvas = document.createElement("canvas");
    canvas.id = "nav-history-chart";
    chartContainer.appendChild(canvas);

    section.appendChild(chartContainer);

    return section;
}

function createPortfolioSection(detail) {
    const section = document.createElement("div");
    section.className = "fund-detail-section fund-portfolio-section";

    const heading = document.createElement("div");
    heading.className = "fund-section-heading";
    heading.innerHTML = `
        <h3 class="fund-section-title">Portfolio</h3>
        <p class="fund-section-subtitle">Asset allocation and top holdings as last reported.</p>
    `;
    section.appendChild(heading);

    if ((!detail.asset_allocation || Object.keys(detail.asset_allocation).length === 0)
        && (!detail.top_holdings || detail.top_holdings.length === 0)) {
        const empty = document.createElement("div");
        empty.className = "fund-empty-state";
        empty.textContent = "Portfolio composition is not available for this fund.";
        section.appendChild(empty);
        return section;
    }

    const grid = document.createElement("div");
    grid.className = "fund-portfolio-grid";

    if (detail.asset_allocation && Object.keys(detail.asset_allocation).length > 0) {
        const allocCard = document.createElement("div");
        allocCard.className = "fund-portfolio-card";

        const allocTitle = document.createElement("h4");
        allocTitle.className = "fund-portfolio-card-title";
        allocTitle.textContent = "Asset Allocation";
        allocCard.appendChild(allocTitle);

        const allocList = document.createElement("div");
        allocList.className = "allocation-list";

        const entries = Object.entries(detail.asset_allocation);
        const total = entries.reduce((sum, [, v]) => sum + (typeof v === "number" ? v : 0), 0);
        const baseDenom = total > 1.01 ? 100 : 1;

        for (const [asset, pct] of entries) {
            const item = document.createElement("div");
            item.className = "allocation-item";

            const label = document.createElement("span");
            label.className = "allocation-label";
            label.textContent = asset;

            const barContainer = document.createElement("span");
            barContainer.className = "allocation-bar-container";

            const bar = document.createElement("span");
            bar.className = "allocation-bar";
            const displayPct = (pct * (baseDenom === 100 ? 1 : 100));
            bar.style.width = `${Math.min(displayPct, 100)}%`;
            barContainer.appendChild(bar);

            const pctLabel = document.createElement("span");
            pctLabel.className = "allocation-pct";
            pctLabel.textContent = `${displayPct.toFixed(1)}%`;

            item.appendChild(label);
            item.appendChild(barContainer);
            item.appendChild(pctLabel);
            allocList.appendChild(item);
        }

        allocCard.appendChild(allocList);
        grid.appendChild(allocCard);
    }

    if (detail.top_holdings && detail.top_holdings.length > 0) {
        const holdingsCard = document.createElement("div");
        holdingsCard.className = "fund-portfolio-card";

        const holdingsTitle = document.createElement("h4");
        holdingsTitle.className = "fund-portfolio-card-title";
        holdingsTitle.textContent = "Top Holdings";
        holdingsCard.appendChild(holdingsTitle);

        const holdingsList = document.createElement("div");
        holdingsList.className = "holdings-list";

        detail.top_holdings.slice(0, 10).forEach((holding, idx) => {
            const item = document.createElement("div");
            item.className = "holding-item";

            const rank = document.createElement("span");
            rank.className = "holding-rank";
            rank.textContent = `${idx + 1}`;

            const name = document.createElement("span");
            name.className = "holding-name";
            name.textContent = holding.name || holding.company || "Unknown";

            const weight = document.createElement("span");
            weight.className = "holding-weight";
            weight.textContent = holding.weight != null ? `${holding.weight.toFixed(2)}%` : "—";

            item.appendChild(rank);
            item.appendChild(name);
            item.appendChild(weight);
            holdingsList.appendChild(item);
        });

        holdingsCard.appendChild(holdingsList);
        grid.appendChild(holdingsCard);
    }

    section.appendChild(grid);
    return section;
}

function createMetadataSection(detail) {
    const section = document.createElement("div");
    section.className = "fund-detail-section fund-metadata-section";

    const heading = document.createElement("div");
    heading.className = "fund-section-heading";
    heading.innerHTML = `
        <h3 class="fund-section-title">Fund Details</h3>
        <p class="fund-section-subtitle">Supporting identifying information.</p>
    `;
    section.appendChild(heading);

    const grid = document.createElement("div");
    grid.className = "fund-metadata-grid";

    const addInfo = (label, value) => {
        if (!value || value === "Not available") return;
        const item = document.createElement("div");
        item.className = "fund-metadata-item";
        const labelEl = document.createElement("span");
        labelEl.className = "fund-metadata-label";
        labelEl.textContent = label;
        const valueEl = document.createElement("span");
        valueEl.className = "fund-metadata-value";
        valueEl.textContent = value;
        item.appendChild(labelEl);
        item.appendChild(valueEl);
        grid.appendChild(item);
    };

    addInfo("Scheme Code", detail.scheme_code);
    addInfo("Latest NAV", detail.nav != null ? detail.nav.toFixed(4) : null);
    addInfo("NAV Date", detail.nav_date);
    if (detail.total_aum_cr != null) {
        addInfo("Total AUM", `₹${detail.total_aum_cr.toFixed(2)} Cr`);
    } else if (detail.aum_cr != null) {
        addInfo("AUM", `₹${detail.aum_cr.toFixed(2)} Cr`);
    }
    addInfo("AUM Quarter", detail.total_aum_quarter || detail.aum_quarter);
    addInfo("Expense Ratio", detail.expense_ratio != null ? `${detail.expense_ratio}%` : null);
    addInfo("Fund Manager", detail.fund_manager);

    if (grid.children.length === 0) {
        section.style.display = "none";
    } else {
        section.appendChild(grid);
    }

    return section;
}

function createRollingReturnsSection(schemeCode) {
    const section = document.createElement("div");
    section.className = "fund-detail-section fund-rolling-section";

    const titleRow = document.createElement("div");
    titleRow.className = "section-title-row";

    const heading = document.createElement("div");
    heading.className = "fund-section-heading fund-section-heading-row";
    heading.innerHTML = `
        <h3 class="fund-section-title">Rolling Returns &amp; Consistency</h3>
        <p class="fund-section-subtitle">How often rolling windows produced a positive return, and the distribution of outcomes.</p>
    `;
    titleRow.appendChild(heading);

    const controls = document.createElement("div");
    controls.className = "rolling-returns-controls";

    const periods = [1, 3, 5];
    periods.forEach(period => {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = `rolling-returns-btn${period === 3 ? " active" : ""}`;
        btn.textContent = `${period}Y`;
        btn.addEventListener("click", () => {
            controls.querySelectorAll(".rolling-returns-btn").forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            loadRollingReturns(schemeCode, period, section);
        });
        controls.appendChild(btn);
    });

    titleRow.appendChild(controls);
    section.appendChild(titleRow);

    const summary = document.createElement("div");
    summary.className = "rolling-returns-summary";
    section.appendChild(summary);

    const chartContainer = document.createElement("div");
    chartContainer.className = "rolling-returns-chart-container";
    const canvas = document.createElement("canvas");
    canvas.id = "rolling-returns-chart";
    chartContainer.appendChild(canvas);
    section.appendChild(chartContainer);

    loadRollingReturns(schemeCode, 3, section);

    return section;
}

async function loadRollingReturns(schemeCode, years, section) {
    const summaryEl = section.querySelector(".rolling-returns-summary");
    const chartContainer = section.querySelector(".rolling-returns-chart-container");

    console.log("[RollingReturns] loadRollingReturns called with schemeCode:", schemeCode, "years:", years);

    summaryEl.innerHTML = `<div class="loading"><div class="loading-spinner"></div> Loading...</div>`;
    chartContainer.innerHTML = `<div class="loading"><div class="loading-spinner"></div> Loading...</div>`;

    if (rollingChart) {
        rollingChart.destroy();
        rollingChart = null;
    }

    try {
        const response = await api.get(`/mutual-funds/${schemeCode}/rolling-returns?years=${years}`);
        console.log("[RollingReturns] API response:", response);
        summaryEl.innerHTML = "";
        chartContainer.innerHTML = "";

        if (response.insufficient_history || !response.summary) {
            summaryEl.innerHTML = "";
            chartContainer.innerHTML = `
                <div class="rolling-returns-insufficient">
                    <div class="rolling-returns-insufficient-title">Insufficient history</div>
                    <div class="rolling-returns-insufficient-text">
                        This fund does not have enough NAV history to calculate ${years}-year rolling returns.
                    </div>
                </div>
            `;
            return;
        }

        renderRollingReturnsSummary(response.summary, years, summaryEl);

        const canvas = document.createElement("canvas");
        canvas.id = "rolling-returns-chart";
        chartContainer.appendChild(canvas);

        requestAnimationFrame(() => {
            initRollingChart(response.dates, response.returns, years);
        });
    } catch (error) {
        summaryEl.innerHTML = "";
        chartContainer.innerHTML = `
            <div class="rolling-returns-insufficient">
                <div class="rolling-returns-insufficient-title">Failed to load rolling returns</div>
                <div class="rolling-returns-insufficient-text">${error.message}</div>
            </div>
        `;
    }
}

function renderRollingReturnsSummary(summary, period, container) {
    const formatPct = (value) => `${(value * 100).toFixed(2)}%`;
    const formatCount = (value) => value.toLocaleString();

    const stats = [
        { label: "Periods", value: formatCount(summary.count) },
        { label: "Average", value: formatPct(summary.avg), className: summary.avg >= 0 ? "positive" : "negative" },
        { label: "Median", value: formatPct(summary.median), className: summary.median >= 0 ? "positive" : "negative" },
        { label: "Minimum", value: formatPct(summary.min), className: "negative" },
        { label: "Maximum", value: formatPct(summary.max), className: "positive" },
        { label: "Positive %", value: `${summary.positive_pct.toFixed(1)}%`, className: summary.positive_pct >= 50 ? "positive" : "negative" },
    ];

    container.innerHTML = stats.map(stat => `
        <div class="rolling-returns-stat">
            <div class="rolling-returns-stat-label">${stat.label}</div>
            <div class="rolling-returns-stat-value ${stat.className || ""}">${stat.value}</div>
        </div>
    `).join("");
}

function initRollingChart(dates, returns, period) {
    const canvas = document.getElementById("rolling-returns-chart");
    if (!canvas || typeof Chart === "undefined") return;

    if (rollingChart) {
        rollingChart.destroy();
    }

    const ctx = canvas.getContext("2d");
    rollingChart = new Chart(ctx, {
        type: "line",
        data: {
            labels: dates,
            datasets: [{
                label: `${period}Y Rolling Return`,
                data: returns,
                borderColor: "#2563eb",
                backgroundColor: "rgba(37, 99, 235, 0.08)",
                borderWidth: 2,
                fill: true,
                tension: 0,
                pointRadius: 0,
                pointHoverRadius: 5,
                pointHoverBackgroundColor: "#2563eb",
                pointHoverBorderColor: "#ffffff",
                pointHoverBorderWidth: 2,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                intersect: false,
                mode: "index",
            },
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: "rgba(15, 23, 42, 0.95)",
                    padding: 10,
                    titleFont: { size: 12, weight: "600" },
                    bodyFont: { size: 12 },
                    displayColors: false,
                    callbacks: {
                        title: (items) => items[0]?.label || "",
                        label: (context) => {
                            const val = context.parsed.y;
                            return `${period}Y Rolling Return: ${(val * 100).toFixed(2)}%`;
                        },
                    },
                },
            },
            scales: {
                x: {
                    title: { display: true, text: "Window End Date", font: { size: 11, weight: "500" }, color: "#64748b" },
                    ticks: { maxTicksLimit: 8, color: "#64748b", font: { size: 11 } },
                    grid: { color: "rgba(15, 23, 42, 0.04)" },
                },
                y: {
                    title: { display: true, text: `${period}Y Rolling Return`, font: { size: 11, weight: "500" }, color: "#64748b" },
                    ticks: { callback: (value) => `${(value * 100).toFixed(1)}%`, color: "#64748b", font: { size: 11 } },
                    grid: { color: "rgba(15, 23, 42, 0.06)" },
                },
            },
        },
    });
}

function initNavChart(navHistory, period) {
    const canvas = document.getElementById("nav-history-chart");
    if (!canvas || typeof Chart === "undefined") return;

    if (navChart) {
        navChart.destroy();
    }

    const filteredData = filterNavByPeriod(navHistory, period);

    const ctx = canvas.getContext("2d");
    navChart = new Chart(ctx, {
        type: "line",
        data: {
            labels: filteredData.dates,
            datasets: [{
                label: "NAV",
                data: filteredData.navs,
                borderColor: "#2563eb",
                backgroundColor: "rgba(37, 99, 235, 0.08)",
                borderWidth: 2,
                fill: true,
                tension: 0,
                pointRadius: 0,
                pointHoverRadius: 5,
                pointHoverBackgroundColor: "#2563eb",
                pointHoverBorderColor: "#ffffff",
                pointHoverBorderWidth: 2,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                intersect: false,
                mode: "index",
            },
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: "rgba(15, 23, 42, 0.95)",
                    padding: 10,
                    titleFont: { size: 12, weight: "600" },
                    bodyFont: { size: 12 },
                    displayColors: false,
                    callbacks: {
                        title: (items) => items[0]?.label || "",
                        label: (context) => {
                            const v = context.parsed.y;
                            const series = filteredData.navs;
                            const idx = context.dataIndex;
                            let changePct = null;
                            if (idx > 0 && series[idx - 1]) {
                                changePct = ((v - series[idx - 1]) / series[idx - 1]) * 100;
                            }
                            const changeLine = changePct != null
                                ? ` (${changePct >= 0 ? "+" : ""}${changePct.toFixed(2)}% vs prior)`
                                : "";
                            return `NAV: ₹${v.toFixed(4)}${changeLine}`;
                        },
                    },
                },
            },
            scales: {
                x: {
                    title: { display: true, text: "Date", font: { size: 11, weight: "500" }, color: "#64748b" },
                    ticks: { maxTicksLimit: 8, color: "#64748b", font: { size: 11 } },
                    grid: { color: "rgba(15, 23, 42, 0.04)" },
                },
                y: {
                    title: { display: true, text: "NAV (₹)", font: { size: 11, weight: "500" }, color: "#64748b" },
                    ticks: { callback: (value) => `₹${value.toFixed(2)}`, color: "#64748b", font: { size: 11 } },
                    grid: { color: "rgba(15, 23, 42, 0.06)" },
                },
            },
        },
    });
}

function updateNavChart(navHistory, period) {
    if (!navChart) {
        initNavChart(navHistory, period);
        return;
    }

    const filteredData = filterNavByPeriod(navHistory, period);

    navChart.data.labels = filteredData.dates;
    navChart.data.datasets[0].data = filteredData.navs;
    navChart.update();
}

function filterNavByPeriod(navHistory, period) {
    if (period === "Max") {
        return {
            dates: navHistory.dates,
            navs: navHistory.navs,
        };
    }

    const years = parseInt(period);
    const endDate = new Date(navHistory.dates[navHistory.dates.length - 1]);
    const startDate = new Date(endDate);
    startDate.setFullYear(startDate.getFullYear() - years);

    const filteredDates = [];
    const filteredNavs = [];

    for (let i = 0; i < navHistory.dates.length; i++) {
        const date = new Date(navHistory.dates[i]);
        if (date >= startDate) {
            filteredDates.push(navHistory.dates[i]);
            filteredNavs.push(navHistory.navs[i]);
        }
    }

    return {
        dates: filteredDates,
        navs: filteredNavs,
    };
}

function renderErrorModal(error, schemeCode, schemeName) {
    const modalContainer = document.getElementById("fund-detail-modal");
    if (!modalContainer) return;

    modalContainer.innerHTML = "";

    const overlay = document.createElement("div");
    overlay.className = "modal-overlay";

    const dialog = document.createElement("div");
    dialog.className = "modal modal-large";
    dialog.setAttribute("role", "dialog");
    dialog.setAttribute("aria-modal", "true");
    dialog.setAttribute("aria-label", schemeName || `Fund ${schemeCode}`);

    const header = document.createElement("div");
    header.className = "modal-header";

    const titleEl = document.createElement("h2");
    titleEl.className = "modal-title";
    titleEl.textContent = schemeName || `Fund ${schemeCode}`;
    header.appendChild(titleEl);

    const closeBtn = document.createElement("button");
    closeBtn.className = "modal-close";
    closeBtn.innerHTML = "&times;";
    closeBtn.setAttribute("aria-label", "Close fund details");
    closeBtn.addEventListener("click", closeFundDetail);
    header.appendChild(closeBtn);

    const content = document.createElement("div");
    content.className = "fund-detail-error";

    const errorMsg = document.createElement("p");
    errorMsg.textContent = `Failed to load fund details: ${error.message}`;
    content.appendChild(errorMsg);

    dialog.appendChild(header);
    dialog.appendChild(content);
    overlay.appendChild(dialog);
    modalContainer.appendChild(overlay);

    lockBodyScroll();

    escapeHandler = (e) => {
        if (e.key === "Escape") {
            closeFundDetail();
        }
    };
    document.addEventListener("keydown", escapeHandler);

    backdropHandler = (e) => {
        if (e.target === overlay) {
            closeFundDetail();
        }
    };
    overlay.addEventListener("click", backdropHandler);

    requestAnimationFrame(() => {
        closeBtn.focus();
    });
}

function lockBodyScroll() {
    const body = document.body;
    const scrollY = window.scrollY;
    body.style.position = "fixed";
    body.style.top = `-${scrollY}px`;
    body.style.width = "100%";
    body.classList.add("modal-open");
}

function unlockBodyScroll() {
    const body = document.body;
    const scrollY = Math.abs(parseInt(body.style.top || "0"));
    body.style.position = "";
    body.style.top = "";
    body.style.width = "";
    body.classList.remove("modal-open");
    window.scrollTo(0, scrollY);
}

export function closeFundDetail() {
    const modalContainer = document.getElementById("fund-detail-modal");
    if (modalContainer) {
        modalContainer.innerHTML = "";
    }
    if (navChart) {
        navChart.destroy();
        navChart = null;
    }
    if (rollingChart) {
        rollingChart.destroy();
        rollingChart = null;
    }

    if (escapeHandler) {
        document.removeEventListener("keydown", escapeHandler);
        escapeHandler = null;
    }

    if (backdropHandler) {
        document.removeEventListener("click", backdropHandler);
        backdropHandler = null;
    }

    unlockBodyScroll();

    if (lastFocusedElement && typeof lastFocusedElement.focus === "function") {
        requestAnimationFrame(() => {
            lastFocusedElement.focus();
        });
    }
}
