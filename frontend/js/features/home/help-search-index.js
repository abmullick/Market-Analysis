/**
 * Level 1 client-side Smart Search index for the Help & Methodology page.
 * Purely local — no AI, no network calls, no external search service.
 *
 * Each entry describes a searchable Help section / card / accordion item.
 * Targets are resolved at runtime from the existing help.html DOM
 * (accordion items by .metric-name text, cards by <h4> text, sections by heading text),
 * so no IDs had to be injected into the existing markup.
 */

export const HELP_SEARCH_INDEX = [
    // ── Mutual Fund Analysis (help cards) ─────────────────────────────
    {
        id: "mf-fund-ranking",
        type: "card",
        heading: "Fund Ranking",
        sectionHeading: "Mutual Fund Analysis",
        keywords: ["ranking", "rank", "score", "presets", "weights", "category", "mutual fund"],
        aliases: ["rank funds", "fund ranks", "best overall", "highest returns", "lowest risk", "best consistency"],
    },
    {
        id: "mf-category-relative",
        type: "card",
        heading: "Category-Relative Analysis",
        sectionHeading: "Mutual Fund Analysis",
        keywords: ["percentile", "peers", "ordinal", "position", "category", "peer comparison"],
        aliases: ["peer comparison", "category position", "percentile rank"],
    },
    {
        id: "mf-fund-comparison",
        type: "card",
        heading: "Fund Comparison",
        sectionHeading: "Mutual Fund Analysis",
        keywords: ["compare", "comparison", "side-by-side", "overlay", "charts"],
        aliases: ["compare funds", "side by side comparison"],
    },
    {
        id: "mf-fund-details",
        type: "card",
        heading: "Fund Details",
        sectionHeading: "Mutual Fund Analysis",
        keywords: ["nav", "sharpe", "sortino", "volatility", "drawdown", "holdings", "detail"],
        aliases: ["fund page", "fund detail modal"],
    },
    {
        id: "mf-top-3",
        type: "card",
        heading: "Top 3 Highlighted Funds",
        sectionHeading: "Mutual Fund Analysis",
        keywords: ["top 3", "top funds", "podium", "highlight", "why"],
        aliases: ["best funds", "top three", "why button"],
    },
    {
        id: "mf-how-ranking-works",
        type: "card",
        heading: "How Ranking Works",
        sectionHeading: "Mutual Fund Analysis",
        keywords: ["weights", "metric groups", "preset", "custom criteria", "performance", "risk-adjusted", "consistency"],
        aliases: ["ranking methodology", "weightage", "how ranking calculated"],
    },
    {
        id: "mf-why-ranks-here",
        type: "card",
        heading: "Why This Fund Ranks Here",
        sectionHeading: "Mutual Fund Analysis",
        keywords: ["strengths", "trade-offs", "tradeoffs", "component scores", "why", "explanation"],
        aliases: ["why this fund", "fund strengths", "trade-offs explained"],
    },
    {
        id: "mf-screening-filters",
        type: "card",
        heading: "Screening & Filters",
        sectionHeading: "Mutual Fund Analysis",
        keywords: ["aum", "filter", "filters", "chips", "fund age", "plan", "option type", "screening"],
        aliases: ["filters", "fund filters", "screen funds"],
    },
    {
        id: "mf-methodology",
        type: "card",
        heading: "Methodology",
        sectionHeading: "Mutual Fund Analysis",
        keywords: ["returns", "nav", "cagr", "risk", "standard deviation", "252", "normalize", "inverted", "formula"],
        aliases: ["calculation methodology", "how returns are calculated", "how are returns calculated"],
    },


    // ── Metrics Reference (accordion items) ───────────────────────────
    {
        id: "metric-1y-return",
        type: "metric",
        heading: "1Y Return",
        keywords: ["return", "1y", "one year", "simple return", "nav", "performance"],
        aliases: ["annual return", "yearly return", "1 year return", "how are returns calculated"],
    },
    {
        id: "metric-3y-cagr",
        type: "metric",
        heading: "3Y CAGR",
        keywords: ["cagr", "compound annual growth rate", "annualized", "3y", "three year", "growth", "nav"],
        aliases: ["compounded annual growth", "annualised return", "compounded return", "how does cagr work", "how is cagr calculated"],
    },
    {
        id: "metric-5y-cagr",
        type: "metric",
        heading: "5Y CAGR",
        keywords: ["cagr", "compound annual growth rate", "annualized", "5y", "five year", "growth", "long-term"],
        aliases: ["compounded annual growth", "annualised return", "five year cagr"],
    },
    {
        id: "metric-10y-cagr",
        type: "metric",
        heading: "10Y CAGR",
        keywords: ["cagr", "compound annual growth rate", "annualized", "10y", "ten year", "growth", "long-tenured"],
        aliases: ["compounded annual growth", "annualised return", "ten year cagr"],
    },
    {
        id: "metric-sharpe",
        type: "metric",
        heading: "Sharpe Ratio",
        keywords: ["sharpe", "risk-adjusted", "risk adjusted", "excess return", "volatility", "ratio"],
        aliases: ["risk adjusted return", "how does risk-adjusted return work", "reward to variability", "what is sharpe ratio"],
    },
    {
        id: "metric-sortino",
        type: "metric",
        heading: "Sortino Ratio",
        keywords: ["sortino", "downside", "risk-adjusted", "ratio", "downside deviation"],
        aliases: ["downside risk ratio", "what is sortino ratio"],
    },
    {
        id: "metric-volatility",
        type: "metric",
        heading: "Annualized Volatility",
        keywords: ["volatility", "standard deviation", "risk", "252", "annualized", "sd"],
        aliases: ["std dev", "standard deviation", "how is volatility calculated"],
    },
    {
        id: "metric-max-drawdown",
        type: "metric",
        heading: "Maximum Drawdown",
        keywords: ["drawdown", "peak", "trough", "loss", "decline", "recovery"],
        aliases: ["mdd", "max drawdown", "peak to trough", "biggest loss"],
    },
    {
        id: "metric-downside-deviation",
        type: "metric",
        heading: "Downside Deviation",
        keywords: ["downside", "deviation", "loss", "negative returns", "risk"],
        aliases: ["downside risk", "downside std dev"],
    },
    {
        id: "metric-1y-rolling-consistency",
        type: "metric",
        heading: "1Y Rolling Consistency",
        keywords: ["rolling", "consistency", "positive", "windows", "rolling return", "cagr"],
        aliases: ["rolling returns", "what does rolling return mean", "consistency metric"],
    },
    {
        id: "metric-overall-score",
        type: "metric",
        heading: "Overall Score",
        keywords: ["score", "overall", "ranking", "0-100", "weighted", "total score"],
        aliases: ["total score", "ranking score", "final score"],
    },
    {
        id: "metric-normalized-score",
        type: "metric",
        heading: "Normalized Metric Score",
        keywords: ["normalization", "normalized", "min", "max", "score", "invert", "lower is better", "0-100"],
        aliases: ["min-max normalization", "score inversion", "how is score calculated"],
    },
    {
        id: "metric-percentile-rank",
        type: "metric",
        heading: "Percentile Rank",
        keywords: ["percentile", "category", "peers", "relative", "position"],
        aliases: ["how are percentiles calculated", "percentile formula"],
    },
    {
        id: "metric-ordinal-rank",
        type: "metric",
        heading: "Ordinal Rank",
        keywords: ["rank", "ordinal", "1st", "2nd", "3rd", "position", "peers"],
        aliases: ["ordinal position", "fund rank number"],
    },


    // ── Using Metrics in Fund Details (accordion items) ───────────────
    {
        id: "usage-performance-metrics",
        type: "metric",
        heading: "Performance Metrics Section",
        keywords: ["performance", "kpi", "fund details", "card grid", "metrics"],
        aliases: ["fund details performance", "performance card"],
    },
    {
        id: "usage-rolling-consistency",
        type: "metric",
        heading: "Rolling Return Consistency",
        keywords: ["rolling", "consistency", "windows", "1y", "3y", "5y", "positive"],
        aliases: ["rolling returns", "rolling return chart"],
    },
    {
        id: "usage-category-relative",
        type: "metric",
        heading: "Category Relative Analysis",
        keywords: ["category", "percentile", "position", "peers", "ordinal"],
        aliases: ["category position", "peer position"],
    },
    {
        id: "usage-drawdown-analysis",
        type: "metric",
        heading: "Drawdown Analysis",
        keywords: ["drawdown", "chart", "peak", "trough", "recovery", "resilience"],
        aliases: ["drawdown chart", "recovery time"],
    },

    // ── Using Metrics in Comparison (accordion items) ─────────────────
    {
        id: "comparison-metrics-table",
        type: "metric",
        heading: "Side-by-Side Metrics Table",
        keywords: ["comparison", "table", "side-by-side", "metrics", "raw values"],
        aliases: ["comparison table", "metrics table"],
    },
    {
        id: "comparison-risk-return",
        type: "metric",
        heading: "Risk-Return Profile",
        keywords: ["risk-return", "scatter", "quadrant", "efficiency", "return vs risk"],
        aliases: ["risk return scatter", "risk reward chart"],
    },
    {
        id: "comparison-drawdown",
        type: "metric",
        heading: "Drawdown Comparison",
        keywords: ["drawdown", "comparison", "overlay", "peak", "loss"],
        aliases: ["compare drawdowns", "drawdown overlay"],
    },
    {
        id: "comparison-rolling-returns",
        type: "metric",
        heading: "Rolling Returns Comparison",
        keywords: ["rolling", "comparison", "overlay", "cagr", "stability"],
        aliases: ["compare rolling returns", "rolling comparison chart"],
    },

    // ── Data Transparency & Freshness (help cards) ────────────────────
    {
        id: "data-as-of",
        type: "card",
        heading: "Data as of",
        sectionHeading: "Data Transparency & Freshness",
        keywords: ["data as of", "nav_date", "freshness", "date", "latest nav"],
        aliases: ["data date", "how fresh is the data", "data freshness"],
    },
    {
        id: "data-history-coverage",
        type: "card",
        heading: "History from / Coverage",
        sectionHeading: "Data Transparency & Freshness",
        keywords: ["history", "coverage", "data points", "range", "10y"],
        aliases: ["data coverage", "history range"],
    },
    {
        id: "data-calculation-periods",
        type: "card",
        heading: "Calculation Periods",
        sectionHeading: "Data Transparency & Freshness",
        keywords: ["period", "kpi", "1y", "3y", "5y", "full history", "labels"],
        aliases: ["calculation window", "lookback period"],
    },
    {
        id: "data-not-available",
        type: "card",
        heading: "Not Available — Why?",
        sectionHeading: "Data Transparency & Freshness",
        keywords: ["not available", "insufficient history", "insufficient data", "unavailable", "tooltip", "missing"],
        aliases: ["why is data missing", "na values"],
    },
    {
        id: "data-comparison-period",
        type: "card",
        heading: "Comparison Period",
        sectionHeading: "Data Transparency & Freshness",
        keywords: ["comparison", "period", "overlap", "common window", "shorter histories"],
        aliases: ["common period", "overlap period"],
    },
    {
        id: "data-no-freshness-threshold",
        type: "card",
        heading: "No Invented Freshness Threshold",
        sectionHeading: "Data Transparency & Freshness",
        keywords: ["stale", "freshness threshold", "warning", "green dot"],
        aliases: ["stale data"],
    },

    // ── Other sections ────────────────────────────────────────────────
    {
        id: "stock-screening",
        type: "card",
        heading: "Screening",
        sectionHeading: "Stock Selection",
        keywords: ["stocks", "screening", "market cap", "sector", "pe ratio", "pb ratio", "roe", "debt-to-equity", "fundamental"],
        aliases: ["stock screener", "stock filters"],
    },
    {
        id: "stock-ranking",
        type: "card",
        heading: "Ranking",
        sectionHeading: "Stock Selection",
        keywords: ["stocks", "ranking", "scoring", "strategies", "deterministic"],
        aliases: ["stock ranking", "stock strategies"],
    },
    {
        id: "portfolio-upload",
        type: "card",
        heading: "Upload & Parse",
        sectionHeading: "Portfolio Analysis",
        keywords: ["portfolio", "upload", "csv", "excel", "holdings", "quantities", "invested value"],
        aliases: ["import portfolio", "upload holdings"],
    },
    {
        id: "portfolio-analysis",
        type: "card",
        heading: "Analysis",
        sectionHeading: "Portfolio Analysis",
        keywords: ["portfolio", "weights", "sector allocation", "concentration", "diversification"],
        aliases: ["portfolio allocation", "portfolio analysis"],
    },
    {
        id: "data-sources-caching",
        type: "section",
        heading: "Data Sources & Caching",
        keywords: ["mfapi", "tigzig", "cache", "caching", "ttl", "data sources", "lookback", "provider"],
        aliases: ["where does data come from", "data providers"],
    },
    {
        id: "architecture",
        type: "section",
        heading: "Architecture",
        keywords: ["architecture", "fastapi", "layers", "modules", "ai", "groq", "frontend", "backend"],
        aliases: ["how is the app built", "tech stack"],
    },
    {
        id: "about",
        type: "section",
        heading: "About",
        keywords: ["about", "platform", "purpose", "disclaimer", "advice", "education"],
        aliases: ["what is market analysis"],
    },
    {
        id: "contact",
        type: "section",
        heading: "Contact",
        keywords: ["contact", "email", "owner", "support", "questions"],
        aliases: ["who made this", "get in touch"],
    },
    {
        id: "feedback",
        type: "section",
        heading: "Feedback",
        keywords: ["feedback", "suggestion", "bug report", "feature request"],
        aliases: ["report a bug", "give feedback"],
    },
];

