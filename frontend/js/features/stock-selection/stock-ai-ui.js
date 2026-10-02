import { api } from "../../core/api.js";
import { buildStockAIContext, buildStockComparisonAIContext } from "./stock-ai-context.js";
import { requestStockAIInsights, requestStockComparisonAIInsights } from "./stock-ai-request.js";
import { renderStockAIError, renderStockAILoading, renderStockAIResponse } from "./stock-ai-response.js";

let observerStarted = false;
let lastIndividualSymbol = null;
let lastComparisonKey = null;

function currentSymbol() {
  return (new URLSearchParams(location.search).get("symbol") || "").trim().toUpperCase();
}

function comparisonSymbols() {
  return (new URLSearchParams(location.search).get("compare") || "")
    .split(",")
    .map((value) => decodeURIComponent(value).trim().toUpperCase())
    .filter(Boolean)
    .slice(0, 4);
}

function createSection(kind, key) {
  const section = document.createElement("section");
  section.className = `stock-section stock-ai-insights-section ${kind === "comparison" ? "stock-ai-comparison-insights" : ""}`;
  section.dataset.aiKey = key;

  const heading = document.createElement("div");
  heading.className = "stock-section-header stock-ai-insights-heading";
  const title = document.createElement("h2");
  title.textContent = "AI Insights";
  heading.appendChild(title);
  const subtitle = document.createElement("p");
  subtitle.className = "stock-ai-insights-subtitle";
  subtitle.textContent = kind === "comparison"
    ? "Interpret the business quality, growth, cash generation, financial health and valuation trade-offs in this comparison."
    : "Get a concise interpretation of the company's quality, consistency, cash generation, financial health and valuation.";
  heading.appendChild(subtitle);
  section.appendChild(heading);

  const status = document.createElement("p");
  status.className = "stock-ai-insights-status";
  status.setAttribute("aria-live", "polite");
  status.textContent = "Click AI Insights to generate an interpretation.";
  section.appendChild(status);

  const result = document.createElement("div");
  result.className = "stock-ai-insights-result";
  section.appendChild(result);

  const button = document.createElement("button");
  button.type = "button";
  button.className = "ai-action ai-action-compact stock-ai-insights-button";
  button.textContent = "✨ AI Insights";
  section.insertBefore(button, status);

  return { section, button, status, result };
}

function setupIndividual() {
  const details = document.getElementById("stock-details");
  const analysis = document.getElementById("stock-analysis-screen");
  const symbol = currentSymbol();
  if (!details || !analysis || analysis.hidden || !symbol || !details.querySelector(".stock-hero")) return;

  const key = symbol;
  if (lastIndividualSymbol === key && details.querySelector(".stock-ai-insights-section")) return;
  details.querySelector(".stock-ai-insights-section")?.remove();
  lastIndividualSymbol = key;

  const { section, button, status, result } = createSection("individual", key);
  const firstSection = details.querySelector(".stock-section");
  if (firstSection) details.insertBefore(section, firstSection);
  else details.appendChild(section);

  let isRequesting = false;
  const requestInsights = async () => {
    if (isRequesting) return;
    isRequesting = true;
    button.disabled = true;
    button.innerHTML = '<span class="loading-spinner"></span> Generating...';
    status.textContent = "Generating AI Insights...";
    renderStockAILoading(result);

    try {
      const response = await api.get(`/stocks/${encodeURIComponent(symbol)}`);
      const context = buildStockAIContext(response);
      const insight = await requestStockAIInsights({ apiClient: api, symbol, context });
      renderStockAIResponse(result, insight);
      status.textContent = "AI Insights generated from the current analysis.";
    } catch (error) {
      renderStockAIError(result, requestInsights);
      status.textContent = "AI Insights could not be generated.";
    } finally {
      isRequesting = false;
      button.innerHTML = "✨ AI Insights";
      button.disabled = false;
    }
  };

  button.addEventListener("click", requestInsights);
}

function setupComparison() {
  const details = document.getElementById("stock-details");
  const analysis = document.getElementById("stock-analysis-screen");
  const header = details?.querySelector(".stock-comparison-header");
  const symbols = comparisonSymbols();
  if (!details || !analysis || analysis.hidden || !header || symbols.length < 2) return;

  const key = symbols.join(",");
  if (lastComparisonKey === key && details.querySelector(".stock-ai-comparison-insights")) return;
  details.querySelector(".stock-ai-comparison-insights")?.remove();
  lastComparisonKey = key;

  const { section, button, status, result } = createSection("comparison", key);
  button.className = "ai-action ai-action-compact stock-ai-insights-button stock-ai-comparison-button";
  button.setAttribute("aria-label", "Generate AI insights for this stock comparison");
  section.removeChild(button);
  header.appendChild(button);
  details.insertBefore(section, header.nextSibling);

  let isRequesting = false;
  const requestInsights = async () => {
    if (isRequesting) return;
    isRequesting = true;
    button.disabled = true;
    button.innerHTML = '<span class="loading-spinner"></span> Generating...';
    status.textContent = "Generating AI Insights...";
    renderStockAILoading(result);

    try {
      const datas = await Promise.all(symbols.map((symbol) => api.get(`/stocks/${encodeURIComponent(symbol)}`)));
      const context = buildStockComparisonAIContext(datas);
      const insight = await requestStockComparisonAIInsights({ apiClient: api, context });
      renderStockAIResponse(result, insight);
      status.textContent = "AI Insights generated from the current comparison.";
    } catch (error) {
      renderStockAIError(result, requestInsights);
      status.textContent = "AI Insights could not be generated.";
    } finally {
      isRequesting = false;
      button.innerHTML = "✨ AI Insights";
      button.disabled = false;
    }
  };

  button.addEventListener("click", requestInsights);
}

function scan() {
  setupIndividual();
  setupComparison();
}

export function initStockAIUI() {
  if (observerStarted) return;
  observerStarted = true;
  const root = document.getElementById("stock-analysis-content") || document.body;
  const observer = new MutationObserver(() => scan());
  observer.observe(root, { childList: true, subtree: true });
  scan();
}
