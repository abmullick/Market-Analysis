const MARKET_ANALYSIS_FAVICON = "/static/images/hero-market-analysis.png?v=4";
const MARKET_ANALYSIS_LOGO = "/static/images/hero-market-analysis.png?v=4";

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

function normalizeStockPortfolioHeader() {
    if (document.body?.dataset.page !== "stock-portfolio-builder") return;
    const header = document.querySelector(".site-header");
    if (!header || header.dataset.stockHeaderNormalized === "1") return;
    header.innerHTML = `
        <div class="header-left">
            <img src="/static/images/logo.png" alt="Market Analysis" class="logo">
            <h1>Stock Portfolio Builder</h1>
        </div>
        <nav id="main-nav"></nav>
    `;
    header.dataset.stockHeaderNormalized = "1";
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

function loadStockPortfolioBuilderExactTheme() {
    if (document.body?.dataset.page !== "stock-portfolio-builder") return;
    if (document.getElementById("stock-portfolio-builder-exact-theme")) return;
    const stylesheet = document.createElement("link");
    stylesheet.id = "stock-portfolio-builder-exact-theme";
    stylesheet.rel = "stylesheet";
    stylesheet.href = "/css/features/stock-portfolio-builder-buttons-exact.css?v=20261004-1";
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

function loadFloatingNavigationTheme() {
    if (document.getElementById("floating-navigation-theme")) return;
    const stylesheet = document.createElement("link");
    stylesheet.id = "floating-navigation-theme";
    stylesheet.rel = "stylesheet";
    stylesheet.href = "/css/features/floating-navigation.css?v=20261004-2";
    document.head.appendChild(stylesheet);
}

function removeLegacyHelpLinks() {
    document.querySelectorAll(".help-link").forEach((link) => link.remove());
}

normalizeStockPortfolioHeader();
setMarketAnalysisFavicon();
setMarketAnalysisHeaderLogo();
loadPortfolioBuilderButtonTheme();
loadStockPortfolioBuilderExactTheme();
loadHorizontalTableScrollTheme();
loadFloatingNavigationTheme();
removeLegacyHelpLinks();

const NAV_ITEMS = [
    {
        href: "/mutual-funds.html",
        label: "Mutual Fund Analysis",
        icon: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 19V9m5 10V5m5 14v-7m5 7V3"/><path d="M2 19h20"/></svg>'
    },
    {
        href: "/portfolio-builder.html",
        label: "Mutual Fund Portfolio Builder",
        icon: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 7h14v13H5z"/><path d="M9 7V5a3 3 0 0 1 6 0v2M8 12h8M12 9v6"/></svg>'
    },
    {
        href: "/bond-analysis.html",
        label: "Bond Analysis",
        icon: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 20h16M6 20V9l6-5 6 5v11M9 20v-7h6v7M3 9l9-7 9 7"/></svg>'
    },
    {
        href: "/stocks.html",
        label: "Stock Analysis",
        icon: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 19V5m0 14h16"/><path d="m7 15 4-4 3 2 5-6"/><path d="M16 7h3v3"/></svg>'
    },
    {
        href: "/stock-portfolio-builder.html",
        label: "Stock Portfolio Builder",
        icon: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 7h14v13H5z"/><path d="M9 7V5a3 3 0 0 1 6 0v2M8 12h8M12 9v6"/></svg>'
    },
    {
        href: "/help.html",
        label: "Help & Methodology",
        icon: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M9.8 9a2.5 2.5 0 1 1 4.7 1.2c-.7 1.2-2.5 1.4-2.5 3"/><path d="M12 17h.01"/></svg>'
    }
];

const HOME_ICON = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m3 11 9-8 9 8"/><path d="M5 10v10h14V10M9 20v-6h6v6"/></svg>';
const MENU_ICON = '<span class="nav-menu-lines" aria-hidden="true"><i></i><i></i><i></i></span>';

function closeFloatingNavigation(nav) {
    nav.classList.remove("is-open");
    const toggle = nav.querySelector(".floating-nav-toggle");
    if (toggle) {
        toggle.setAttribute("aria-expanded", "false");
        toggle.setAttribute("aria-label", "Open navigation menu");
    }
}

export function initNavigation() {
    normalizeStockPortfolioHeader();
    removeLegacyHelpLinks();
    loadFloatingNavigationTheme();

    const nav = document.getElementById("main-nav");
    if (!nav || nav.dataset.floatingNavigationReady === "1") return;

    // Keep the navigation completely independent of the page header. This prevents
    // the fixed dock from ever covering the product-owner/title area, including on mobile.
    if (nav.closest(".site-header")) {
        document.body.appendChild(nav);
    }

    setMarketAnalysisHeaderLogo();
    loadPortfolioBuilderButtonTheme();
    loadStockPortfolioBuilderExactTheme();
    loadHorizontalTableScrollTheme();

    const path = window.location.pathname;
    const isActive = (href) => href === "/" ? path === "/" : path === href;

    nav.innerHTML = `
        <div class="floating-nav-backdrop" aria-hidden="true"></div>
        <div id="floating-nav-items" class="floating-nav-items" aria-label="Market Analysis tools">
            <div class="floating-nav-heading">Explore Market Analysis</div>
            ${NAV_ITEMS.map((item, index) => `
                <a href="${item.href}"
                   class="floating-nav-item${isActive(item.href) ? " active" : ""}"
                   data-nav-index="${index}"
                   target="_blank" rel="noopener noreferrer">
                    <span class="floating-nav-item-icon">${item.icon}</span>
                    <span class="floating-nav-item-label">${item.label}</span>
                    <span class="floating-nav-item-arrow" aria-hidden="true">›</span>
                </a>
            `).join("")}
        </div>
        <div class="floating-nav-dock">
            <a href="/" class="floating-nav-home${isActive("/") ? " active" : ""}" aria-label="Home" title="Home">
                ${HOME_ICON}
                <span>Home</span>
            </a>
            <button class="floating-nav-toggle" type="button" aria-label="Open navigation menu" aria-expanded="false" aria-controls="floating-nav-items">
                ${MENU_ICON}
                <span class="floating-nav-toggle-label">Menu</span>
            </button>
        </div>
    `;

    const toggle = nav.querySelector(".floating-nav-toggle");
    const backdrop = nav.querySelector(".floating-nav-backdrop");
    const items = nav.querySelectorAll(".floating-nav-item");

    toggle.addEventListener("click", (event) => {
        event.stopPropagation();
        const open = nav.classList.toggle("is-open");
        toggle.setAttribute("aria-expanded", String(open));
        toggle.setAttribute("aria-label", open ? "Close navigation menu" : "Open navigation menu");
    });

    backdrop.addEventListener("click", () => closeFloatingNavigation(nav));
    items.forEach((item) => item.addEventListener("click", () => closeFloatingNavigation(nav)));

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && nav.classList.contains("is-open")) {
            closeFloatingNavigation(nav);
            toggle.focus();
        }
    });

    nav.dataset.floatingNavigationReady = "1";
}