const STOP_WORDS = new Set([
    "a", "an", "the", "is", "are", "was", "were", "do", "does", "did", "how", "what",
    "why", "when", "which", "of", "in", "on", "for", "to", "and", "or", "it", "this",
    "that", "i", "my", "me", "can", "be", "with", "there",
]);

/** Normalize a query or text: lowercase, strip punctuation, collapse whitespace. */
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
    return tokenize(value).filter((t) => !STOP_WORDS.has(t));
}

// ── DOM target resolution ─────────────────────────────────────────────

function findAccordionItem(heading) {
    const wanted = normalizeText(heading);
    return [...document.querySelectorAll(".metric-item")].find((item) => {
        const name = item.querySelector(".metric-name");
        return name && normalizeText(name.textContent) === wanted;
    });
}

function findCard(heading, sectionHeading) {
    const wanted = normalizeText(heading);
    const sections = [...document.querySelectorAll(".help-section")];
    const parent = sectionHeading
        ? sections.find((s) => {
              const h = s.querySelector("h2, h3");
              return h && normalizeText(h.textContent) === normalizeText(sectionHeading);
          })
        : null;
    const scope = parent || document;
    return [...scope.querySelectorAll(".help-card")].find((card) => {
        const h = card.querySelector("h4");
        return h && normalizeText(h.textContent) === wanted;
    });
}

