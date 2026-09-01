import { api } from "../../core/api.js";
import { showLoading, hideLoading } from "../../components/loading.js";

let navChart = null;
let rollingChart = null;
let lastFocusedElement = null;
let escapeHandler = null;
let backdropHandler = null;

export async function openFundDetail(schemeCode, schemeName) {
    const modalContainer = document.getElementById("fund-detail-modal");
    if (!modalContainer) return;

    lastFocusedElement = document.activeElement;

    showLoading(modalContainer);

    try {
        const [detail, navHistory] = await Promise.all([
            api.get(`/mutual-funds/${schemeCode}/detail`),
            api.get(`/mutual-funds/${schemeCode}/nav-history?years=10`),
        ]);

        hideLoading(modalContainer);
        renderFundModal(detail, navHistory, schemeCode);
    } catch (error) {
        hideLoading(modalContainer);
        renderErrorModal(error, schemeCode, schemeName);
    }
}

function renderFundModal(detail, navHistory, schemeCode) {
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

    content.appendChild(createFundHeader(detail, schemeCode));
    content.appendChild(createMetricsSection(detail));
    const rollingSectionSchemeCode = schemeCode || detail.scheme_code;
    console.log("[RollingReturns] renderFundModal calling createRollingReturnsSection with:", rollingSectionSchemeCode, "schemeCode:", schemeCode, "detail.scheme_code:", detail.scheme_code);
    content.appendChild(createRollingReturnsSection(rollingSectionSchemeCode));
    content.appendChild(createChartSection(detail, navHistory));
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

function createFundHeader(detail, schemeCode) {
    const section = document.createElement("div");
    section.className = "fund-detail-header";

    const topRow = document.createElement("div");
    topRow.className = "fund-detail-top-row";

    const badgeGroup = document.createElement("div");
    badgeGroup.className = "fund-badges";

    if (detail.amc) {
        const amcBadge = document.createElement("span");
        amcBadge.className = "fund-badge fund-badge-amc";
        amcBadge.textContent = detail.amc;
        badgeGroup.appendChild(amcBadge);
    }

    if (detail.category) {
        const catBadge = document.createElement("span");
        catBadge.className = "fund-badge fund-badge-category";
        catBadge.textContent = detail.category;
        badgeGroup.appendChild(catBadge);
    }

    if (detail.plan) {
        const planBadge = document.createElement("span");
        planBadge.className = `fund-badge fund-badge-plan ${detail.plan.toLowerCase()}`;
        planBadge.textContent = detail.plan;
        badgeGroup.appendChild(planBadge);
    }

    if (detail.option) {
        const optionBadge = document.createElement("span");
        optionBadge.className = "fund-badge fund-badge-option";
        optionBadge.textContent = detail.option;
        badgeGroup.appendChild(optionBadge);
    }

    topRow.appendChild(badgeGroup);
    section.appendChild(topRow);

    const infoGrid = document.createElement("div");
    infoGrid.className = "fund-info-grid";

    infoGrid.appendChild(createInfoItem("Scheme Code", detail.scheme_code || schemeCode || "Not available"));
    infoGrid.appendChild(createInfoItem("Latest NAV", detail.nav != null ? detail.nav.toFixed(4) : "Not available"));
    infoGrid.appendChild(createInfoItem("NAV Date", detail.nav_date || "Not available"));
    const aumValue = detail.total_aum_cr != null
        ? `₹${detail.total_aum_cr.toFixed(2)} Cr`
        : (detail.aum_cr != null ? `₹${detail.aum_cr.toFixed(2)} Cr` : "Not available");
    const aumLabel = detail.total_aum_cr != null ? "Total AUM" : (detail.aum_cr != null ? "AUM (Cr)" : "AUM");
    infoGrid.appendChild(createInfoItem(aumLabel, aumValue));

    const totalQuarter = detail.total_aum_quarter || detail.aum_quarter || "Not available";
    infoGrid.appendChild(createInfoItem("AUM Quarter", totalQuarter));
    infoGrid.appendChild(createInfoItem("First NAV Date", detail.first_nav_date || "Not available"));
    infoGrid.appendChild(createInfoItem("Fund Age", detail.fund_age_years != null ? `${detail.fund_age_years.toFixed(1)} years` : "Not available"));
    infoGrid.appendChild(createInfoItem("Expense Ratio", detail.expense_ratio != null ? `${detail.expense_ratio}%` : "Not available"));

    if (detail.fund_manager) {
        infoGrid.appendChild(createInfoItem("Fund Manager", detail.fund_manager));
    }

    section.appendChild(infoGrid);

    return section;
}

function createInfoItem(label, value) {
    const item = document.createElement("div");
    item.className = "fund-info-item";

    const labelEl = document.createElement("span");
    labelEl.className = "fund-info-label";
    labelEl.textContent = label;

    const valueEl = document.createElement("span");
    valueEl.className = "fund-info-value";
    valueEl.textContent = value;

    item.appendChild(labelEl);
    item.appendChild(valueEl);
    return item;
}

function createMetricsSection(detail) {
    const section = document.createElement("div");
    section.className = "fund-detail-section";

    const title = document.createElement("h3");
    title.className = "section-title";
    title.textContent = "Performance Metrics";
    section.appendChild(title);

    const metricsGrid = document.createElement("div");
    metricsGrid.className = "metrics-grid";

    metricsGrid.appendChild(createMetricCard("1Y Return", detail.one_year_return, "percentage"));
    metricsGrid.appendChild(createMetricCard("3Y CAGR", detail.three_year_cagr, "percentage"));
    metricsGrid.appendChild(createMetricCard("5Y CAGR", detail.five_year_cagr, "percentage"));
    metricsGrid.appendChild(createMetricCard("10Y CAGR", detail.ten_year_cagr, "percentage"));
    metricsGrid.appendChild(createMetricCard("Sharpe Ratio", detail.sharpe_ratio, "ratio"));
    metricsGrid.appendChild(createMetricCard("Sortino Ratio", detail.sortino_ratio, "ratio"));
    metricsGrid.appendChild(createMetricCard("Volatility", detail.annualized_volatility, "percentage"));
    metricsGrid.appendChild(createMetricCard("Max Drawdown", detail.maximum_drawdown, "percentage", true));
    metricsGrid.appendChild(createMetricCard("Downside Dev", detail.downside_deviation, "percentage"));

    section.appendChild(metricsGrid);

    if (detail.rolling_return_consistency) {
        const consistencySection = createConsistencySection(detail.rolling_return_consistency);
        section.appendChild(consistencySection);
    }

    const dataInfo = document.createElement("div");
    dataInfo.className = "data-info";
    dataInfo.textContent = `Based on ${detail.data_points} data points from ${detail.data_start_date || "N/A"} to ${detail.data_end_date || "N/A"}`;
    section.appendChild(dataInfo);

    return section;
}

function createMetricCard(label, value, type, invertColor = false) {
    const card = document.createElement("div");
    card.className = "metric-card";

    const labelEl = document.createElement("div");
    labelEl.className = "metric-label";
    labelEl.textContent = label;

    const valueEl = document.createElement("div");
    valueEl.className = "metric-value";

    if (value == null || value === undefined) {
        valueEl.textContent = "Not available";
        valueEl.classList.add("metric-na");
    } else {
        if (type === "percentage") {
            valueEl.textContent = `${(value * 100).toFixed(2)}%`;
        } else {
            valueEl.textContent = value.toFixed(3);
        }

        if (invertColor) {
            valueEl.classList.add(value <= 0.1 ? "metric-good" : value <= 0.2 ? "metric-warn" : "metric-bad");
        } else {
            if (label.includes("Return") || label.includes("CAGR")) {
                valueEl.classList.add(value > 0 ? "metric-good" : "metric-bad");
            } else if (label.includes("Sharpe") || label.includes("Sortino")) {
                valueEl.classList.add(value > 1 ? "metric-good" : value > 0 ? "metric-warn" : "metric-bad");
            }
        }
    }

    card.appendChild(labelEl);
    card.appendChild(valueEl);
    return card;
}

function createConsistencySection(consistency) {
    const section = document.createElement("div");
    section.className = "consistency-section";

    const title = document.createElement("h4");
    title.className = "subsection-title";
    title.textContent = "Rolling Return Consistency";
    section.appendChild(title);

    const consistencyGrid = document.createElement("div");
    consistencyGrid.className = "consistency-grid";

    for (const [period, data] of Object.entries(consistency)) {
        if (!data) continue;

        const card = document.createElement("div");
        card.className = "consistency-card";

        const periodEl = document.createElement("div");
        periodEl.className = "consistency-period";
        periodEl.textContent = period;
        card.appendChild(periodEl);

        const pctEl = document.createElement("div");
        pctEl.className = "consistency-pct";
        pctEl.textContent = `${data.positive_pct?.toFixed(1) || "N/A"}% positive`;
        card.appendChild(pctEl);

        const windowsEl = document.createElement("div");
        windowsEl.className = "consistency-windows";
        windowsEl.textContent = `${data.windows || "N/A"} windows`;
        card.appendChild(windowsEl);

        consistencyGrid.appendChild(card);
    }

    section.appendChild(consistencyGrid);
    return section;
}

function createChartSection(detail, navHistory) {
    const section = document.createElement("div");
    section.className = "fund-detail-section";

    const titleRow = document.createElement("div");
    titleRow.className = "section-title-row";

    const title = document.createElement("h3");
    title.className = "section-title";
    title.textContent = "Historical NAV";
    titleRow.appendChild(title);

    const buttons = document.createElement("div");
    buttons.className = "chart-period-buttons";

    const periods = ["1Y", "3Y", "5Y", "10Y", "Max"];
    periods.forEach(period => {
        const btn = document.createElement("button");
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
    chartContainer.className = "chart-container";

    const canvas = document.createElement("canvas");
    canvas.id = "nav-history-chart";
    chartContainer.appendChild(canvas);

    section.appendChild(chartContainer);

    return section;
}

function createMetadataSection(detail) {
    const section = document.createElement("div");
    section.className = "fund-detail-section";

    const title = document.createElement("h3");
    title.className = "section-title";
    title.textContent = "Fund Details";
    section.appendChild(title);

    const detailsGrid = document.createElement("div");
    detailsGrid.className = "details-grid";

    if (detail.asset_allocation && Object.keys(detail.asset_allocation).length > 0) {
        const allocationCard = document.createElement("div");
        allocationCard.className = "detail-card";

        const allocTitle = document.createElement("h4");
        allocTitle.className = "detail-card-title";
        allocTitle.textContent = "Asset Allocation";
        allocationCard.appendChild(allocTitle);

        const allocList = document.createElement("div");
        allocList.className = "allocation-list";

        for (const [asset, pct] of Object.entries(detail.asset_allocation)) {
            const item = document.createElement("div");
            item.className = "allocation-item";

            const label = document.createElement("span");
            label.className = "allocation-label";
            label.textContent = asset;

            const barContainer = document.createElement("span");
            barContainer.className = "allocation-bar-container";

            const bar = document.createElement("span");
            bar.className = "allocation-bar";
            bar.style.width = `${Math.min(pct * 100, 100)}%`;
            barContainer.appendChild(bar);

            const pctLabel = document.createElement("span");
            pctLabel.className = "allocation-pct";
            pctLabel.textContent = `${(pct * 100).toFixed(1)}%`;

            item.appendChild(label);
            item.appendChild(barContainer);
            item.appendChild(pctLabel);
            allocList.appendChild(item);
        }

        allocationCard.appendChild(allocList);
        detailsGrid.appendChild(allocationCard);
    }

    if (detail.top_holdings && detail.top_holdings.length > 0) {
        const holdingsCard = document.createElement("div");
        holdingsCard.className = "detail-card";

        const holdingsTitle = document.createElement("h4");
        holdingsTitle.className = "detail-card-title";
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
            weight.textContent = holding.weight ? `${holding.weight.toFixed(2)}%` : "";

            item.appendChild(rank);
            item.appendChild(name);
            item.appendChild(weight);
            holdingsList.appendChild(item);
        });

        holdingsCard.appendChild(holdingsList);
        detailsGrid.appendChild(holdingsCard);
    }

    section.appendChild(detailsGrid);
    return section;
}

function createRollingReturnsSection(schemeCode) {
    const section = document.createElement("div");
    section.className = "rolling-returns-section";

    const header = document.createElement("div");
    header.className = "rolling-returns-header";

    const title = document.createElement("h3");
    title.className = "rolling-returns-title";
    title.textContent = "Rolling Returns";
    header.appendChild(title);

    const controls = document.createElement("div");
    controls.className = "rolling-returns-controls";

    const periods = [1, 3, 5];
    periods.forEach(period => {
        const btn = document.createElement("button");
        btn.className = `rolling-returns-btn${period === 3 ? " active" : ""}`;
        btn.textContent = `${period}Y`;
        btn.addEventListener("click", () => {
            controls.querySelectorAll(".rolling-returns-btn").forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            loadRollingReturns(schemeCode, period, section);
        });
        controls.appendChild(btn);
    });

    header.appendChild(controls);
    section.appendChild(header);

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
                backgroundColor: "rgba(37, 99, 235, 0.1)",
                borderWidth: 2,
                fill: true,
                tension: 0.1,
                pointRadius: 0,
                pointHoverRadius: 4,
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
                legend: {
                    display: false,
                },
                tooltip: {
                    callbacks: {
                        label: (context) => {
                            const val = context.parsed.y;
                            return `${period}Y Rolling: ${(val * 100).toFixed(2)}%`;
                        },
                    },
                },
            },
            scales: {
                x: {
                    ticks: {
                        maxTicksLimit: 8,
                    },
                },
                y: {
                    ticks: {
                        callback: (value) => `${(value * 100).toFixed(1)}%`,
                    },
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
                backgroundColor: "rgba(37, 99, 235, 0.1)",
                borderWidth: 2,
                fill: true,
                tension: 0.1,
                pointRadius: 0,
                pointHoverRadius: 4,
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
                legend: {
                    display: false,
                },
                tooltip: {
                    callbacks: {
                        label: (context) => `NAV: ${context.parsed.y.toFixed(4)}`,
                    },
                },
            },
            scales: {
                x: {
                    ticks: {
                        maxTicksLimit: 8,
                    },
                },
                y: {
                    ticks: {
                        callback: (value) => value.toFixed(2),
                    },
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
