import { serializeStockAIContext } from "./stock-ai-context.js";

export async function requestStockAIInsights({ apiClient, symbol, context }) {
  if (!apiClient || typeof apiClient.post !== "function") {
    throw new Error("An API client is required for AI insights.");
  }
  if (!symbol) throw new Error("A stock symbol is required for AI insights.");
  const { serialized } = serializeStockAIContext(context);
  return apiClient.post(`/stocks/${encodeURIComponent(String(symbol))}/insights`, JSON.parse(serialized));
}

export async function requestStockComparisonAIInsights({ apiClient, context }) {
  if (!apiClient || typeof apiClient.post !== "function") {
    throw new Error("An API client is required for AI insights.");
  }
  const { serialized } = serializeStockAIContext(context);
  return apiClient.post("/stocks/comparison-insights", JSON.parse(serialized));
}
