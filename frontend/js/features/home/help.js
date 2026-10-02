import { searchHelp, resolveTarget } from "./help-search-index.js";

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

/** Open an accordion item without breaking the existing toggle behaviour. */
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
                <p>
                    The Stock Analysis selector uses the Nifty Total Market universe — the Nifty 500 plus the Nifty
                    Microcap 250 source universe. The selector supports sector filtering, company/symbol search,
                    and market-cap presets for Large Cap, Mid Cap, Small Cap, and Micro Cap.
                </p>
            </div>
            <div class="help-card">
                <h4>Multi-Select Screening</h4>
                <p>
                    Sector selection is multi-select: choosing several sectors includes stocks from any selected sector.
                    Search, market-cap presets, and the other screening controls refine the already-loaded universe
                    locally where possible, avoiding unnecessary repeated backend requests.
                </p>
            </div>
            <div class="help-card">
                <h4>Select, Analyze & Compare</h4>
                <p>
                    Selecting a stock makes it the active stock for analysis and also adds it to the Compare Stocks list.
                    The user can remove it from the comparison list later. Up to four stocks can be staged for comparison,
                    and the selected stock can be opened in the individual analysis view.
                </p>
            </div>
            <div class="help-card">
                <h4>Individual Stock Analysis</h4>
                <p>
                    The analysis view presents company summary data, valuation ratios, profitability, financial health,
                    growth metrics, historical financial statements, and valuation/performance trend charts where source
                    data is available. Debt / Equity is included as a core financial-health metric and as a screening field.
                </p>
            </div>
            <div class="help-card">
                <h4>Data Sources</h4>
                <p>
                    Screener is the primary Indian fundamental-data source for company financials and ratios. Yahoo
                    market data is used as supplemental market data where appropriate, including Forward P/E and Beta.
                    Values that are not meaningful for a particular financial business are displayed as
                    <strong>N/M — Not Meaningful</strong> rather than as misleading dashes.
                </p>
            </div>
            <div class="help-card">
                <h4>Data Notes & Missing Values</h4>
                <p>
                    A missing value means the relevant source did not provide a usable value; it is not silently replaced
                    with an invented estimate. The analysis page keeps Data Notes at the bottom of the page so they do not
                    interrupt the financial-statement reading flow.
                </p>
            </div>
            <div class="help-card">
                <h4>Comparison View</h4>
                <p>
                    The comparison page presents the selected stocks side by side using the same fundamental data model.
                    Debt / Equity is included alongside the other core valuation, profitability, growth, and financial-health
                    metrics, with consistent table dimensions and source-aware missing-value treatment.
                </p>
            </div>
            <div class="help-card">
                <h4>Filter Performance & Stability</h4>
                <p>
                    The stock selector avoids mutation-observer feedback loops and repeated full-page DOM rebuilds.
                    Quick filters are designed to operate against the loaded universe without continuously recalculating
                    the backend universe, keeping refreshes and filter interactions responsive.
                </p>
            </div>
        </div>`;

    // Remove the obsolete Stock Analysis card from the Future / Planned section.
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
