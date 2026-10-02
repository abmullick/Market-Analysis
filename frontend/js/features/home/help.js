import { searchHelp, resolveTarget, HELP_SEARCH_INDEX } from "./help-search-index.js";

const SEARCH_DEBOUNCE_MS = 150;
const STRONG_MATCH_SCORE = 45;
const HIGHLIGHT_DURATION_MS = 2600;

const SUGGESTED_QUESTIONS = [
    "How is CAGR calculated?",
    "What is Sharpe ratio?",
    "What does rolling return mean?",
    "How do stock filters work?",
    "What is Debt / Equity?",
    "What is Forward P/E?",
    "What is Beta?",
    "How are stock charts calculated?",
    "How does stock comparison work?",
    "How does Bond Analysis work?",
    "What is calculated YTM?",
    "What is duration?",
    "What is DV01?",
    "How fresh is the data?",
    "What is Portfolio Health Score?",
    "How is portfolio health calculated?",
    "How does portfolio analysis work?",
    "What is Fund Mix?",
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
                   placeholder="Search Help & Methodology — e.g. CAGR, Sharpe, Debt / Equity, stock filters, YTM, DV01…"
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
                <p class="help-search-no-results-hint">Try returns, risk, ranking, filters, ratios, charts, bonds, YTM, duration, DV01, cash flows, or methodology.</p>
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
        HELP_SEARCH_INDEX.push({
            id,
            type: "card",
            heading,
            sectionHeading,
            keywords,
            aliases,
        });
    }
}

function registerStockHelpSearchEntries() {
    // Remove stale placeholder entries from older releases.
    for (let i = HELP_SEARCH_INDEX.length - 1; i >= 0; i -= 1) {
        const entry = HELP_SEARCH_INDEX[i];
        if (
            entry.id === "stock-analysis-coming-soon" ||
            (entry.heading === "Coming Soon" && entry.sectionHeading === "Stock Analysis")
        ) {
            HELP_SEARCH_INDEX.splice(i, 1);
        }
    }

    upsertHelpSearchEntries("Stock Analysis", [
        ["stock-universe", "Stock Universe & Selection", ["stock universe", "nifty total market", "nifty 500", "microcap 250", "large cap", "mid cap", "small cap", "micro cap"], ["which stocks are available", "stock universe"]],
        ["stock-screening-controls", "Screening Controls", ["sector", "multi select", "multiple sectors", "search", "market cap", "large cap", "mid cap", "small cap", "micro cap", "filter", "presets"], ["select multiple sectors", "sector filter", "stock screening"]],
        ["stock-selection-workflow", "Select, Analyze & Compare", ["select stock", "analyze stock", "compare stocks", "comparison", "auto add", "selected stock"], ["how do I compare stocks", "select and analyze"]],
        ["stock-pagination", "Full-Universe Filtering & Pagination", ["pagination", "page", "full universe", "first page", "result count", "sector filtering"], ["does sector filter use first page", "stock pagination"]],
        ["stock-valuation", "Valuation Metrics", ["pe", "p/e", "forward pe", "pb", "price book", "price sales", "peg", "ev ebitda", "ev revenue", "dividend yield", "payout ratio", "valuation"], ["stock valuation ratios", "what is forward pe"]],
        ["stock-profitability", "Profitability Metrics", ["roe", "roa", "gross margin", "operating margin", "net margin", "profitability"], ["stock profitability", "what is roe", "what is roa"]],
        ["stock-financial-health", "Financial Health Metrics", ["debt equity", "debt / equity", "current ratio", "quick ratio", "beta", "financial health", "leverage"], ["what is debt equity", "what is beta", "stock financial health"]],
        ["stock-growth", "Growth & CAGR Metrics", ["growth", "cagr", "revenue growth", "profit growth", "eps growth", "annualized growth"], ["stock growth metrics", "how is stock cagr calculated"]],
        ["stock-statements", "Financial Statements", ["income statement", "balance sheet", "cash flow", "revenue", "net profit", "ebitda", "free cash flow", "financial statements"], ["stock financial statements", "company accounts"]],
        ["stock-charts", "Charts & Historical Trends", ["chart", "charts", "trend", "pe history", "p/e history", "pb history", "price performance", "historical valuation", "time series"], ["stock charts", "valuation trend charts"]],
        ["stock-report", "Individual Stock Report", ["report", "analysis", "summary", "ratios", "statements", "data notes", "individual stock"], ["stock report", "what is in stock analysis"]],
        ["stock-comparison", "Comparison View", ["comparison", "debt equity", "side by side", "metrics", "table", "compare"], ["compare stock fundamentals", "stock comparison"]],
        ["stock-data-sources", "Data Sources & Freshness", ["screener", "yahoo", "forward pe", "beta", "fundamental data", "market data", "source", "freshness"], ["where does stock data come from", "yahoo market data"]],
        ["stock-missing-values", "Missing & Not Meaningful Values", ["n/m", "not meaningful", "missing data", "data notes", "unavailable", "financial company"], ["why is a stock metric missing", "not meaningful"]],
        ["stock-methodology", "Stock Analysis Methodology", ["methodology", "source aware", "historical", "descriptive", "forecast", "calculation"], ["stock analysis methodology"]],
        ["stock-filter-stability", "Filter Performance & Stability", ["mutation observer", "performance", "dom", "backend requests", "refresh", "loading", "stability", "coalescing"], ["why did the stock page keep loading", "filter performance"]],
    ]);
}

