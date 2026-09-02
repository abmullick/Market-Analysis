import { api } from "../../../core/api.js";

const COLORS = [
    "#2563eb", "#dc2626", "#16a34a", "#d97706", "#7c3aed",
    "#059669", "#db2777", "#65a30d", "#0891b2", "#ea580c",
];

export async function renderNavHistoryChart(container, enrichedFunds) {
    if (!container || !enrichedFunds || enrichedFunds.length < 2) return;

    container.innerHTML = "";
    const wrapper = document.createElement("div");
    wrapper.className = "comparison-chart-section";

    const header = document.createElement("div");
    header.className = "comparison-section-header";
    header.textContent = "Historical Performance";
    wrapper.appendChild(header);

    const description = document.createElement("p");
    description.className = "comparison-chart-description";
    description.textContent = "Each fund is rebased to 100 at the start of the common historical window. No interpolation of missing NAVs.";
    wrapper.appendChild(description);

    const loadingEl = document.createElement("div");
    loadingEl.className = "comparison-chart-loading";
    loadingEl.textContent = "Loading NAV history...";
    wrapper.appendChild(loadingEl);

    const chartContainer = document.createElement("div");
    chartContainer.className = "chart-container";
    chartContainer.hidden = true;
    wrapper.appendChild(chartContainer);

    container.appendChild(wrapper);

    let navDataByFund;
    try {
        navDataByFund = await fetchNavHistoryForAll(enrichedFunds);
    } catch (err) {
        loadingEl.textContent = `Failed to load NAV history: ${err.message}`;
        return;
    }

    const series = enrichedFunds
        .map((fund, i) => buildSeries(fund, navDataByFund[i]))
        .filter(s => s !== null);

    if (series.length < 2) {
        loadingEl.textContent = "Not enough data — at least 2 funds need sufficient NAV history.";
        return;
    }

    const aligned = alignToCommonPeriod(series);
    if (!aligned) {
        loadingEl.textContent = "No overlapping historical period across the selected funds.";
        return;
    }

    loadingEl.hidden = true;
    chartContainer.hidden = false;

    drawChart(chartContainer, aligned, enrichedFunds);
}

async function fetchNavHistoryForAll(enrichedFunds) {
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

function buildSeries(fund, navHistory) {
    if (!navHistory || !navHistory.dates || !navHistory.navs) return null;
    if (navHistory.dates.length === 0 || navHistory.navs.length === 0) return null;
    if (navHistory.dates.length !== navHistory.navs.length) return null;

    const points = [];
    for (let i = 0; i < navHistory.dates.length; i++) {
        const date = navHistory.dates[i];
        const nav = navHistory.navs[i];
        if (!date || nav == null || !Number.isFinite(nav) || nav <= 0) continue;
        points.push({ date, nav });
    }

    if (points.length < 2) return null;

    return {
        schemeCode: fund.scheme_code,
        schemeName: fund.scheme_name,
        points,
    };
}

function alignToCommonPeriod(series) {
    let latestStart = series[0].points[0].date;
    let earliestEnd = series[0].points[series[0].points.length - 1].date;

    for (const s of series) {
        const sStart = s.points[0].date;
        const sEnd = s.points[s.points.length - 1].date;
        if (sStart > latestStart) latestStart = sStart;
        if (sEnd < earliestEnd) earliestEnd = sEnd;
    }

    if (latestStart >= earliestEnd) return null;

    const aligned = series.map(s => {
        const base = s.points.find(p => p.date === latestStart);
        if (!base) return null;

        const baseNav = base.nav;
        const filtered = s.points.filter(p => p.date >= latestStart && p.date <= earliestEnd);

        if (filtered.length < 2) return null;

        const normalized = filtered.map(p => ({
            date: p.date,
            value: (p.nav / baseNav) * 100,
        }));

        return {
            schemeCode: s.schemeCode,
            schemeName: s.schemeName,
            points: normalized,
        };
    });

    if (aligned.some(a => a === null)) return null;

    return {
        startDate: latestStart,
        endDate: earliestEnd,
        funds: aligned.filter(a => a !== null),
    };
}

function drawChart(chartContainer, aligned, enrichedFunds) {
    if (typeof Chart === "undefined") {
        chartContainer.innerHTML = `<div class="empty-state"><p>Chart.js is not loaded.</p></div>`;
        return;
    }

    const labels = aligned.funds[0].points.map(p => p.date);

    const datasets = aligned.funds.map((fund, i) => {
        const enriched = enrichedFunds.find(f => f.scheme_code === fund.schemeCode);
        const amc = enriched?.amc || "";
        const color = COLORS[i % COLORS.length];
        return {
            label: `${fund.schemeName}${amc ? ` (${amc})` : ""} · ${fund.schemeCode}`,
            data: fund.points.map(p => p.value),
            borderColor: color,
            backgroundColor: color,
            borderWidth: 2,
            fill: false,
            tension: 0.1,
            pointRadius: 0,
            pointHoverRadius: 4,
            spanGaps: false,
        };
    });

    chartContainer.innerHTML = "";
    const canvas = document.createElement("canvas");
    chartContainer.appendChild(canvas);

    new Chart(canvas.getContext("2d"), {
        type: "line",
        data: { labels, datasets },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                intersect: false,
                mode: "index",
            },
            plugins: {
                legend: {
                    position: "bottom",
                    labels: {
                        usePointStyle: true,
                        pointStyle: "circle",
                        padding: 16,
                        font: { size: 12 },
                    },
                },
                tooltip: {
                    callbacks: {
                        label: (ctx) => {
                            const fund = aligned.funds[ctx.datasetIndex];
                            const v = ctx.parsed.y;
                            return `${fund.schemeName}: ${v.toFixed(2)}`;
                        },
                    },
                },
            },
            scales: {
                x: {
                    title: { display: true, text: "Date", font: { size: 12 } },
                    ticks: { maxTicksLimit: 8 },
                },
                y: {
                    title: { display: true, text: "Normalized Value (Base = 100)", font: { size: 12 } },
                    ticks: { callback: (v) => v.toFixed(0) },
                },
            },
        },
    });
}