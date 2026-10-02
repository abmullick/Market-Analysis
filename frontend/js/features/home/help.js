import { searchHelp, resolveTarget, HELP_SEARCH_INDEX } from "./help-search-index.js";

const SEARCH_DEBOUNCE_MS = 150;
const STRONG_MATCH_SCORE = 45;
const HIGHLIGHT_DURATION_MS = 2600;

const SUGGESTED_QUESTIONS = [
    "How do stock filters work?",
    "What does Market Cap Min mean?",
    "What is Debt / Equity?",
    "What is PEG?",
    "What is Revenue CAGR 3Y?",
    "How are stock charts calculated?",
    "How does stock comparison work?",
    "How does Bond Analysis work?",
    "What is Market YTM?",
    "What is calculated YTM?",
    "What is accrued interest?",
    "What is duration?",
    "What is DV01?",
    "What do bond credit ratings mean?",
    "How fresh is the bond data?",
    "How is CAGR calculated?",
    "What is Sharpe ratio?",
    "What is Portfolio Health Score?",
];

function buildSearchUI() {
    const container = document.querySelector(".help-container");
    if (!container || document.getElementById("help-search")) return null;

    const wrapper = document.createElement("div");
    wrapper.className = "help-search";
    wrapper.id = "help-search";

    const chips = SUGGESTED_QUESTIONS.map(
        (q) => `<button type="button" class="help-search-chip" data-query="${q}">${q}</button>`
    ).join("");

    wrapper.innerHTML = `
        <div class="help-search-box">
            <svg class="help-search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <circle cx="11" cy="11" r="8"></circle>
                <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
            </svg>
            <input id="help-search-input" type="search" autocomplete="off" enterkeyhint="search"
                   placeholder="Search Help & Methodology — e.g. stock filters, P/E, PEG, ROE, YTM, duration…"
                   aria-label="Search Help and Methodology">
            <button id="help-search-clear" class="help-search-clear" type="button" aria-label="Clear search" hidden>&times;</button>
        </div>
        <div class="help-search-suggestions" aria-label="Suggested questions">
            <span class="help-search-suggestions-label">Try:</span>
            ${chips}
        </div>
        <div id="help-search-results" class="help-search-results" role="listbox" hidden></div>
    `;
    container.insertBefore(wrapper, container.firstChild);
    return wrapper;
}

function renderResults(resultsEl, results) {
    resultsEl.innerHTML = "";
    resultsEl.hidden = false;

    if (!results.length) {
        resultsEl.innerHTML = `
            <div class="help-search-no-results">
                <p>No matching Help topics found.</p>
                <p class="help-search-no-results-hint">Try stock filters, ratios, charts, bonds, YTM, duration, DV01, cash flows, ratings, or methodology.</p>
            </div>`;
        return;
    }

    for (const result of results) {
        const item = document.createElement("button");
        item.type = "button";
        item.className = "help-search-result";
        item.setAttribute("role", "option");
        item.dataset.entryId = result.entry.id;
        item.innerHTML = `
            <span class="help-search-result-title">${result.entry.heading}</span>
            <span class="help-search-result-snippet">${result.snippet}</span>
        `;
        item.addEventListener("click", () => navigateToEntry(result.entry));
        resultsEl.appendChild(item);
    }
}

function hideResults(resultsEl) {
    resultsEl.hidden = true;
    resultsEl.innerHTML = "";
}

function openAccordionItem(item) {
    if (!item.classList.contains("metric-item") || item.classList.contains("open")) return;
    const trigger = item.querySelector(".metric-trigger");
    if (trigger) trigger.click();
}

function navigateToEntry(entry) {
    const target = resolveTarget(entry);
    if (!target) return;

    openAccordionItem(target);
    target.scrollIntoView({ behavior: "smooth", block: "start" });
    target.classList.remove("search-highlight");
    void target.offsetWidth;
    target.classList.add("search-highlight");
    window.setTimeout(() => target.classList.remove("search-highlight"), HIGHLIGHT_DURATION_MS);
}

