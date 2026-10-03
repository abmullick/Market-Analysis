/* Stock Portfolio — chart segregation layer.
 *
 * Presentation-only. Existing Chart.js instances, data, calculations and
 * endpoints are untouched. The layer moves each existing visualization into
 * its own collapsible card using the same Portfolio Builder card language.
 */

const CHART_CARD_CONFIG = [
    {
        selector: ".portfolio-performance-chart-wrap",
        key: "return-trend",
        title: "Portfolio Return Trend",
        subtitle: "Historical annualised price CAGR across the current allocation",
        icon: "trend",
        color: "#059669",
        tint: "rgba(5,150,105,.055)",
        border: "rgba(5,150,105,.22)",
        highlights: () => {
            const section = document.querySelector(".portfolio-performance-section");
            return [...(section?.querySelectorAll(".portfolio-performance-cards .stock-metric-card") || [])]
                .slice(0, 3)
                .map(card => ({
                    value: card.querySelector(".stock-metric-value")?.textContent?.trim() || "—",
                    label: card.querySelector(".stock-metric-label")?.textContent?.trim() || "Return"
                }));
        }
    },
    {
        selector: ".portfolio-performance-side",
        key: "holding-return-view",
        title: "Holding Return View",
        subtitle: "3Y historical return by holding, alongside current allocation",
        icon: "bars",
        color: "#2563eb",
        tint: "rgba(37,99,235,.055)",
        border: "rgba(37,99,235,.22)",
        highlights: () => {
            const section = document.querySelector(".portfolio-performance-section");
            const rows = [...(section?.querySelectorAll(".portfolio-performance-holding") || [])];
            return rows.slice(0, 3).map(row => ({
                value: row.querySelector("strong")?.textContent?.trim() || "—",
                label: row.querySelector("span")?.textContent?.trim() || "Holding"
            }));
        }
    },
    {
        selector: ".portfolio-benchmark-chart-wrap",
        key: "benchmark-chart",
        title: "Benchmark Return Comparison",
        subtitle: "Portfolio CAGR against the selected market benchmark",
        icon: "compare",
        color: "#7c3aed",
        tint: "rgba(124,58,237,.055)",
        border: "rgba(124,58,237,.22)",
        highlights: () => {
            const section = document.querySelector("#portfolio-benchmark-section");
            return [...(section?.querySelectorAll(".portfolio-benchmark-highlight-card") || [])]
                .slice(0, 3)
                .map(card => ({
                    value: card.querySelector("strong")?.textContent?.trim() || "—",
                    label: card.querySelector("span")?.textContent?.trim() || "Comparison"
                }));
        }
    },
    {
        selector: ".portfolio-positioning-chart-wrap",
        key: "positioning-map",
        title: "Quality × Growth Positioning",
        subtitle: "Revenue growth and ROE with bubble size representing allocation",
        icon: "scatter",
        color: "#0f766e",
        tint: "rgba(15,118,110,.055)",
        border: "rgba(15,118,110,.22)",
        highlights: () => {
            const section = document.querySelector("#portfolio-positioning-map");
            return [...(section?.querySelectorAll(".portfolio-positioning-summary > div") || [])]
                .slice(0, 3)
                .map(card => ({
                    value: card.querySelector("strong")?.textContent?.trim() || "—",
                    label: card.querySelector("span")?.textContent?.trim() || "Positioning"
                }));
        }
    },
    {
        selector: ".portfolio-risk-chart-wrap",
        key: "drawdown-chart",
        title: "Historical Drawdown Path",
        subtitle: "Portfolio drawdown history and recovery profile",
        icon: "risk",
        color: "#b45309",
        tint: "rgba(180,83,9,.055)",
        border: "rgba(180,83,9,.22)",
        highlights: () => {
            const section = document.querySelector("#portfolio-risk-drawdown");
            return [...(section?.querySelectorAll(".portfolio-risk-card") || [])]
                .slice(0, 3)
                .map(card => ({
                    value: card.querySelector("strong")?.textContent?.trim() || "—",
                    label: card.querySelector("span")?.textContent?.trim() || "Risk"
                }));
        }
    }
];

const CHART_ICONS = {
    trend: '<polyline points="3 17 9 11 13 14 21 5"></polyline><polyline points="15 5 21 5 21 11"></polyline>',
    bars: '<path d="M5 20V10"></path><path d="M12 20V4"></path><path d="M19 20V7"></path><path d="M3 20h18"></path>',
    compare: '<path d="M4 18V6"></path><path d="M12 18V3"></path><path d="M20 18V9"></path><path d="M2 18h20"></path>',
    scatter: '<circle cx="7" cy="15" r="2"></circle><circle cx="13" cy="9" r="2"></circle><circle cx="19" cy="6" r="2"></circle><path d="M5 17l6-6 6-3"></path>',
    risk: '<path d="M12 3l7 3v5c0 5-3.2 8.4-7 10-3.8-1.6-7-5-7-10V6l7-3z"></path><path d="M8 14l2-2 2 2 4-5"></path>'
};

