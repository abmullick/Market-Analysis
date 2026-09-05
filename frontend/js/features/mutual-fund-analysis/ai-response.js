const LIST_FIELDS = ["key_points", "risks", "opportunities"];

function validateInsightResponse(response) {
    if (!response || typeof response !== "object") {
        throw new Error("Invalid AI insights response.");
    }
    if (typeof response.summary !== "string") {
        throw new Error("Invalid AI insights response.");
    }
    for (const field of LIST_FIELDS) {
        if (!Array.isArray(response[field]) || response[field].some(item => typeof item !== "string")) {
            throw new Error("Invalid AI insights response.");
        }
    }
    if (response.recommendation !== null && typeof response.recommendation !== "string") {
        throw new Error("Invalid AI insights response.");
    }
}

function appendTextSection(documentRef, container, title, text) {
    const section = documentRef.createElement("div");
    section.className = "fund-ai-insights-result-section";

    const heading = documentRef.createElement("h4");
    heading.className = "fund-ai-insights-result-title";
    heading.textContent = title;
    section.appendChild(heading);

    const paragraph = documentRef.createElement("p");
    paragraph.className = "fund-ai-insights-result-text";
    paragraph.textContent = text;
    section.appendChild(paragraph);

    container.appendChild(section);
}

function appendListSection(documentRef, container, title, items) {
    const section = documentRef.createElement("div");
    section.className = "fund-ai-insights-result-section";

    const heading = documentRef.createElement("h4");
    heading.className = "fund-ai-insights-result-title";
    heading.textContent = title;
    section.appendChild(heading);

    const list = documentRef.createElement("ul");
    list.className = "fund-ai-insights-result-list";
    if (items.length === 0) {
        const empty = documentRef.createElement("li");
        empty.className = "fund-ai-insights-result-empty";
        empty.textContent = "No additional points provided.";
        list.appendChild(empty);
    } else {
        items.forEach(item => {
            const listItem = documentRef.createElement("li");
            listItem.textContent = item;
            list.appendChild(listItem);
        });
    }
    section.appendChild(list);
    container.appendChild(section);
}

export function renderInsightResponse(container, response) {
    validateInsightResponse(response);
    const documentRef = container?.ownerDocument || globalThis.document;
    if (!container || !documentRef) return;

    container.replaceChildren();
    appendTextSection(documentRef, container, "Summary", response.summary);
    appendListSection(documentRef, container, "Key Points", response.key_points);
    appendListSection(documentRef, container, "Risks", response.risks);
    appendListSection(documentRef, container, "Opportunities", response.opportunities);
    appendTextSection(
        documentRef,
        container,
        "Recommendation",
        response.recommendation || "No recommendation provided.",
    );

    const disclosure = documentRef.createElement("p");
    disclosure.className = "fund-ai-insights-disclosure";
    disclosure.textContent = "AI interpretation based on the fund analysis and your selected ranking criteria.";
    container.appendChild(disclosure);
}

export function renderInsightLoading(container) {
    const documentRef = container?.ownerDocument || globalThis.document;
    if (!container || !documentRef) return;

    container.replaceChildren();
    const loading = documentRef.createElement("div");
    loading.className = "fund-ai-insights-loading";
    loading.setAttribute("role", "status");
    loading.textContent = "Generating AI Insights...";
    container.appendChild(loading);
}

export function renderInsightError(container, onRetry) {
    const documentRef = container?.ownerDocument || globalThis.document;
    if (!container || !documentRef) return;

    container.replaceChildren();
    const message = documentRef.createElement("p");
    message.className = "fund-ai-insights-error";
    message.textContent = "AI Insights could not be generated right now. Please try again.";
    container.appendChild(message);

    const retry = documentRef.createElement("button");
    retry.type = "button";
    retry.className = "btn-text fund-ai-insights-retry";
    retry.textContent = "Retry";
    retry.addEventListener("click", onRetry);
    container.appendChild(retry);
}
