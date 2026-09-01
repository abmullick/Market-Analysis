export function renderRiskReturnChart(container, enrichedFunds) {
    if (!container || !enrichedFunds || enrichedFunds.length < 2) return;

    const fundsWithData = enrichedFunds.filter(f => {
        const volatility = f._detail?.annualized_volatility;
        const oneYear = f._detail?.one_year_return;
        return volatility != null && oneYear != null;
    });

    if (fundsWithData.length < 2) {
        container.innerHTML = `<div class="empty-state"><h3>Not enough data</h3><p>At least 2 funds need both volatility and 1Y return data for Risk vs Return analysis.</p></div>`;
        return;
    }

    const wrapper = document.createElement("div");
    wrapper.className = "comparison-chart-section";

    const header = document.createElement("div");
    header.className = "comparison-section-header";
    header.textContent = "Risk vs Return";
    wrapper.appendChild(header);

    const description = document.createElement("p");
    description.className = "comparison-chart-description";
    description.textContent = "Higher return is generally preferable, while lower volatility represents lower historical variability.";
    wrapper.appendChild(description);

    const chartContainer = document.createElement("div");
    chartContainer.className = "chart-container";

    const canvas = document.createElement("canvas");
    canvas.id = `risk-return-chart-${Date.now()}`;
    chartContainer.appendChild(canvas);
    wrapper.appendChild(chartContainer);

    container.appendChild(wrapper);

    if (typeof Chart === "undefined") {
        container.innerHTML += `<div class="empty-state"><p>Chart.js is not loaded.</p></div>`;
        return;
    }

    const colors = [
        "#2563eb", "#dc2626", "#16a34a", "#d97706", "#7c3aed",
        "#059669", "#db2777", "#2563eb", "#65a30d", "#0891b2",
    ];

    const datasets = fundsWithData.map((f, i) => {
        const volatility = f._detail.annualized_volatility * 100;
        const oneYear = f._detail.one_year_return * 100;
        return {
            label: f.scheme_name,
            data: [{ x: volatility, y: oneYear }],
            backgroundColor: colors[i % colors.length],
            pointRadius: 8,
            pointHoverRadius: 10,
        };
    });

    new Chart(canvas.getContext("2d"), {
        type: "scatter",
        data: { datasets },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: "bottom",
                    labels: { usePointStyle: true, pointStyle: "circle", padding: 16, font: { size: 12 } },
                },
                tooltip: {
                    callbacks: {
                        label(ctx) {
                            const fund = fundsWithData[ctx.datasetIndex];
                            const vol = fund._detail.annualized_volatility * 100;
                            const ret = fund._detail.one_year_return * 100;
                            return [
                                fund.scheme_name,
                                `Volatility: ${vol.toFixed(2)}%`,
                                `1Y Return: ${ret.toFixed(2)}%`,
                            ];
                        },
                    },
                },
            },
            scales: {
                x: {
                    title: { display: true, text: "Annualized Volatility (%)", font: { size: 12 } },
                    ticks: { callback: (v) => `${v.toFixed(1)}%` },
                },
                y: {
                    title: { display: true, text: "1Y Return (%)", font: { size: 12 } },
                    ticks: { callback: (v) => `${v.toFixed(1)}%` },
                },
            },
        },
    });
}
