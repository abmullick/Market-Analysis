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
                   placeholder="Search Help & Methodology — e.g. stock filters, Debt / Equity, YTM, duration, DV01…"
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
        ["Valuation — Every Displayed Parameter", "<strong>P/E</strong> (price/earnings), <strong>Forward P/E</strong> (forward earnings expectation), <strong>Price / Book</strong>, <strong>Price / Sales</strong>, <strong>PEG</strong>, <strong>EV / EBITDA</strong>, <strong>EV / Revenue</strong>, <strong>Dividend Yield</strong> and <strong>Payout Ratio</strong>. PEG can show the implemented calculation note based on P/E divided by supported 3Y EPS CAGR."],
        ["Profitability — Every Displayed Parameter", "<strong>ROE</strong>, <strong>ROA</strong>, <strong>Gross Margin</strong>, <strong>Operating Margin</strong> and <strong>Net Margin</strong>. These are source-backed profitability measures; the application does not invent missing values."],
        ["Financial Health — Every Displayed Parameter", "<strong>Debt / Equity</strong>, <strong>Current Ratio</strong>, <strong>Quick Ratio</strong> and <strong>Beta</strong>. Debt / Equity is a first-class metric and is used consistently in individual analysis, applicable screening and comparison. Beta is supplemental market data where available."],
        ["Growth & CAGR — Every Displayed Parameter", "The Growth group contains <strong>Revenue Growth, Profit Growth, EPS Growth, Revenue CAGR 3Y, Revenue CAGR 5Y, Profit CAGR 3Y, Profit CAGR 5Y, EPS CAGR 3Y, EPS CAGR 5Y, FCF CAGR 3Y, FCF CAGR 5Y</strong> and <strong>Operating Margin Change</strong> in percentage points. CAGR is historical annualised growth, not a forecast."],
        ["Financial Statements & Display Units", "The report contains <strong>Income Statement, Balance Sheet and Cash Flow</strong> tabs. Annual periods are shown. Financial values use the source/international <strong>B / T</strong> representation or, for INR companies, the <strong>₹ Cr</strong> display option. EPS-like rows are rendered as per-share numeric values."],
        ["Charts & Historical Trends", "Stock analysis can display historical price/performance information and valuation histories such as <strong>P/E</strong> and <strong>P/B</strong> when the source provides enough observations. These charts describe historical data; they are not forecasts."],
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
