/* Stock Portfolio Analysis UI
 * Reuses the Mutual Fund Portfolio Builder collapsible-card pattern.
 * This is presentation-only: it moves/wraps the already-rendered analysis
 * sections and does not introduce another data source or calculation engine.
 */

const CARD_CONFIG = [
    { match: /portfolio quality/i, title: "Portfolio Quality", subtitle: "Allocation-weighted fundamental quality and growth", color: "#1e3a5f", tint: "rgba(30,58,95,.05)", border: "rgba(30,58,95,.22)", icon: "shield" },
    { match: /portfolio valuation/i, title: "Portfolio Valuation", subtitle: "Allocation-weighted valuation exposure", color: "#7c3aed", tint: "rgba(124,58,237,.05)", border: "rgba(124,58,237,.20)", icon: "coins" },
    { match: /sector allocation/i, title: "Sector Allocation", subtitle: "How the current portfolio is distributed across sectors", color: "#b45309", tint: "rgba(180,83,9,.05)", border: "rgba(180,83,9,.20)", icon: "layers" },
    { match: /holding analysis/i, title: "Holding Analysis", subtitle: "Allocation-weighted view of every holding", color: "#475569", tint: "rgba(71,85,105,.05)", border: "rgba(71,85,105,.20)", icon: "grid" },
    { match: /portfolio performance/i, title: "Portfolio Performance", subtitle: "Historical price growth using your current allocation", color: "#059669", tint: "rgba(5,150,105,.05)", border: "rgba(5,150,105,.20)", icon: "trend" },
    { match: /portfolio vs market/i, title: "Portfolio vs Market", subtitle: "Historical performance relative to a market benchmark", color: "#2563eb", tint: "rgba(37,99,235,.05)", border: "rgba(37,99,235,.20)", icon: "compare" },
    { match: /positioning map/i, title: "Portfolio Positioning", subtitle: "Quality × growth view of the current holdings", color: "#0f766e", tint: "rgba(15,118,110,.05)", border: "rgba(15,118,110,.20)", icon: "scatter" },
    { match: /risk & drawdown/i, title: "Risk & Drawdown", subtitle: "Historical risk and concentration exposures", color: "#b45309", tint: "rgba(180,83,9,.05)", border: "rgba(180,83,9,.20)", icon: "risk" },
    { match: /what-if \/ rebalancing/i, title: "What-If / Rebalancing", subtitle: "Compare allocation changes without executing trades", color: "#7c3aed", tint: "rgba(124,58,237,.05)", border: "rgba(124,58,237,.20)", icon: "sliders" },
    { match: /portfolio action view/i, title: "Portfolio Action View", subtitle: "Key characteristics that may warrant review", color: "#059669", tint: "rgba(5,150,105,.05)", border: "rgba(5,150,105,.20)", icon: "check" },
];

const ICONS = {
    shield: '<path d="M12 3l7 3v5c0 5-3.2 8.4-7 10-3.8-1.6-7-5-7-10V6l7-3z"></path><path d="M9 12l2 2 4-4"></path>',
    coins: '<circle cx="8" cy="8" r="3"></circle><circle cx="16" cy="16" r="3"></circle><path d="M10.5 10.5l3 3"></path><path d="M5 19l3-3"></path>',
    layers: '<path d="M12 3l9 5-9 5-9-5 9-5z"></path><path d="M3 12l9 5 9-5"></path><path d="M3 16l9 5 9-5"></path>',
    grid: '<rect x="4" y="4" width="6" height="6" rx="1"></rect><rect x="14" y="4" width="6" height="6" rx="1"></rect><rect x="4" y="14" width="6" height="6" rx="1"></rect><rect x="14" y="14" width="6" height="6" rx="1"></rect>',
    trend: '<polyline points="3 17 9 11 13 14 21 5"></polyline><polyline points="15 5 21 5 21 11"></polyline>',
    compare: '<path d="M4 18V6"></path><path d="M12 18V3"></path><path d="M20 18V9"></path><path d="M2 18h20"></path>',
    scatter: '<circle cx="7" cy="15" r="2"></circle><circle cx="13" cy="9" r="2"></circle><circle cx="19" cy="6" r="2"></circle><path d="M5 17l6-6 6-3"></path>',
    risk: '<path d="M12 3l7 3v5c0 5-3.2 8.4-7 10-3.8-1.6-7-5-7-10V6l7-3z"></path><path d="M8 14l2-2 2 2 4-5"></path>',
    sliders: '<line x1="4" y1="6" x2="20" y2="6"></line><line x1="4" y1="12" x2="20" y2="12"></line><line x1="4" y1="18" x2="20" y2="18"></line><circle cx="9" cy="6" r="2"></circle><circle cx="15" cy="12" r="2"></circle><circle cx="11" cy="18" r="2"></circle>',
    check: '<circle cx="12" cy="12" r="9"></circle><path d="M8 12l2.5 2.5L16 9"></path>',
};

