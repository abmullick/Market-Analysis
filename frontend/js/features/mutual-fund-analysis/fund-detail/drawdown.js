export function renderDrawdownAnalysis(container, detail, navHistory) {
    if (!container || !navHistory || !navHistory.dates || !navHistory.navs || navHistory.dates.length < 2) {
        return;
    }

    const section = document.createElement("div");
    section.className = "fund-detail-section";

    const titleRow = document.createElement("div");
    titleRow.className = "section-title-row";

    const title = document.createElement("h3");
    title.className = "section-title";
    title.textContent = "Drawdown Analysis";
    titleRow.appendChild(title);

    const subtitle = document.createElement("span");
    subtitle.className = "section-subtitle";
    subtitle.textContent = "Shows how far the fund has fallen from its previous NAV peak over time.";
    titleRow.appendChild(subtitle);

    section.appendChild(titleRow);

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
                backgroundColor: "rgba(37, 99, 235, 0.1)",
                borderWidth: 2,
                fill: true,
                tension: 0.1,
                pointRadius: 0,
                pointHoverRadius: 4,
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
                legend: {
                    display: false,
                },
                tooltip: {
                    callbacks: {
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
                    ticks: {
                        maxTicksLimit: 8,
                    },
                },
                y: {
                    ticks: {
                        callback: (value) => `${value.toFixed(1)}%`,
                    },
                },
            },
        },
    });
}