function initSearch() {
    const wrapper = buildSearchUI();
    if (!wrapper) return;

    const input = wrapper.querySelector("#help-search-input");
    const clearBtn = wrapper.querySelector("#help-search-clear");
    const resultsEl = wrapper.querySelector("#help-search-results");
    let debounceTimer = null;

    function handleSearch(query, { navigate = false } = {}) {
        const trimmed = (query || "").trim();
        if (!trimmed) {
            clearBtn.hidden = true;
            hideResults(resultsEl);
            return;
        }
        const results = searchHelp(trimmed);
        renderResults(resultsEl, results);
        if (navigate && results.length && results[0].score >= STRONG_MATCH_SCORE) {
            navigateToEntry(results[0].entry);
        }
    }

    input.addEventListener("input", () => {
        clearBtn.hidden = !input.value;
        window.clearTimeout(debounceTimer);
        debounceTimer = window.setTimeout(() => handleSearch(input.value), SEARCH_DEBOUNCE_MS);
    });

    input.addEventListener("keydown", (event) => {
        if (event.key !== "Enter") return;
        event.preventDefault();
        window.clearTimeout(debounceTimer);
        handleSearch(input.value, { navigate: true });
    });

    clearBtn.addEventListener("click", () => {
        input.value = "";
        clearBtn.hidden = true;
        hideResults(resultsEl);
        input.focus();
    });

    wrapper.querySelectorAll(".help-search-chip").forEach((chip) => {
        chip.addEventListener("click", () => {
            const query = chip.dataset.query || chip.textContent;
            input.value = query;
            clearBtn.hidden = false;
            handleSearch(query, { navigate: true });
        });
    });
}

function upsertHelpSearchEntries(sectionHeading, entries) {
    for (const [id, heading, keywords, aliases] of entries) {
        const existing = HELP_SEARCH_INDEX.find((entry) => entry.id === id);
        if (existing) continue;
        HELP_SEARCH_INDEX.push({ id, type: "card", heading, sectionHeading, keywords, aliases });
    }
}

function removeLegacyStockPlaceholder() {
    for (let i = HELP_SEARCH_INDEX.length - 1; i >= 0; i -= 1) {
        const entry = HELP_SEARCH_INDEX[i];
        if (
            entry.id === "stock-analysis-coming-soon" ||
            (entry.heading === "Coming Soon" && entry.sectionHeading === "Stock Analysis")
        ) {
            HELP_SEARCH_INDEX.splice(i, 1);
        }
    }
}

function ensureSection(title, beforeTitle = null) {
    const sections = [...document.querySelectorAll(".help-section")];
    let section = sections.find((s) => s.querySelector("h3")?.textContent?.trim() === title);
    if (section) return section;

    section = document.createElement("section");
    section.className = "help-section";
    section.innerHTML = `<h3>${title}</h3><div class="help-grid"></div>`;

    if (beforeTitle) {
        const before = sections.find((s) => s.querySelector("h3")?.textContent?.trim() === beforeTitle);
        if (before) {
            before.parentNode.insertBefore(section, before);
            return section;
        }
    }

    document.querySelector(".help-container")?.appendChild(section);
    return section;
}

function renderCards(section, cards) {
    const grid = section.querySelector(".help-grid") || (() => {
        const g = document.createElement("div");
        g.className = "help-grid";
        section.appendChild(g);
        return g;
    })();

    grid.innerHTML = cards.map(([heading, body]) => `
        <div class="help-card">
            <h4>${heading}</h4>
            <p>${body}</p>
        </div>
    `).join("");
}