function registerBondHelpSearchEntries() {
    upsertHelpSearchEntries("Bond Analysis", [
        ["bond-universes", "Government & Corporate Bond Universes", ["bond", "government", "corporate", "g-sec", "t-bill", "sdl", "universe"], ["what bonds are covered", "government bonds", "corporate bonds"]],
        ["bond-selection", "Bond Selection & Identity", ["select bond", "isin", "record id", "identity", "selection"], ["how do I select a bond", "bond identifier"]],
        ["bond-search-filters", "Search, Sort & Filters", ["search", "filter", "sort", "issuer", "instrument type", "source", "coupon", "maturity", "yield"], ["how do bond filters work", "bond screening"]],
        ["bond-market-data", "Market Price & Yield Data", ["market price", "clean price", "dirty price", "bid", "offer", "ltp", "trade count", "vwap", "market ytm"], ["bond market data", "bond price and yield"]],
        ["bond-current-yield", "Current Yield", ["current yield", "coupon", "clean price", "yield"], ["what is current yield"]],
        ["bond-ytm", "Calculated YTM vs Market YTM", ["ytm", "yield to maturity", "calculated ytm", "market ytm", "source yield"], ["what is calculated ytm", "calculated versus market ytm"]],
        ["bond-accrued-interest", "Accrued Interest & Settlement", ["accrued interest", "settlement date", "accrued days", "clean", "dirty"], ["what is accrued interest"]],
        ["bond-duration", "Duration", ["macaulay duration", "modified duration", "duration", "interest rate sensitivity"], ["what is duration"]],
        ["bond-convexity", "Convexity", ["convexity", "second order", "yield sensitivity"], ["what is convexity"]],
        ["bond-dv01", "DV01", ["dv01", "basis point", "0.01", "price sensitivity"], ["what is dv01"]],
        ["bond-cashflows", "Coupon Schedule & Redemption Cash Flows", ["cash flow", "coupon schedule", "redemption", "maturity", "face value", "cash flows"], ["bond cash flows", "redemption cash flows"]],
        ["bond-corporate-ratings", "Corporate Credit Ratings", ["credit rating", "rating agency", "ratings watch", "outlook", "rated", "unrated", "unknown"], ["bond credit ratings", "corporate rating filter"]],
        ["bond-corporate-terms", "Corporate Bond Terms", ["secured", "seniority", "call", "put", "issue size", "outstanding", "perpetual", "guarantee"], ["corporate bond terms"]],
        ["bond-data-sources", "Bond Data Sources & Freshness", ["ccil", "nse", "rbi", "cdsl", "bond central", "source", "freshness", "traded", "indicative"], ["where does bond data come from", "bond source status"]],
        ["bond-methodology", "Bond Analytics Methodology", ["day count", "coupon frequency", "settlement", "analytics", "backend", "calculation"], ["bond methodology"]],
        ["bond-missing-data", "Bond Missing Data & Availability", ["missing", "unavailable", "not available", "insufficient", "analytics gating"], ["why is bond analytics unavailable"]],
    ]);
}

