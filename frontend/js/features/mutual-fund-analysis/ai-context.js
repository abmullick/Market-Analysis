const MAX_PEERS = 5;
const TARGET_CONTEXT_BYTES = 12000;
const MAX_CONTEXT_BYTES = 16000;
const MAX_HOLDINGS = 5;
const MAX_ALLOCATION_ENTRIES = 8;

const FUND_FIELDS = [
    ["scheme_name", "scheme_name"],
    ["category", "category"],
    ["sub_category", "sub_category"],
    ["amc", "amc"],
    ["aum_cr", "aum_cr"],
    ["total_aum_cr", "total_aum_cr"],
    ["expense_ratio", "expense_ratio"],
    ["fund_age_years", "fund_age_years"],
    ["first_nav_date", "first_nav_date"],
];

const PERFORMANCE_FIELDS = [
    ["one_year_return", "one_year_return"],
    ["three_year_cagr", "three_year_cagr"],
    ["five_year_cagr", "five_year_cagr"],
    ["ten_year_cagr", "ten_year_cagr"],
];

const RISK_FIELDS = [
    ["annualized_volatility", "annualized_volatility"],
    ["sharpe_ratio", "sharpe_ratio"],
    ["sortino_ratio", "sortino_ratio"],
    ["maximum_drawdown", "maximum_drawdown"],
    ["downside_deviation", "downside_deviation"],
];

const RANKING_FIELDS = [
    ["rank", "rank"],
    ["total_funds", "total_funds"],
    ["percentile", "percentile"],
    ["overall_score", "overall_score"],
];

function isDefined(value) {
    return value !== undefined && value !== null;
}

function addDefined(target, source, fields) {
    fields.forEach(([outputKey, sourceKey]) => {
        if (isDefined(source?.[sourceKey])) {
            target[outputKey] = source[sourceKey];
        }
    });
}

function pickConsistency(detail) {
    const consistency = detail?.rolling_return_consistency;
    if (!consistency || typeof consistency !== "object" || Array.isArray(consistency)) {
        return undefined;
    }

    const oneYear = consistency["1Y"];
    if (!oneYear || typeof oneYear !== "object" || Array.isArray(oneYear)) {
        return undefined;
    }

    const result = {};
    ["positive_pct", "count"].forEach(key => {
        if (isDefined(oneYear[key])) result[key] = oneYear[key];
    });
    return Object.keys(result).length ? { "1Y": result } : undefined;
}

function pickPortfolio(detail) {
    const portfolio = {};
    const allocation = detail?.asset_allocation;
    if (allocation && typeof allocation === "object" && !Array.isArray(allocation)) {
        const entries = Object.entries(allocation).slice(0, MAX_ALLOCATION_ENTRIES);
        if (entries.length) portfolio.asset_allocation = Object.fromEntries(entries);
    }

    const holdings = Array.isArray(detail?.top_holdings) ? detail.top_holdings : [];
    const compactHoldings = holdings.slice(0, MAX_HOLDINGS).map(holding => {
        if (!holding || typeof holding !== "object") return null;
        const item = {};
        if (isDefined(holding.name)) item.name = holding.name;
        else if (isDefined(holding.company)) item.name = holding.company;
        if (isDefined(holding.weight)) item.weight = holding.weight;
        return Object.keys(item).length ? item : null;
    }).filter(Boolean);
    if (compactHoldings.length) portfolio.top_holdings = compactHoldings;

    return Object.keys(portfolio).length ? portfolio : undefined;
}

function pickMetricScores(ranking) {
    if (!Array.isArray(ranking?.criteria_scores)) return undefined;
    const scores = ranking.criteria_scores.map(score => {
        if (!score || typeof score !== "object") return null;
        const item = {};
        ["criterion", "weight", "score", "raw_value"].forEach(key => {
            if (isDefined(score[key])) item[key] = score[key];
        });
        return Object.keys(item).length ? item : null;
    }).filter(Boolean);
    return scores.length ? scores : undefined;
}

function pickCategoryMetrics(categoryAnalysis) {
    if (!Array.isArray(categoryAnalysis?.metrics)) return undefined;
    const metrics = categoryAnalysis.metrics.map(metric => {
        if (!metric || typeof metric !== "object") return null;
        const item = {};
        ["metric", "label", "fund_value", "percentile", "category_count", "higher_is_better", "rank"].forEach(key => {
            if (isDefined(metric[key])) item[key] = metric[key];
        });
        return Object.keys(item).length ? item : null;
    }).filter(Boolean);
    return metrics.length ? metrics : undefined;
}

