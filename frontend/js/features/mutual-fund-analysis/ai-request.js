import { serializeFundAIContext } from "./ai-context.js";

export async function requestFundAIInsights({
    apiClient,
    buildContext,
    schemeCode,
    detail,
    categoryAnalysis,
    ranking,
    rankingConfiguration,
    peers,
}) {
    if (!apiClient || typeof apiClient.post !== "function") {
        throw new Error("An API client is required for AI insights.");
    }
    if (!buildContext) {
        throw new Error("The compact AI context builder is required.");
    }
    if (schemeCode == null || schemeCode === "") {
        throw new Error("A scheme code is required for AI insights.");
    }

    const context = buildContext({
        detail,
        ranking,
        categoryAnalysis,
        rankingConfiguration,
        peers,
    });
    const { serialized } = serializeFundAIContext(context);

    return apiClient.post(
        `/mutual-funds/${encodeURIComponent(String(schemeCode))}/insights`,
        JSON.parse(serialized),
    );
}
