const MAX_STOCKS = 4;
const MAX_HISTORY = 6;
const MAX_CONTEXT_BYTES = 16000;

const FUNDAMENTAL_FIELDS = [
  "symbol", "name", "exchange", "sector", "industry", "country", "currency",
  "price", "market_cap", "enterprise_value", "pe", "forward_pe", "pb", "ps", "peg",
  "ev_ebitda", "ev_revenue", "dividend_yield", "payout_ratio",
  "roe", "roa", "gross_margin", "operating_margin", "profit_margin",
  "debt_equity", "current_ratio", "quick_ratio", "beta", "cash", "total_debt",
  "revenue", "operating_profit", "ebitda", "net_profit", "eps",
  "operating_cash_flow", "capital_expenditure", "free_cash_flow",
  "revenue_growth", "profit_growth", "eps_growth",
  "revenue_cagr_3y", "revenue_cagr_5y", "profit_cagr_3y", "profit_cagr_5y",
  "eps_cagr_3y", "eps_cagr_5y", "fcf_cagr_3y", "fcf_cagr_5y", "operating_margin_change",
  "roce", "data_as_of",
];

const DERIVED_FIELDS = [
  "cash_conversion_ratio", "fcf_to_profit", "fcf_margin_derived", "roic", "croic",
  "net_debt_ebitda", "average_roe_3y", "average_roe_5y",
  "operating_margin_3y_avg", "operating_margin_5y_avg",
  "debtor_days", "inventory_days", "payable_days", "cash_conversion_cycle",
  "debt_change_1y", "debt_change_3y", "piotroski_proxy_score",
];

function defined(value) {
  return value !== undefined && value !== null;
}

function pick(source, fields) {
  const result = {};
  for (const key of fields) {
    if (defined(source?.[key])) result[key] = source[key];
  }
  return result;
}

function compactHistory(data) {
  const income = Array.isArray(data?.income_statement) ? data.income_statement : [];
  const balance = Array.isArray(data?.balance_sheet) ? data.balance_sheet : [];
  const byPeriod = new Map();

  for (const row of [...income, ...balance]) {
    const period = String(row?.period || "").slice(0, 10);
    if (!period) continue;
    if (!byPeriod.has(period)) byPeriod.set(period, { period: period.slice(0, 4) });
    const target = byPeriod.get(period);
    const values = row?.values || {};
    for (const [key, value] of Object.entries(values)) {
      if (["TotalRevenue", "NetIncome", "OperatingIncome", "TotalDebt", "StockholdersEquity"].includes(key) && defined(value)) {
        target[key] = value;
      }
    }
    if (defined(values.TotalRevenue) && defined(values.OperatingIncome) && Number(values.TotalRevenue) !== 0) {
      target.operating_margin = Number(values.OperatingIncome) / Number(values.TotalRevenue) * 100;
    }
  }

  return [...byPeriod.values()]
    .sort((a, b) => String(b.period).localeCompare(String(a.period)))
    .slice(0, MAX_HISTORY);
}

function compactStock(data) {
  const fundamentals = data?.fundamentals || {};
  const stock = { fundamentals: pick(fundamentals, FUNDAMENTAL_FIELDS) };
  const derived = pick(data?.derived_analysis, DERIVED_FIELDS);
  if (Object.keys(derived).length) stock.derived_analysis = derived;
  const history = compactHistory(data);
  if (history.length) stock.historical_trend = history;
  return stock;
}

function serialize(context) {
  const serialized = JSON.stringify(context);
  const bytes = new TextEncoder().encode(serialized).length;
  if (bytes > MAX_CONTEXT_BYTES) {
    throw new Error(`Stock AI context exceeds the ${MAX_CONTEXT_BYTES}-byte safety limit.`);
  }
  return { serialized, bytes };
}

export function buildStockAIContext(data) {
  if (!data || typeof data !== "object") throw new Error("Stock analysis data is required for AI context.");
  const context = {
    analysis_type: "individual_stock",
    selected_stock: compactStock(data),
  };
  serialize(context);
  return context;
}

export function buildStockComparisonAIContext(datas) {
  if (!Array.isArray(datas) || datas.length < 2) {
    throw new Error("At least two stocks are required for comparison AI context.");
  }
  const context = {
    analysis_type: "stock_comparison",
    stocks: datas.slice(0, MAX_STOCKS).map(compactStock),
  };
  serialize(context);
  return context;
}

export function serializeStockAIContext(context) {
  return serialize(context);
}

export const STOCK_AI_CONTEXT_LIMITS = Object.freeze({
  maxStocks: MAX_STOCKS,
  maxHistory: MAX_HISTORY,
  maxBytes: MAX_CONTEXT_BYTES,
});