function escapeHtml(value) {
    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

function iconSvg(type) {
    return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${CHART_ICONS[type] || CHART_ICONS.trend}</svg>`;
}

function findConfig(wrapper) {
    return CHART_CARD_CONFIG.find(config => wrapper.matches(config.selector)) || null;
}

function buildCard(wrapper, config, index) {
    if (!wrapper || wrapper.dataset.pbChartCard === "1") return;

    const card = document.createElement("section");
    card.className = "pb-section-card pb-health-card stock-pb-chart-card";
    card.dataset.pbChartCard = "1";
    card.dataset.pbChartKey = config.key;
    card.style.setProperty("--pb-accent", config.color);
    card.style.setProperty("--pb-tint", config.tint);
    card.style.setProperty("--pb-border", config.border);

    const contentId = `stock-pb-chart-content-${config.key}-${index}`;
    const content = document.createElement("div");
    content.className = "pb-section-content pb-health-content stock-pb-chart-content";
    content.id = contentId;

    wrapper.parentNode.insertBefore(card, wrapper);
    content.appendChild(wrapper);

    const highlights = (config.highlights?.() || []).filter(item => item.value && item.label).slice(0, 3);
    const kpis = highlights.map(item => `<span class="stock-pb-highlight"><strong>${escapeHtml(item.value)}</strong><small>${escapeHtml(item.label)}</small></span>`).join("");

    const header = document.createElement("div");
    header.className = "pb-section-header pb-health-header stock-pb-card-header stock-pb-chart-header";
    header.setAttribute("role", "button");
    header.setAttribute("tabindex", "0");
    header.setAttribute("aria-expanded", "false");
    header.setAttribute("aria-controls", contentId);
    header.innerHTML = `
        <div class="pb-health-header-main">
            <span class="pb-section-icon pb-health-icon stock-pb-icon">${iconSvg(config.icon)}</span>
            <span class="pb-section-titlewrap pb-health-summary-label">${escapeHtml(config.title)}<small>${escapeHtml(config.subtitle)}</small></span>
        </div>
        <div class="pb-section-kpis stock-pb-kpis">${kpis}</div>
        <div class="pb-section-controls">
            <button type="button" class="pb-section-caret-btn pb-health-caret-button stock-pb-caret" aria-expanded="false" aria-controls="${contentId}" aria-label="Expand ${escapeHtml(config.title)}">
                <svg class="pb-section-caret pb-health-caret" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 7.5L10 12.5L15 7.5"></path></svg>
            </button>
        </div>`;

    card.append(header, content);

    const toggle = () => {
        const open = header.getAttribute("aria-expanded") === "true";
        setOpen(card, !open);
    };
    header.addEventListener("click", event => {
        if (event.target.closest("button")) return;
        toggle();
    });
    header.addEventListener("keydown", event => {
        if (event.target.closest("button")) return;
        if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            toggle();
        }
    });
    header.querySelector("button")?.addEventListener("click", event => {
        event.preventDefault();
        event.stopPropagation();
        toggle();
    });

    setOpen(card, false);
    requestAnimationFrame(() => window.dispatchEvent(new Event("resize")));
}

function setOpen(card, open) {
    const header = card.querySelector(":scope > .pb-section-header");
    const content = card.querySelector(":scope > .pb-section-content");
    const button = card.querySelector(":scope .stock-pb-caret");
    if (!header || !content) return;
    header.setAttribute("aria-expanded", String(open));
    content.hidden = !open;
    card.classList.toggle("is-open", open);
    if (button) {
        button.setAttribute("aria-expanded", String(open));
        button.setAttribute("aria-label", `${open ? "Collapse" : "Expand"} ${card.querySelector(".pb-health-summary-label")?.childNodes?.[0]?.textContent?.trim() || "chart"}`);
    }
    if (open) requestAnimationFrame(() => window.dispatchEvent(new Event("resize")));
}

function wrapCharts() {
    const root = document.getElementById("stock-portfolio-analysis-content");
    if (!root || root.hidden) return;

    CHART_CARD_CONFIG.forEach((config, index) => {
        const wrappers = [...root.querySelectorAll(config.selector)].filter(el => el.dataset.pbChartCard !== "1");
        wrappers.forEach((wrapper, offset) => buildCard(wrapper, config, `${index}-${offset}`));
    });
}

function init() {
    const root = document.getElementById("stock-portfolio-analysis-content");
    if (!root) return;
    const observer = new MutationObserver(() => {
        clearTimeout(init.timer);
        init.timer = setTimeout(wrapCharts, 100);
    });
    observer.observe(root, { childList: true, subtree: true, attributes: true, attributeFilter: ["hidden"] });
    wrapCharts();
}

if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
else init();
