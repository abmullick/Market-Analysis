/*
 * User-facing step-by-step Help for every major analysis utility.
 * This module intentionally describes how to use the application, not its
 * internal implementation. It also removes older partial workflow cards so
 * there is one authoritative set of instructions.
 */

const HOW_TO_SECTIONS = [
    {
        title: "How to Use the Platform",
        cards: [
            ["Start Here", `
                <ol>
                    <li>Use the main menu to choose the asset class and utility you want: <strong>Stock Analysis</strong>, <strong>Stock Portfolio Builder</strong>, <strong>Mutual Fund Analysis</strong>, <strong>Mutual Fund Portfolio Builder</strong>, or <strong>Bond Analysis</strong>.</li>
                    <li>Start with the selection controls to narrow the universe. You can normally search by name/symbol and use the available filters before opening a detailed analysis.</li>
                    <li>Use <strong>Analyze</strong> or the equivalent action to open a detailed report for the selected security/fund.</li>
                    <li>Use <strong>Compare</strong> when the decision requires side-by-side evaluation rather than looking at one security in isolation.</li>
                    <li>For a portfolio decision, use the relevant <strong>Portfolio Builder</strong> after selecting the securities you want to combine.</li>
                    <li>Use the Help search box at the top of this page whenever you want instructions for a specific control, metric, chart, or workflow. Search terms such as <strong>how to filter stocks</strong>, <strong>how to compare funds</strong>, <strong>build portfolio</strong>, <strong>rolling returns</strong>, <strong>bond YTM</strong>, or <strong>DV01</strong> will take you to the relevant guidance.</li>
                </ol>`],
            ["How to Use Help & Methodology", `
                <ol>
                    <li>Type a question or topic into <strong>Search Help & Methodology</strong>.</li>
                    <li>Use the suggested questions when you want a quick starting point.</li>
                    <li>Select a search result to jump directly to the relevant explanation.</li>
                    <li>Use the detailed methodology sections after the workflow instructions when you need to understand a formula, data source, calculation rule, or limitation.</li>
                </ol>`],
        ],
    },
    {
        title: "How to Use Stock Analysis",
        cards: [
            ["1. Find the Stocks You Want to Study", `
                <ol>
                    <li>Open <strong>Stock Analysis</strong>.</li>
                    <li>Choose the required stock universe or market-cap group if the utility provides that choice.</li>
                    <li>Use <strong>Search</strong> to find a company by name or symbol.</li>
                    <li>Use <strong>Sector</strong> to restrict the result to one or more sectors. Multiple selected sectors are treated as alternatives, so a company matching any selected sector can remain in the results.</li>
                    <li>Use the market-cap controls when you want to focus on Large Cap, Mid Cap, Small Cap, or Micro Cap companies.</li>
                    <li>Use the detailed fundamental filters when you need numerical constraints rather than a broad category selection.</li>
                </ol>`],
            ["2. Filter by Fundamentals", `
                <ol>
                    <li>Open the detailed filter controls.</li>
                    <li>Enter minimum and/or maximum values for the metrics you care about, such as Market Cap, P/E, P/B, PEG, ROE, ROA, Debt/Equity, Current Ratio, EV/EBITDA, EV/Revenue, and Dividend Yield.</li>
                    <li>Leave a boundary empty when you do not want to constrain that side of the range.</li>
                    <li>Use <strong>Apply Filters</strong> to apply the complete set of conditions.</li>
                    <li>Use <strong>Clear Filters</strong> to remove the detailed range conditions and start again.</li>
                    <li>Review the result count after filtering. The filters operate on the loaded universe, not merely the rows currently visible on the first page.</li>
                </ol>
                <p><strong>Practical approach:</strong> start with only a few high-value constraints. Add more filters gradually so you can see which condition is eliminating companies.</p>`],
            ["3. Select a Stock", `
                <ol>
                    <li>Review the filtered result list.</li>
                    <li>Click <strong>Select</strong> for a company you want to work with.</li>
                    <li>The selected company becomes the active stock and is also staged for comparison.</li>
                    <li>Change the selection whenever you want to study another company.</li>
                </ol>`],
            ["4. Analyze an Individual Stock", `
                <ol>
                    <li>Select the company and click <strong>Analyze Stock</strong>.</li>
                    <li>Start with the company summary and data notes to confirm the company identity, sector, price and data availability.</li>
                    <li>Review valuation metrics such as P/E, P/B, PEG, EV/EBITDA, EV/Revenue and Dividend Yield.</li>
                    <li>Review profitability and financial-health measures such as ROE, ROA, margins, Debt/Equity and liquidity.</li>
                    <li>Review growth and CAGR measures to understand the historical direction of revenue, profit, EPS and cash flow.</li>
                    <li>Use the historical charts to see how price and valuation metrics behaved over time rather than relying only on today's ratio.</li>
                    <li>Review the additional analytical sections such as momentum/trend, valuation context, quality/growth positioning, capital efficiency and shareholding where available.</li>
                    <li>Read the <strong>Data Notes</strong> at the bottom for source, data-as-of information and any warnings or unavailable fields.</li>
                </ol>`],
            ["5. Compare Stocks", `
                <ol>
                    <li>Select each company you want to compare.</li>
                    <li>Confirm that the required companies appear in the comparison selection.</li>
                    <li>Open <strong>Compare</strong>.</li>
                    <li>Use the side-by-side table to compare valuation, profitability, financial health and growth.</li>
                    <li>Use the comparison charts and derived insights to identify meaningful differences rather than judging a company from one metric alone.</li>
                    <li>Return to the selector when you want to add or remove a company and run the comparison again.</li>
                </ol>`],
            ["6. Read Stock Charts Correctly", `
                <ol>
                    <li>Open the relevant historical-analysis section.</li>
                    <li>Hover over a chart point to inspect the value and date where tooltips are available.</li>
                    <li>Use P/E and P/B history to judge whether today's valuation is high or low relative to the company's own historical range.</li>
                    <li>Use price-performance charts to understand the historical path of the share price.</li>
                    <li>Do not treat a historical trend as a forecast. Historical charts provide context for a decision; they do not guarantee future returns.</li>
                    <li>If a chart says <strong>Not available</strong>, treat that as insufficient source history rather than assuming zero or inventing a value.</li>
                </ol>`],
            ["7. Interpret Missing or N/M Values", `
                <ol>
                    <li>Check whether the value is shown as <strong>N/M</strong>, <strong>Not available</strong>, or another explicit unavailable state.</li>
                    <li>N/M normally means the metric is not meaningful for that company or the underlying inputs make the ratio unsuitable.</li>
                    <li>Missing historical data means the application does not have enough valid observations for that calculation.</li>
                    <li>Do not substitute zero for an unavailable metric. Use other relevant metrics and read the Data Notes.</li>
                </ol>`],
        ],
    },
    {
        title: "How to Use Stock Portfolio Builder",
        cards: [
            ["1. Build the Portfolio", `
                <ol>
                    <li>Open <strong>Stock Portfolio Builder</strong>.</li>
                    <li>Search for the stocks you want to include.</li>
                    <li>Add the stocks to the portfolio.</li>
                    <li>Review the selected holdings and remove any stock you no longer want.</li>
                    <li>Enter the intended allocation for each holding.</li>
                    <li>Make sure the allocation totals exactly <strong>100%</strong> before running portfolio analysis.</li>
                </ol>`],
            ["2. Check Portfolio Structure", `
                <ol>
                    <li>Review the number of holdings and the allocation of each holding.</li>
                    <li>Look for excessive concentration in one company or a small group of companies.</li>
                    <li>Review sector exposure and valuation/quality characteristics at the portfolio level.</li>
                    <li>Remember that a portfolio can contain many stocks and still be highly concentrated if a few holdings dominate the weights.</li>
                </ol>`],
            ["3. Run Portfolio Analysis", `
                <ol>
                    <li>After the allocations total 100%, run <strong>Portfolio Analysis</strong>.</li>
                    <li>Start with the portfolio-level return and risk summary.</li>
                    <li>Review CAGR, volatility, maximum drawdown, Sharpe and Sortino where available.</li>
                    <li>Review the Portfolio Health Score as a summary indicator, then inspect the underlying sections before making a decision.</li>
                    <li>Use Return Contribution to understand which holdings added to or detracted from the portfolio's historical result.</li>
                </ol>`],
            ["4. Study Drawdown & Recovery", `
                <ol>
                    <li>Open the Drawdown & Recovery section after running the analysis.</li>
                    <li>Review the maximum historical drawdown first.</li>
                    <li>Inspect individual drawdown episodes to see peak, trough and recovery dates.</li>
                    <li>Pay attention to ongoing drawdowns: an ongoing episode has no claimed recovery date.</li>
                    <li>Use recovery duration together with drawdown magnitude to understand the historical pain experienced by the portfolio.</li>
                </ol>`],
            ["5. Study Rolling Performance", `
                <ol>
                    <li>Open Rolling Performance.</li>
                    <li>Choose the available 1-year, 3-year or 5-year rolling window.</li>
                    <li>Review the average and median rolling CAGR, best and worst periods, and percentage of positive rolling periods.</li>
                    <li>Use the chart to see whether returns were consistently positive or depended on a small number of periods.</li>
                    <li>Do not confuse rolling CAGR with the portfolio's single full-period CAGR. Rolling CAGR describes many overlapping historical windows.</li>
                </ol>`],
            ["6. Use What-If / Rebalancing", `
                <ol>
                    <li>Open the portfolio what-if or rebalancing controls when available.</li>
                    <li>Change the allocation of one or more holdings.</li>
                    <li>Keep the revised allocation valid and check that the total remains 100%.</li>
                    <li>Run the analysis again to see how the changed weights would have affected the historical portfolio results.</li>
                    <li>Compare the revised portfolio with the original rather than judging the new allocation in isolation.</li>
                </ol>
                <p>These are historical scenario analyses. They do not predict that the revised allocation will produce the same result in the future.</p>`],
            ["7. Interpret Portfolio Charts", `
                <ol>
                    <li>Use the growth/performance chart to understand the historical path of the portfolio.</li>
                    <li>Use drawdown charts to understand loss from previous peaks.</li>
                    <li>Use rolling-return charts to judge consistency across different historical windows.</li>
                    <li>Use sector and holding-level views to identify concentration that may not be obvious from the headline return.</li>
                </ol>`],
        ],
    },
    {
        title: "How to Use Mutual Fund Analysis",
        cards: [
            ["1. Choose the Fund Universe and Category", `
                <ol>
                    <li>Open <strong>Mutual Fund Analysis</strong>.</li>
                    <li>Choose the relevant mutual-fund category or universe.</li>
                    <li>Use the available plan/option and other selection controls to narrow the candidates.</li>
                    <li>Remember that many ranking metrics are category-relative, so compare funds within an appropriate peer group.</li>
                </ol>`],
            ["2. Filter Funds", `
                <ol>
                    <li>Open the filter controls.</li>
                    <li>Set the criteria you care about, such as AUM, fund age and plan/option type where available.</li>
                    <li>Apply the filters.</li>
                    <li>Review the match count and active filter chips.</li>
                    <li>Remove individual filter chips or use <strong>Clear All</strong> when you want to restart.</li>
                </ol>`],
            ["3. Rank Funds", `
                <ol>
                    <li>Choose a built-in ranking preset such as <strong>Best Overall</strong>, <strong>Highest Returns</strong>, <strong>Lowest Risk</strong>, or <strong>Best Consistency</strong>.</li>
                    <li>Review the ranking table and the top highlighted funds.</li>
                    <li>When you need a different decision framework, use the custom criteria/weights instead of relying on the default preset.</li>
                    <li>Open the ranking explanation to see the active metric groups and their weights.</li>
                    <li>Use the rank as a structured comparison aid, not as a guarantee of future performance.</li>
                </ol>`],
            ["4. Understand Why a Fund Ranks Where It Does", `
                <ol>
                    <li>Use the <strong>Why?</strong> action for the fund.</li>
                    <li>Review the strongest contributing metrics and the main trade-offs.</li>
                    <li>Check the fund's percentile and ordinal position within its category.</li>
                    <li>Open Fund Details when you need the underlying return, risk and consistency measures.</li>
                </ol>`],
            ["5. Open Fund Details", `
                <ol>
                    <li>Select the fund and open <strong>Fund Details</strong>.</li>
                    <li>Review NAV history and the available 1Y/3Y/5Y/10Y returns.</li>
                    <li>Review Sharpe, Sortino, volatility, maximum drawdown and downside deviation.</li>
                    <li>Use rolling-return information to judge how consistent the fund has been across different historical periods.</li>
                    <li>Check the available-history note before comparing funds with very different track records.</li>
                </ol>`],
            ["6. Compare Funds", `
                <ol>
                    <li>Select the funds you want to compare.</li>
                    <li>Open <strong>Fund Comparison</strong>.</li>
                    <li>Compare performance, risk and consistency side-by-side.</li>
                    <li>Use risk-return, drawdown and rolling-return charts to see differences that a single ranking score may hide.</li>
                    <li>Prefer like-for-like comparisons within the same category and relevant plan/option.</li>
                </ol>`],
            ["7. Read the Ranking Correctly", `
                <ol>
                    <li>First check the active ranking preset or custom weights.</li>
                    <li>Check whether the metrics are higher-is-better or lower-is-better.</li>
                    <li>Use the percentile/rank to understand relative standing within the selected category.</li>
                    <li>Open the underlying fund metrics before treating a small score difference as economically significant.</li>
                </ol>`],
        ],
    },
    {
        title: "How to Use Mutual Fund Portfolio Builder",
        cards: [
            ["1. Select Funds", `
                <ol>
                    <li>Open <strong>Mutual Fund Portfolio Builder</strong>.</li>
                    <li>Search the available AMFI fund universe.</li>
                    <li>Add the funds you want to combine. The builder supports a defined multi-fund portfolio rather than a single-fund analysis.</li>
                    <li>Remove any unwanted fund before assigning final weights.</li>
                </ol>`],
            ["2. Allocate 100%", `
                <ol>
                    <li>Enter an allocation percentage for every selected fund.</li>
                    <li>Use values from 0 to 100 with the supported decimal precision.</li>
                    <li>Ensure the total allocation is exactly <strong>100%</strong>.</li>
                    <li>At least two contributing funds are required for the portfolio analysis; a zero-weight fund does not contribute to the calculations.</li>
                </ol>`],
            ["3. Run Portfolio Analysis", `
                <ol>
                    <li>Run the analysis only after the allocation is valid.</li>
                    <li>Review portfolio CAGR, volatility, drawdown, Sharpe and Sortino where available.</li>
                    <li>Review Portfolio Health Score and then inspect the component evidence behind it.</li>
                    <li>Review Return Contribution to see which funds contributed most or detracted most.</li>
                    <li>Use Drawdown & Recovery and Rolling Performance to understand the experience across historical periods.</li>
                </ol>`],
            ["4. Evaluate Historical Consistency", `
                <ol>
                    <li>Use the rolling 1Y, 3Y and 5Y views when sufficient common history exists.</li>
                    <li>Compare the percentage of positive rolling periods with the best and worst periods.</li>
                    <li>Use drawdown duration as well as drawdown depth when assessing historical risk.</li>
                    <li>Remember that all portfolio analytics are historical descriptions, not forward-looking guarantees.</li>
                </ol>`],
        ],
    },
    {
        title: "How to Use Bond Analysis",
        cards: [
            ["1. Choose the Bond Universe", `
                <ol>
                    <li>Open <strong>Bond Analysis</strong>.</li>
                    <li>Choose the relevant government or corporate bond universe.</li>
                    <li>Use the instrument type or source controls when available to narrow the universe.</li>
                    <li>For corporate bonds, pay particular attention to issuer and credit rating before comparing yields.</li>
                </ol>`],
            ["2. Search and Filter Bonds", `
                <ol>
                    <li>Search by issuer, ISIN, instrument or other supported identity field.</li>
                    <li>Use filters for maturity, coupon, yield, trade date, credit rating and other available fields.</li>
                    <li>Sort the results when you want to compare candidates by a particular attribute.</li>
                    <li>Check the data type and freshness before using a quoted price or yield as if it were a live executable market quote.</li>
                </ol>`],
            ["3. Select and Inspect a Bond", `
                <ol>
                    <li>Select the bond you want to study.</li>
                    <li>Confirm the issuer, ISIN, coupon, coupon frequency, maturity and face-value/contract information.</li>
                    <li>Review market price and yield information where available.</li>
                    <li>Review credit rating and rating information for corporate bonds.</li>
                </ol>`],
            ["4. Compare Yield Measures", `
                <ol>
                    <li>Start with <strong>Market YTM</strong> when the source provides a market-derived yield.</li>
                    <li>Use <strong>Calculated YTM</strong> when you want a yield calculated from the bond's price, cash flows and remaining maturity.</li>
                    <li>Do not assume the two values must be identical: they can differ because their inputs and source conventions differ.</li>
                    <li>Use Current Yield as a simpler coupon-to-price measure; do not treat it as a replacement for YTM.</li>
                </ol>`],
            ["5. Understand Accrued Interest", `
                <ol>
                    <li>Check the settlement date and coupon schedule.</li>
                    <li>Use accrued interest to understand the coupon interest accumulated since the last coupon date.</li>
                    <li>Distinguish <strong>clean price</strong> from <strong>dirty price</strong>: dirty price incorporates accrued interest where the calculation is applicable.</li>
                    <li>Use the settlement convention shown by the application when interpreting the result.</li>
                </ol>`],
            ["6. Use Duration, Convexity and DV01", `
                <ol>
                    <li>Use <strong>Modified Duration</strong> as a first-order measure of percentage price sensitivity to a change in yield.</li>
                    <li>Use <strong>DV01</strong> when you want the approximate currency price/PV change for a 1-basis-point yield move.</li>
                    <li>Use <strong>Convexity</strong> to understand the second-order curvature that duration alone does not capture.</li>
                    <li>For a rate-sensitive portfolio decision, compare bonds with similar credit quality while considering both yield and interest-rate sensitivity.</li>
                    <li>These are sensitivity measures, not forecasts of the next market move.</li>
                </ol>`],
            ["7. Evaluate Corporate Credit Risk", `
                <ol>
                    <li>Review the credit rating, rating agency, outlook and rating action where available.</li>
                    <li>Compare bonds with similar maturity and seniority before concluding that one yield is unusually attractive.</li>
                    <li>Investigate whether a higher yield is compensation for higher credit risk, lower liquidity or different bond structure.</li>
                    <li>Do not compare a corporate bond's yield directly with a government bond without considering credit and liquidity differences.</li>
                </ol>`],
            ["8. Check Bond Data Quality", `
                <ol>
                    <li>Look at the source and data type shown by the application.</li>
                    <li>Distinguish traded observations from indicative, reference, auction or other non-traded data where the application identifies them.</li>
                    <li>Check the data-as-of or freshness information.</li>
                    <li>If a required input is unavailable, use the displayed unavailable state rather than assuming zero or estimating an unsupported value.</li>
                </ol>`],
        ],
    },
];