function esc(value) {
    return String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");
}

function iconSvg(type) {
    return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONS[type] || ICONS.grid}</svg>`;
}

function getConfig(section) {
    const text = String(section.textContent || "").replace(/\s+/g, " ").trim();
    return CARD_CONFIG.find(item => item.match.test(text)) || null;
}

function valueText(el) {
    return String(el?.textContent || "").replace(/\s+/g, " ").trim();
}

function makeCard(section, index) {
    if (!section || section.dataset.pbCollapsible === "1") return;
    const config = getConfig(section);
    if (!config) return;

    const originalHeader = section.querySelector(":scope > .stock-section-header");
    let title = config.title;
    let subtitle = config.subtitle;
    if (originalHeader) {
        const h2 = originalHeader.querySelector("h2");
        const sub = originalHeader.querySelector("span");
        if (h2?.textContent?.trim()) title = h2.textContent.trim();
        if (sub?.textContent?.trim()) subtitle = sub.textContent.trim();
        originalHeader.remove();
    }

    const content = document.createElement("div");
    content.className = "pb-section-content pb-health-content stock-portfolio-collapsible-content";
    while (section.firstChild) content.appendChild(section.firstChild);

    section.className = "pb-section-card pb-health-card stock-portfolio-collapsible-card";
    section.dataset.pbCollapsible = "1";
    section.dataset.pbIndex = String(index);
    section.style.setProperty("--pb-accent", config.color);
    section.style.setProperty("--pb-tint", config.tint);
    section.style.setProperty("--pb-border", config.border);

    const contentId = `stock-pb-content-${index}`;
    content.id = contentId;
    const highlights = extractHighlightsFromContent(content);
    const kpis = highlights.map(item => `<span class="stock-pb-highlight"><strong>${esc(item.value)}</strong><small>${esc(item.label)}</small></span>`).join("");

    const header = document.createElement("div");
    header.className = "pb-section-header pb-health-header stock-pb-card-header";
    header.setAttribute("role", "button");
    header.setAttribute("tabindex", "0");
    header.setAttribute("aria-expanded", "false");
    header.setAttribute("aria-controls", contentId);
    header.innerHTML = `<div class="pb-health-header-main"><span class="pb-section-icon pb-health-icon stock-pb-icon">${iconSvg(config.icon)}</span><span class="pb-section-titlewrap pb-health-summary-label">${esc(title)}<small>${esc(subtitle)}</small></span></div><div class="pb-section-kpis stock-pb-kpis">${kpis}</div><div class="pb-section-controls"><button type="button" class="pb-section-caret-btn pb-health-caret-button stock-pb-caret" aria-expanded="false" aria-controls="${contentId}" aria-label="Expand ${esc(title)}"><svg class="pb-section-caret pb-health-caret" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 7.5L10 12.5L15 7.5"></path></svg></button></div>`;

    section.append(header, content);
    section.classList.remove("portfolio-analysis-section");
    section.classList.add("stock-portfolio-collapsible-ready");

    // The entire header is clickable. The caret is a real button as well and
    // must toggle independently; the old implementation stopped propagation
    // and then called a guard that immediately returned, making the caret inert.
    const toggle = () => {
        const open = header.getAttribute("aria-expanded") === "true";
        setOpen(section, !open);
    };
    header.addEventListener("click", event => {
        if (event.target.closest("button")) return;
        toggle();
    });
    header.addEventListener("keydown", event => {
        if (event.target.closest("button")) return;
        if (event.key === "Enter" || event.key === " ") { event.preventDefault(); toggle(); }
    });
    header.querySelector("button")?.addEventListener("click", event => {
        event.preventDefault();
        event.stopPropagation();
        toggle();
    });
    setOpen(section, false);
}

