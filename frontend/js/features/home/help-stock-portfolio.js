/* Stock Portfolio Builder Help
 * Keeps Help & Methodology synchronized with the live Stock Portfolio Builder.
 * The Help search indexes visible DOM content dynamically, so these cards are searchable
 * without maintaining a second search index.
 */

const PORTFOLIO_SECTION_TITLE = "Stock Portfolio Builder";
const RECENT_STOCK_SECTION_TITLE = "Recent Stock Analysis Updates";

const cards = [
    ["Build Workflow", `Build the portfolio from the same stock universe used by Stock Analysis. Search by company/symbol, optionally filter by sector and market-cap class, add the required stocks, assign allocations, and make the total exactly <strong>100%</strong> before continuing to analysis. The selected portfolio is kept in browser storage so the analysis and what-if modules can reuse the same holdings.`],
    ["Stock Selection & Filters", `The selector reuses the Stock Analysis universe and filtering behaviour. Available controls include <strong>Company or symbol</strong> search, <strong>Sector</strong> multi-select, and <strong>Large Cap / Mid Cap / Small Cap / Micro Cap</strong> quick filters. The list is filtered before the visible result page is limited, so the sector selector operates on the loaded stock universe rather than only the currently visible cards.`],
    ["Allocation Rules", `Each selected holding receives an allocation percentage. The <strong>Continue to Portfolio Analysis</strong> action is enabled only when the portfolio total is exactly 100% within the builder's validation tolerance. Allocation is the core weight used throughout the portfolio calculations. This builder does not record transaction prices, quantities, tax lots or trade history.`],
    ["Portfolio Snapshot", `The analysis starts with the number of holdings, largest position, number of sectors and an allocation concentration measure. The largest-position percentage shows direct single-stock exposure. Concentration is calculated using the <strong>Herfindahl-Hirschman Index (HHI)</strong> over the current stock allocations, so a more concentrated allocation produces a higher HHI.`],
    ["Portfolio Quality", `Quality metrics are allocation-weighted from the existing Stock Analysis fundamentals. The current view includes <strong>ROE, ROCE, Revenue Growth, Profit Growth and Debt / Equity</strong>, together with coverage. A metric's coverage is the percentage of portfolio allocation for which that metric is actually available. Missing company data is not replaced with an arbitrary estimate.`],
    ["Portfolio Valuation", `The valuation view displays allocation-weighted <strong>P/E, P/B, EV / EBITDA and Dividend Yield</strong> with coverage. These are exposure indicators, not a mathematically aggregated portfolio multiple. Financial-sector holdings may require a different valuation interpretation, so EV/EBITDA is not treated as equally informative across all business models.`],
    ["Sector Allocation", `Sector exposure is calculated by summing the portfolio allocation of holdings belonging to each sector. The result is displayed as proportional bars so the largest sector exposures can be identified immediately. Holdings without a usable sector classification are grouped as <strong>Other</strong>.`],
    ["Holding Analysis & Signals", `Holding Analysis shows each stock's allocation, P/E, ROE, Revenue Growth, Debt / Equity and a directional fundamental <strong>Signal</strong>. The signal reuses the shared Stock Analysis fundamental-signal engine when available. It can display <strong>Positive</strong>, <strong>Watch</strong>, <strong>Mixed</strong> or <strong>No signal</strong>. A signal is a compact description of the available fundamentals; it is not a portfolio return forecast or a buy/sell instruction.`],
    ["Historical Portfolio Performance", `Portfolio Performance converts each holding's existing Stock Analysis <strong>price CAGR</strong> into a growth factor, applies the current portfolio allocations, combines the growth factors geometrically, and converts the result back into CAGR. It reports <strong>1Y, 3Y, 5Y and 10Y</strong> historical price CAGR where data exists, plus coverage for each period. The visual includes a CAGR bar chart and a 3Y holding-level view.`],
    ["Performance Calculation", `For a period of <em>n</em> years, each available holding contributes its historical CAGR as a growth factor: <code>(1 + CAGR)ⁿ</code>. The factors are combined using allocation-normalised weights and converted back to annualised CAGR: <code>(Σ weight × (1 + CAGR)ⁿ)^(1/n) − 1</code>. When a holding lacks the required history, the displayed portfolio CAGR is calculated on the covered allocation and the coverage percentage is shown. This is not a transaction-level backtest and excludes dividends, taxes, costs and rebalancing.`],
    ["Portfolio vs Market", `The benchmark comparison reuses the same portfolio price-CAGR methodology and compares it with a selectable market benchmark: <strong>NIFTY 50, NIFTY 500 or BSE SENSEX</strong>. The view shows 1Y/3Y/5Y/10Y CAGR, coverage, a comparison chart and the difference between portfolio and benchmark CAGR. Benchmark history comes from the application's benchmark endpoint; it is not fabricated in the browser.`],
    ["Benchmark Methodology", `Benchmark comparison is a historical <strong>price-return</strong> comparison. Portfolio returns reuse the Stock Analysis price-CAGR inputs and the allocation-weighted geometric-growth calculation. Benchmark returns use annual market-price history. Dividends, taxes, transaction costs and portfolio rebalancing are excluded. A positive or negative historical difference describes the selected period; it is not a forecast.`],
    ["Portfolio Positioning Map", `The Quality × Growth map uses the existing Holding Analysis data rather than introducing another portfolio calculation engine. <strong>X-axis = Revenue Growth</strong>, <strong>Y-axis = ROE</strong>, and <strong>bubble size = current allocation</strong>. The horizontal and vertical reference lines are the portfolio's own median Revenue Growth and median ROE. This makes the map relative to the current holdings and is a descriptive visual, not an investment score.`],
    ["Portfolio Risk & Drawdown", `The risk view reconstructs a historical portfolio path from annual closing prices using the current allocation weights. It reports <strong>Maximum Drawdown, Annual Volatility, Current Drawdown and HHI concentration</strong>, plus exposure bars for the largest holding, holdings with Debt / Equity above 1x, and holdings with negative revenue growth. Because the source is annual closing prices, intra-year drawdowns can be understated.`],
    ["Risk Calculation", `Maximum Drawdown is the largest decline from a previous historical portfolio peak. Annual volatility is calculated from successive annual portfolio-price returns using sample standard deviation. Current Drawdown measures the latest indexed portfolio value relative to its historical peak. The historical path is an exposure view rather than a transaction-level backtest and excludes dividends, taxes, costs and rebalancing.`],
    ["What-If / Rebalancing", `The What-If / Rebalancing panel lets you change allocations across the <strong>same holdings</strong> and immediately compare the proposed portfolio with the current one. It recomputes allocation-weighted <strong>P/E, ROE, Revenue Growth, Debt / Equity and HHI</strong>, and shows sector exposure plus each allocation change. The proposed allocation must total exactly 100%. The scenario is not saved and does not execute trades.`],
    ["Portfolio Action View", `The Action View is a concise descriptive summary of portfolio characteristics that may warrant review. It highlights position concentration, sector concentration, leverage exposure, growth exposure and valuation, alongside allocation-weighted ROE, ROCE, Revenue Growth, Profit Growth, P/E, Debt / Equity and HHI. It deliberately does <strong>not</strong> generate buy/sell recommendations or predict future returns.`],
    ["Data Notes & Coverage", `Data Notes explain that portfolio metrics reuse the same Stock Analysis fundamentals and calculations, that signals reuse the shared fundamental-signal engine, and that coverage represents the percentage of portfolio allocation with an available metric. Historical portfolio calculations depend on the underlying stock price and fundamental history. Missing inputs remain missing rather than being filled with invented values.`],
    ["Shared Stock Analysis Engine", `The Stock Portfolio Builder intentionally reuses existing Stock Analysis calculations and endpoints wherever possible. Fundamentals come from the stock analysis data model, holding-level signals use the shared fundamental-signal engine, historical price CAGR uses the existing stock chart data, and benchmark/risk features reuse the same price-history inputs. This keeps definitions consistent between an individual stock and the portfolio containing it.`],
    ["Interpretation & Limitations", `Portfolio analysis is <strong>historical and descriptive</strong>. It describes the characteristics and historical price behaviour of the selected allocation; it does not forecast future returns, simulate individual trades, include dividends unless explicitly stated by a source metric, model taxes or transaction costs, or execute rebalancing. A portfolio metric with partial coverage should always be read together with its coverage percentage.`],
    ["Collapsible Analysis Cards", `Portfolio analysis is organised into distinct collapsible sections so the page remains readable on mobile and desktop. Each card exposes key highlights while collapsed and the detailed calculation or visualisation when expanded. The cards use distinct visual accents and bold icons while following the application's existing portfolio-builder interaction pattern.`],
    ["Charts & Visualizations", `The portfolio analysis uses visualisations for historical performance, benchmark comparison, quality-versus-growth positioning and historical risk/drawdown. Charts are presentation layers over the existing calculations; they do not introduce separate investment logic. Tooltips expose the underlying values for the selected holding, period or benchmark.`],
    ["Analysis Loading State", `Running <strong>Continue to Portfolio Analysis</strong> now uses a blocking busy state while the analysis is being prepared. The overlay prevents accidental repeated submissions and makes it clear that the application is working. The underlying portfolio data and calculations are unchanged.`],
    ["Chart Subcards", `Portfolio analysis visualisations can be presented as independently collapsible chart cards. Collapsing a chart hides only its presentation area; it does not delete the underlying calculation, Chart.js instance or data. Reopening a card resizes the chart so it renders correctly after being displayed again.`],
];

