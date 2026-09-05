import { serializeRankingAIContext } from "./ranking-ai-context.js";

export async function requestRankingAIInsights({ apiClient, context }) {
    if (!apiClient || typeof apiClient.post !== "function") {
        throw new Error("An API client is required for ranking insights.");
    }
    const { serialized } = serializeRankingAIContext(context);
    return apiClient.post("/mutual-funds/ranking-insights", JSON.parse(serialized));
}
