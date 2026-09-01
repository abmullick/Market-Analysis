export function renderRiskReturnChart(container, enrichedFunds) {
    if (!container || !enrichedFunds || enrichedFunds.length < 2) return;

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

    const controls = document.createElement("div");
    controls.className = "chart-period-buttons";

    const periods = [
        { label: "1Y", returnKey: "one_year_return", volatilityKey: "one_year_volatility" },
        { label: "3Y", returnKey: "three_year_cagr", volatilityKey: "three_year_volatility" },
        { label: "5Y", returnKey: "five_year_cagr", volatilityKey: "five_year_volatility" },
        { label: "10Y", returnKey: "ten_year_cagr", volatilityKey: "ten_year_volatility" },
    ];

    let activePeriod = periods[1];

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

    function getFundData(period) {
        return enrichedFunds.filter(f => {
            const vol = f._detail?.[period.volatilityKey];
            const ret = f._detail?.[period.returnKey];
            return vol != null && ret != null;
        });
    }

    function renderChart(period) {
        chartContainer.innerHTML = "";
        const newCanvas = document.createElement("canvas");
        newCanvas.id = canvas.id;
        chartContainer.appendChild(newCanvas);

        const fundsWithData = getFundData(period);
        if (fundsWithData.length < 2) {
            chartContainer.innerHTML = `<div class="empty-state"><h3>Not enough data</h3><p>At least 2 funds need both ${period.label} return and ${period.label} volatility data.</p></div>`;
            return;
        }

        const colors = [
            "#2563eb", "#dc2626", "#16a34a", "#d97706", "#7c3aed",
            "#059669", "#db2777", "#2563eb", "#65a30d", "#0891b2",
        ];

        const datasets = fundsWithData.map((f, i) => {
            const volatility = f._detail[period.volatilityKey] * 100;
            const ret = f._detail[period.returnKey] * 100;
            return {
                label: f.scheme_name,
                data: [{ x: volatility, y: ret }],
                backgroundColor: colors[i % colors.length],
                pointRadius: 8,
                pointHoverRadius: 10,
            };
        });

        new Chart(newCanvas.getContext("2d"), {
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
                                const vol = fund._detail[period.volatilityKey] * 100;
                                const ret = fund._detail[period.returnKey] * 100;
                                return [
                                    fund.scheme_name,
                                    `Volatility: ${vol.toFixed(2)}%`,
                                    `${period.label} Return: ${ret.toFixed(2)}%`,
                                ];
                            },
                        },
                    },
                },
                scales: {
                    x: {
                        title: { display: true, text: `${period.label} Annualized Volatility (%)`, font: { size: 12 } },
                        ticks: { callback: (v) => `${v.toFixed(1)}%` },
                    },
                    y: {
                        title: { display: true, text: `${period.label} Return (%)`, font: { size: 12 } },
                        ticks: { callback: (v) => `${v.toFixed(1)}%` },
                    },
                },
            },
        });
    }

    periods.forEach(period => {
        const btn = document.createElement("button");
        btn.className = `chart-period-btn${period === activePeriod ? " active" : ""}`;
        btn.textContent = period.label;
        btn.addEventListener("click", () => {
            controls.querySelectorAll(".chart-period-btn").forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            activePeriod = period;
            renderChart(period);
        });
        controls.appendChild(btn);
    });

    wrapper.insertBefore(controls, chartContainer);
    renderChart(activePeriod);
}
