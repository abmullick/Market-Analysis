// Portfolio Builder — Compact AI Context builder & serializer.
//
// Mirrors the Mutual Fund AI Insights pattern (frontend/js/features/
// mutual-fund-analysis/ai-context.js): the AI payload is a STRICT, bounded
// subset of the deterministic analysis already rendered by renderAnalysis().
//
// Rules
// -----
// - Only decision-useful values are included (fund selection/allocations +
//   portfolio-analysis summary). Raw historical series, full benchmark arrays,
//   full stock tables and other large payloads are NEVER sent.
// - The serialized context is guarded by a strict byte limit (same approach
//   as serializeFundAIContext / ranking context) so it stays small enough for
//   the free Groq usage limits.
// - No financial calculations happen here — values are copied from the
//   deterministic backend result as-is.

const TARGET_CONTEXT_BYTES = 12000;
const MAX_CONTEXT_BYTES = 16000;

const MAX_FUNDS = 40;
const MAX_TOP_STOCKS = 8;
const MAX_DRAWDOWN_EPISODES = 3;
const MAX_CONTRIBUTIONS = 8;

const HEALTH_COMPONENT_KEYS = [
    "return_quality",
    "downside_risk",
    "risk_adjusted_return",
    "concentration",
    "fund_mix",
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

// ---------------------------------------------------------------------------
// Compact pickers — each returns undefined when it has nothing useful to add.
// ---------------------------------------------------------------------------

function compactFund(fund) {
    if (!fund || typeof fund !== "object") return null;
    const item = {};
    [
        ["scheme_code", "scheme_code"],
        ["scheme_name", "scheme_name"],
        ["amc", "amc"],
        ["category", "category"],
        ["allocation", "allocation"],
    ].forEach(([outputKey, sourceKey]) => {
        if (isDefined(fund[sourceKey])) item[outputKey] = fund[sourceKey];
    });
    return Object.keys(item).length ? item : null;
}

function compactFunds(funds) {
    if (!Array.isArray(funds)) return [];
    return funds.slice(0, MAX_FUNDS).map(compactFund).filter(Boolean);
}

function compactHealthScore(health) {
    if (!health || typeof health !== "object") return undefined;
    const item = {};
    addDefined(item, health, [
        ["score", "score"],
        ["score_withheld", "score_withheld"],
        ["withholding_reason", "withholding_reason"],
        ["single_fund_portfolio", "single_fund_portfolio"],
        ["has_legacy_scheme", "has_legacy_scheme"],
    ]);
    if (health.confidence && typeof health.confidence === "object") {
        const confidence = {};
        addDefined(confidence, health.confidence, [
            ["tier", "tier"],
            ["label", "label"],
        ]);
        if (Object.keys(confidence).length) item.confidence = confidence;
    }
    if (health.components && typeof health.components === "object") {
        const components = {};
        HEALTH_COMPONENT_KEYS.forEach((key) => {
            if (isDefined(health.components[key])) components[key] = health.components[key];
        });
        if (Object.keys(components).length) item.components = components;
    }
    if (Array.isArray(health.available_components) && health.available_components.length) {
        item.available_components = health.available_components;
    }
    return Object.keys(item).length ? item : undefined;
}

function compactMetrics(metrics) {
    if (!metrics || typeof metrics !== "object") return undefined;
    const item = {};
    addDefined(item, metrics, [
        ["cagr", "cagr"],
        ["annualized_volatility", "annualized_volatility"],
        ["sharpe_ratio", "sharpe_ratio"],
        ["sortino_ratio", "sortino_ratio"],
        ["downside_deviation", "downside_deviation"],
        ["maximum_drawdown", "maximum_drawdown"],
        ["total_return", "total_return"],
    ]);
    return Object.keys(item).length ? item : undefined;
}

function compactBenchmark(bd) {
    if (!bd || typeof bd !== "object" || bd.available !== true) return undefined;
    const item = { available: true };
    addDefined(item, bd, [
        ["nifty50_tri_available", "nifty50_tri_available"],
        ["sp500_available", "sp500_available"],
        ["common_start", "common_start"],
        ["common_end", "common_end"],
        ["observations", "observations"],
        ["portfolio_cagr", "portfolio_cagr"],
        ["nifty50_tri_cagr", "nifty50_tri_cagr"],
        ["sp500_total_return_cagr", "sp500_total_return_cagr"],
        ["nifty50_outperformance", "nifty50_outperformance"],
        ["sp500_outperformance", "sp500_outperformance"],
    ]);
    if (Array.isArray(bd.warnings) && bd.warnings.length) {
        item.warnings = bd.warnings.slice(0, 4);
    }
    return Object.keys(item).length > 1 ? item : undefined;
}

function compactRollingWindow(win) {
    if (!win || typeof win !== "object" || win.insufficient_history) return undefined;
    if (!win.summary || typeof win.summary !== "object") return undefined;
    const item = {};
    addDefined(item, win.summary, [
        ["count", "count"],
        ["avg", "avg"],
        ["median", "median"],
        ["min", "min"],
        ["max", "max"],
        ["positive_pct", "positive_pct"],
        ["std_dev", "std_dev"],
    ]);
    return Object.keys(item).length ? item : undefined;
}

function compactRolling(rp) {
    if (!rp || typeof rp !== "object") return undefined;
    const item = {};
    addDefined(item, rp, [["portfolio_cagr", "portfolio_cagr"]]);
    const windows = {};
    [
        ["1Y", rp.one_year],
        ["3Y", rp.three_year],
        ["5Y", rp.five_year],
    ].forEach(([label, window]) => {
        const compact = compactRollingWindow(window);
        if (compact) windows[label] = compact;
    });
    if (Object.keys(windows).length) item.windows = windows;
    return Object.keys(item).length ? item : undefined;
}
function compactDrawdown(dd, includeEpisodes) {
    if (!dd || typeof dd !== "object") return undefined;
    const item = {};
    addDefined(item, dd, [
        ["maximum_drawdown", "maximum_drawdown"],
        ["current_drawdown", "current_drawdown"],
        ["current_status", "current_status"],
        ["longest_recovery_days", "longest_recovery_days"],
    ]);
    if (includeEpisodes && Array.isArray(dd.episodes) && dd.episodes.length) {
        const episodes = dd.episodes.slice(0, MAX_DRAWDOWN_EPISODES).map((episode) => {
            if (!episode || typeof episode !== "object") return null;
            const episodeItem = {};
            addDefined(episodeItem, episode, [
                ["peak_date", "peak_date"],
                ["trough_date", "trough_date"],
                ["recovery_date", "recovery_date"],
                ["drawdown", "drawdown"],
                ["decline_duration_days", "decline_duration_days"],
                ["recovery_duration_days", "recovery_duration_days"],
                ["total_duration_days", "total_duration_days"],
                ["is_ongoing", "is_ongoing"],
            ]);
            return Object.keys(episodeItem).length ? episodeItem : null;
        }).filter(Boolean);
        if (episodes.length) {
            item.episodes = episodes;
            if (dd.episodes.length > episodes.length) item.episodes_truncated = dd.episodes.length;
        }
    }
    return Object.keys(item).length ? item : undefined;
}

function compactContribution(rc, includeContributions) {
    if (!rc || typeof rc !== "object") return undefined;
    const item = {};
    addDefined(item, rc, [
        ["total_contribution", "total_contribution"],
        ["portfolio_return", "portfolio_return"],
        ["reconciliation_difference", "reconciliation_difference"],
    ]);
    if (includeContributions && Array.isArray(rc.contributions) && rc.contributions.length) {
        const rows = rc.contributions.map((c) => {
            if (!c || typeof c !== "object") return null;
            const row = {};
            addDefined(row, c, [
                ["scheme_code", "scheme_code"],
                ["scheme_name", "scheme_name"],
                ["allocation", "allocation"],
                ["fund_return", "fund_return"],
                ["contribution", "contribution"],
                ["contribution_percentage", "contribution_percentage"],
            ]);
            return Object.keys(row).length ? row : null;
        }).filter(Boolean);
        // Keep the most decision-relevant rows (largest impact first).
        rows.sort((a, b) => Math.abs(b.contribution || 0) - Math.abs(a.contribution || 0));
        if (rows.length) {
            item.contributions = rows.slice(0, MAX_CONTRIBUTIONS);
            if (rc.contributions.length > rows.length) item.contributions_truncated = rc.contributions.length;
        }
    }
    return Object.keys(item).length ? item : undefined;
}

function compactStockOverlap(overlap, includeStocks) {
    if (!overlap || typeof overlap !== "object") return undefined;
    const item = {};
    addDefined(item, overlap, [
        ["overlapping_stock_count", "overlapping_stock_count"],
        ["total_unique_stock_count", "total_unique_stock_count"],
    ]);
    if (includeStocks && Array.isArray(overlap.stocks) && overlap.stocks.length) {
        const stocks = overlap.stocks.slice(0, MAX_TOP_STOCKS).map((stock) => {
            if (!stock || typeof stock !== "object") return null;
            const stockItem = {};
            addDefined(stockItem, stock, [
                ["security_name", "security_name"],
                ["isin", "isin"],
                ["fund_count", "fund_count"],
                ["effective_portfolio_exposure", "effective_portfolio_exposure"],
            ]);
            return Object.keys(stockItem).length ? stockItem : null;
        }).filter(Boolean);
        if (stocks.length) {
            item.top_stocks = stocks;
            if (overlap.stocks.length > stocks.length) item.top_stocks_truncated = overlap.stocks.length;
        }
    }
    return Object.keys(item).length ? item : undefined;
}

function compactWhatIf(wf, includeScenarioAllocations) {
    if (!wf || typeof wf !== "object") return undefined;
    const item = {};
    const period = {};
    addDefined(period, wf.analysis_period || {}, [
        ["start_date", "start_date"],
        ["end_date", "end_date"],
        ["observations", "observations"],
        ["years", "years"],
    ]);
    if (Object.keys(period).length) item.analysis_period = period;

    if (Array.isArray(wf.warnings) && wf.warnings.length) {
        item.warnings = wf.warnings.slice(0, 4);
    }

    // Deterministic scenario-vs-current metrics + deltas. The current side's
    // allocations duplicate portfolio_input.funds, so only the scenario side
    // carries its allocation list (and only while it fits the budget).
    const currentMetrics = compactMetrics(wf.current?.metrics);
    if (currentMetrics) item.current_metrics = currentMetrics;
    const scenarioMetrics = compactMetrics(wf.scenario?.metrics);
    if (scenarioMetrics) item.scenario_metrics = scenarioMetrics;

    if (includeScenarioAllocations && wf.scenario && Array.isArray(wf.scenario.allocations)) {
        const allocs = wf.scenario.allocations.map((a) => {
            if (!a || typeof a !== "object") return null;
            const alloc = {};
            addDefined(alloc, a, [
                ["scheme_code", "scheme_code"],
                ["allocation", "allocation"],
            ]);
            return Object.keys(alloc).length ? alloc : null;
        }).filter(Boolean);
        if (allocs.length) item.scenario_allocations = allocs;
    }

    if (wf.deltas && typeof wf.deltas === "object") {
        const deltas = {};
        addDefined(deltas, wf.deltas, [
            ["cagr", "cagr"],
            ["volatility", "volatility"],
            ["sharpe", "sharpe"],
            ["sortino", "sortino"],
            ["max_drawdown", "max_drawdown"],
            ["total_return", "total_return"],
        ]);
        if (Object.keys(deltas).length) item.deltas = deltas;
    }

    return Object.keys(item).length ? item : undefined;
}
// ---------------------------------------------------------------------------
// Context builder
// ---------------------------------------------------------------------------

function collectWarnings(result) {
    const warnings = [];
    if (Array.isArray(result.warnings)) {
        result.warnings
            .filter((w) => typeof w === "string" && w.trim())
            .forEach((w) => warnings.push(w));
    }
    const years = result?.metrics?.years;
    if (isDefined(years) && Number.isFinite(years) && years < 1) {
        warnings.push("Limited history: less than 1 year of common history; long-term performance and risk metrics may be unreliable.");
    } else if (isDefined(years) && Number.isFinite(years) && years < 3) {
        warnings.push("Limited history: portfolio metrics are based on less than 3 years of common history.");
    }
    return warnings.slice(0, 6);
}

export function buildPortfolioAIContext({ funds, result, stockOverlap, whatIf }) {
    if (!Array.isArray(funds) || funds.length === 0) {
        throw new Error("Portfolio funds are required for AI context.");
    }
    if (!result || typeof result !== "object" || !result.metrics || typeof result.metrics !== "object") {
        throw new Error("A completed portfolio analysis result is required for AI context.");
    }

    const metrics = result.metrics;
    const analysisPeriod = {};
    addDefined(analysisPeriod, metrics, [
        ["start_date", "start_date"],
        ["end_date", "end_date"],
        ["observations", "observations"],
        ["years", "years"],
    ]);

    const totalAllocation = funds.reduce((sum, fund) => {
        if (fund && typeof fund.allocation === "number" && Number.isFinite(fund.allocation)) {
            return sum + fund.allocation;
        }
        return sum;
    }, 0);

    const warnings = collectWarnings(result);

    const build = (includeOverlapStocks, includeEpisodes, includeContributions, includeScenarioAllocations) => {
        const portfolioAnalysis = {
            analysis_period: Object.keys(analysisPeriod).length ? analysisPeriod : undefined,
            metrics: compactMetrics(metrics),
            health_score: compactHealthScore(result.health_score),
            benchmark: compactBenchmark(result.benchmark_data),
            rolling: compactRolling(result.rolling_performance),
            drawdown_recovery: compactDrawdown(result.drawdown_recovery, includeEpisodes),
            return_contribution: compactContribution(result.return_contribution, includeContributions),
            stock_overlap: compactStockOverlap(stockOverlap, includeOverlapStocks),
            what_if: compactWhatIf(whatIf, includeScenarioAllocations),
            warnings: warnings.length ? warnings : undefined,
        };
        Object.keys(portfolioAnalysis).forEach((key) => {
            if (!isDefined(portfolioAnalysis[key])) delete portfolioAnalysis[key];
        });
        return {
            portfolio_input: {
                fund_count: funds.length,
                total_allocation: Math.round(totalAllocation * 100) / 100,
                funds: compactFunds(funds),
            },
            portfolio_analysis: portfolioAnalysis,
        };
    };

    // Progressive degradation mirrors buildFundAIContext: start with the most
    // informative context and drop optional detail until it fits the limit.
    const candidates = [
        [true, true, true, true],
        [false, true, true, true],
        [false, false, true, true],
        [false, false, true, false],
        [false, false, false, false],
    ];

    let lastContext = null;
    for (const [includeOverlapStocks, includeEpisodes, includeContributions, includeScenarioAllocations] of candidates) {
        const context = build(includeOverlapStocks, includeEpisodes, includeContributions, includeScenarioAllocations);
        lastContext = context;
        try {
            serializePortfolioAIContext(context);
            return context;
        } catch (error) {
            if (!(error instanceof Error) || !error.message.includes("safety limit")) throw error;
        }
    }

    serializePortfolioAIContext(lastContext);
    return lastContext;
}

function utf8ByteLength(value) {
    return new TextEncoder().encode(value).length;
}

function serializeContext(context) {
    const serialized = JSON.stringify(context);
    const bytes = utf8ByteLength(serialized);
    if (bytes > MAX_CONTEXT_BYTES) {
        throw new Error(`Portfolio AI context exceeds the ${MAX_CONTEXT_BYTES}-byte safety limit.`);
    }
    return { serialized, bytes };
}

export function serializePortfolioAIContext(context) {
    return serializeContext(context);
}

export const PORTFOLIO_AI_CONTEXT_LIMITS = Object.freeze({
    maxFunds: MAX_FUNDS,
    maxTopStocks: MAX_TOP_STOCKS,
    targetBytes: TARGET_CONTEXT_BYTES,
    maxBytes: MAX_CONTEXT_BYTES,
});