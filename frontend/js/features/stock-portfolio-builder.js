const PORTFOLIO_STORAGE_KEY = "market-analysis-stock-portfolio-v1";
const PORTFOLIO_PAGE_SIZE = 40;

let portfolioStocks = [];
let portfolioHoldings = new Map();
let portfolioPage = 1;
let portfolioSelectedSectors = new Set();

function pbEsc(value) {
    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

function pbCapKey(stock) {
    const supplied = String(stock?.market_cap_band || "").trim().toLowerCase();
    if (["large", "mid", "small", "micro"].includes(supplied)) return supplied;
    const value = Number(stock?.market_cap_cr);
    if (!Number.isFinite(value)) return null;
    if (value >= 100000) return "large";
    if (value >= 20000) return "mid";
    if (value >= 5000) return "small";
    return "micro";
}

function pbCapLabel(stock) {
    const cap = pbCapKey(stock);
    return cap === "large" ? "Large Cap" : cap === "mid" ? "Mid Cap" : cap === "small" ? "Small Cap" : cap === "micro" ? "Micro Cap" : "";
}

function pbLoadSavedPortfolio() {
    try {
        const saved = JSON.parse(localStorage.getItem(PORTFOLIO_STORAGE_KEY) || "[]");
        if (!Array.isArray(saved)) return;
        saved.forEach(item => {
            const symbol = String(item?.symbol || "").trim().toUpperCase();
            const allocation = Number(item?.allocation);
            if (symbol && Number.isFinite(allocation) && allocation > 0) portfolioHoldings.set(symbol, { allocation });
        });
    } catch (_) {
        portfolioHoldings.clear();
    }
}

function pbSavePortfolio() {
    const payload = [...portfolioHoldings.entries()].map(([symbol, value]) => ({ symbol, allocation: Number(value.allocation) || 0 }));
    localStorage.setItem(PORTFOLIO_STORAGE_KEY, JSON.stringify(payload));
}

function pbTotalAllocation() {
    return [...portfolioHoldings.values()].reduce((sum, item) => sum + (Number(item.allocation) || 0), 0);
}

function pbFormatPercent(value) {
    return Number(value).toLocaleString("en-IN", { maximumFractionDigits: 2 });
}

function pbSelectedSectors() {
    return [...portfolioSelectedSectors];
}

function pbSelectedCaps() {
    return [...document.querySelectorAll("#portfolio-cap-filter input:checked")]
        .map(input => String(input.value || "").trim().toLowerCase());
}

function pbFilteredStocks() {
    const query = String(document.getElementById("portfolio-stock-search")?.value || "").trim().toLowerCase();
    const sectors = pbSelectedSectors();
    const caps = pbSelectedCaps();

    return portfolioStocks.filter(stock => {
        const sector = String(stock.sector || "").trim();
        if (sectors.length && !sectors.includes(sector)) return false;
        if (caps.length && !caps.includes(pbCapKey(stock))) return false;
        if (query) {
            const haystack = `${stock.name || ""} ${stock.symbol || ""}`.toLowerCase();
            if (!haystack.includes(query)) return false;
        }
        return true;
    });
}

function pbStockRow(stock) {
    const symbol = String(stock.symbol || "").trim().toUpperCase();
    const selected = portfolioHoldings.has(symbol);
    const capLabel = pbCapLabel(stock);
    return `<div class="stock-picker-row ${selected ? "selected" : ""}" data-symbol="${pbEsc(symbol)}">
        <div>
            <strong>${pbEsc(stock.name || symbol)}${capLabel ? ` <span class="stock-cap-badge ${pbEsc(pbCapKey(stock))}">${pbEsc(capLabel)}</span>` : ""}</strong>
            <small>${pbEsc(symbol)}</small>
        </div>
        <div class="stock-picker-metrics">
            <span>Market Cap <b>${stock.market_cap_cr == null ? "—" : `₹${Number(stock.market_cap_cr).toLocaleString("en-IN", { maximumFractionDigits: 0 })} Cr`}</b></span>
            <span>Sector <b>${pbEsc(stock.sector || "—")}</b></span>
        </div>
        <button class="stock-select-btn" type="button">${selected ? "Added" : "Add"}</button>
    </div>`;
}

function pbRenderStockList() {
    const list = document.getElementById("portfolio-stock-list");
    const summary = document.getElementById("portfolio-result-summary");
    if (!list || !summary) return;

    const result = pbFilteredStocks();
    const pages = Math.max(1, Math.ceil(result.length / PORTFOLIO_PAGE_SIZE));
    portfolioPage = Math.min(portfolioPage, pages);
    const start = (portfolioPage - 1) * PORTFOLIO_PAGE_SIZE;
    const visible = result.slice(start, start + PORTFOLIO_PAGE_SIZE);

    list.innerHTML = visible.length ? visible.map(pbStockRow).join("") : `<div class="stock-no-data">No stocks match the current selection.</div>`;
    summary.innerHTML = `<strong>${result.length}</strong> stock${result.length === 1 ? "" : "s"} available${result.length !== portfolioStocks.length ? " after the current filters" : ""}.`;

    list.querySelectorAll(".stock-select-btn").forEach(button => {
        button.addEventListener("click", event => {
            event.preventDefault();
            const row = button.closest(".stock-picker-row");
            const symbol = String(row?.dataset.symbol || "").trim().toUpperCase();
            const stock = portfolioStocks.find(item => String(item.symbol || "").trim().toUpperCase() === symbol);
            if (!stock) return;
            if (portfolioHoldings.has(symbol)) portfolioHoldings.delete(symbol);
            else portfolioHoldings.set(symbol, { allocation: 0 });
            pbSavePortfolio();
            pbRenderStockList();
            pbRenderPortfolio();
        });
    });

    list.parentElement.querySelector(".portfolio-pagination")?.remove();
    if (pages > 1) {
        const pager = document.createElement("div");
        pager.className = "stock-client-pagination portfolio-pagination";
        pager.innerHTML = `<span>Showing ${start + 1}–${Math.min(start + PORTFOLIO_PAGE_SIZE, result.length)} of ${result.length}</span><div class="stock-client-pagination-controls"><button type="button" data-page="${portfolioPage - 1}" ${portfolioPage <= 1 ? "disabled" : ""}>‹</button><span>${portfolioPage} / ${pages}</span><button type="button" data-page="${portfolioPage + 1}" ${portfolioPage >= pages ? "disabled" : ""}>›</button></div>`;
        list.insertAdjacentElement("afterend", pager);
        pager.querySelectorAll("[data-page]").forEach(button => button.addEventListener("click", () => {
            if (button.disabled) return;
            portfolioPage = Number(button.dataset.page);
            pbRenderStockList();
        }));
    }
}

function pbRenderPortfolio() {
    const empty = document.getElementById("portfolio-empty");
    const holdings = document.getElementById("portfolio-holdings");
    const totalEl = document.getElementById("portfolio-total");
    const status = document.getElementById("portfolio-status");
    const continueButton = document.getElementById("portfolio-continue");
    const clearButton = document.getElementById("portfolio-clear");
    const count = document.getElementById("portfolio-stock-count");
    if (!empty || !holdings || !totalEl || !status || !continueButton || !clearButton || !count) return;

    const entries = [...portfolioHoldings.entries()]
        .map(([symbol, value]) => ({ symbol, stock: portfolioStocks.find(item => String(item.symbol || "").trim().toUpperCase() === symbol), allocation: Number(value.allocation) || 0 }))
        .filter(item => item.stock);
    const total = pbTotalAllocation();
    const valid = entries.length > 0 && Math.abs(total - 100) < 0.01;

    count.textContent = `${entries.length} selected`;
    totalEl.textContent = `${pbFormatPercent(total)}%`;
    empty.hidden = entries.length > 0;
    holdings.hidden = entries.length === 0;
    clearButton.hidden = entries.length === 0;

    if (!entries.length) holdings.innerHTML = "";
    else {
        holdings.innerHTML = entries.map(({ symbol, stock, allocation }) => `
            <div class="portfolio-holding" data-symbol="${pbEsc(symbol)}">
                <div class="portfolio-holding-info"><strong>${pbEsc(stock.name || symbol)}</strong><small>${pbEsc(symbol)} · ${pbEsc(stock.sector || "—")}</small></div>
                <div class="portfolio-allocation-control">
                    <label class="sr-only" for="portfolio-allocation-${pbEsc(symbol)}">Allocation for ${pbEsc(stock.name || symbol)}</label>
                    <input id="portfolio-allocation-${pbEsc(symbol)}" class="portfolio-allocation-input" type="number" min="0" max="100" step="0.1" value="${pbEsc(allocation)}" inputmode="decimal" aria-label="Allocation for ${pbEsc(stock.name || symbol)}">
                    <span>%</span>
                </div>
                <button class="portfolio-remove" type="button" title="Remove ${pbEsc(stock.name || symbol)}" aria-label="Remove ${pbEsc(stock.name || symbol)}">×</button>
            </div>`).join("");

        holdings.querySelectorAll(".portfolio-allocation-input").forEach(input => input.addEventListener("input", () => {
            const row = input.closest(".portfolio-holding");
            const symbol = String(row?.dataset.symbol || "").trim().toUpperCase();
            let value = Number(input.value);
            if (!Number.isFinite(value)) value = 0;
            value = Math.max(0, Math.min(100, value));
            portfolioHoldings.set(symbol, { allocation: value });
            pbSavePortfolio();
            pbUpdatePortfolioSummary();
        }));

        holdings.querySelectorAll(".portfolio-remove").forEach(button => button.addEventListener("click", () => {
            const row = button.closest(".portfolio-holding");
            const symbol = String(row?.dataset.symbol || "").trim().toUpperCase();
            if (!symbol) return;
            portfolioHoldings.delete(symbol);
            pbSavePortfolio();
            pbRenderPortfolio();
            pbRenderStockList();
        }));
    }

    continueButton.disabled = !valid;
    status.className = `portfolio-status ${valid ? "portfolio-status-success" : "portfolio-status-warn"}`;
    status.textContent = valid ? "Portfolio allocation is complete. You can continue to portfolio analysis." : entries.length === 0 ? "Add stocks and set the allocation to 100%." : total < 100 ? `Allocate another ${pbFormatPercent(100 - total)}% to reach 100%.` : `Reduce the allocation by ${pbFormatPercent(total - 100)}% to reach 100%.`;
}

function pbUpdatePortfolioSummary() {
    const totalEl = document.getElementById("portfolio-total");
    const status = document.getElementById("portfolio-status");
    const continueButton = document.getElementById("portfolio-continue");
    if (!totalEl || !status || !continueButton) return;
    const total = pbTotalAllocation();
    const valid = portfolioHoldings.size > 0 && Math.abs(total - 100) < 0.01;
    totalEl.textContent = `${pbFormatPercent(total)}%`;
    continueButton.disabled = !valid;
    status.className = `portfolio-status ${valid ? "portfolio-status-success" : "portfolio-status-warn"}`;
    status.textContent = valid ? "Portfolio allocation is complete. You can continue to portfolio analysis." : total < 100 ? `Allocate another ${pbFormatPercent(100 - total)}% to reach 100%.` : `Reduce the allocation by ${pbFormatPercent(total - 100)}% to reach 100%.`;
}

function pbRenderSectorPicker() {
    const list = document.getElementById("portfolio-sector-list");
    const value = document.getElementById("portfolio-sector-value");
    if (!list) return;

    const query = String(document.getElementById("portfolio-sector-search")?.value || "").trim().toLowerCase();
    const sectors = [...new Set(portfolioStocks.map(stock => String(stock.sector || "").trim()).filter(Boolean))].sort((a, b) => a.localeCompare(b));
    const filtered = sectors.filter(sector => sector.toLowerCase().includes(query));

    list.innerHTML = filtered.map(sector => {
        const selected = portfolioSelectedSectors.has(sector);
        return `<div class="category-picker-item ${selected ? "selected" : ""}" data-value="${pbEsc(sector)}"><span class="category-picker-checkbox">${selected ? "✓" : ""}</span><span>${pbEsc(sector)}</span></div>`;
    }).join("") || `<div class="category-picker-footer">No sectors found</div>`;

    const values = pbSelectedSectors();
    if (value) {
        value.textContent = values.length === 0 ? "All Sectors" : values.length === 1 ? values[0] : `${values.length} sectors selected`;
        value.classList.toggle("has-selection", values.length > 0);
    }
}

function pbSetSectorDropdown(open) {
    const trigger = document.getElementById("portfolio-sector-trigger");
    const dropdown = document.getElementById("portfolio-sector-dropdown");
    if (!trigger || !dropdown) return;
    dropdown.hidden = !open;
    trigger.setAttribute("aria-expanded", String(open));
    if (open) requestAnimationFrame(() => pbPositionSectorDropdown());
}

function pbPositionSectorDropdown() {
    const trigger = document.getElementById("portfolio-sector-trigger");
    const dropdown = document.getElementById("portfolio-sector-dropdown");
    if (!trigger || !dropdown || dropdown.hidden) return;

    const rect = trigger.getBoundingClientRect();
    const width = Math.max(rect.width, 360);
    const left = Math.min(Math.max(8, rect.left), Math.max(8, window.innerWidth - width - 8));
    const below = window.innerHeight - rect.bottom - 8;
    const above = rect.top - 8;
    const openBelow = below >= 280 || below >= above;
    const height = Math.min(430, Math.max(220, openBelow ? below : above));

    dropdown.style.left = `${left}px`;
    dropdown.style.width = `${width}px`;
    dropdown.style.maxHeight = `${height}px`;
    dropdown.style.top = openBelow
        ? `${Math.min(window.innerHeight - height - 8, rect.bottom + 6)}px`
        : `${Math.max(8, rect.top - height - 6)}px`;
}

function pbInstallSectorDropdown() {
    const trigger = document.getElementById("portfolio-sector-trigger");
    const dropdown = document.getElementById("portfolio-sector-dropdown");
    const wrap = document.querySelector(".portfolio-sector-picker");
    if (!trigger || !dropdown || !wrap || trigger.dataset.pbBound === "1") return;
    trigger.dataset.pbBound = "1";

    dropdown.classList.add("pb-sector-portal");
    document.body.appendChild(dropdown);

    const closeIfOutside = event => {
        if (!wrap.contains(event.target) && !dropdown.contains(event.target)) pbSetSectorDropdown(false);
    };

    trigger.addEventListener("click", event => {
        event.preventDefault();
        event.stopPropagation();
        pbRenderSectorPicker();
        pbSetSectorDropdown(dropdown.hidden);
    });

    dropdown.addEventListener("click", event => event.stopPropagation());
    document.addEventListener("click", closeIfOutside);
    window.addEventListener("resize", pbPositionSectorDropdown, { passive: true });
    window.addEventListener("scroll", pbPositionSectorDropdown, { passive: true, capture: true });

    const sectorSearch = document.getElementById("portfolio-sector-search");
    sectorSearch?.addEventListener("input", pbRenderSectorPicker);

    dropdown.querySelector("#portfolio-sector-list")?.addEventListener("click", event => {
        const item = event.target.closest(".category-picker-item");
        if (!item) return;
        event.preventDefault();
        event.stopPropagation();
        const sector = String(item.dataset.value || "").trim();
        if (!sector) return;
        if (portfolioSelectedSectors.has(sector)) portfolioSelectedSectors.delete(sector);
        else portfolioSelectedSectors.add(sector);
        pbRenderSectorPicker();
        portfolioPage = 1;
        pbRenderStockList();
    });

    document.getElementById("portfolio-sector-select-all")?.addEventListener("click", event => {
        event.preventDefault();
        event.stopPropagation();
        const query = String(sectorSearch?.value || "").trim().toLowerCase();
        [...new Set(portfolioStocks.map(stock => String(stock.sector || "").trim()).filter(Boolean))]
            .filter(sector => sector.toLowerCase().includes(query))
            .forEach(sector => portfolioSelectedSectors.add(sector));
        pbRenderSectorPicker();
        portfolioPage = 1;
        pbRenderStockList();
    });

    document.getElementById("portfolio-sector-clear-all")?.addEventListener("click", event => {
        event.preventDefault();
        event.stopPropagation();
        portfolioSelectedSectors.clear();
        pbRenderSectorPicker();
        portfolioPage = 1;
        pbRenderStockList();
    });
}

function pbResetFilters() {
    const search = document.getElementById("portfolio-stock-search");
    if (search) search.value = "";
    document.querySelectorAll("#portfolio-cap-filter input").forEach(input => { input.checked = false; });
    portfolioSelectedSectors.clear();
    pbRenderSectorPicker();
    pbSetSectorDropdown(false);
    portfolioPage = 1;
    pbRenderStockList();
}

function pbBindFilters() {
    const search = document.getElementById("portfolio-stock-search");
    const reset = document.getElementById("portfolio-reset-filters");

    search?.addEventListener("input", () => { portfolioPage = 1; pbRenderStockList(); });
    document.querySelectorAll("#portfolio-cap-filter input").forEach(input => input.addEventListener("change", () => { portfolioPage = 1; pbRenderStockList(); }));
    reset?.addEventListener("click", pbResetFilters);

    document.getElementById("portfolio-clear")?.addEventListener("click", () => {
        portfolioHoldings.clear();
        pbSavePortfolio();
        pbRenderPortfolio();
        pbRenderStockList();
    });

    document.getElementById("portfolio-continue")?.addEventListener("click", () => {
        const payload = [...portfolioHoldings.entries()].map(([symbol, value]) => ({ symbol, allocation: Number(value.allocation) || 0 }));
        sessionStorage.setItem("market-analysis-stock-portfolio-current", JSON.stringify(payload));
        const button = document.getElementById("portfolio-continue");
        if (button) button.textContent = "Portfolio Saved";
        window.setTimeout(() => { if (button) button.textContent = "Continue to Portfolio Analysis"; }, 1200);
    });
}

async function pbLoadUniverse() {
    const list = document.getElementById("portfolio-stock-list");
    const summary = document.getElementById("portfolio-result-summary");
    try {
        const response = await fetch("/api/stocks/universe", { headers: { Accept: "application/json" }, cache: "no-store" });
        const data = await response.json();
        if (!response.ok) throw new Error(data?.detail || `HTTP ${response.status}`);
        portfolioStocks = Array.isArray(data.stocks) ? data.stocks : [];
        pbRenderSectorPicker();
        pbRenderStockList();
        pbRenderPortfolio();
    } catch (error) {
        console.warn("Unable to load stock universe:", error);
        if (list) list.innerHTML = `<div class="stock-error"><h2>Unable to load stocks</h2><p>${pbEsc(error?.message || "Please try again later.")}</p></div>`;
        if (summary) summary.textContent = "Stock universe unavailable.";
    }
}

export function initStockPortfolioBuilder() {
    pbLoadSavedPortfolio();
    pbBindFilters();
    pbInstallSectorDropdown();
    pbLoadUniverse();
}