function ensureSection(title, beforeTitle = null) {
    const sections = [...document.querySelectorAll(".help-section")];
    let section = sections.find((s) => {
        const h = s.querySelector("h3");
        return h && h.textContent.trim() === title;
    });
    if (section) return section;

    section = document.createElement("section");
    section.className = "help-section";
    section.innerHTML = `<h3>${title}</h3><div class="help-grid"></div>`;

    if (beforeTitle) {
        const before = sections.find((s) => {
            const h = s.querySelector("h3");
            return h && h.textContent.trim() === beforeTitle;
        });
        if (before) before.parentNode.insertBefore(section, before);
        else document.querySelector(".help-container")?.appendChild(section);
    } else {
        document.querySelector(".help-container")?.appendChild(section);
    }
    return section;
}

function renderCards(section, cards) {
    section.innerHTML = `
        <h3>${section.querySelector("h3")?.textContent || ""}</h3>
        <div class="help-grid">
            ${cards.map(([heading, body]) => `
                <div class="help-card">
                    <h4>${heading}</h4>
                    <p>${body}</p>
                </div>`).join("")}
        </div>`;
}

function updateAboutText() {
    const about = [...document.querySelectorAll(".help-section")].find((s) => s.id === "about");
    if (!about) return;
    const lead = about.querySelector("p");
    if (lead) {
        lead.innerHTML = "Market Analysis is a quantitative analysis platform for Indian markets with active <strong>Stock Analysis</strong>, <strong>Bond Analysis</strong>, <strong>Mutual Fund Analysis</strong>, and <strong>Mutual Fund Portfolio Builder</strong> modules. Stock Portfolio Builder remains a planned product area.";
    }
}

function updateStockAnalysisHelp() {
    const section = ensureSection("Stock Analysis", "Future / Planned");
    renderCards(section, [
        ["Stock Universe & Selection", "The selector uses the <strong>Nifty Total Market</strong> source universe — Nifty 500 plus the Nifty Microcap 250 source universe. It is broader than a large-cap-only universe and includes Large, Mid, Small and Micro Cap stocks."],
        ["Sector, Search & Market-Cap Filters", "Sector is a multi-select control. Search matches company name or symbol. Market-cap presets refine the loaded universe by <strong>Large Cap, Mid Cap, Small Cap, or Micro Cap</strong>. These quick controls remain outside the collapsible Filter Results body."],
        ["Full-Universe Filtering & Pagination", "Filtering is applied across the <strong>full loaded universe</strong> before the visible result page is limited for presentation. Selecting a sector or cap therefore does not mean the application is screening only the first displayed page."],
        ["Select → Analyze → Compare", "Selecting a stock makes it the active <strong>Selected Stock</strong> and also adds it automatically to <strong>Compare Stocks</strong>. The user can remove it from comparison later. Navigation to the individual analysis page happens only when <strong>Analyze Stock</strong> is clicked."],
        ["Valuation — P/E & Forward P/E", "<strong>P/E</strong> relates market price to earnings per share. <strong>Forward P/E</strong> uses forward earnings expectations when supplied by Yahoo Finance and is treated as supplemental market data rather than the primary Screener fundamental field."],
        ["Valuation — P/B, P/S & PEG", "<strong>P/B</strong> relates market price to book value per share. <strong>P/S</strong> relates market value to sales. <strong>PEG</strong> relates valuation to a supported earnings-growth measure. Values are shown only when the source supports them."],
        ["Valuation — EV/EBITDA & EV/Revenue", "<strong>EV/EBITDA</strong> and <strong>EV/Revenue</strong> compare enterprise value with operating earnings or revenue. These metrics may be shown as N/M — Not Meaningful for businesses where the metric is not appropriate, rather than forcing a misleading value."],
        ["Dividend Yield & Payout Ratio", "<strong>Dividend Yield</strong> expresses dividend income relative to market price. <strong>Payout Ratio</strong> relates dividends to the relevant earnings measure. Availability depends on the underlying company data."],
        ["Profitability — ROE & ROA", "<strong>ROE</strong> measures return generated on shareholders' equity. <strong>ROA</strong> measures return relative to the asset base. They are source-backed fundamentals and are not invented when unavailable."],
        ["Profitability — Margins", "<strong>Gross Margin, Operating Margin, and Net Margin</strong> show profit retained at successive income-statement levels as a percentage of revenue. The analysis keeps the source value rather than substituting estimates."],
        ["Financial Health — Debt / Equity", "<strong>Debt / Equity</strong> is a first-class financial-health metric and is carried into individual analysis, screening where applicable, and stock comparison. It measures debt relative to shareholders' equity."],
        ["Financial Health — Current Ratio, Quick Ratio & Beta", "<strong>Current Ratio</strong> and <strong>Quick Ratio</strong> are balance-sheet liquidity measures. <strong>Beta</strong> is a supplemental Yahoo market-data field describing market sensitivity; it is not substituted for a fundamental ratio."],
        ["Growth & CAGR", "Revenue, profit, EPS and other supported growth measures describe historical change. <strong>CAGR</strong> annualizes historical growth over the supported period. It is descriptive of the historical period and is not a forecast."],
        ["Financial Statements", "The individual report can expose annual <strong>Income Statement, Balance Sheet, and Cash Flow</strong> tables, including Revenue, EBITDA, Net Profit, Free Cash Flow and other source fields where available."],
        ["Historical Charts", "Historical price/performance and valuation charts are source-backed descriptive views. Where data exists, the application can show trends such as <strong>P/E and P/B history</strong>. Charts describe historical observations rather than predicting future prices or returns."],
        ["Comparison View", "Stock comparison uses the same source-aware fundamental model as individual analysis and presents core valuation, profitability, growth and financial-health metrics side by side, including Debt / Equity."],
        ["Data Sources & Freshness", "<strong>Screener</strong> is the primary Indian fundamental-data source. <strong>Yahoo Finance</strong> is supplemental for fields such as Forward P/E and Beta. The application keeps source provenance visible and does not fabricate fundamentals to fill a card."],
        ["N/M vs Missing Data", "<strong>N/M — Not Meaningful</strong> means the metric is not meaningful for the company's financial model. <strong>Unavailable / missing</strong> means the source did not provide a usable value. These states are intentionally kept distinct."],
        ["Filter Results & Stability", "The Filter Results bar is independently collapsible. Sector, Search and quick filters remain usable outside it. The selector is designed to avoid MutationObserver feedback loops, repeated full-page DOM rebuilds, and duplicate lightweight universe requests."],
        ["Stock Analysis Methodology", "Stock metrics are rendered from the normalized backend data model. Historical charts and ratios are descriptive; screening applies the selected controls to the loaded universe; comparison reuses the same source-aware metrics so definitions stay consistent across views."]
    ]);

    // Remove stale placeholder content from the planned section.
    const future = [...document.querySelectorAll(".help-section")].find((s) => {
        const h = s.querySelector("h3");
        return h && h.textContent.trim() === "Future / Planned";
    });
    if (future) {
        future.querySelectorAll(".help-card").forEach((card) => {
            const h = card.querySelector("h4");
            if (h && (h.textContent.trim() === "Stock Analysis" || h.textContent.trim() === "Coming Soon")) card.remove();
        });
    }
}