function registerStockHelpSearchEntries() {
    removeLegacyStockPlaceholder();
    upsertHelpSearchEntries("Stock Analysis", [
        ["stock-universe", "Stock Universe & Selection", ["stock universe", "nifty total market", "nifty 500", "microcap 250", "large cap", "mid cap", "small cap", "micro cap"], ["which stocks are available", "stock universe"]],
        ["stock-selector", "Sector, Search & Market-Cap Controls", ["sector", "multi select", "search", "symbol", "market cap", "large cap", "mid cap", "small cap", "micro cap", "presets"], ["stock selector", "sector filter", "stock screening controls"]],
        ["stock-fundamental-filters", "Fundamental Range Filters", ["market cap min", "market cap max", "p/e min", "p/e max", "p/b", "peg", "roe", "roa", "debt equity", "current ratio", "ev ebitda", "ev revenue", "dividend yield", "apply filters", "clear filters"], ["all stock filters", "stock range filters"]],
        ["stock-selection-workflow", "Select, Analyze & Compare", ["select stock", "analyze stock", "compare stocks", "comparison", "auto add", "selected stock"], ["how do I compare stocks", "select and analyze"]],
        ["stock-pagination", "Full-Universe Filtering & Pagination", ["pagination", "page", "full universe", "first page", "result count", "sector filtering"], ["does sector filter use first page", "stock pagination"]],
        ["stock-summary", "Company Summary & Data Notes", ["price", "market cap", "enterprise value", "revenue", "net profit", "ebitda", "free cash flow", "data as of", "source", "warnings"], ["stock summary", "stock data notes"]],
        ["stock-valuation", "Valuation Metrics", ["pe", "p/e", "forward pe", "pb", "price book", "price sales", "peg", "ev ebitda", "ev revenue", "dividend yield", "payout ratio", "valuation"], ["stock valuation ratios", "what is forward pe"]],
        ["stock-profitability", "Profitability Metrics", ["roe", "roa", "gross margin", "operating margin", "net margin", "profitability"], ["stock profitability", "what is roe", "what is roa"]],
        ["stock-financial-health", "Financial Health Metrics", ["debt equity", "debt / equity", "current ratio", "quick ratio", "beta", "financial health", "leverage"], ["what is debt equity", "what is beta", "stock financial health"]],
        ["stock-growth", "Growth & CAGR Metrics", ["growth", "cagr", "revenue growth", "profit growth", "eps growth", "revenue cagr", "profit cagr", "eps cagr", "fcf cagr", "operating margin change"], ["stock growth metrics", "how is stock cagr calculated"]],
        ["stock-statements", "Financial Statements & Display Units", ["income statement", "balance sheet", "cash flow", "b/t", "inr", "rupee", "crore", "financial statements"], ["stock financial statements", "stock financial units"]],
        ["stock-charts", "Charts & Historical Trends", ["chart", "charts", "trend", "pe history", "p/e history", "pb history", "price performance", "historical valuation"], ["stock charts", "valuation trend charts"]],
        ["stock-comparison", "Comparison View", ["comparison", "debt equity", "side by side", "metrics", "table", "compare"], ["compare stock fundamentals", "stock comparison"]],
        ["stock-data-sources", "Data Sources & Freshness", ["screener", "yahoo", "forward pe", "beta", "fundamental data", "market data", "source", "freshness"], ["where does stock data come from", "yahoo market data"]],
        ["stock-missing-values", "N/M, Missing & Unavailable Values", ["n/m", "not meaningful", "missing data", "data notes", "unavailable", "financial company"], ["why is a stock metric missing", "not meaningful"]],
        ["stock-methodology", "Stock Analysis Methodology", ["methodology", "historical", "descriptive", "forecast", "calculation"], ["stock analysis methodology"]],
        ["stock-filter-stability", "Filter Performance & Stability", ["mutation observer", "performance", "dom", "backend requests", "refresh", "loading", "stability", "coalescing"], ["why did the stock page keep loading", "filter performance"]],
    ]);
}

function registerBondHelpSearchEntries() {
    upsertHelpSearchEntries("Bond Analysis", [
        ["bond-universes", "Government & Corporate Bond Universes", ["government", "corporate", "g-sec", "t-bill", "sdl", "universe"], ["what bonds are covered", "government bonds", "corporate bonds"]],
        ["bond-selection", "Bond Selection & Identity", ["select bond", "isin", "record id", "identity", "selection"], ["how do I select a bond", "bond identifier"]],
        ["bond-search-filters", "Search, Sort & Filters", ["search", "filter", "sort", "issuer", "instrument type", "source", "coupon", "maturity", "yield", "trade date", "credit rating"], ["how do bond filters work", "bond screening"]],
        ["bond-market-data", "Market Price, Yield & Trading Data", ["market price", "clean price", "dirty price", "bid", "offer", "ltp", "trade count", "traded value", "quantity", "vwap", "market ytm", "freshness"], ["bond market data", "bond price and yield"]],
        ["bond-contract-terms", "Contract Terms & Cash Flows", ["coupon", "frequency", "face value", "issue size", "outstanding", "redemption", "call", "put", "secured", "seniority", "perpetual"], ["bond cash flows", "bond contract terms"]],
        ["bond-current-yield", "Current Yield", ["current yield", "coupon", "clean price", "yield"], ["what is current yield"]],
        ["bond-ytm", "Calculated YTM vs Market YTM", ["ytm", "yield to maturity", "calculated ytm", "market ytm", "source yield"], ["what is calculated ytm", "calculated versus market ytm"]],
        ["bond-accrued-interest", "Accrued Interest & Settlement", ["accrued interest", "settlement date", "accrued days", "clean", "dirty"], ["what is accrued interest"]],
        ["bond-duration", "Duration, Convexity & DV01", ["macaulay", "modified duration", "duration", "convexity", "dv01", "basis point", "bps"], ["what is duration", "what is dv01", "bond sensitivity"]],
        ["bond-ratings", "Corporate Credit Ratings", ["credit rating", "agency", "outlook", "rating action", "unknown", "unrated", "aaa", "aa", "a"], ["bond ratings", "corporate credit ratings"]],
        ["bond-sources", "Bond Sources, Data Type & Freshness", ["ccil", "nse", "rbi", "cdsl", "bond central", "traded", "indicative", "mtm", "reference", "auction", "historical", "freshness"], ["bond data sources", "how fresh is bond data"]],
        ["bond-missing", "Missing Bond Data & Calculation Rules", ["missing", "unavailable", "not enough data", "fabricated", "analytics", "calculation"], ["why is bond metric unavailable"]],
    ]);
}

