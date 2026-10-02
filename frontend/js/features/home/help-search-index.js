/**
 * Client-side Help & Methodology search.
 *
 * The Help page contains a mix of static and dynamically rendered cards.
 * Search targets are therefore discovered from the live DOM instead of
 * depending on duplicated heading strings in a static index. This prevents
 * search links from breaking when a Help card heading is renamed or expanded.
 */

export const HELP_SEARCH_INDEX = [];

const STOP_WORDS = new Set([
    "a", "an", "the", "is", "are", "was", "were", "do", "does", "did", "how", "what",
    "why", "when", "which", "of", "in", "on", "for", "to", "and", "or", "it", "this",
    "that", "i", "my", "me", "can", "be", "with", "there",
]);

const STOCK_FORMULA_HEADINGS = new Set([
    "P/E (Price-to-Earnings Ratio)",
    "Forward P/E",
    "P/B (Price-to-Book Ratio)",
    "Price / Sales (P/S)",
    "PEG (Price/Earnings-to-Growth Ratio)",
    "EV / EBITDA",
    "EV / Revenue",
    "Dividend Yield",
    "Payout Ratio",
    "ROE (Return on Equity)",
    "ROA (Return on Assets)",
    "Gross Margin",
    "Operating Margin",
    "Net Margin",
    "Debt / Equity (D/E)",
    "Current Ratio",
    "Quick Ratio",
    "Beta",
    "Revenue Growth",
    "Profit Growth",
    "EPS Growth",
    "Revenue CAGR",
    "Profit CAGR",
    "EPS CAGR",
    "FCF CAGR",
    "Operating Margin Change",
]);

function metricChevron() {
    return `<svg class="metric-chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="6 9 12 15 18 9"></polyline></svg>`;
}

function wireMetricAccordion(item) {
    const trigger = item.querySelector(".metric-trigger");
    if (!trigger || trigger.dataset.accordionWired === "true") return;

    trigger.dataset.accordionWired = "true";
    trigger.setAttribute("aria-expanded", "false");
    trigger.addEventListener("click", () => {
        const isOpen = item.classList.toggle("open");
        trigger.setAttribute("aria-expanded", String(isOpen));
    });
}

/**
 * Stock formula explanations use the same expandable metric pattern as the
 * Mutual Fund Help page. The stock Help cards are rendered dynamically by
 * help.js, so this enhancer watches the Help DOM and converts only the
 * individual formula/metric cards into the existing .metric-item pattern.
 */
function enhanceStockFormulaCards() {
    const section = [...document.querySelectorAll(".help-section")].find((candidate) => {
        const heading = candidate.querySelector("h2, h3");
        return heading && normalizeText(heading.textContent) === normalizeText("Stock Analysis");
    });
    if (!section) return;

    section.querySelectorAll(".metric-item").forEach(wireMetricAccordion);

    [...section.querySelectorAll(".help-card")].forEach((card) => {
        const headingEl = card.querySelector("h4");
        const heading = headingEl?.textContent?.trim();
        if (!heading || !STOCK_FORMULA_HEADINGS.has(heading)) return;

        const bodyHtml = card.querySelector("p")?.innerHTML || "";
        const item = document.createElement("div");
        item.className = "metric-item";
        item.innerHTML = `
            <button class="metric-trigger" type="button" aria-expanded="false">
                <span class="metric-name">${heading}</span>
                <span class="metric-meta">Formula • Calculation • Interpretation</span>
                ${metricChevron()}
            </button>
            <div class="metric-panel">
                <div class="metric-panel-inner">
                    <div class="metric-block">
                        <h4>Explanation &amp; Formula</h4>
                        <p>${bodyHtml}</p>
                    </div>
                </div>
            </div>
        `;

        card.replaceWith(item);
        wireMetricAccordion(item);
    });
}

function installStockFormulaEnhancer() {
    const start = () => {
        enhanceStockFormulaCards();
        const observer = new MutationObserver(() => enhanceStockFormulaCards());
        if (document.body) {
            observer.observe(document.body, { childList: true, subtree: true });
        }
    };

    if (document.body) start();
    else document.addEventListener("DOMContentLoaded", start, { once: true });
}

export function normalizeText(value) {
    return String(value || "")
        // Treat common financial notation as the same search term whether the
        // user types P/E, PE, Debt/Equity, etc. The Help content uses both
        // slash notation and word notation in different places.
        .replace(/\bp\s*\/\s*e\b/gi, " pe ")
        .replace(/\bp\s*\/\s*b\b/gi, " pb ")
        .replace(/\bev\s*\/\s*ebitda\b/gi, " ev ebitda ")
        .replace(/\bev\s*\/\s*revenue\b/gi, " ev revenue ")
        .replace(/\bdebt\s*\/\s*equity\b/gi, " debt equity ")
        .toLowerCase()
        .replace(/[^a-z0-9\s-]/g, " ")
        .replace(/\s+/g, " ")
        .trim();
}

function tokenize(value) {
    return normalizeText(value).split(" ").filter(Boolean);
}

function meaningfulTokens(value) {
    return tokenize(value).filter((token) => !STOP_WORDS.has(token));
}

function slugify(value) {
    return normalizeText(value).replace(/\s+/g, "-").slice(0, 80);
}