function addHowToStyles() {
    if (document.getElementById("help-how-to-styles")) return;
    const style = document.createElement("style");
    style.id = "help-how-to-styles";
    style.textContent = `
        .help-how-to-section .help-card ol { margin: .55rem 0 .2rem 1.35rem; padding: 0; }
        .help-how-to-section .help-card li { margin: .42rem 0; line-height: 1.5; }
        .help-how-to-section .help-card p { line-height: 1.55; }
        .help-how-to-section .help-card p + p { margin-top: .65rem; }
        .help-how-to-section .help-card { min-height: 0; }
        .help-how-to-intro { margin: 0 0 .8rem; line-height: 1.55; }
    `;
    document.head.appendChild(style);
}

function removePartialWorkflowCards() {
    const partialHeadings = new Set([
        "Build Workflow",
    ]);
    document.querySelectorAll(".help-section .help-card h4").forEach((heading) => {
        if (!partialHeadings.has(heading.textContent.trim())) return;
        const card = heading.closest(".help-card");
        if (card) card.remove();
    });
}

function renderHowToSections() {
    if (!document.querySelector(".help-container") || document.getElementById("help-how-to-root")) return;

    removePartialWorkflowCards();
    addHowToStyles();

    const root = document.createElement("div");
    root.id = "help-how-to-root";

    HOW_TO_SECTIONS.forEach((sectionData, sectionIndex) => {
        const section = document.createElement("section");
        section.className = "help-section help-how-to-section";
        section.dataset.helpHowTo = "true";
        section.innerHTML = `<h3>${sectionData.title}</h3>`;

        if (sectionIndex === 0) {
            const intro = document.createElement("p");
            intro.className = "help-how-to-intro";
            intro.innerHTML = "Use these workflows when you want practical, step-by-step instructions. They cover the complete user journey for each major utility; the sections below them explain the underlying metrics and methodology.";
            section.appendChild(intro);
        }

        const grid = document.createElement("div");
        grid.className = "help-grid";
        sectionData.cards.forEach(([heading, body]) => {
            const card = document.createElement("div");
            card.className = "help-card";
            card.innerHTML = `<h4>${heading}</h4><div>${body}</div>`;
            grid.appendChild(card);
        });
        section.appendChild(grid);
        root.appendChild(section);
    });

    const firstExisting = document.querySelector(".help-container > .help-section:nth-of-type(2)");
    const container = document.querySelector(".help-container");
    if (firstExisting) container.insertBefore(root, firstExisting);
    else container.appendChild(root);
}

function init() {
    renderHowToSections();
}

if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init, { once: true });
else init();
