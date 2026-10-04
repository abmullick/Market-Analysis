/* Stock Portfolio Builder Help
 * Keeps Help & Methodology synchronized with the live Stock Portfolio Builder.
 * The Help search indexes visible DOM content dynamically, so these cards are searchable
 * without maintaining a second search index.
 */

const PORTFOLIO_SECTION_TITLE = "Stock Portfolio Builder";

const cards = [
    ["Build Workflow", `Build the portfolio from the same stock universe used by Stock Analysis. Search by company/symbol, optionally filter by sector and market-cap class, add the required stocks, assign allocations, and make the total exactly <strong>100%</strong> before continuing to analysis.`],
    ["Stock Selection & Filters", `The selector uses the Stock Analysis stock universe. Available controls include <strong>Company or symbol</strong> search, <strong>Sector</strong> multi-select, and <strong>Large Cap / Mid Cap / Small Cap / Micro Cap</strong> quick filters. Filtering is applied to the loaded stock universe before the visible results are paginated.`],
    ["Allocation Rules", `Each selected holding receives an allocation percentage. The <strong>Continue to Portfolio Analysis</strong> action is enabled when the portfolio total is 100%. Allocation is the weight used throughout the portfolio calculations. This builder does not record transaction prices, quantities, tax lots or trade history.`],
    ["Portfolio Snapshot", `The analysis starts with the number of holdings, largest position, number of sectors and an allocation concentration measure. The largest-position percentage shows direct single-stock exposure. Concentration is calculated using the <strong>Herfindahl-Hirschman Index (HHI)</strong> over the current stock allocations, so a more concentrated allocation produces a higher HHI.`],
    ["Portfolio Quality", `Quality metrics are allocation-weighted from the Stock Analysis fundamentals. The current view includes <strong>ROE, ROCE, Revenue Growth, Profit Growth and Debt / Equity</strong>, together with coverage. Coverage is the percentage of portfolio allocation for which that metric is available. Missing company data is not replaced with an arbitrary estimate.`],
    ["Portfolio Valuation", `The valuation view displays allocation-weighted <strong>P/E, P/B, EV / EBITDA and Dividend Yield</strong> with coverage. These are exposure indicators rather than mathematically aggregated portfolio multiples. Financial-sector holdings may require a different valuation interpretation, so EV/EBITDA is not treated as equally informative across all business models.`],
    ["Sector Allocation", `Sector exposure is calculated by summing the portfolio allocation of holdings belonging to each sector. The result is displayed as proportional bars so the largest sector exposures can be identified immediately. Holdings without a usable sector classification are grouped as <strong>Other</strong>.`],
    ["Holding Analysis & Signals", `Holding Analysis shows each stock's allocation, P/E, ROE, Revenue Growth, Debt / Equity and a directional fundamental <strong>Signal</strong>. The signal can display <strong>Positive</strong>, <strong>Watch</strong>, <strong>Mixed</strong> or <strong>No signal</strong>. A signal is a compact description of the available fundamentals; it is not a portfolio return forecast or a buy/sell instruction.`],
    ["Historical Portfolio Performance", `Portfolio Performance converts each holding's historical <strong>price CAGR</strong> into a growth factor, applies the current portfolio allocations, combines the growth factors geometrically, and converts the result back into CAGR. It reports <strong>1Y, 3Y, 5Y and 10Y</strong> historical price CAGR where data exists, plus coverage for each period. The visual includes a CAGR bar chart and a 3Y holding-level view.`],
    ["Performance Calculation", `For a period of <em>n</em> years, each available holding contributes its historical CAGR as a growth factor: <code>(1 + CAGR)ⁿ</code>. The factors are combined using allocation-normalised weights and converted to annualised CAGR: <code>(Σ weight × (1 + CAGR)ⁿ)^(1/n) − 1</code>. When a holding lacks the required history, the displayed portfolio CAGR is calculated on the covered allocation and the coverage percentage is shown. This is not a transaction-level backtest and excludes dividends, taxes, costs and rebalancing.`],
    ["Portfolio vs Market", `The benchmark comparison compares the portfolio's historical price-CAGR performance with a selectable market benchmark: <strong>NIFTY 50, NIFTY 500 or BSE SENSEX</strong>. The view shows 1Y/3Y/5Y/10Y CAGR, coverage, a comparison chart and the difference between portfolio and benchmark CAGR.`],
    ["Benchmark Methodology", `Benchmark comparison is a historical <strong>price-return</strong> comparison. Portfolio returns use the allocation-weighted geometric-growth calculation described above. Benchmark returns use annual market-price history. Dividends, taxes, transaction costs and portfolio rebalancing are excluded. A positive or negative historical difference describes the selected period; it is not a forecast.`],
    ["Portfolio Positioning Map", `The Quality × Growth map uses <strong>X-axis = Revenue Growth</strong>, <strong>Y-axis = ROE</strong>, and <strong>bubble size = current allocation</strong>. The horizontal and vertical reference lines are the portfolio's own median Revenue Growth and median ROE. This makes the map relative to the current holdings and is a descriptive visual, not an investment score.`],
    ["Portfolio Risk & Drawdown", `The risk view reconstructs a historical portfolio path from annual closing prices using the current allocation weights. It reports <strong>Maximum Drawdown, Annual Volatility, Current Drawdown and HHI concentration</strong>, plus exposure bars for the largest holding, holdings with Debt / Equity above 1x, and holdings with negative revenue growth. Because the source is annual closing prices, intra-year drawdowns can be understated.`],
    ["Risk Calculation", `Maximum Drawdown is the largest decline from a previous historical portfolio peak. Annual volatility is calculated from successive annual portfolio-price returns using sample standard deviation. Current Drawdown measures the latest indexed portfolio value relative to its historical peak. The historical path is an exposure view rather than a transaction-level backtest and excludes dividends, taxes, costs and rebalancing.`],
    ["What-If / Rebalancing", `The What-If / Rebalancing panel lets you change allocations across the <strong>same holdings</strong> and immediately compare the proposed portfolio with the current one. It recomputes allocation-weighted <strong>P/E, ROE, Revenue Growth, Debt / Equity and HHI</strong>, and shows sector exposure plus each allocation change. The proposed allocation must total exactly 100%. The scenario is not saved and does not execute trades.`],
    ["Portfolio Action View", `The Action View is a concise descriptive summary of portfolio characteristics that may warrant review. It highlights position concentration, sector concentration, leverage exposure, growth exposure and valuation, alongside allocation-weighted ROE, ROCE, Revenue Growth, Profit Growth, P/E, Debt / Equity and HHI. It deliberately does <strong>not</strong> generate buy/sell recommendations or predict future returns.`],
    ["Data Notes & Coverage", `Data Notes explain that portfolio metrics use the same Stock Analysis fundamentals and calculations, that signals use the same fundamental-signal definitions, and that coverage represents the percentage of portfolio allocation with an available metric. Historical portfolio calculations depend on the underlying stock price and fundamental history. Missing inputs remain missing rather than being filled with invented values.`],
    ["Calculation Consistency", `Portfolio metrics use the same fundamental definitions and historical price data conventions as Stock Analysis wherever the corresponding metric is available. This keeps the meaning of a metric consistent between an individual stock and the portfolio containing it.`],
    ["Interpretation & Limitations", `Portfolio analysis is <strong>historical and descriptive</strong>. It describes the characteristics and historical price behaviour of the selected allocation; it does not forecast future returns, simulate individual trades, include dividends unless explicitly stated by a source metric, model taxes or transaction costs, or execute rebalancing. A portfolio metric with partial coverage should always be read together with its coverage percentage.`],
    ["Charts & Visualizations", `The portfolio analysis includes visualisations for historical performance, benchmark comparison, quality-versus-growth positioning and historical risk/drawdown. Charts help interpret the underlying portfolio calculations. Tooltips provide the values represented by the selected holding, period or benchmark.`],
];

