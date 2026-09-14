// Portfolio Builder — AI Insights request handler.
//
// Mirrors the Mutual Fund AI Insights request pattern
// (frontend/js/features/mutual-fund-analysis/ai-request.js): builds the
// compact deterministic context, enforces the byte-size guard, then POSTs it
// to the shared portfolio AI endpoint. No calculations are performed here.

import { api } from "../../core/api.js";
import { serializePortfolioAIContext } from "./ai-context.js";

export async function requestPortfolioAIInsights({ buildContext, funds, result, stockOverlap, whatIf }) {
    if (!buildContext) {
        throw new Error("The compact AI context builder is required.");
    }
    if (!Array.isArray(funds) || funds.length === 0) {
        throw new Error("Portfolio funds are required for AI insights.");
    }
    if (!result || typeof result !== "object") {
        throw new Error("The portfolio analysis result is required for AI insights.");
    }

    const context = buildContext({ funds, result, stockOverlap, whatIf });
    const { serialized } = serializePortfolioAIContext(context);
    return api.post("/portfolio/mutual-fund-analysis/insights", JSON.parse(serialized));
}