function pickPreferences(preferences) {
    if (!preferences || typeof preferences !== "object") {
        throw new Error("A ranking configuration is required for AI context.");
    }

    return {
        categories: Array.isArray(preferences.categories) ? [...preferences.categories] : [],
        screening_filters: Array.isArray(preferences.screening_filters)
            ? preferences.screening_filters.map(filter => {
                const item = {};
                ["field", "operator", "value", "value_min", "value_max", "values"].forEach(key => {
                    if (isDefined(filter?.[key])) item[key] = Array.isArray(filter[key]) ? [...filter[key]] : filter[key];
                });
                return item;
            })
            : [],
        criteria: Array.isArray(preferences.criteria)
            ? preferences.criteria.map(criterion => ({
                name: criterion?.name,
                weight: criterion?.weight,
            }))
            : [],
        auto_renormalize: preferences.auto_renormalize === true,
    };
}

function pickFund(detail, includePortfolio, includeSecondaryMetadata) {
    const fund = {};
    addDefined(fund, detail, FUND_FIELDS);

    const performance = {};
    addDefined(performance, detail, PERFORMANCE_FIELDS);
    if (Object.keys(performance).length) fund.performance = performance;

    const risk = {};
    addDefined(risk, detail, RISK_FIELDS);
    if (Object.keys(risk).length) fund.risk = risk;

    const consistency = pickConsistency(detail);
    if (consistency) fund.consistency = consistency;

    if (includePortfolio) {
        const portfolio = pickPortfolio(detail);
        if (portfolio) fund.portfolio = portfolio;
    }

    if (includeSecondaryMetadata) {
        ["nav", "nav_date", "data_start_date", "data_end_date", "data_points"].forEach(key => {
            if (isDefined(detail?.[key])) fund[key] = detail[key];
        });
    }

    return fund;
}

function pickRanking(ranking) {
    const result = {};
    addDefined(result, ranking, RANKING_FIELDS);
    const metricScores = pickMetricScores(ranking);
    if (metricScores) result.metric_scores = metricScores;
    return result;
}

function pickPeers(peers) {
    if (!Array.isArray(peers)) return undefined;
    const compactPeers = peers.slice(0, MAX_PEERS).map(peer => {
        if (!peer || typeof peer !== "object") return null;
        const item = {};
        ["rank", "scheme_name", "name", "overall_score", "score", "key_metric"].forEach(key => {
            if (isDefined(peer[key])) item[key === "scheme_name" ? "name" : key] = peer[key];
        });
        return Object.keys(item).length ? item : null;
    }).filter(Boolean);
    return compactPeers.length ? compactPeers : undefined;
}

function utf8ByteLength(value) {
    return new TextEncoder().encode(value).length;
}

function serializeContext(context) {
    const serialized = JSON.stringify(context);
    const bytes = utf8ByteLength(serialized);
    if (bytes > MAX_CONTEXT_BYTES) {
        throw new Error(`Mutual fund AI context exceeds the ${MAX_CONTEXT_BYTES}-byte safety limit.`);
    }
    return { serialized, bytes };
}

export function buildFundAIContext({ detail, ranking, categoryAnalysis, rankingConfiguration, peers = [] }) {
    if (!detail || typeof detail !== "object") {
        throw new Error("Fund detail is required for AI context.");
    }

    const preferences = pickPreferences(rankingConfiguration);
    const categoryMetrics = pickCategoryMetrics(categoryAnalysis);
    const rankingData = pickRanking(ranking || {});
    const peerData = pickPeers(peers);

    const build = (includePeers, includePortfolio, includeSecondaryMetadata) => {
        const context = {
            selected_fund: pickFund(detail, includePortfolio, includeSecondaryMetadata),
            ranking: rankingData,
            user_preferences: preferences,
        };
        if (categoryMetrics) context.category_analysis = { metrics: categoryMetrics };
        if (includePeers && peerData) context.peers = peerData;
        return context;
    };

    const candidates = [
        [true, true, true],
        [false, true, true],
        [false, false, true],
        [false, false, false],
    ];

    let lastContext = null;
    for (const [includePeers, includePortfolio, includeSecondaryMetadata] of candidates) {
        const context = build(includePeers, includePortfolio, includeSecondaryMetadata);
        lastContext = context;
        try {
            serializeContext(context);
            return context;
        } catch (error) {
            if (!(error instanceof Error) || !error.message.includes("safety limit")) throw error;
        }
    }

    // Serialize once more to preserve the same failure contract if the core is oversized.
    serializeContext(lastContext);
    return lastContext;
}

export function serializeFundAIContext(context) {
    return serializeContext(context);
}

export const AI_CONTEXT_LIMITS = Object.freeze({
    maxPeers: MAX_PEERS,
    targetBytes: TARGET_CONTEXT_BYTES,
    maxBytes: MAX_CONTEXT_BYTES,
});
