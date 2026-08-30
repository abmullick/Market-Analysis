export function initNavigation() {
    const nav = document.getElementById("main-nav");
    if (!nav) return;

    const path = window.location.pathname;
    const isActive = (href) => path.includes(href);

    nav.innerHTML = `
        <a href="index.html" class="${isActive("index.html") ? "active" : ""}">Home</a>
        <a href="stocks.html" class="${isActive("stocks.html") ? "active" : ""}">Stock Selection</a>
        <a href="portfolio.html" class="${isActive("portfolio.html") ? "active" : ""}">Portfolio Analysis</a>
        <a href="mutual-funds.html" class="${isActive("mutual-funds.html") ? "active" : ""}">Mutual Fund Analysis</a>
    `;
}
