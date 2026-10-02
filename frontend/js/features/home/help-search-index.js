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

export function normalizeText(value) {
    return String(value || "")
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

function sectionHeadingFor(element) {
    const section = element.closest(".help-section");
    const heading = section?.querySelector("h2, h3");
    return heading?.textContent?.trim() || "";
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

    // Give a strong boost when the query is a natural phrase that appears
    // verbatim in the card, e.g. "market cap min" or "debt / equity".
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