function updateBondAnalysisHelp() {
    const section = ensureSection("Bond Analysis", "Stock Analysis");
    renderCards(section, [
        ["Government & Corporate Universes", "Bond Analysis has separate <strong>Government Bonds</strong> and <strong>Corporate Bonds</strong> universes. Government instruments include G-Secs, T-Bills and SDLs. The two universes are lazy-loaded independently so the inactive universe is not requested."],
        ["Bond Selection & Identity", "Every listed bond with a usable published identity is selectable. The application prefers the source-published <strong>ISIN</strong>; records without an ISIN use the backend-provided <strong>record ID</strong>. The browser never invents an identifier."],
        ["Search, Sort & Instrument Filters", "Search supports security name, ISIN and issuer. Government bonds can be filtered by G-Sec, SDL or T-Bill. Sorting includes maturity date, market YTM, clean price, coupon rate, security name and instrument type, with ascending/descending direction."],
        ["Advanced Bond Filters", "Advanced filters include coupon-rate range and maturity-date range. Corporate bonds additionally support weighted-average-yield range, trade date, issuer and credit-rating filtering."],
        ["Market Price & Yield Data", "Market observations can include <strong>clean price, dirty price, bid/offer price and yield, last traded price/yield, traded value, quantity, trade count, and volume-weighted average price/yield</strong>. The source and observation freshness are retained with the data."],
        ["Current Yield", "<strong>Current Yield</strong> is the annual coupon relative to the clean price. It is a separate concept from Yield to Maturity and is displayed only when the required inputs are available."],
        ["Calculated YTM vs Market YTM", "<strong>Calculated YTM</strong> is independently computed by the backend analytics engine from the bond's terms and price. <strong>Market YTM</strong> is the source-reported yield. The application deliberately keeps them separate rather than silently substituting one for the other."],
        ["Accrued Interest & Settlement", "<strong>Accrued Interest</strong> represents interest accumulated since the relevant coupon date under the analytics convention. The analysis also exposes settlement date, accrued-interest days and day-count convention where available."],
        ["Macaulay & Modified Duration", "<strong>Macaulay Duration</strong> is the weighted-average time to receive the bond's cash flows. <strong>Modified Duration</strong> approximates the percentage price change for a 1% change in yield."],
        ["Convexity", "<strong>Convexity</strong> is a second-order price/yield sensitivity measure that captures how duration changes as yield changes. It complements duration rather than replacing it."],
        ["DV01", "<strong>DV01</strong> means Dollar Value of One Basis Point. In this application's bond analytics it represents the approximate price/value change for a 0.01% yield move, per 100 of face value."],
        ["Coupon Schedule & Redemption Cash Flows", "The bond detail can expose coupon schedules and redemption cash flows. The normalized model carries coupon rate, frequency, face value, maturity/redemption information and source cash-flow schedule data where supplied."],
        ["Corporate Credit Ratings", "Corporate bonds can expose source-published credit ratings, rating agency, rating date, ratings watch and outlook. Multiple rating observations are preserved rather than silently collapsing different agencies or rating actions."],
        ["Corporate Bond Terms", "Corporate detail can include secured/unsecured status, seniority, call/put options and dates, issue size, outstanding amount, issue price, coupon type/basis, issuance mode, guarantee status, perpetual status and exchange/listing information when supplied."],
        ["Data Sources & Freshness", "The bond layer normalizes multiple source feeds behind the service/model layer. The UI can show source status for <strong>CCIL, NSE and RBI</strong>, while corporate data can use CDSL/Bond Central integrations. Market observations retain source, data type, as-of date and freshness."],
        ["Market Observation Types", "Bond observations can be classified as <strong>traded, indicative, MTM, reference, auction, historical</strong> or unknown depending on the source payload. A stale observation is not presented as if it were a current trade."],
        ["Bond Analytics Methodology", "Bond calculations are performed in the backend analytics service. Coupon frequency, day-count convention, settlement date, maturity, price type and accrued interest are treated as explicit inputs where available. Browser JavaScript does not duplicate the financial calculation engine."],
        ["Missing Data & Analytics Availability", "If a source does not provide enough information for a price, yield, rating, cash-flow event, duration, convexity or DV01 calculation, the application leaves the metric unavailable rather than inventing or silently substituting another value."],
        ["Bond Research Workflow", "Use the left-side universe and filters to narrow the securities, select a bond, then inspect its summary, market observations, calculated analytics, cash-flow/contract details and source information. The Help page explains the terminology used throughout that workflow."]
    ]);
}