const recentStockCards = [
    ["Historical Analysis Sections", `The individual Stock Analysis report now groups the major historical analytics into readable collapsible sections. <strong>Historical Growth & Return Trends</strong>, <strong>Company Pedigree & Trend Comparison</strong>, and <strong>Earnings Quality, Capital Allocation & Dilution Comparison</strong> use a consistent card pattern. Collapsing a section hides the charts without removing their calculations or source data.`],
    ["Chart Empty States", `Historical stock charts now retain their intended chart/card structure when data is unavailable. Instead of silently removing a chart area, the application can present a meaningful empty state in place. This distinguishes <strong>no usable observations</strong> from a missing UI component and keeps the report layout stable.`],
    ["Historical Chart Tooltips", `Stock historical-chart hover behaviour has been refined so the tooltip follows the mouse reliably without recursive Chart.js tooltip handling. The chart data and calculations are unchanged; the improvement is limited to interaction and presentation.`],
    ["Comparison & Analysis Tables", `Individual Stock Analysis and Compare tables have received a consistent portfolio-style visual treatment. The refinements improve hierarchy, spacing, headers and readability for comparison-heavy sections without introducing a new scoring or calculation model.`],
    ["Stock Analysis Loading State", `Stock Analysis and ranking actions use a non-invasive busy overlay while analysis is running. The overlay communicates that the request is in progress without replacing the report content or changing the underlying analytical results.`],
    ["NSE Symbol Normalization", `Stock API routes now normalize bare NSE symbols consistently before downstream processing. This is an internal reliability improvement for symbol handling; it does not change the stock universe or the analytical definitions shown to users.`],
    ["Stock Portfolio Builder Presentation", `The Stock Portfolio Builder analysis now follows the portfolio-style collapsible-card presentation more consistently, including independent chart cards and improved visual hierarchy. These are presentation-layer improvements over the existing portfolio calculations.`],
];

