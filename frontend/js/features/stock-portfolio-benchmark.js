// Stock Portfolio — Portfolio vs Benchmark comparison.
// Uses the same portfolio allocation + price-CAGR methodology already used by
// stock-portfolio-analysis.js. Benchmark market history is supplied by the
// dedicated backend endpoint and is never fabricated client-side.

const BENCHMARK_API = "/api/stock-benchmarks/comparison";
const PORTFOLIO_STORAGE_KEY = "market-analysis-stock-portfolio-v1";
const BENCHMARK_CACHE_KEY = "stock-portfolio-benchmark-data-v1";
const PORTFOLIO_CHART_CACHE_KEY = "stock-portfolio-benchmark-chart-cache-v1";

let benchmarkData = null;
let benchmarkChart = null;
let benchmarkChartsLoaded = false;
let benchmarkRenderToken = 0;

const benchmarkEsc = value => String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");

const benchmarkNum = value => {
    const n = Number(value);
    return Number.isFinite(n) ? n : null;
};

const benchmarkPct = value => {
    const n = benchmarkNum(value);
    return n == null ? "—" : `${n.toLocaleString("en-IN", { maximumFractionDigits: 1 })}%`;
};

function readPortfolio() {
    try {
        const raw = JSON.parse(localStorage.getItem(PORTFOLIO_STORAGE_KEY) || "[]");
        if (!Array.isArray(raw)) return [];
        return raw.map(item => ({
            symbol: String(item?.symbol || "").trim().toUpperCase(),
            allocation: benchmarkNum(item?.allocation) || 0,
        })).filter(item => item.symbol && item.allocation > 0);
    } catch (_) {
        return [];
    }
}

function readCache(key) {
    try { return JSON.parse(sessionStorage.getItem(key) || "null"); } catch (_) { return null; }
}

function writeCache(key, value) {
    try { sessionStorage.setItem(key, JSON.stringify(value)); } catch (_) {}
}

async function loadBenchmarkData() {
    const cached = readCache(BENCHMARK_CACHE_KEY);
    if (cached && typeof cached === "object") return cached;
    const response = await fetch(BENCHMARK_API, { headers: { Accept: "application/json" }, cache: "no-store" });
    if (!response.ok) throw new Error("Benchmark data request failed");
    const data = await response.json();
    writeCache(BENCHMARK_CACHE_KEY, data);
    return data;
}

async function loadStockChart(symbol) {
    const cache = readCache(PORTFOLIO_CHART_CACHE_KEY) || {};
    if (cache[symbol]) return cache[symbol];
    const response = await fetch(`/api/stocks/${encodeURIComponent(symbol)}/charts`, { headers: { Accept: "application/json" }, cache: "no-store" });
    if (!response.ok) throw new Error(`Unable to load ${symbol} price history`);
    const data = await response.json();
    cache[symbol] = data;
    writeCache(PORTFOLIO_CHART_CACHE_KEY, cache);
    return data;
}

function cagrFromStockCharts(stockCharts, years) {
    const points = stockCharts?.charts?.price_cagr || [];
    const point = points.find(item => String(item?.year || "").toUpperCase() === `${years}Y`);
    const value = benchmarkNum(point?.value);
    if (value != null) return value;

    // Reuse the same rolling-CAGR fallback already exposed by Stock Analysis
    // for 3Y and 5Y when the Screener CAGR is unavailable.
    if (years === 3 || years === 5) {
        const rolling = stockCharts?.charts?.[`price_cagr_${years}y`] || [];
        const latest = rolling[rolling.length - 1];
        const fallback = benchmarkNum(latest?.value);
        if (fallback != null) return fallback;
    }
    return null;
}

function portfolioCagrs(portfolio, chartMap) {
    const periods = [1, 3, 5, 10];
    return Object.fromEntries(periods.map(years => {
        const available = portfolio.map(row => {
            const cagr = cagrFromStockCharts(chartMap[row.symbol], years);
            return cagr == null ? null : { ...row, cagr };
        }).filter(Boolean);

        const coverage = available.reduce((sum, row) => sum + row.allocation, 0);
        if (!available.length || coverage <= 0) return [String(years), { cagr: null, coverage: 0 }];

        // This is deliberately the same calculation as performanceRows() in
        // stock-portfolio-analysis.js: allocation-normalised geometric growth,
        // not allocation x CAGR.
        let growth = 0;
        available.forEach(row => {
            const weight = row.allocation / coverage;
            growth += weight * Math.pow(1 + row.cagr / 100, years);
        });
        const cagr = (Math.pow(growth, 1 / years) - 1) * 100;
        return [String(years), { cagr, coverage }];
    }));
}