function updateStockAnalysisHelp() {
    const section = ensureSection("Stock Analysis", "Stock Portfolio Builder");
    renderCards(section, [
        ["Stock Universe & Selection", "The selector uses the <strong>Nifty Total Market</strong> source universe — Nifty 500 plus Nifty Microcap 250. The loaded universe is broader than a large-cap-only universe and is classified into <strong>Large Cap, Mid Cap, Small Cap and Micro Cap</strong>. Filtering is performed against the loaded universe before the visible result pages are paginated, so sector/cap selection is not limited to page 1."],
        ["Sector, Search & Market-Cap Controls", "<strong>Sector</strong> is a multi-select control and multiple selected sectors are combined as an OR selection. <strong>Search</strong> refines by company name or symbol. The market-cap presets are <strong>Large Cap, Mid Cap, Small Cap and Micro Cap</strong>. These quick controls remain outside the collapsible Filter Results body and refine the loaded universe rather than intentionally reloading it for every click."],
        ["Fundamental Range Filters — Complete Parameter List", "The detailed filter panel contains <strong>Market Cap Min/Max (₹ Cr)</strong>, <strong>P/E Min/Max</strong>, <strong>P/B Min/Max</strong>, <strong>PEG Min/Max</strong>, <strong>ROE Min/Max (%)</strong>, <strong>ROA Min/Max (%)</strong>, <strong>D/E Min/Max</strong>, <strong>Current Ratio Min/Max</strong>, <strong>EV/EBITDA Min/Max</strong>, <strong>EV/Revenue Min/Max</strong>, and <strong>Dividend Yield Min/Max (%)</strong>. Empty boundaries mean that side of the range is unconstrained. <strong>Apply Filters</strong> applies these constraints; <strong>Clear Filters</strong> removes the detailed range constraints."],
        ["Select → Selected Stock → Compare → Analyze", "Clicking <strong>Select</strong> makes the result the active <strong>Selected Stock</strong> and automatically adds it to <strong>Compare Stocks</strong>. The user can remove it from comparison later. Only <strong>Analyze Stock</strong> opens the individual analysis report. This keeps selection, comparison staging and navigation separate."],
        ["Company Summary & Data Notes", "The report can display exchange, symbol, company name, sector, industry, country, current price and currency plus <strong>Market Cap, Enterprise Value, Latest Revenue, Latest Net Profit, Latest EBITDA and Latest Free Cash Flow</strong>. The bottom <strong>Data Notes</strong> area shows source, data-as-of information and backend warnings instead of interrupting the financial statements."],

        ["P/E (Price-to-Earnings Ratio)", "<strong>What it means:</strong> P/E tells you how many rupees investors are paying for each rupee of the company's earnings. <strong>Formula:</strong> P/E = Share Price ÷ Earnings Per Share (EPS). Equivalently, P/E = Market Capitalisation ÷ Net Profit. <strong>Example:</strong> if a share is ₹500 and EPS is ₹25, P/E = 500 ÷ 25 = <strong>20×</strong>. A higher P/E means the market price is higher relative to current earnings; it does not by itself tell you whether the stock is expensive or cheap. <strong>Important:</strong> negative earnings make P/E not meaningful, and trailing P/E uses historical earnings."],
        ["Forward P/E", "<strong>What it means:</strong> Forward P/E compares today's share price with expected future EPS rather than already-reported trailing EPS. <strong>Formula:</strong> Forward P/E = Current Share Price ÷ Expected Forward EPS. <strong>Example:</strong> ₹500 price and expected EPS of ₹30 gives 500 ÷ 30 = <strong>16.7×</strong>. Forward EPS is an estimate, so Forward P/E can change when earnings expectations change even if the share price does not. In this application, Forward P/E is supplemental market data where supplied, primarily from Yahoo Finance; it is not the application's independently forecast EPS."],
        ["P/B (Price-to-Book Ratio)", "<strong>What it means:</strong> P/B compares the market value of a share with the accounting book value attributable to each share. <strong>Formula:</strong> P/B = Share Price ÷ Book Value Per Share (BVPS), where BVPS = Shareholders' Equity ÷ Shares Outstanding. Equivalently, P/B = Market Capitalisation ÷ Shareholders' Equity. <strong>Example:</strong> ₹300 share price and ₹150 BVPS gives <strong>2.0×</strong>. P/B is especially tied to the balance sheet and can be less informative when book values do not capture important intangible or economic assets."],
        ["Price / Sales (P/S)", "<strong>What it means:</strong> P/S compares the company's market value with the revenue it generates. <strong>Formula:</strong> P/S = Market Capitalisation ÷ Revenue, or Share Price ÷ Revenue Per Share. <strong>Example:</strong> ₹100 crore market cap and ₹50 crore revenue gives <strong>2.0×</strong>. Unlike P/E, P/S can still be calculated when a company has little or negative profit, but it ignores margins, costs, interest and taxes."],
        ["PEG (Price/Earnings-to-Growth Ratio)", "<strong>What it means:</strong> PEG relates a company's P/E to its earnings-growth rate. <strong>Formula used by this application:</strong> PEG = P/E ÷ 3Y EPS CAGR expressed as a percentage. <strong>Example:</strong> P/E = 24× and 3Y EPS CAGR = 12%, so PEG = 24 ÷ 12 = <strong>2.0×</strong>. The percentage must be used as 12, not 0.12, in this formula. PEG therefore depends heavily on the selected historical growth period and can become misleading when growth is very low, negative or unusually volatile. The application uses the implemented P/E ÷ 3Y EPS CAGR relationship."],
        ["EV / EBITDA", "<strong>What it means:</strong> EV/EBITDA compares the enterprise value of a company with EBITDA, a measure of operating earnings before interest, tax, depreciation and amortisation. <strong>Formula:</strong> EV/EBITDA = Enterprise Value ÷ EBITDA. Enterprise Value is broadly Equity Value + Debt + other debt-like claims − Cash and cash equivalents, subject to the provider's definitions. <strong>Example:</strong> EV ₹1,000 crore and EBITDA ₹100 crore gives <strong>10×</strong>. It is commonly used to compare operating businesses with different capital structures."],
        ["EV / Revenue", "<strong>What it means:</strong> EV/Revenue compares enterprise value with company revenue. <strong>Formula:</strong> EV/Revenue = Enterprise Value ÷ Revenue. <strong>Example:</strong> EV ₹1,000 crore and revenue ₹250 crore gives <strong>4.0×</strong>. It is useful when earnings or EBITDA are weak or negative, but it does not tell you how much of revenue becomes profit or cash flow."],
        ["Dividend Yield", "<strong>What it means:</strong> Dividend Yield measures the annual dividend received relative to the share price. <strong>Formula:</strong> Dividend Yield = Annual Dividend Per Share ÷ Current Share Price × 100. <strong>Example:</strong> ₹12 annual dividend on a ₹300 share gives 12 ÷ 300 × 100 = <strong>4%</strong>. The displayed yield is not a guarantee of future dividends; dividend amounts can change."],
        ["Payout Ratio", "<strong>What it means:</strong> Payout Ratio shows what portion of earnings is distributed as dividends. <strong>Formula:</strong> Payout Ratio = Dividends ÷ Net Income × 100, or Dividend Per Share ÷ EPS × 100 when both are measured consistently. <strong>Example:</strong> EPS ₹20 and dividend ₹8 gives <strong>40%</strong>. A payout ratio above 100% can occur when dividends exceed the period's reported earnings and should be interpreted carefully."],

        ["ROE (Return on Equity)", "<strong>What it means:</strong> ROE measures how efficiently a company generates profit from shareholders' equity. <strong>Formula:</strong> ROE = Net Profit ÷ Average Shareholders' Equity × 100. Using average equity is preferable when beginning and ending equity are available. <strong>Example:</strong> ₹100 crore profit and average equity of ₹500 crore gives <strong>20% ROE</strong>. High ROE can be caused by strong profitability, efficient capital use or high leverage, so it should be read together with Debt/Equity and margins. The application's historical ROE trend is derived from annual net profit and average shareholder equity."],
        ["ROA (Return on Assets)", "<strong>What it means:</strong> ROA measures profit generated from the assets employed by the business. <strong>Formula:</strong> ROA = Net Profit ÷ Average Total Assets × 100. <strong>Example:</strong> ₹100 crore profit and average assets of ₹1,000 crore gives <strong>10% ROA</strong>. ROA is useful for comparing how effectively businesses use their asset base, although asset intensity differs substantially across industries."],
        ["Gross Margin", "<strong>What it means:</strong> Gross Margin shows how much revenue remains after the direct cost of goods or services. <strong>Formula:</strong> Gross Margin = (Revenue − Cost of Goods Sold) ÷ Revenue × 100. <strong>Example:</strong> revenue ₹1,000 crore and COGS ₹600 crore gives <strong>40%</strong>. It is a measure of product/service economics before operating expenses, interest and tax."],
        ["Operating Margin", "<strong>What it means:</strong> Operating Margin shows operating profit generated from revenue. <strong>Formula:</strong> Operating Margin = Operating Profit ÷ Revenue × 100. <strong>Example:</strong> operating profit ₹150 crore on ₹1,000 crore revenue gives <strong>15%</strong>. It reflects the profitability of the core business after operating expenses but before financing and tax effects."],
        ["Net Margin", "<strong>What it means:</strong> Net Margin shows how much final profit remains from each rupee of revenue after all recognised expenses. <strong>Formula:</strong> Net Margin = Net Profit ÷ Revenue × 100. <strong>Example:</strong> ₹100 crore net profit on ₹1,000 crore revenue gives <strong>10%</strong>. It is affected by operating performance, interest, tax, exceptional items and other non-operating effects."],

        ["Debt / Equity (D/E)", "<strong>What it means:</strong> Debt/Equity measures the amount of debt relative to shareholders' equity. <strong>Formula:</strong> D/E = Debt ÷ Shareholders' Equity. The exact debt definition can vary by provider. <strong>Example:</strong> ₹400 crore debt and ₹800 crore equity gives <strong>0.50×</strong>. A higher ratio generally means more debt financing relative to equity, but appropriate leverage differs by industry. For financial companies, conventional debt/equity comparisons can be less directly meaningful because borrowings are part of the operating model."],
        ["Current Ratio", "<strong>What it means:</strong> Current Ratio measures current assets relative to current liabilities. <strong>Formula:</strong> Current Ratio = Current Assets ÷ Current Liabilities. <strong>Example:</strong> ₹500 crore current assets and ₹250 crore current liabilities gives <strong>2.0×</strong>. It is a short-term liquidity measure, not a guarantee that all current assets are readily convertible to cash."],
        ["Quick Ratio", "<strong>What it means:</strong> Quick Ratio is a stricter liquidity measure that excludes less-liquid inventory and similar items. A common formula is <strong>(Cash + Marketable Securities + Accounts Receivable) ÷ Current Liabilities</strong>. <strong>Example:</strong> ₹300 crore quick assets and ₹250 crore current liabilities gives <strong>1.2×</strong>. Exact provider definitions can vary."],
        ["Beta", "<strong>What it means:</strong> Beta measures how a stock's historical returns have moved relative to a market benchmark. <strong>Conceptual formula:</strong> Beta = Covariance(Stock Returns, Market Returns) ÷ Variance(Market Returns). A beta of 1 implies similar historical sensitivity to the benchmark; above 1 indicates greater historical sensitivity and below 1 lower sensitivity. Beta is statistical and depends on the return window, frequency and benchmark. In this application it is supplemental market data where available."],

        ["Revenue Growth", "<strong>Formula:</strong> Revenue Growth = (Current Revenue − Prior Revenue) ÷ Prior Revenue × 100. <strong>Example:</strong> revenue rising from ₹800 crore to ₹1,000 crore gives <strong>25%</strong> growth. This is a period-over-period growth rate, not a CAGR unless explicitly labelled CAGR."],
        ["Profit Growth", "<strong>Formula:</strong> Profit Growth = (Current Net Profit − Prior Net Profit) ÷ Prior Net Profit × 100. <strong>Example:</strong> profit rising from ₹80 crore to ₹100 crore gives <strong>25%</strong>. Growth can be distorted when the prior-year profit is very small or negative."],
        ["EPS Growth", "<strong>Formula:</strong> EPS Growth = (Current EPS − Prior EPS) ÷ Prior EPS × 100. EPS growth reflects both earnings changes and changes in the share count. It can therefore differ from net-profit growth."],
        ["Revenue CAGR", "<strong>What it means:</strong> CAGR is the constant annualised growth rate that would turn a starting value into an ending value over a specified number of years. <strong>Formula:</strong> CAGR = (Ending Value ÷ Beginning Value)^(1 / Years) − 1, then × 100 for percentage display. <strong>Example:</strong> revenue rising from ₹100 crore to ₹172.8 crore over 3 years gives approximately <strong>20% CAGR</strong>. It smooths the path between the endpoints and does not mean revenue actually grew by exactly that percentage every year."],
        ["Profit CAGR", "<strong>Formula:</strong> Profit CAGR = (Ending Profit ÷ Beginning Profit)^(1 / Years) − 1. It is meaningful only when the start and end values support a mathematically meaningful CAGR; negative or sign-changing profits can make CAGR inappropriate or unavailable. The application treats CAGR as a historical descriptive measure, not a forecast."],
        ["EPS CAGR", "<strong>Formula:</strong> EPS CAGR = (Ending EPS ÷ Beginning EPS)^(1 / Years) − 1. <strong>Example:</strong> EPS increasing from ₹10 to ₹17.28 over 3 years gives approximately <strong>20% CAGR</strong>. Because PEG uses the application's 3Y EPS CAGR, unusual EPS bases or share-count changes can materially affect PEG."],
        ["FCF CAGR", "<strong>Formula:</strong> FCF CAGR = (Ending Free Cash Flow ÷ Beginning Free Cash Flow)^(1 / Years) − 1. Free cash flow is the cash remaining after the relevant operating and investment cash flows under the provider's definition. CAGR may be unavailable or misleading when FCF changes sign."],
        ["Operating Margin Change", "<strong>Formula:</strong> Operating Margin Change = Current Operating Margin − Prior Operating Margin, expressed in <strong>percentage points (pp)</strong>, not percent growth. <strong>Example:</strong> margin rising from 12% to 15% is a <strong>+3 percentage-point</strong> change, not +3%."],

        ["Financial Statements & Display Units", "The report contains <strong>Income Statement, Balance Sheet and Cash Flow</strong> tabs. Annual periods are shown. Financial values use the source/international <strong>B / T</strong> representation or, for INR companies, the <strong>₹ Cr</strong> display option. EPS-like rows are rendered as per-share numeric values."],
        ["Charts & Historical Trends", "Stock analysis can display historical price/performance information and valuation histories such as <strong>P/E</strong> and <strong>P/B</strong> when the source provides enough observations. Historical P/E is based on year-end market price divided by annual EPS. Historical P/B is derived from annual equity and the applicable share count and can be approximate when share count changes materially. These charts describe historical data; they are not forecasts."],
        ["Comparison View", "Comparison uses the same source-aware fundamental model as individual analysis and places valuation, profitability, financial-health and growth metrics side-by-side, including <strong>Debt / Equity</strong>. The comparison view does not silently use a different calculation source for the same metric."],
        ["Data Sources & Freshness", "<strong>Screener</strong> is the primary Indian fundamental-data source for company financials and ratios. <strong>Yahoo Finance</strong> is supplemental for market-data fields such as Forward P/E and Beta where available. Source and data-as-of information remain visible in the report."],
        ["N/M vs Missing / Unavailable", "<strong>N/M — Not Meaningful</strong> means the metric does not meaningfully apply to the company's financial model, particularly some enterprise-value metrics for financial companies. <strong>Missing / unavailable</strong> means the source did not provide a usable value. The application does not fill either state with invented estimates."],
        ["Filter Performance & Stability", "Quick filtering is designed to operate on the loaded universe. Identical lightweight requests are coalesced, and the selector avoids MutationObserver feedback loops and repeated full-page DOM rebuilds. Purely visual filter changes should not trigger expensive repeated backend universe loads."],
    ]);
}