export function initHelp() {
    registerStockHelpSearchEntries();
    registerBondHelpSearchEntries();
    updateAboutText();
    updateStockAnalysisHelp();
    updateBondAnalysisHelp();
    initSearch();

    const triggers = document.querySelectorAll(".metric-trigger");
    triggers.forEach(trigger => {
        trigger.addEventListener("click", () => {
            const item = trigger.parentElement;
            const isOpen = item.classList.contains("open");

            document.querySelectorAll(".metric-item.open").forEach(openItem => {
                openItem.classList.remove("open");
                openItem.querySelector(".metric-panel").setAttribute("hidden", "");
                openItem.querySelector(".metric-chevron").style.transform = "";
            });

            if (!isOpen) {
                item.classList.add("open");
                const panel = item.querySelector(".metric-panel");
                panel.removeAttribute("hidden");
                trigger.querySelector(".metric-chevron").style.transform = "rotate(180deg)";
            }
        });
    });

    const feedbackForm = document.getElementById("feedback-form");
    const feedbackInput = document.getElementById("feedback-message");
    const feedbackError = document.getElementById("feedback-error");
    if (!feedbackForm || !feedbackInput || !feedbackError) return;

    feedbackForm.addEventListener("submit", (event) => {
        event.preventDefault();
        const message = feedbackInput.value.trim();
        if (!message) {
            feedbackError.textContent = "Please enter feedback before opening your email client.";
            feedbackError.removeAttribute("hidden");
            feedbackInput.focus();
            return;
        }

        feedbackError.setAttribute("hidden", "");
        const subject = encodeURIComponent("Market Analysis Feedback");
        const body = encodeURIComponent(message);
        window.location.href = `mailto:abmullick@gmail.com?subject=${subject}&body=${body}`;
    });
}
