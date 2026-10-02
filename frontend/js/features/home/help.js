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
                   placeholder="Search Help & Methodology — e.g. CAGR, Sharpe ratio, Debt / Equity, stock filters…"
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
                <p class="help-search-no-results-hint">Try a broader term such as returns, risk, ranking, percentiles, data sources, stock filters, ratios, charts, or methodology.</p>
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
    if (item.classList.contains("open")) return;
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

function registerStockHelpSearchEntries() {
    // Older releases shipped a static "Coming Soon" search entry. Remove it so
    // Help search can never surface stale Stock Analysis documentation after
    // the live implementation has been enabled.
    for (let i = HELP_SEARCH_INDEX.length - 1; i >= 0; i -= 1) {
        const entry = HELP_SEARCH_INDEX[i];
        if (entry.id === "stock-analysis-coming-soon" || entry.heading === "Coming Soon" && entry.sectionHeading === "Stock Analysis") {
            HELP_SEARCH_INDEX.splice(i, 1);
        }
    }

    const entries = [
        ["stock-universe", "Stock Universe & Selection", ["stock universe", "nifty total market", "nifty 500", "microcap 250", "large cap", "mid cap", "small cap", "micro cap"], ["which stocks are available", "stock universe"]],
        ["stock-multiselect", "Multi-Select Screening", ["sector", "multi select", "multiple sectors", "search", "market cap", "filter", "presets"], ["select multiple sectors", "sector filter", "stock screening"]],
        ["stock-select-compare", "Select, Analyze & Compare", ["select stock", "analyze stock", "compare stocks", "comparison", "auto add"], ["how do I compare stocks", "select and analyze"]],
        ["stock-individual", "Individual Stock Analysis", ["valuation", "profitability", "financial health", "debt equity", "financial statements", "cagr", "pe", "pb", "ratios", "analysis"], ["stock fundamentals", "individual stock analysis"]],
        ["stock-valuation", "Valuation Metrics", ["pe", "p/e", "forward pe", "pb", "price book", "price sales", "peg", "ev ebitda", "ev revenue", "dividend yield", "payout ratio", "valuation"], ["stock valuation ratios", "what is forward pe"]],
        ["stock-profitability", "Profitability Metrics", ["roe", "roa", "gross margin", "operating margin", "net margin", "profitability"], ["stock profitability", "what is roe", "what is roa"]],
        ["stock-financial-health", "Financial Health Metrics", ["debt equity", "debt / equity", "current ratio", "quick ratio", "beta", "financial health", "leverage"], ["what is debt equity", "what is beta", "stock financial health"]],
        ["stock-growth", "Growth & CAGR Metrics", ["growth", "cagr", "revenue growth", "profit growth", "earnings growth", "annualized growth"], ["stock growth metrics", "how is stock cagr calculated"]],
        ["stock-statements", "Financial Statements", ["income statement", "balance sheet", "cash flow", "revenue", "net profit", "ebitda", "free cash flow", "financial statements"], ["stock financial statements", "company accounts"]],
        ["stock-charts", "Charts & Historical Trends", ["chart", "charts", "trend", "pe history", "p/e history", "pb history", "price performance", "historical valuation", "time series"], ["stock charts", "valuation trend charts"]],
        ["stock-data-sources", "Data Sources", ["screener", "yahoo", "forward pe", "beta", "fundamental data", "market data", "source"], ["where does stock data come from", "yahoo market data"]],
        ["stock-missing-values", "Data Notes & Missing Values", ["n/m", "not meaningful", "missing data", "data notes", "unavailable", "financial company"], ["why is a stock metric missing", "not meaningful"]],
        ["stock-comparison", "Comparison View", ["comparison", "debt equity", "side by side", "metrics", "table", "compare"], ["compare stock fundamentals", "stock comparison"]],
        ["stock-filters", "Stock Filters & Screening Controls", ["filter", "sector", "search", "market cap", "large cap", "mid cap", "small cap", "micro cap", "apply filters", "clear filters"], ["how do stock filters work", "filter stocks"]],
        ["stock-stability", "Filter Performance & Stability", ["mutation observer", "performance", "dom", "backend requests", "refresh", "loading", "stability"], ["why did the stock page keep loading", "filter performance"]],
    ];

    for (const [id, heading, keywords, aliases] of entries) {
        if (HELP_SEARCH_INDEX.some((entry) => entry.id === id)) continue;
        HELP_SEARCH_INDEX.push({
            id,
            type: "card",
            heading,
            sectionHeading: "Stock Analysis",
            keywords,
            aliases,
        });
    }
}