function findSection(title) {
    return [...document.querySelectorAll(".help-section")].find((section) =>
        section.querySelector("h3")?.textContent?.trim() === title
    ) || null;
}

function removeLegacySections() {
    [...document.querySelectorAll(".help-section")].forEach((section) => {
        const heading = section.querySelector("h3")?.textContent?.trim() || "";
        if (heading === "Legacy Stock Portfolio Analysis" || heading === "Recent Stock Analysis Updates") section.remove();
    });

    [...document.querySelectorAll(".help-section")].forEach((section) => {
        if (section.querySelector("h3")?.textContent?.trim() !== "Future / Planned") return;
        [...section.querySelectorAll(".help-card")].forEach((card) => {
            if (card.querySelector("h4")?.textContent?.trim() === PORTFOLIO_SECTION_TITLE) card.remove();
        });
    });
}

function renderCards(section, cardList) {
    if (!section) return false;
    const grid = section.querySelector(".help-grid") || document.createElement("div");
    grid.className = "help-grid";
    grid.innerHTML = cardList.map(([heading, body]) => `
        <div class="help-card">
            <h4>${heading}</h4>
            <p>${body}</p>
        </div>
    `).join("");
    if (!grid.parentElement) section.appendChild(grid);
    return true;
}

function renderPortfolioHelp() {
    const section = findSection(PORTFOLIO_SECTION_TITLE);
    if (!section || section.dataset.stockPortfolioHelpUpdated === "true") return Boolean(section);
    renderCards(section, cards);
    section.dataset.stockPortfolioHelpUpdated = "true";
    return true;
}

function install() {
    removeLegacySections();
    const portfolioReady = renderPortfolioHelp();
    if (portfolioReady) return;

    const root = document.body;
    if (!root) return;
    const observer = new MutationObserver(() => {
        removeLegacySections();
        const p = renderPortfolioHelp();
        if (p) observer.disconnect();
    });
    observer.observe(root, { childList: true, subtree: true });
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", install, { once: true });
} else {
    install();
}

export { renderPortfolioHelp };