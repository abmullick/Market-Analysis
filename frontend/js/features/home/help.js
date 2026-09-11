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

    // Temporary highlight; restartable on repeat navigations.
    target.classList.remove("search-highlight");
    void target.offsetWidth;
    target.classList.add("search-highlight");
    window.setTimeout(() => target.classList.remove("search-highlight"), HIGHLIGHT_DURATION_MS);
}

/**
 * Single central search pipeline used by typing, Enter, suggestion chips,
 * and clearing. No AI, no network — purely local.
 */
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
        // Enter: jump to the top result when it is a strong match,
        // otherwise keep the ranked results displayed.
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
            // Suggested questions run through the exact same search pipeline.
            handleSearch(query, { navigate: true });
        });
    });
}

export function initHelp() {
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