function extractHighlightsFromContent(content) {
    const cards = [...content.querySelectorAll(":scope .stock-metric-card")];
    if (cards.length) return cards.slice(0, 3).map(card => ({ label: valueText(card.querySelector(".stock-metric-label")), value: valueText(card.querySelector(".stock-metric-value")) })).filter(x => x.label && x.value);
    const riskCards = [...content.querySelectorAll(":scope .portfolio-risk-card")];
    if (riskCards.length) return riskCards.slice(0, 3).map(card => ({ label: valueText(card.querySelector("span")), value: valueText(card.querySelector("strong")) })).filter(x => x.label && x.value);
    const summary = [...content.querySelectorAll(":scope .portfolio-positioning-summary > div, :scope .portfolio-benchmark-highlight-card")];
    if (summary.length) return summary.slice(0, 3).map(card => ({ label: valueText(card.querySelector("span")), value: valueText(card.querySelector("strong")) })).filter(x => x.label && x.value);
    const firstRow = content.querySelector(":scope .portfolio-analysis-table tbody tr");
    if (firstRow) {
        const cells = firstRow.querySelectorAll("td");
        return [{ label: "Largest visible holding", value: valueText(cells[0]?.querySelector("strong")) || "—" }, { label: "Allocation", value: valueText(cells[1]) || "—" }, { label: "Signal", value: valueText(cells[6]?.querySelector(".portfolio-signal")) || "—" }];
    }
    const sector = content.querySelector(":scope .portfolio-sector-row");
    if (sector) return [{ label: "Largest sector", value: valueText(sector.querySelector(".portfolio-sector-label span")) || "—" }, { label: "Allocation", value: valueText(sector.querySelector(".portfolio-sector-label strong")) || "—" }];
    const rebalance = [...content.querySelectorAll(":scope .portfolio-rebalance-metric")];
    if (rebalance.length) return rebalance.slice(0, 3).map(card => ({ label: valueText(card.querySelector(".stock-metric-label")), value: valueText(card.querySelector(".portfolio-rebalance-values")) })).filter(x => x.label && x.value);
    const action = [...content.querySelectorAll(":scope .portfolio-action-metric")];
    if (action.length) return action.slice(0, 3).map(card => ({ label: valueText(card.querySelector(".stock-metric-label")), value: valueText(card.querySelector(".stock-metric-value")) })).filter(x => x.label && x.value);
    return [];
}

function setOpen(section, open) {
    const header = section.querySelector(":scope > .pb-section-header");
    const content = section.querySelector(":scope > .pb-section-content");
    const button = section.querySelector(":scope .stock-pb-caret");
    if (!header || !content) return;
    header.setAttribute("aria-expanded", open ? "true" : "false");
    if (button) {
        button.setAttribute("aria-expanded", open ? "true" : "false");
        button.setAttribute("aria-label", `${open ? "Collapse" : "Expand"} ${header.querySelector(".pb-health-summary-label")?.childNodes?.[0]?.textContent?.trim() || "section"}`);
    }
    content.hidden = !open;
    section.classList.toggle("is-open", open);
}

function wrapResults() {
    const results = document.getElementById("portfolio-analysis-results");
    if (!results || results.hidden) return;
    const sections = [...results.querySelectorAll(":scope > section.stock-section.portfolio-analysis-section")];
    sections.forEach((section, index) => makeCard(section, index + 1));
}

function wrapExternalSections() {
    const analysis = document.getElementById("stock-portfolio-analysis-content");
    if (!analysis || analysis.hidden) return;
    const external = [
        document.querySelector("#portfolio-rebalancing > section.stock-section"),
        document.querySelector("#portfolio-action-view > section.stock-section"),
    ].filter(Boolean);
    external.forEach((section, index) => makeCard(section, 100 + index));
}

function normaliseNotes() {
    const analysis = document.getElementById("stock-portfolio-analysis-content");
    if (!analysis) return;
    const candidate = [...analysis.querySelectorAll(".stock-portfolio-collapsible-card")].find(card => /data notes/i.test(card.textContent || ""));
    if (!candidate) return;
    candidate.dataset.pbNotes = "1";
    analysis.appendChild(candidate);
}

function refresh() {
    wrapResults();
    wrapExternalSections();
    normaliseNotes();
}

function init() {
    const analysis = document.getElementById("stock-portfolio-analysis-content");
    if (!analysis) return;
    const observer = new MutationObserver(() => {
        clearTimeout(init.timer);
        init.timer = setTimeout(refresh, 120);
    });
    observer.observe(analysis, { childList: true, subtree: true, attributes: true, attributeFilter: ["hidden"] });
    refresh();
}

if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
