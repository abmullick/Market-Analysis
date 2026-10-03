/* Stock Portfolio — Quality × Growth positioning map
 *
 * Intentionally consumes the already-rendered Holding Analysis table rather than
 * introducing another portfolio-data request or a second calculation engine.
 * X = Revenue Growth, Y = ROE, bubble size = current allocation.
 */
(function () {
    const ROOT_ID = "portfolio-positioning-map";
    let chart = null;

    function esc(value) {
        return String(value ?? "")
            .replaceAll("&", "&amp;")
            .replaceAll("<", "&lt;")
            .replaceAll(">", "&gt;")
            .replaceAll('"', "&quot;")
            .replaceAll("'", "&#039;");
    }

    function valueFromCell(cell) {
        if (!cell) return null;
        const match = String(cell.textContent || "").replace(/,/g, "").match(/-?\d+(?:\.\d+)?/);
        return match ? Number(match[0]) : null;
    }

    function readRows() {
        return [...document.querySelectorAll(".portfolio-analysis-table tbody tr")].map(row => {
            const cells = row.querySelectorAll("td");
            const name = row.querySelector("td:first-child strong")?.textContent?.trim() || "Holding";
            return {
                name,
                allocation: valueFromCell(cells[1]),
                pe: valueFromCell(cells[2]),
                roe: valueFromCell(cells[3]),
                growth: valueFromCell(cells[4]),
                debtEquity: valueFromCell(cells[5])
            };
        }).filter(item => item.roe != null && item.growth != null && item.allocation != null);
    }

    function quadrant(x, y, medianX, medianY) {
        if (x >= medianX && y >= medianY) return "High growth · High quality";
        if (x < medianX && y >= medianY) return "Lower growth · High quality";
        if (x >= medianX && y < medianY) return "High growth · Lower quality";
        return "Lower growth · Lower quality";
    }

    function median(values) {
        const sorted = [...values].sort((a, b) => a - b);
        if (!sorted.length) return 0;
        const middle = Math.floor(sorted.length / 2);
        return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
    }

    function destroy() {
        if (chart) {
            try { chart.destroy(); } catch (_) {}
            chart = null;
        }
        document.getElementById(ROOT_ID)?.remove();
    }

    function render() {
        const results = document.getElementById("portfolio-analysis-results");
        if (!results || results.hidden || !results.querySelector(".portfolio-analysis-table")) return;

        const rows = readRows();
        if (rows.length < 2) return;

        destroy();

        const medianGrowth = median(rows.map(item => item.growth));
        const medianRoe = median(rows.map(item => item.roe));
        const root = document.createElement("section");
        root.id = ROOT_ID;
        root.className = "stock-section portfolio-analysis-section portfolio-positioning-section";
        root.innerHTML = `
            <div class="stock-section-header">
                <div>
                    <h2>Portfolio Positioning Map</h2>
                    <span>Quality × growth view · bubble size represents portfolio allocation</span>
                </div>
                <span class="portfolio-positioning-badge">VISUAL</span>
            </div>
            <div class="portfolio-positioning-chart-wrap">
                <canvas class="portfolio-positioning-chart" aria-label="Portfolio quality and growth positioning map"></canvas>
            </div>
            <div class="portfolio-positioning-legend">
                <span><i class="position-dot"></i> Each bubble is a holding</span>
                <span><strong>X</strong> Revenue Growth</span>
                <span><strong>Y</strong> ROE</span>
                <span>Bubble size = allocation</span>
            </div>
            <div class="portfolio-positioning-summary">
                <div><strong>${rows.length}</strong><span>holdings plotted</span></div>
                <div><strong>${esc(medianGrowth.toFixed(1))}%</strong><span>median revenue growth</span></div>
                <div><strong>${esc(medianRoe.toFixed(1))}%</strong><span>median ROE</span></div>
            </div>
            <p class="portfolio-analysis-note">The horizontal and vertical reference lines use the portfolio's own medians. This makes the map relative to the current holdings rather than applying an external threshold. It is a descriptive positioning view, not an investment score.</p>
        `;

        const sector = results.querySelector(".portfolio-analysis-table")?.closest(".portfolio-analysis-section");
        const valuation = [...results.querySelectorAll(".portfolio-analysis-section")].find(section => section.textContent.includes("Portfolio Valuation"));
        const anchor = valuation || sector || results.firstElementChild;
        if (anchor) anchor.insertAdjacentElement("afterend", root);
        else results.prepend(root);

        const canvas = root.querySelector(".portfolio-positioning-chart");
        if (!canvas || typeof Chart === "undefined") return;

        const maxAllocation = Math.max(...rows.map(item => item.allocation), 1);
        chart = new Chart(canvas, {
            type: "scatter",
            data: {
                datasets: [{
                    label: "Holdings",
                    data: rows.map(item => ({ x: item.growth, y: item.roe, name: item.name, allocation: item.allocation, pe: item.pe, debtEquity: item.debtEquity })),
                    backgroundColor: "rgba(15, 23, 42, 0.82)",
                    borderColor: "#2563eb",
                    borderWidth: 1.5,
                    pointRadius: rows.map(item => Math.max(7, Math.min(22, 7 + (item.allocation / maxAllocation) * 15))),
                    pointHoverRadius: rows.map(item => Math.max(10, Math.min(25, 10 + (item.allocation / maxAllocation) * 15)))
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { mode: "nearest", intersect: true },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            title: items => items[0]?.raw?.name || "Holding",
                            label: context => {
                                const item = context.raw || {};
                                const lines = [`Revenue Growth: ${Number(item.x).toFixed(1)}%`, `ROE: ${Number(item.y).toFixed(1)}%`, `Allocation: ${Number(item.allocation).toFixed(1)}%`];
                                if (item.pe != null) lines.push(`P/E: ${Number(item.pe).toFixed(1)}x`);
                                return lines;
                            }
                        }
                    },
                    positioningReference: { medianGrowth, medianRoe }
                },
                scales: {
                    x: {
                        title: { display: true, text: "Revenue Growth (%)", color: "#475569", font: { weight: "700" } },
                        grid: { color: "#e8edf4" },
                        ticks: { color: "#64748b", callback: value => `${value}%` }
                    },
                    y: {
                        title: { display: true, text: "ROE (%)", color: "#475569", font: { weight: "700" } },
                        grid: { color: "#e8edf4" },
                        ticks: { color: "#64748b", callback: value => `${value}%` }
                    }
                }
            },
            plugins: [{
                id: "portfolioMedianLines",
                afterDraw(instance) {
                    const xScale = instance.scales.x;
                    const yScale = instance.scales.y;
                    if (!xScale || !yScale) return;
                    const ctx = instance.ctx;
                    const x = xScale.getPixelForValue(medianGrowth);
                    const y = yScale.getPixelForValue(medianRoe);
                    ctx.save();
                    ctx.setLineDash([5, 5]);
                    ctx.lineWidth = 1;
                    ctx.strokeStyle = "#94a3b8";
                    ctx.beginPath(); ctx.moveTo(x, yScale.top); ctx.lineTo(x, yScale.bottom); ctx.stroke();
                    ctx.beginPath(); ctx.moveTo(xScale.left, y); ctx.lineTo(xScale.right, y); ctx.stroke();
                    ctx.setLineDash([]);
                    ctx.fillStyle = "#64748b";
                    ctx.font = "600 11px system-ui, sans-serif";
                    ctx.fillText("Median", Math.min(x + 6, xScale.right - 45), yScale.top + 14);
                    ctx.restore();
                }
            }]
        });
    }

    let timer = null;
    function scheduleRender() {
        clearTimeout(timer);
        timer = setTimeout(render, 80);
    }

    function init() {
        const results = document.getElementById("portfolio-analysis-results");
        if (!results) return;
        const observer = new MutationObserver(scheduleRender);
        observer.observe(results, { childList: true, subtree: true });
        scheduleRender();
    }

    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
    else init();
})();
