export function initNavigation() {
    const nav = document.getElementById("main-nav");
    if (!nav) return;

    const path = window.location.pathname;
    const isActive = (href) => href === "/" ? path === "/" : path === href;

    nav.innerHTML = `
        <a href="/" class="${isActive("/") ? "active" : ""}">Home</a>
        <a href="/mutual-funds.html" class="${isActive("/mutual-funds.html") ? "active" : ""}">Mutual Fund Analysis</a>
        <a href="/portfolio-builder.html" class="${isActive("/portfolio-builder.html") ? "active" : ""}">Mutual Fund Portfolio Builder</a>
        <a href="/stocks.html" class="${isActive("/stocks.html") ? "active" : ""}">Stock Analysis</a>
        <a href="/stock-portfolio-builder.html" class="${isActive("/stock-portfolio-builder.html") ? "active" : ""}">Stock Portfolio Builder</a>
        <a href="/help.html" class="${isActive("/help.html") ? "active" : ""}">Help</a>
    `;
}
