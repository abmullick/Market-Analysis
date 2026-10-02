const LIST_FIELDS = ["key_points", "risks", "opportunities"];

function validate(response) {
  if (!response || typeof response !== "object" || typeof response.summary !== "string") {
    throw new Error("Invalid AI insights response.");
  }
  for (const field of LIST_FIELDS) {
    if (!Array.isArray(response[field]) || response[field].some((item) => typeof item !== "string")) {
      throw new Error("Invalid AI insights response.");
    }
  }
  if (response.recommendation !== null && typeof response.recommendation !== "string") {
    throw new Error("Invalid AI insights response.");
  }
}

function section(documentRef, container, title, text) {
  const wrapper = documentRef.createElement("div");
  wrapper.className = "stock-ai-insights-result-section";
  const heading = documentRef.createElement("h4");
  heading.textContent = title;
  heading.className = "stock-ai-insights-result-title";
  wrapper.appendChild(heading);
  const paragraph = documentRef.createElement("p");
  paragraph.textContent = text;
  paragraph.className = "stock-ai-insights-result-text";
  wrapper.appendChild(paragraph);
  container.appendChild(wrapper);
}

function listSection(documentRef, container, title, items) {
  const wrapper = documentRef.createElement("div");
  wrapper.className = "stock-ai-insights-result-section";
  const heading = documentRef.createElement("h4");
  heading.textContent = title;
  heading.className = "stock-ai-insights-result-title";
  wrapper.appendChild(heading);
  const list = documentRef.createElement("ul");
  list.className = "stock-ai-insights-result-list";
  if (!items.length) {
    const item = documentRef.createElement("li");
    item.textContent = "No additional points provided.";
    item.className = "stock-ai-insights-result-empty";
    list.appendChild(item);
  } else {
    items.forEach((text) => {
      const item = documentRef.createElement("li");
      item.textContent = text;
      list.appendChild(item);
    });
  }
  wrapper.appendChild(list);
  container.appendChild(wrapper);
}

export function renderStockAIResponse(container, response) {
  validate(response);
  const documentRef = container?.ownerDocument || globalThis.document;
  if (!container || !documentRef) return;
  container.replaceChildren();
  section(documentRef, container, "Summary", response.summary);
  listSection(documentRef, container, "Key Points", response.key_points);
  listSection(documentRef, container, "Risks", response.risks);
  listSection(documentRef, container, "Opportunities", response.opportunities);
  section(documentRef, container, "Recommendation", response.recommendation || "No recommendation provided.");
  const disclosure = documentRef.createElement("p");
  disclosure.className = "stock-ai-insights-disclosure";
  disclosure.textContent = "AI interpretation based on the current stock analysis data.";
  container.appendChild(disclosure);
}

export function renderStockAILoading(container) {
  const documentRef = container?.ownerDocument || globalThis.document;
  if (!container || !documentRef) return;
  container.replaceChildren();
  const loading = documentRef.createElement("div");
  loading.className = "stock-ai-insights-loading";
  loading.setAttribute("role", "status");
  loading.textContent = "Generating AI Insights...";
  container.appendChild(loading);
}

export function renderStockAIError(container, onRetry) {
  const documentRef = container?.ownerDocument || globalThis.document;
  if (!container || !documentRef) return;
  container.replaceChildren();
  const message = documentRef.createElement("p");
  message.className = "stock-ai-insights-error";
  message.textContent = "AI Insights could not be generated right now. Please try again.";
  container.appendChild(message);
  const retry = documentRef.createElement("button");
  retry.type = "button";
  retry.className = "btn-text stock-ai-insights-retry";
  retry.textContent = "Retry";
  retry.addEventListener("click", onRetry);
  container.appendChild(retry);
}
