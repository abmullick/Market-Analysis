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

setMarketAnalysisFavicon();
setMarketAnalysisHeaderLogo();

export function initNavigation() {
    const nav = document.getElementById("main-nav");
    if (!nav) return;

    setMarketAnalysisHeaderLogo();

    const path = window.location.pathname;
    const isActive = (href) => href === "/" ? path === "/" : path === href;

    nav.innerHTML = `
        <a href="/" class="${isActive("/") ? "active" : ""}">Home</a>
        <a href="/mutual-funds.html" class="${isActive("/mutual-funds.html") ? "active" : ""}">Mutual Fund Analysis</a>
        <a href="/portfolio-builder.html" class="${isActive("/portfolio-builder.html") ? "active" : ""}">Mutual Fund Portfolio Builder</a>
        <a href="/bond-analysis.html" class="${isActive("/bond-analysis.html") ? "active" : ""}">Bond Analysis</a>
        <a href="/stocks.html" class="${isActive("/stocks.html") ? "active" : ""}">Stock Analysis</a>
        <a href="/stock-portfolio-builder.html" class="${isActive("/stock-portfolio-builder.html") ? "active" : ""}">Stock Portfolio Builder</a>
        <a href="/help.html" class="${isActive("/help.html") ? "active" : ""}">Help</a>
    `;
}
