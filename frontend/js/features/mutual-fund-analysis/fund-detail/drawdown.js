export function renderDrawdownAnalysis(container, detail, navHistory) {
    if (!container || !navHistory || !navHistory.dates || !navHistory.navs || navHistory.dates.length < 2) {
        return;
    }

    const section = document.createElement("div");
    section.className = "fund-drawdown-subsection";

    const heading = document.createElement("div");
    heading.className = "fund-section-heading";
    heading.innerHTML = `
        <h3 class="fund-section-title fund-section-title-sub">Drawdown Analysis</h3>
        <p class="fund-section-subtitle">How far the fund has fallen from its previous NAV peak over time.</p>
    `;
    section.appendChild(heading);

    const dates = navHistory.dates;
    const navs = navHistory.navs;

    let peak = navs[0];
    const drawdowns = [];
    let maxDrawdown = 0;
    let maxDrawdownDate = dates[0];
    let currentDrawdown = 0;

    for (let i = 0; i < navs.length; i++) {
        if (navs[i] > peak) {
            peak = navs[i];
        }
        const dd = ((navs[i] / peak) - 1) * 100;
        drawdowns.push(dd);

        if (dd < maxDrawdown) {
            maxDrawdown = dd;
            maxDrawdownDate = dates[i];
        }
        currentDrawdown = dd;
    }

    const statsContainer = document.createElement("div");
    statsContainer.className = "drawdown-stats";

    const maxDdStat = document.createElement("div");
    maxDdStat.className = "drawdown-stat";
    maxDdStat.innerHTML = `
        <div class="drawdown-stat-label">Maximum Drawdown</div>
        <div class="drawdown-stat-value negative">${maxDrawdown.toFixed(2)}%</div>
        <div class="drawdown-stat-date">${maxDrawdownDate}</div>
    `;
    statsContainer.appendChild(maxDdStat);

    const currentDdStat = document.createElement("div");
    currentDdStat.className = "drawdown-stat";
    const currentDdClass = currentDrawdown < 0 ? "negative" : "positive";
    currentDdStat.innerHTML = `
        <div class="drawdown-stat-label">Current Drawdown</div>
        <div class="drawdown-stat-value ${currentDdClass}">${currentDrawdown.toFixed(2)}%</div>
        <div class="drawdown-stat-date">${dates[dates.length - 1]}</div>
    `;
    statsContainer.appendChild(currentDdStat);

    const recoveryStat = document.createElement("div");
    recoveryStat.className = "drawdown-stat";
    const recoveryValue = currentDrawdown >= 0 ? "0.00%" : "In drawdown";
    recoveryStat.innerHTML = `
        <div class="drawdown-stat-label">Recovery Status</div>
        <div class="drawdown-stat-value ${currentDrawdown >= 0 ? "positive" : "negative"}">${recoveryValue}</div>
        <div class="drawdown-stat-date">From peak</div>
    `;
    statsContainer.appendChild(recoveryStat);

    section.appendChild(statsContainer);

    const chartContainer = document.createElement("div");
    chartContainer.className = "chart-container";

    const canvas = document.createElement("canvas");
    canvas.id = "drawdown-chart";
    chartContainer.appendChild(canvas);
    section.appendChild(chartContainer);

    container.appendChild(section);

    if (typeof Chart === "undefined") {
        container.innerHTML += `<div class="empty-state"><p>Chart.js is not loaded.</p></div>`;
        return;
    }

    const ctx = canvas.getContext("2d");

    const maxDdIndex = drawdowns.indexOf(maxDrawdown);
    const pointColors = drawdowns.map((_, i) => i === maxDdIndex ? "#dc2626" : "#2563eb");

    new Chart(ctx, {
        type: "line",
        data: {
            labels: dates,
            datasets: [{
                label: "Drawdown %",
                data: drawdowns,
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
                pointBackgroundColor: pointColors,
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
                            const dd = context.parsed.y;
                            const label = dd === maxDrawdown ? " [MAX DRAWDOWN]" : "";
                            return `Drawdown: ${dd.toFixed(2)}%${label}`;
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
                    title: { display: true, text: "Drawdown (%)", font: { size: 11, weight: "500" }, color: "#64748b" },
                    ticks: { callback: (value) => `${value.toFixed(1)}%`, color: "#64748b", font: { size: 11 } },
                    grid: { color: "rgba(15, 23, 42, 0.06)" },
                },
            },
        },
    });
}
