import { searchHelp, resolveTarget, HELP_SEARCH_INDEX } from "./help-search-index.js";

const SEARCH_DEBOUNCE_MS = 150;
const STRONG_MATCH_SCORE = 45;
const HIGHLIGHT_DURATION_MS = 2600;
const SUGGESTED_QUESTIONS = [
    "How is CAGR calculated?",
    "What is Sharpe ratio?",
    "What does rolling return mean?",
    "How does fund ranking work?",
    "How are percentile ranks calculated?",
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
                   placeholder="Search Help & Methodology — e.g. CAGR, Sharpe ratio, rolling returns…"
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
                <p class="help-search-no-results-hint">Try a broader term such as returns, risk, ranking, percentiles, data sources, or methodology.</p>
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
    const entries = [
        ["stock-universe", "Stock Universe & Selection", ["stock universe", "nifty total market", "nifty 500", "microcap 250", "large cap", "mid cap", "small cap", "micro cap"], ["which stocks are available", "stock universe"]],
        ["stock-multiselect", "Multi-Select Screening", ["sector", "multi select", "multiple sectors", "search", "market cap", "filter"], ["select multiple sectors", "sector filter"]],
        ["stock-select-compare", "Select, Analyze & Compare", ["select stock", "analyze stock", "compare stocks", "comparison", "auto add"], ["how do I compare stocks", "select and analyze"]],
        ["stock-individual", "Individual Stock Analysis", ["valuation", "profitability", "financial health", "debt equity", "financial statements", "cagr", "pe", "pb"], ["stock fundamentals", "individual stock analysis"]],
        ["stock-data-sources", "Data Sources", ["screener", "yahoo", "forward pe", "beta", "fundamental data", "market data"], ["where does stock data come from", "yahoo market data"]],
        ["stock-missing-values", "Data Notes & Missing Values", ["n/m", "not meaningful", "missing data", "data notes", "unavailable"], ["why is a stock metric missing", "not meaningful"]],
        ["stock-comparison", "Comparison View", ["comparison", "debt equity", "side by side", "metrics", "table"], ["compare stock fundamentals"]],
        ["stock-stability", "Filter Performance & Stability", ["mutation observer", "performance", "dom", "backend requests", "refresh", "loading"], ["why did the stock page keep loading", "filter performance"]],
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
                <p>The selector uses the Nifty Total Market universe — Nifty 500 plus the Nifty Microcap 250 source universe. It supports sector filtering, company/symbol search, and Large/Mid/Small/Micro Cap presets.</p>
            </div>
            <div class="help-card">
                <h4>Multi-Select Screening</h4>
                <p>Sector selection is multi-select. Choosing several sectors includes stocks from any selected sector. Search and quick market-cap controls refine the already-loaded universe locally where possible.</p>
            </div>
            <div class="help-card">
                <h4>Select, Analyze & Compare</h4>
                <p>Selecting a stock makes it the active analysis stock and also adds it to the Compare Stocks list. The user can remove it later; multiple stocks can be staged for comparison.</p>
            </div>
            <div class="help-card">
                <h4>Individual Stock Analysis</h4>
                <p>The analysis view presents company summary data, valuation, profitability, financial health, growth, financial statements, and valuation/performance trend charts where source data is available. Debt / Equity is a core metric and screening field.</p>
            </div>
            <div class="help-card">
                <h4>Data Sources</h4>
                <p>Screener is the primary Indian fundamental-data source. Yahoo market data is supplemental, including Forward P/E and Beta where available. Values are not invented simply to fill a card.</p>
            </div>
            <div class="help-card">
                <h4>Data Notes & Missing Values</h4>
                <p><strong>N/M — Not Meaningful</strong> is used when a metric does not meaningfully apply to the business model. Genuine unavailable source data remains unavailable. Data Notes stay at the bottom of the analysis page.</p>
            </div>
            <div class="help-card">
                <h4>Comparison View</h4>
                <p>The comparison page uses the same source-aware fundamental model and includes Debt / Equity with the core valuation, profitability, growth, and financial-health metrics.</p>
            </div>
            <div class="help-card">
                <h4>Filter Performance & Stability</h4>
                <p>The selector avoids MutationObserver feedback loops and repeated full-page DOM rebuilds. Quick filters operate against the loaded universe where possible, keeping refreshes and filter interactions responsive.</p>
            </div>
        </div>`;

    const future = sections.find((s) => {
        const h = s.querySelector("h3");
        return h && h.textContent.trim() === "Future / Planned";
    });
    if (future) {
        future.querySelectorAll(".help-card").forEach((card) => {
            const h = card.querySelector("h4");
            if (h && h.textContent.trim() === "Stock Analysis") card.remove();
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