/* Keep Help & Methodology synchronized with the implemented Stock Analysis page. */
function updateStockAnalysisHelp() {
    const sections = [...document.querySelectorAll(".help-section")];
    const section = sections.find((s) => {
        const h = s.querySelector("h3");
        return h && h.textContent.trim() === "Stock Analysis";
    });
    if (!section) return;

    section.innerHTML = `
        <h3>Stock Analysis</h3>
        <div class="help-grid">
            <div class="help-card">
                <h4>Stock Universe & Selection</h4>
                <p>The selector uses the Nifty Total Market universe — Nifty 500 plus the Nifty Microcap 250 source universe. It is broader than a large-cap-only universe and includes Large, Mid, Small and Micro Cap stocks.</p>
            </div>
            <div class="help-card">
                <h4>Sector, Search & Quick Filters</h4>
                <p>Sector is a multi-select control. Search filters by company name or symbol. Market Cap presets refine the full loaded universe by Large, Mid, Small or Micro Cap. Quick controls are separate from the collapsible Filter Results area.</p>
            </div>
            <div class="help-card">
                <h4>Select, Analyze & Compare</h4>
                <p>Selecting a stock makes it the active analysis stock and also adds it to the Compare Stocks list automatically. The user can remove it later. The comparison workflow supports multiple staged stocks.</p>
            </div>
            <div class="help-card">
                <h4>Valuation Ratios</h4>
                <p>The analysis can show P/E, Forward P/E, Price/Book, Price/Sales, PEG, EV/EBITDA, EV/Revenue, Dividend Yield and Payout Ratio where meaningful. Forward P/E is supplemental Yahoo market data; Screener remains the primary Indian fundamental source.</p>
            </div>
            <div class="help-card">
                <h4>Profitability Ratios</h4>
                <p>Profitability includes ROE, ROA, Gross Margin, Operating Margin and Net Margin where source data supports them. Ratios are displayed as source values rather than invented estimates.</p>
            </div>
            <div class="help-card">
                <h4>Financial Health & Leverage</h4>
                <p><strong>Debt / Equity</strong> is a first-class metric. The section can also include Current Ratio, Quick Ratio and Beta. Beta is supplemental Yahoo market data and is not substituted for a fundamental ratio.</p>
            </div>
            <div class="help-card">
                <h4>Growth & CAGR</h4>
                <p>Growth measures and CAGR metrics describe historical changes in revenue, profit or other supported fundamentals. CAGR annualizes growth over the available source period; it is historical analysis, not a forecast.</p>
            </div>
            <div class="help-card">
                <h4>Financial Statements</h4>
                <p>Annual Income Statement, Balance Sheet and Cash Flow tables expose source financials such as Revenue, EBITDA, Net Profit, Free Cash Flow, assets, liabilities, equity and cash-flow items where available.</p>
            </div>
            <div class="help-card">
                <h4>Charts & Historical Trends</h4>
                <p>Historical price/performance and valuation charts show source-backed time series where available, including P/E and P/B history. Charts are descriptive of historical observations and are not forecasts.</p>
            </div>
            <div class="help-card">
                <h4>Comparison View</h4>
                <p>The comparison page uses the same source-aware fundamental model as individual analysis and keeps metric definitions consistent. Debt / Equity is included alongside valuation, profitability, growth and financial-health metrics.</p>
            </div>
            <div class="help-card">
                <h4>Data Sources & Freshness</h4>
                <p><strong>Screener</strong> is the primary Indian fundamental-data source. <strong>Yahoo Finance</strong> is supplemental for market-data fields such as Forward P/E and Beta where available. The UI does not fabricate values merely to fill a card.</p>
            </div>
            <div class="help-card">
                <h4>Missing vs Not Meaningful</h4>
                <p><strong>N/M — Not Meaningful</strong> means the metric does not meaningfully apply to the business or financial model, especially for certain financial-company metrics. Genuine source gaps remain unavailable rather than being shown as a misleading numeric value.</p>
            </div>
            <div class="help-card">
                <h4>Filter Results & Report Workflow</h4>
                <p>The Filter Results bar is collapsible so the detailed screening results can be hidden while Sector, Search and quick filters remain usable. Selecting a stock leads into the individual analysis report, while staged selections can be opened in comparison.</p>
            </div>
            <div class="help-card">
                <h4>Filter Performance & Stability</h4>
                <p>The selector avoids MutationObserver feedback loops and repeated full-page DOM rebuilds. Lightweight universe requests are coalesced and quick controls refine the loaded universe locally wherever possible, keeping filtering and refresh behaviour responsive.</p>
            </div>
        </div>`;

    const future = sections.find((s) => {
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

export function initHelp() {
    registerStockHelpSearchEntries();
    updateStockAnalysisHelp();
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
