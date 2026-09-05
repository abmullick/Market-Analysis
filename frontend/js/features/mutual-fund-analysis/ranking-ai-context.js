const MAX_TOP_FUNDS = 10;
const MAX_BOTTOM_FUNDS = 5;
const TARGET_CONTEXT_BYTES = 12000;
const MAX_CONTEXT_BYTES = 16000;

const FUND_FIELDS = ["rank", "scheme_name", "category", "overall_score"];
const METRIC_FIELDS = ["criterion", "weight", "score", "raw_value"];

function isDefined(value) {
    return value !== undefined && value !== null;
}

function compactMetricScores(criteriaScores) {
    if (!Array.isArray(criteriaScores)) return undefined;
    const scores = criteriaScores.map(score => {
        if (!score || typeof score !== "object") return null;
        const compact = {};
        METRIC_FIELDS.forEach(key => {
            if (isDefined(score[key])) compact[key] = score[key];
        });
        return Object.keys(compact).length ? compact : null;
    }).filter(Boolean);
    return scores.length ? scores : undefined;
}

function compactFund(fund, includeMetrics) {
    if (!fund || typeof fund !== "object") return null;
    const compact = {};
    FUND_FIELDS.forEach(key => {
        if (isDefined(fund[key])) compact[key] = fund[key];
    });
    if (includeMetrics) {
        const metricScores = compactMetricScores(fund.criteria_scores);
        if (metricScores) compact.metric_scores = metricScores;
    }
    return Object.keys(compact).length ? compact : null;
}

function compactConfiguration(configuration) {
    if (!configuration || typeof configuration !== "object") {
        throw new Error("A successful ranking configuration is required.");
    }
    return {
        categories: Array.isArray(configuration.categories) ? [...configuration.categories] : [],
        screening_filters: Array.isArray(configuration.screening_filters)
            ? configuration.screening_filters.map(filter => ({ ...filter }))
            : [],
        criteria: Array.isArray(configuration.criteria)
            ? configuration.criteria.map(criteria => ({ ...criteria }))
            : [],
        auto_renormalize: configuration.auto_renormalize === true,
    };
}

function byteLength(serialized) {
    return new TextEncoder().encode(serialized).length;
}

export function serializeRankingAIContext(context) {
    const serialized = JSON.stringify(context);
    const bytes = byteLength(serialized);
    if (bytes > MAX_CONTEXT_BYTES) {
        throw new Error(`Ranking AI context exceeds the ${MAX_CONTEXT_BYTES}-byte safety limit.`);
    }
    return { serialized, bytes };
}

export function buildRankingAIContext({ rankingConfiguration, rankings, metadata = {} }) {
    if (!Array.isArray(rankings) || rankings.length === 0) {
        throw new Error("A successful ranking is required for ranking insights.");
    }

    const configuration = compactConfiguration(rankingConfiguration);
    const validRankings = rankings.filter(fund => fund && fund.overall_score != null);
    const baseSummary = {
        total_funds: validRankings.length,
        displayed_funds: rankings.length,
        eligible_funds: isDefined(metadata.eligible_funds) ? metadata.eligible_funds : validRankings.length,
        matching_funds: isDefined(metadata.matching_funds) ? metadata.matching_funds : undefined,
    };
    Object.keys(baseSummary).forEach(key => {
        if (!isDefined(baseSummary[key])) delete baseSummary[key];
    });

    const build = (includeMetrics, includeBottom) => {
        const context = {
            ranking_configuration: configuration,
            ranking_summary: {
                ...baseSummary,
                categories: [...configuration.categories],
            },
            top_funds: validRankings.slice(0, MAX_TOP_FUNDS)
                .map(fund => compactFund(fund, includeMetrics)).filter(Boolean),
        };
        if (includeBottom) {
            context.bottom_funds = validRankings.slice(-MAX_BOTTOM_FUNDS)
                .map(fund => compactFund(fund, includeMetrics)).filter(Boolean);
        }
        return context;
    };

    const candidates = [
        [true, true],
        [true, false],
        [false, false],
    ];
    let lastContext = null;
    for (const [includeMetrics, includeBottom] of candidates) {
        const context = build(includeMetrics, includeBottom);
        lastContext = context;
        try {
            serializeRankingAIContext(context);
            return context;
        } catch (error) {
            if (!(error instanceof Error) || !error.message.includes("safety limit")) throw error;
        }
    }

    serializeRankingAIContext(lastContext);
    return lastContext;
}

export const RANKING_AI_CONTEXT_LIMITS = Object.freeze({
    maxTopFunds: MAX_TOP_FUNDS,
    maxBottomFunds: MAX_BOTTOM_FUNDS,
    targetBytes: TARGET_CONTEXT_BYTES,
    maxBytes: MAX_CONTEXT_BYTES,
});
