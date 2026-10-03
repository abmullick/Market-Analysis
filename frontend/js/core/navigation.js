const MARKET_ANALYSIS_FAVICON = "/static/images/hero-market-analysis.png?v=4";
const MARKET_ANALYSIS_LOGO = "/static/images/hero-market-analysis.png?v=4";

// Apply the home-page Market Analysis artwork as the favicon on every page
// that loads the shared navigation module. Remove older favicon declarations
// so the browser does not continue using /favicon.ico or the legacy icon.
function setMarketAnalysisFavicon() {
    document.querySelectorAll('link[rel="icon"], link[rel="shortcut icon"], link[rel="apple-touch-icon"]').forEach((link) => link.remove());

    const favicon = document.createElement("link");
    favicon.rel = "icon";
    favicon.type = "image/png";
    favicon.href = MARKET_ANALYSIS_FAVICON;
    document.head.appendChild(favicon);
}

function setMarketAnalysisHeaderLogo() {
    document.querySelectorAll(".site-header .logo").forEach((logo) => {
        logo.src = MARKET_ANALYSIS_LOGO;
        logo.alt = "Market Analysis";
    });
}

function loadPortfolioBuilderButtonTheme() {
    const page = document.body?.dataset.page;
    if (page !== "portfolio-builder" && page !== "portfolio-select-funds") return;
    if (document.getElementById("portfolio-builder-button-theme")) return;

    const stylesheet = document.createElement("link");
    stylesheet.id = "portfolio-builder-button-theme";
    stylesheet.rel = "stylesheet";
    stylesheet.href = "/css/features/portfolio-builder-buttons.css?v=2";
    document.head.appendChild(stylesheet);
}

function loadHorizontalTableScrollTheme() {
    if (!document.getElementById("horizontal-table-scroll-theme")) {
        const stylesheet = document.createElement("link");
        stylesheet.id = "horizontal-table-scroll-theme";
        stylesheet.rel = "stylesheet";
        stylesheet.href = "/css/features/horizontal-table-scroll.css?v=20261003-1";
        document.head.appendChild(stylesheet);
    }

    if (!document.getElementById("horizontal-table-scroll-script")) {
        const script = document.createElement("script");
        script.id = "horizontal-table-scroll-script";
        script.type = "module";
        script.src = "/js/core/horizontal-table-scroll.js?v=20261003-1";
        document.head.appendChild(script);
    }
}

function configureHelpLinks() {
    document.querySelectorAll('a[href="/help.html"], a[href="help.html"]').forEach((link) => {
        link.target = "_blank";
        link.rel = "noopener noreferrer";
    });
}

setMarketAnalysisFavicon();
setMarketAnalysisHeaderLogo();
loadPortfolioBuilderButtonTheme();
loadHorizontalTableScrollTheme();
configureHelpLinks();

export function initNavigation() {
    const nav = document.getElementById("main-nav");
    if (!nav) return;

    setMarketAnalysisHeaderLogo();
    loadPortfolioBuilderButtonTheme();
    loadHorizontalTableScrollTheme();

    const path = window.location.pathname;
    const isActive = (href) => href === "/" ? path === "/" : path === href;

    nav.innerHTML = `
        <a href="/" class="${isActive("/") ? "active" : ""}">Home</a>
        <a href="/mutual-funds.html" class="${isActive("/mutual-funds.html") ? "active" : ""}">Mutual Fund Analysis</a>
        <a href="/portfolio-builder.html" class="${isActive("/portfolio-builder.html") ? "active" : ""}">Mutual Fund Portfolio Builder</a>
        <a href="/bond-analysis.html" class="${isActive("/bond-analysis.html") ? "active" : ""}">Bond Analysis</a>
        <a href="/stocks.html" class="${isActive("/stocks.html") ? "active" : ""}">Stock Analysis</a>
        <a href="/stock-portfolio-builder.html" class="${isActive("/stock-portfolio-builder.html") ? "active" : ""}">Stock Portfolio Builder</a>
        <a href="/help.html" target="_blank" rel="noopener noreferrer" class="${isActive("/help.html") ? "active" : ""}">Help</a>
    `;
}
