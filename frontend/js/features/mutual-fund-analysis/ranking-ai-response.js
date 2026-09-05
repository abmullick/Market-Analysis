const LIST_FIELDS = ["key_points", "risks", "opportunities"];

function validateResponse(response) {
    if (!response || typeof response !== "object" || typeof response.summary !== "string") {
        throw new Error("Invalid ranking insights response.");
    }
    for (const field of LIST_FIELDS) {
        if (!Array.isArray(response[field]) || response[field].some(item => typeof item !== "string")) {
            throw new Error("Invalid ranking insights response.");
        }
    }
    if (response.recommendation !== null && typeof response.recommendation !== "string") {
        throw new Error("Invalid ranking insights response.");
    }
}

function appendText(documentRef, container, title, text) {
    const section = documentRef.createElement("section");
    section.className = "ranking-ai-result-section";
    const heading = documentRef.createElement("h4");
    heading.className = "ranking-ai-result-title";
    heading.textContent = title;
    const paragraph = documentRef.createElement("p");
    paragraph.className = "ranking-ai-result-text";
    paragraph.textContent = text;
    section.appendChild(heading);
    section.appendChild(paragraph);
    container.appendChild(section);
}

function appendList(documentRef, container, title, items) {
    const section = documentRef.createElement("section");
    section.className = "ranking-ai-result-section";
    const heading = documentRef.createElement("h4");
    heading.className = "ranking-ai-result-title";
    heading.textContent = title;
    const list = documentRef.createElement("ul");
    list.className = "ranking-ai-result-list";
    items.forEach(item => {
        const entry = documentRef.createElement("li");
        entry.textContent = item;
        list.appendChild(entry);
    });
    if (!items.length) {
        const entry = documentRef.createElement("li");
        entry.textContent = "No additional points provided.";
        list.appendChild(entry);
    }
    section.appendChild(heading);
    section.appendChild(list);
    container.appendChild(section);
}

export function renderRankingAIResponse(container, response) {
    validateResponse(response);
    const documentRef = container?.ownerDocument || globalThis.document;
    if (!container || !documentRef) return;

    container.replaceChildren();
    appendText(documentRef, container, "Summary", response.summary);
    appendList(documentRef, container, "Drivers & Key Points", response.key_points);
    appendList(documentRef, container, "Trade-offs & Risks", response.risks);
    appendList(documentRef, container, "Opportunities", response.opportunities);
    appendText(documentRef, container, "Recommendation", response.recommendation || "No recommendation provided.");

    const disclosure = documentRef.createElement("p");
    disclosure.className = "ranking-ai-disclosure";
    disclosure.textContent = "AI interpretation of the deterministic ranking and your selected criteria. It does not recalculate the ranking.";
    container.appendChild(disclosure);
}

export function renderRankingAILoading(container) {
    const documentRef = container?.ownerDocument || globalThis.document;
    if (!container || !documentRef) return;
    container.replaceChildren();
    const loading = documentRef.createElement("div");
    loading.className = "ranking-ai-loading";
    loading.setAttribute("role", "status");
    loading.textContent = "Generating AI Ranking Insights...";
    container.appendChild(loading);
}

export function renderRankingAIError(container, onRetry) {
    const documentRef = container?.ownerDocument || globalThis.document;
    if (!container || !documentRef) return;
    container.replaceChildren();
    const message = documentRef.createElement("p");
    message.className = "ranking-ai-error";
    message.textContent = "AI Ranking Insights could not be generated right now. Please try again.";
    const retry = documentRef.createElement("button");
    retry.type = "button";
    retry.className = "btn-text ranking-ai-retry";
    retry.textContent = "Retry";
    retry.addEventListener("click", onRetry);
    container.appendChild(message);
    container.appendChild(retry);
}