function updateBondAnalysisHelp() {
    const section = ensureSection("Bond Analysis", "Stock Analysis");
    renderCards(section, [
        ["Government & Corporate Bond Universes", "Government covers <strong>G-Secs, Treasury Bills (T-Bills) and State Development Loans (SDLs)</strong>. Corporate covers corporate securities normalized through the application's CDSL / Bond Central integrations. The two universes are separate and lazy-loaded: only the active universe is requested."],
        ["Bond Selection & Identity", "A bond is identified by its published <strong>ISIN</strong> when available. If a source record has no ISIN, the application uses the backend-provided source-scoped <strong>Record ID</strong>. The browser never fabricates an identifier. Every bond with a usable published identity is selectable."],
        ["Search, Sort & Filter Controls", "Search supports <strong>Security Name, ISIN and Issuer</strong>. Government instrument types are <strong>G-Sec, SDL and T-Bill</strong>. Source filters can include <strong>CCIL, NSE and RBI</strong>. Sorting supports <strong>Maturity Date, Market YTM, Clean Price, Coupon Rate, Security Name and Instrument Type</strong> with ascending/descending direction."],
        ["Range Filters — Every Parameter", "The selector range state contains <strong>Coupon Min, Coupon Max</strong> (%), <strong>Weighted Average Yield Min, Weighted Average Yield Max</strong> (%) for corporate bonds, and <strong>Maturity From / Maturity To</strong> dates. Corporate-only controls additionally include <strong>Trade Date</strong> and <strong>Issuer</strong>. Range and corporate filters are applied to the active-universe results."],
        ["Corporate Credit Rating Filter", "Corporate bonds support multi-select credit-rating filtering. Standard ratings such as AAA, AA+, A- and similar source values are normalized to canonical keys. Missing/NA-like values map to <strong>Unknown</strong>; an explicit source value of <strong>Unrated</strong> remains distinct from Unknown."],
        ["Bond Result Row — Every Displayed Parameter", "A result row can display <strong>Security Name, ISIN or Record ID, Instrument Type, Credit Rating, Issuer, Maturity Date and YTM</strong>. The row can also show a market-data flag such as <strong>Traded, Indicative</strong> or a freshness-age warning. Corporate rows can use weighted-average yield as the headline yield when a source YTM is absent."],
        ["Market Price & Trading Data", "The normalized market observation can contain <strong>Clean Price, Dirty Price, Market YTM, Bid Price, Bid Yield, Offer Price, Offer Yield, Last Traded Price, Last Traded Yield, Traded Value, Traded Quantity, Trade Count, VWAP, volume-weighted average yield, observation/trade date, observation/trade time, source, data type, as-of date and freshness</strong>."],
        ["Contract Terms & Cash Flows", "Bond details can expose <strong>Coupon Rate, Coupon Frequency, Coupon Basis/Type, Face Value, Issue Price, Issue Size, Outstanding Amount, Redemption Type/Date/Premium, Perpetual Status, Secured/Unsecured Status, Seniority, Exchange/Listing Status</strong> and, for corporate bonds, <strong>Call/Put Options and Dates</strong>. Coupon and redemption schedules form the cash-flow inputs for analytics where available."],
        ["Current Yield", "Current Yield relates the annual coupon cash amount to the relevant clean market price. It is distinct from YTM because it does not, by itself, model the full remaining cash-flow stream through maturity."],
        ["Calculated YTM vs Market YTM", "<strong>Calculated YTM</strong> is independently calculated from the bond terms, cash flows, price and required settlement/day-count assumptions. <strong>Market YTM</strong> is the source-reported market yield. The application retains the two separately and never silently substitutes one for the other."],
        ["Accrued Interest & Settlement", "Analytics can expose <strong>Accrued Interest, Accrued-Interest Days, Settlement Date, Clean Price and Dirty Price</strong>. Clean price excludes accrued interest; dirty price includes it. The backend analytics layer handles the calculation when sufficient contract and settlement data exists."],
        ["Duration, Convexity & DV01", "<strong>Macaulay Duration</strong> is the weighted-average timing of bond cash flows. <strong>Modified Duration</strong> approximates percentage price sensitivity to a 1% yield change. <strong>Convexity</strong> captures second-order price/yield sensitivity. <strong>DV01</strong> approximates price/value change for a 0.01% (one basis point) yield move, normally per 100 of face value."],
        ["Corporate Credit Ratings", "Corporate rating observations can include <strong>Rating, Rating Agency, Rating Status, Outlook and Rating-Action Date</strong>. Multiple source observations are preserved rather than collapsed into an invented single rating. Unknown and explicit Unrated states remain distinct."],
        ["Sources, Data Type & Freshness", "The bond layer normalizes multiple sources including <strong>CCIL, NSE, RBI, CDSL and Bond Central</strong> where applicable. Market observations may be classified as <strong>Traded, Indicative, MTM, Reference, Auction, Historical or Unknown</strong>. Freshness describes the age/status of supplied data; it is not an investment-quality score."],
        ["Calculation Conventions", "Backend bond analytics treat <strong>Settlement Date, Maturity Date, Coupon Rate, Coupon Frequency, Day-Count Convention, Price Type, Accrued Interest and Contract Cash Flows</strong> as explicit inputs where available. Calculations are performed in the backend rather than duplicated in browser JavaScript."],
        ["Missing Bond Data", "The application does not fabricate a price, yield, rating, cash-flow event, duration, convexity, DV01, accrued interest or contract term. If required inputs are unavailable, the affected calculation remains unavailable. A source Market YTM is not used as a replacement for a missing Calculated YTM."],
    ]);
}

function updateAboutText() {
    const about = [...document.querySelectorAll(".help-section")].find((s) => s.id === "about");
    if (!about) return;
    const lead = about.querySelector("p");
    if (lead) lead.innerHTML = "A quantitative analysis platform for Indian stocks, bonds and mutual funds, combining source-backed market data, deterministic calculations and transparent methodology.";
}

function initialiseHelp() {
    removeLegacyStockPlaceholder();
    registerStockHelpSearchEntries();
    registerBondHelpSearchEntries();
    updateAboutText();
    updateStockAnalysisHelp();
    updateBondAnalysisHelp();
    initSearch();
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initialiseHelp, { once: true });
} else {
    initialiseHelp();
}