function findSection(title) {
    return [...document.querySelectorAll(".help-section")].find((section) =>
        section.querySelector("h3")?.textContent?.trim() === title
    ) || null;
}

function removeLegacySections() {
    [...document.querySelectorAll(".help-section")].forEach((section) => {
        const heading = section.querySelector("h3")?.textContent?.trim() || "";
        if (heading === "Legacy Stock Portfolio Analysis") section.remove();
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

function renderRecentStockHelp() {
    const stockSection = findSection("Stock Analysis");
    if (!stockSection || stockSection.dataset.recentStockHelpUpdated === "true") return Boolean(stockSection);

    const recentSection = document.createElement("section");
    recentSection.className = "help-section";
    recentSection.innerHTML = `<h3>${RECENT_STOCK_SECTION_TITLE}</h3><div class="help-grid"></div>`;
    renderCards(recentSection, recentStockCards);
    stockSection.parentNode?.insertBefore(recentSection, stockSection.nextSibling);
    recentSection.dataset.recentStockHelpUpdated = "true";
    return true;
}

function install() {
    removeLegacySections();
    const portfolioReady = renderPortfolioHelp();
    const stockReady = renderRecentStockHelp();
    if (portfolioReady && stockReady) return;

    const root = document.body;
    if (!root) return;
    const observer = new MutationObserver(() => {
        removeLegacySections();
        const p = renderPortfolioHelp();
        const s = renderRecentStockHelp();
        if (p && s) observer.disconnect();
    });
    observer.observe(root, { childList: true, subtree: true });
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", install, { once: true });
} else {
    install();
}

export { renderPortfolioHelp, renderRecentStockHelp };
