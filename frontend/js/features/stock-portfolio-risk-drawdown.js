/* Stock Portfolio — Risk & Drawdown
 * Uses the existing holding-analysis table plus the existing /charts endpoint.
 * No second calculation engine: historical risk is derived from the same
 * annual Yahoo price series already used by Stock Analysis.
 */
(function () {
    const ROOT_ID = "portfolio-risk-drawdown";
    let chart = null;
    let requestToken = 0;

    const esc = (value) => String(value ?? "")
        .replaceAll("&", "&amp;").replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");
    const num = (v) => { const n = Number(v); return Number.isFinite(n) ? n : null; };
    const pct = (v, d = 1) => num(v) == null ? "—" : `${num(v).toFixed(d)}%`;

    function parseRows() {
        return [...document.querySelectorAll(".portfolio-analysis-table tbody tr")].map(row => {
            const cells = row.querySelectorAll("td");
            const name = row.querySelector("td:first-child strong")?.textContent?.trim() || "Holding";
            const symbol = row.querySelector("td:first-child small")?.textContent?.split("·")[0]?.trim() || "";
            return {
                name,
                symbol,
                allocation: num(cells[1]?.textContent),
                roe: num(cells[3]?.textContent),
                revenueGrowth: num(cells[4]?.textContent),
                debtEquity: num(cells[5]?.textContent)
            };
        }).filter(r => r.symbol && r.allocation != null);
    }

    function destroy() {
        if (chart) { try { chart.destroy(); } catch (_) {} chart = null; }
        document.getElementById(ROOT_ID)?.remove();
    }

    function calculatePortfolioPath(rows, priceMap) {
        const years = [...new Set(rows.flatMap(r => Object.keys(priceMap[r.symbol] || {})))].sort();
        if (years.length < 3) return null;
        const usable = rows.filter(r => priceMap[r.symbol] && years.some(y => priceMap[r.symbol][y] != null));
        const firstCommon = years.find(y => usable.every(r => priceMap[r.symbol][y] != null));
        if (!firstCommon) return null;
        const pathYears = years.filter(y => y >= firstCommon);
        const values = pathYears.map(year => usable.reduce((sum, r) => {
            const start = priceMap[r.symbol][firstCommon], current = priceMap[r.symbol][year];
            if (start == null || current == null || start <= 0 || current <= 0) return sum;
            return sum + (r.allocation / 100) * (current / start) * 100;
        }, 0));
        const coverage = usable.reduce((sum, r) => sum + r.allocation, 0);
        if (coverage <= 0 || values.length < 3) return null;
        return { years: pathYears, values: values.map(v => v * 100 / coverage), coverage };
    }

    function riskMetrics(path) {
        let peak = path.values[0], maxDd = 0, peakYear = path.years[0], troughYear = path.years[0];
        path.values.forEach((value, i) => {
            if (value > peak) { peak = value; peakYear = path.years[i]; }
            const dd = (value / peak - 1) * 100;
            if (dd < maxDd) { maxDd = dd; troughYear = path.years[i]; }
        });
        const returns = [];
        for (let i = 1; i < path.values.length; i++) {
            if (path.values[i - 1] > 0) returns.push(path.values[i] / path.values[i - 1] - 1);
        }
        const mean = returns.length ? returns.reduce((a, b) => a + b, 0) / returns.length : 0;
        const volatility = returns.length > 1 ? Math.sqrt(returns.reduce((s, r) => s + Math.pow(r - mean, 2), 0) / (returns.length - 1)) * 100 : null;
        const currentDrawdown = path.values.length ? (path.values[path.values.length - 1] / Math.max(...path.values) - 1) * 100 : 0;
        return { maxDd, peakYear, troughYear, volatility, currentDrawdown };
    }

    function render(rows, path, metrics) {
        destroy();
        const hhi = rows.reduce((s, r) => s + Math.pow(r.allocation, 2), 0);
        const largest = Math.max(...rows.map(r => r.allocation));
        const leverageExposure = rows.reduce((s, r) => s + (r.debtEquity != null && r.debtEquity > 1 ? r.allocation : 0), 0);
        const negativeGrowthExposure = rows.reduce((s, r) => s + (r.revenueGrowth != null && r.revenueGrowth < 0 ? r.allocation : 0), 0);
        const root = document.createElement("section");
        root.id = ROOT_ID;
        root.className = "stock-section portfolio-analysis-section portfolio-risk-section";
        root.innerHTML = `
            <div class="stock-section-header">
                <div><h2>Portfolio Risk &amp; Drawdown</h2><span>Historical price path and current portfolio exposures</span></div>
                <span class="portfolio-risk-badge">RISK VIEW</span>
            </div>
            <div class="portfolio-risk-metrics">
                <div class="portfolio-risk-card"><span>Max drawdown</span><strong>${pct(metrics.maxDd)}</strong><small>${esc(metrics.peakYear)} peak → ${esc(metrics.troughYear)} trough</small></div>
                <div class="portfolio-risk-card"><span>Annual volatility</span><strong>${pct(metrics.volatility)}</strong><small>Based on annual price returns</small></div>
                <div class="portfolio-risk-card"><span>Current drawdown</span><strong>${pct(metrics.currentDrawdown)}</strong><small>From the historical peak</small></div>
                <div class="portfolio-risk-card"><span>Concentration</span><strong>${pct(hhi)}</strong><small>HHI · higher means more concentrated</small></div>
            </div>
            <div class="portfolio-risk-chart-wrap"><canvas class="portfolio-risk-chart" aria-label="Portfolio historical drawdown path"></canvas></div>
            <div class="portfolio-risk-exposure-grid">
                <div><div class="risk-exposure-label"><span>Largest position</span><strong>${pct(largest)}</strong></div><div class="risk-track"><span style="width:${Math.min(100, largest)}%"></span></div></div>
                <div><div class="risk-exposure-label"><span>Allocation in D/E &gt; 1x holdings</span><strong>${pct(leverageExposure)}</strong></div><div class="risk-track"><span style="width:${Math.min(100, leverageExposure)}%"></span></div></div>
                <div><div class="risk-exposure-label"><span>Allocation in negative revenue-growth holdings</span><strong>${pct(negativeGrowthExposure)}</strong></div><div class="risk-track"><span style="width:${Math.min(100, negativeGrowthExposure)}%"></span></div></div>
            </div>
            <p class="portfolio-analysis-note">Drawdown is calculated from annual closing prices over the available history using your current allocation weights. It is a historical exposure view, not a transaction-level backtest: it excludes dividends, taxes, costs and rebalancing. Annual data can understate an intra-year drawdown.</p>
        `;
        const anchor = document.getElementById("portfolio-positioning-map") || [...document.querySelectorAll(".portfolio-analysis-section")].find(s => s.textContent.includes("Portfolio Performance"));
        if (anchor) anchor.insertAdjacentElement("afterend", root); else document.getElementById("portfolio-analysis-results")?.appendChild(root);

        const canvas = root.querySelector(".portfolio-risk-chart");
        if (canvas && typeof Chart !== "undefined") {
            chart = new Chart(canvas, {
                type: "line",
                data: { labels: path.years, datasets: [{ label: "Portfolio value", data: path.values, borderColor: "#172033", backgroundColor: "rgba(37,99,235,0.10)", fill: true, tension: 0.25, pointRadius: 3, pointHoverRadius: 5 }] },
                options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false }, tooltip: { callbacks: { label: c => ` Portfolio value: ${Number(c.parsed.y).toFixed(1)}` } } }, scales: { x: { grid: { display: false }, ticks: { color: "#64748b" } }, y: { grid: { color: "#edf2f7" }, ticks: { color: "#64748b" }, title: { display: true, text: "Indexed value (first common year = 100)", color: "#475569", font: { weight: "600" } } } } }
            });
        }
    }

    async function load() {
        const results = document.getElementById("portfolio-analysis-results");
        if (!results || results.hidden) return;
        const rows = parseRows();
        if (!rows.length) return;
        const token = ++requestToken;
        const responses = await Promise.all(rows.map(async row => {
            try {
                const response = await fetch(`/api/stocks/${encodeURIComponent(row.symbol)}/charts`, { cache: "no-store" });
                if (!response.ok) return [row.symbol, {}];
                const payload = await response.json();
                const prices = Array.isArray(payload?.charts?.annual_prices) ? payload.charts.annual_prices : [];
                return [row.symbol, Object.fromEntries(prices.map(p => [String(p.date || "").slice(0, 4), num(p.close)]).filter(([, v]) => v != null))];
            } catch (_) { return [row.symbol, {}]; }
        }));
        if (token !== requestToken) return;
        const priceMap = Object.fromEntries(responses);
        const path = calculatePortfolioPath(rows, priceMap);
        if (!path) return;
        render(rows, path, riskMetrics(path));
    }

    let timer;
    function schedule() { clearTimeout(timer); timer = setTimeout(load, 150); }
    function init() {
        const results = document.getElementById("portfolio-analysis-results");
        if (!results) return;
        new MutationObserver(schedule).observe(results, { childList: true, subtree: true });
        schedule();
    }
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
})();