function benchmarkSelectMarkup(selected) {
    const options = [
        ["nifty50", "NIFTY 50"],
        ["nifty500", "NIFTY 500"],
        ["sensex", "BSE SENSEX"],
    ];
    return options.map(([key, label]) => `<option value="${key}" ${selected === key ? "selected" : ""}>${label}</option>`).join("");
}

function findDataNotesSection(container) {
    return [...container.querySelectorAll("section")].find(section =>
        String(section.querySelector("h2")?.textContent || "").trim().toLowerCase() === "data notes"
    ) || null;
}

function renderBenchmarkShell(container) {
    const existing = container.querySelector("#portfolio-benchmark-section");
    if (existing) return existing;

    const section = document.createElement("section");
    section.id = "portfolio-benchmark-section";
    section.className = "stock-section portfolio-analysis-section portfolio-benchmark-section";
    section.innerHTML = `
        <div class="stock-section-header portfolio-benchmark-header">
            <div>
                <h2>Portfolio vs Market</h2>
                <span>Historical price CAGR compared with a market benchmark</span>
            </div>
            <label class="portfolio-benchmark-selector">
                <span>Compare with</span>
                <select id="portfolio-benchmark-select" aria-label="Benchmark">${benchmarkSelectMarkup("nifty50")}</select>
            </label>
        </div>
        <div id="portfolio-benchmark-status" class="portfolio-benchmark-status">Loading benchmark comparison…</div>
        <div id="portfolio-benchmark-content" hidden>
            <div id="portfolio-benchmark-highlight" class="portfolio-benchmark-highlight"></div>
            <div class="portfolio-benchmark-chart-wrap"><canvas id="portfolio-benchmark-chart"></canvas></div>
            <div id="portfolio-benchmark-table" class="portfolio-benchmark-table-wrap"></div>
            <div id="portfolio-benchmark-note" class="portfolio-analysis-note"></div>
        </div>`;

    const notes = findDataNotesSection(container);
    if (notes) container.insertBefore(section, notes);
    else container.appendChild(section);

    section.querySelector("#portfolio-benchmark-select")?.addEventListener("change", () => renderBenchmarkComparison(container));
    return section;
}

function renderBenchmarkComparison(container) {
    if (!benchmarkData) return;
    const token = ++benchmarkRenderToken;
    const section = renderBenchmarkShell(container);
    const select = section.querySelector("#portfolio-benchmark-select");
    const key = select?.value || "nifty50";
    const benchmark = benchmarkData[key];
    const portfolio = readPortfolio();
    const status = section.querySelector("#portfolio-benchmark-status");
    const content = section.querySelector("#portfolio-benchmark-content");

    if (!benchmark?.available) {
        status.textContent = "Benchmark data is currently unavailable.";
        content.hidden = true;
        return;
    }

    status.textContent = "Preparing portfolio comparison…";
    content.hidden = true;

    Promise.allSettled(portfolio.map(row => loadStockChart(row.symbol))).then(results => {
        if (token !== benchmarkRenderToken) return;
        const chartMap = {};
        results.forEach((result, index) => {
            if (result.status === "fulfilled") chartMap[portfolio[index].symbol] = result.value;
        });

        const portfolioCagr = portfolioCagrs(portfolio, chartMap);
        const periods = [1, 3, 5, 10];
        const rows = periods.map(years => ({
            years,
            portfolio: portfolioCagr[String(years)]?.cagr ?? null,
            coverage: portfolioCagr[String(years)]?.coverage ?? 0,
            benchmark: benchmark.cagr?.[String(years)] ?? null,
        }));
        const complete = rows.filter(row => row.portfolio != null && row.benchmark != null);
        if (!complete.length) {
            status.textContent = "There is not enough overlapping historical data to compare this portfolio with the selected benchmark.";
            content.hidden = true;
            return;
        }

        const selected5Y = rows.find(row => row.years === 5) || complete[complete.length - 1];
        const relative = selected5Y.portfolio != null && selected5Y.benchmark != null ? selected5Y.portfolio - selected5Y.benchmark : null;
        const coverageNote = rows.some(row => row.portfolio != null && row.coverage < 99.99)
            ? "Portfolio CAGR is calculated on the covered allocation where a holding does not have the required historical CAGR."
            : "Portfolio CAGR uses the full current allocation.";

        section.querySelector("#portfolio-benchmark-highlight").innerHTML = `
            <div class="portfolio-benchmark-highlight-card">
                <span>5Y portfolio CAGR</span><strong>${benchmarkPct(selected5Y.portfolio)}</strong>
                <small>${benchmarkEsc(coverageNote.replace("Portfolio CAGR is calculated on the covered allocation where a holding does not have the required historical CAGR.", "Current allocation"))}</small>
            </div>
            <div class="portfolio-benchmark-highlight-card">
                <span>5Y ${benchmarkEsc(benchmark.label)}</span><strong>${benchmarkPct(selected5Y.benchmark)}</strong>
                <small>Same historical period</small>
            </div>
            <div class="portfolio-benchmark-highlight-card portfolio-benchmark-relative">
                <span>5Y difference</span><strong>${relative == null ? "—" : `${relative >= 0 ? "+" : ""}${benchmarkPct(relative)}`}</strong>
                <small>Portfolio CAGR minus benchmark CAGR</small>
            </div>`;

        section.querySelector("#portfolio-benchmark-table").innerHTML = `
            <div class="portfolio-benchmark-table-title">CAGR comparison</div>
            <div class="portfolio-benchmark-table-scroll"><table class="stock-table portfolio-benchmark-table"><thead><tr><th>Period</th><th>Portfolio</th><th>${benchmarkEsc(benchmark.label)}</th><th>Difference</th><th>Coverage</th></tr></thead><tbody>${rows.map(row => {
                const diff = row.portfolio != null && row.benchmark != null ? row.portfolio - row.benchmark : null;
                return `<tr><td><strong>${row.years}Y</strong></td><td>${benchmarkPct(row.portfolio)}</td><td>${benchmarkPct(row.benchmark)}</td><td>${diff == null ? "—" : `${diff >= 0 ? "+" : ""}${benchmarkPct(diff)}`}</td><td>${row.portfolio == null ? "—" : benchmarkPct(row.coverage)}</td></tr>`;
            }).join("")}</tbody></table></div>`;

        section.querySelector("#portfolio-benchmark-note").textContent =
            "Benchmark returns are based on annual market-price history from Yahoo Finance. Portfolio returns reuse the Stock Analysis price-CAGR inputs and the existing allocation-weighted geometric-growth calculation. This is a price-return comparison; dividends, taxes, transaction costs and portfolio rebalancing are not included.";

        status.textContent = `${benchmark.label} comparison · ${complete.length} comparable periods`;
        content.hidden = false;
        drawBenchmarkChart(section, rows, benchmark.label);
    });
}