function findSection(heading) {
    const wanted = normalizeText(heading);
    return [...document.querySelectorAll(".help-section")].find((section) => {
        const h = section.querySelector("h2, h3");
        return h && normalizeText(h.textContent) === wanted;
    });
}

/** Resolve an index entry to its DOM element on the current page (or null). */
export function resolveTarget(entry) {
    if (entry.type === "metric") return findAccordionItem(entry.heading) || null;
    if (entry.type === "card") return findCard(entry.heading, entry.sectionHeading) || null;
    return findSection(entry.heading) || null;
}

/** Extract a short text snippet from a resolved DOM target. */
function snippetFor(element) {
    if (!element) return "";
    const text = element.textContent.replace(/\s+/g, " ").trim();
    return text.length > 220 ? `${text.slice(0, 220)}…` : text;
}

// ── Ranking ───────────────────────────────────────────────────────────

const MIN_SCORE = 12;
const MAX_RESULTS = 6;

function scoreEntry(entry, tokens, normalizedQuery, text) {
    let score = 0;
    const normalizedTitle = normalizeText(entry.heading);

    // Title matches (strongest signal)
    if (normalizedQuery === normalizedTitle) {
        score += 100;
    } else if (normalizedQuery && normalizedTitle.startsWith(normalizedQuery)) {
        score += 70;
    } else if (normalizedQuery && normalizedTitle.includes(normalizedQuery)) {
        score += 55;
    } else {
        const titleTokens = meaningfulTokens(normalizedTitle);
        if (titleTokens.length) {
            const overlap = titleTokens.filter((t) => tokens.includes(t)).length;
            score += (overlap / titleTokens.length) * 40;
        }
    }

    // Keywords: exact token hit, or multi-word keyword present in the query phrase
    for (const keyword of entry.keywords || []) {
        const nk = normalizeText(keyword);
        if (!nk) continue;
        if (nk.includes(" ")) {
            if (normalizedQuery.includes(nk)) score += 45;
        } else if (tokens.includes(nk)) {
            score += 35;
        } else if (normalizedQuery && nk.startsWith(normalizedQuery) && normalizedQuery.length >= 3) {
            score += 18;
        }
    }

    // Aliases: natural-language variants of the keyword set
    for (const alias of entry.aliases || []) {
        const na = normalizeText(alias);
        if (!na) continue;
        if (normalizedQuery.includes(na) || na.includes(normalizedQuery)) score += 40;
    }

    // Weak signal: whole-token occurrence inside the section text
    if (text) {
        const haystack = ` ${normalizeText(text)} `;
        for (const token of tokens) {
            if (haystack.includes(` ${token} `)) score += 4;
        }
    }

    return score;
}

/**
 * Central client-side search. Pure function over the index + current DOM.
 * Returns a ranked list of { entry, score, snippet } (max 6 results).
 */
export function searchHelp(rawQuery) {
    const normalizedQuery = normalizeText(rawQuery);
    const tokens = meaningfulTokens(rawQuery);
    if (!normalizedQuery || !tokens.length) return [];

    const results = [];
    for (const entry of HELP_SEARCH_INDEX) {
        const target = resolveTarget(entry);
        // Skip entries whose target does not exist on the current page.
        if (!target) continue;

        const text = snippetFor(target);
        const score = scoreEntry(entry, tokens, normalizedQuery, text);
        if (score >= MIN_SCORE) results.push({ entry, score, snippet: text });
    }

    results.sort((a, b) => b.score - a.score || a.entry.id.localeCompare(b.entry.id));
    return results.slice(0, MAX_RESULTS);
}