function buildDomIndex() {
    const entries = [];

    document.querySelectorAll(".help-section").forEach((section, sectionIndex) => {
        const sectionHeading = section.querySelector("h2, h3")?.textContent?.trim();
        if (sectionHeading) {
            entries.push({
                id: `section-${slugify(sectionHeading) || sectionIndex}`,
                type: "section",
                heading: sectionHeading,
                sectionHeading: "",
                keywords: [],
                aliases: [],
                target: section,
            });
        }

        section.querySelectorAll(".help-card").forEach((card, cardIndex) => {
            const heading = card.querySelector("h4")?.textContent?.trim();
            if (!heading) return;
            entries.push({
                id: `card-${slugify(sectionHeading)}-${slugify(heading) || cardIndex}`,
                type: "card",
                heading,
                sectionHeading: sectionHeading || "",
                keywords: [],
                aliases: [],
                target: card,
            });
        });

        section.querySelectorAll(".metric-item").forEach((item, metricIndex) => {
            const heading = item.querySelector(".metric-name")?.textContent?.trim();
            if (!heading) return;
            entries.push({
                id: `metric-${slugify(heading) || metricIndex}`,
                type: "metric",
                heading,
                sectionHeading: sectionHeading || "",
                keywords: [],
                aliases: [],
                target: item,
            });
        });
    });

    return entries;
}

/** Resolve an index entry to its current DOM element. */
export function resolveTarget(entry) {
    if (entry?.target && document.contains(entry.target)) return entry.target;

    if (entry?.type === "metric") {
        const wanted = normalizeText(entry.heading);
        return [...document.querySelectorAll(".metric-item")].find((item) => {
            const name = item.querySelector(".metric-name");
            return name && normalizeText(name.textContent) === wanted;
        }) || null;
    }

    if (entry?.type === "card") {
        const wanted = normalizeText(entry.heading);
        const sectionWanted = normalizeText(entry.sectionHeading);
        const scope = sectionWanted
            ? [...document.querySelectorAll(".help-section")].find((section) => {
                  const heading = section.querySelector("h2, h3");
                  return heading && normalizeText(heading.textContent) === sectionWanted;
              })
            : document;
        return [...scope.querySelectorAll(".help-card")].find((card) => {
            const heading = card.querySelector("h4");
            return heading && normalizeText(heading.textContent) === wanted;
        }) || null;
    }

    const wanted = normalizeText(entry?.heading);
    return [...document.querySelectorAll(".help-section")].find((section) => {
        const heading = section.querySelector("h2, h3");
        return heading && normalizeText(heading.textContent) === wanted;
    }) || null;
}

function snippetFor(element) {
    if (!element) return "";
    const text = element.textContent.replace(/\s+/g, " ").trim();
    return text.length > 220 ? `${text.slice(0, 220)}…` : text;
}

const MIN_SCORE = 10;
const MAX_RESULTS = 6;

function scoreEntry(entry, tokens, normalizedQuery) {
    const target = resolveTarget(entry);
    if (!target) return 0;

    const heading = normalizeText(entry.heading);
    const body = normalizeText(target.textContent);
    const combined = `${heading} ${body}`;
    let score = 0;

    if (normalizedQuery === heading) score += 120;
    else if (heading.startsWith(normalizedQuery)) score += 90;
    else if (heading.includes(normalizedQuery)) score += 70;

    if (body.includes(normalizedQuery)) score += 65;

    const titleTokens = meaningfulTokens(heading);
    const bodyTokens = new Set(tokenize(combined));
    const titleOverlap = titleTokens.filter((token) => tokens.includes(token)).length;
    const bodyOverlap = tokens.filter((token) => bodyTokens.has(token)).length;

    if (titleTokens.length) score += (titleOverlap / titleTokens.length) * 45;
    score += bodyOverlap * 24;

    // A short financial term such as PEG, PE, ROE, ROA, Beta, CAGR, YTM,
    // DV01, etc. is a valid search intent on its own. Give an exact token
    // match enough weight to pass the navigation threshold used by help.js.
    // This is deliberately token-based so "PE" does not accidentally match
    // unrelated words such as "price" or "performance".
    if (tokens.length === 1 && bodyTokens.has(tokens[0])) {
        score += 60;
    }

    if (tokens.length === 1 && titleTokens.includes(tokens[0])) {
        score += 45;
    }

    // Give a strong boost when the query is a natural phrase whose meaningful
    // tokens are all present in the card, e.g. "market cap min" or
    // "debt / equity".
    const phraseTokens = meaningfulTokens(normalizedQuery);
    if (phraseTokens.length >= 2 && phraseTokens.every((token) => bodyTokens.has(token))) {
        score += 30;
    }

    return score;
}

/**
 * Search the live Help DOM. The index is rebuilt on each search so it also
 * works when Help cards are inserted/replaced after page load.
 */
export function searchHelp(query) {
    const normalizedQuery = normalizeText(query);
    if (!normalizedQuery) return [];

    const tokens = meaningfulTokens(normalizedQuery);
    const entries = buildDomIndex();

    const results = entries
        .map((entry) => ({
            entry,
            score: scoreEntry(entry, tokens, normalizedQuery),
            snippet: snippetFor(resolveTarget(entry)),
        }))
        .filter((result) => result.score >= MIN_SCORE)
        .sort((a, b) => b.score - a.score || a.entry.heading.localeCompare(b.entry.heading))
        .slice(0, MAX_RESULTS);

    return results;
}

installStockFormulaEnhancer();