function drawBenchmarkChart(section, rows, benchmarkLabel) {
    const canvas = section.querySelector("#portfolio-benchmark-chart");
    if (!canvas || typeof Chart === "undefined") return;
    if (benchmarkChart) { try { benchmarkChart.destroy(); } catch (_) {} }

    const available = rows.filter(row => row.portfolio != null || row.benchmark != null);
    benchmarkChart = new Chart(canvas, {
        type: "bar",
        data: {
            labels: available.map(row => `${row.years}Y`),
            datasets: [
                { label: "Your portfolio", data: available.map(row => row.portfolio), backgroundColor: "#0f172a", borderRadius: 6, borderSkipped: false, maxBarThickness: 42 },
                { label: benchmarkLabel, data: available.map(row => row.benchmark), backgroundColor: "#64748b", borderRadius: 6, borderSkipped: false, maxBarThickness: 42 },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: "top", labels: { usePointStyle: true, boxWidth: 8, color: "#334155", font: { weight: "600" } } },
                tooltip: { callbacks: { label: context => `${context.dataset.label}: ${benchmarkPct(context.parsed.y)}` } },
            },
            scales: {
                x: { grid: { display: false }, ticks: { color: "#475569", font: { weight: "600" } } },
                y: { grid: { color: "#edf2f7" }, ticks: { color: "#64748b", callback: value => `${value}%` }, title: { display: true, text: "Annualised return", color: "#475569", font: { weight: "600" } } },
            },
        },
    });
}

async function initialiseBenchmarkFeature(container) {
    if (benchmarkChartsLoaded) {
        renderBenchmarkComparison(container);
        return;
    }
    benchmarkChartsLoaded = true;
    try {
        benchmarkData = await loadBenchmarkData();
        renderBenchmarkComparison(container);
    } catch (error) {
        const section = renderBenchmarkShell(container);
        const status = section.querySelector("#portfolio-benchmark-status");
        if (status) status.textContent = "Benchmark comparison could not be loaded right now.";
        console.warn("Stock portfolio benchmark comparison unavailable:", error);
    }
}

function watchPortfolioAnalysis() {
    const container = document.getElementById("portfolio-analysis-results");
    if (!container) return;

    const observer = new MutationObserver(() => {
        if (container.children.length && !container.querySelector("#portfolio-benchmark-section")) {
            initialiseBenchmarkFeature(container);
        }
    });
    observer.observe(container, { childList: true, subtree: true });

    if (container.children.length) initialiseBenchmarkFeature(container);
}

export function initStockPortfolioBenchmark() {
    watchPortfolioAnalysis();
}
