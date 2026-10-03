const PORTFOLIO_STORAGE_KEY = "market-analysis-stock-portfolio-v1";
const PORTFOLIO_PAGE_SIZE = 40;

let portfolioStocks = [];
let portfolioHoldings = new Map();
let portfolioPage = 1;

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
            if (symbol && Number.isFinite(allocation) && allocation > 0) {
                portfolioHoldings.set(symbol, { allocation });
            }
        });
    } catch (_) {
        portfolioHoldings.clear();
    }
}

function pbSavePortfolio() {
    const payload = [...portfolioHoldings.entries()].map(([symbol, value]) => ({
        symbol,
        allocation: Number(value.allocation) || 0,
    }));
    localStorage.setItem(PORTFOLIO_STORAGE_KEY, JSON.stringify(payload));
}

function pbSelectedCount() {
    return portfolioHoldings.size;
}

function pbTotalAllocation() {
    return [...portfolioHoldings.values()].reduce((sum, item) => sum + (Number(item.allocation) || 0), 0);
}

function pbFormatPercent(value) {
    return Number(value).toLocaleString("en-IN", { maximumFractionDigits: 2 });
}

function pbFilteredStocks() {
    const query = String(document.getElementById("portfolio-stock-search")?.value || "").trim().toLowerCase();
    const sector = String(document.getElementById("portfolio-sector-filter")?.value || "").trim();
    const cap = String(document.getElementById("portfolio-cap-filter")?.value || "").trim().toLowerCase();

    return portfolioStocks.filter(stock => {
        if (sector && String(stock.sector || "").trim() !== sector) return false;
        if (cap && pbCapKey(stock) !== cap) return false;
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

    list.innerHTML = visible.length
        ? visible.map(pbStockRow).join("")
        : `<div class="stock-no-data">No stocks match the current selection.</div>`;

    summary.innerHTML = `<strong>${result.length}</strong> stock${result.length === 1 ? "" : "s"} available${result.length !== portfolioStocks.length ? " after the current filters" : ""}.`;

    list.querySelectorAll(".stock-select-btn").forEach(button => {
        button.addEventListener("click", event => {
            event.preventDefault();
            const row = button.closest(".stock-picker-row");
            const symbol = String(row?.dataset.symbol || "").trim().toUpperCase();
            if (!symbol) return;
            const stock = portfolioStocks.find(item => String(item.symbol || "").trim().toUpperCase() === symbol);
            if (!stock) return;

            if (portfolioHoldings.has(symbol)) {
                portfolioHoldings.delete(symbol);
            } else {
                portfolioHoldings.set(symbol, { allocation: 0 });
            }

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
        .map(([symbol, value]) => ({
            symbol,
            stock: portfolioStocks.find(item => String(item.symbol || "").trim().toUpperCase() === symbol),
            allocation: Number(value.allocation) || 0,
        }))
        .filter(item => item.stock);

    const total = pbTotalAllocation();
    const valid = entries.length > 0 && Math.abs(total - 100) < 0.01;

    count.textContent = `${entries.length} selected`;
    totalEl.textContent = `${pbFormatPercent(total)}%`;
    empty.hidden = entries.length > 0;
    holdings.hidden = entries.length === 0;
    clearButton.hidden = entries.length === 0;

    if (!entries.length) {
        holdings.innerHTML = "";
    } else {
        holdings.innerHTML = entries.map(({ symbol, stock, allocation }) => `
            <div class="portfolio-holding" data-symbol="${pbEsc(symbol)}">
                <div class="portfolio-holding-info">
                    <strong>${pbEsc(stock.name || symbol)}</strong>
                    <small>${pbEsc(symbol)} · ${pbEsc(stock.sector || "—")}</small>
                </div>
                <div class="portfolio-allocation-control">
                    <label class="sr-only" for="portfolio-allocation-${pbEsc(symbol)}">Allocation for ${pbEsc(stock.name || symbol)}</label>
                    <input id="portfolio-allocation-${pbEsc(symbol)}" class="portfolio-allocation-input" type="number" min="0" max="100" step="0.1" value="${pbEsc(allocation)}" inputmode="decimal" aria-label="Allocation for ${pbEsc(stock.name || symbol)}">
                    <span>%</span>
                </div>
                <button class="portfolio-remove" type="button" title="Remove ${pbEsc(stock.name || symbol)}" aria-label="Remove ${pbEsc(stock.name || symbol)}">×</button>
            </div>`).join("");

        holdings.querySelectorAll(".portfolio-allocation-input").forEach(input => {
            input.addEventListener("input", () => {
                const row = input.closest(".portfolio-holding");
                const symbol = String(row?.dataset.symbol || "").trim().toUpperCase();
                let value = Number(input.value);
                if (!Number.isFinite(value)) value = 0;
                value = Math.max(0, Math.min(100, value));
                portfolioHoldings.set(symbol, { allocation: value });
                pbSavePortfolio();
                pbUpdatePortfolioSummary();
            });
        });

        holdings.querySelectorAll(".portfolio-remove").forEach(button => {
            button.addEventListener("click", () => {
                const row = button.closest(".portfolio-holding");
                const symbol = String(row?.dataset.symbol || "").trim().toUpperCase();
                if (!symbol) return;
                portfolioHoldings.delete(symbol);
                pbSavePortfolio();
                pbRenderPortfolio();
                pbRenderStockList();
            });
        });
    }

    continueButton.disabled = !valid;
    status.className = `portfolio-status ${valid ? "portfolio-status-success" : "portfolio-status-warn"}`;
    status.textContent = valid
        ? "Portfolio allocation is complete. You can continue to portfolio analysis."
        : entries.length === 0
            ? "Add stocks and set the allocation to 100%."
            : total < 100
                ? `Allocate another ${pbFormatPercent(100 - total)}% to reach 100%.`
                : `Reduce the allocation by ${pbFormatPercent(total - 100)}% to reach 100%.`;
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
    status.textContent = valid
        ? "Portfolio allocation is complete. You can continue to portfolio analysis."
        : total < 100
            ? `Allocate another ${pbFormatPercent(100 - total)}% to reach 100%.`
            : `Reduce the allocation by ${pbFormatPercent(total - 100)}% to reach 100%.`;
}

function pbPopulateSectors() {
    const select = document.getElementById("portfolio-sector-filter");
    if (!select) return;
    const sectors = [...new Set(portfolioStocks.map(stock => String(stock.sector || "").trim()).filter(Boolean))].sort((a, b) => a.localeCompare(b));
    select.innerHTML = `<option value="">All sectors</option>${sectors.map(sector => `<option value="${pbEsc(sector)}">${pbEsc(sector)}</option>`).join("")}`;
}

function pbBindFilters() {
    const search = document.getElementById("portfolio-stock-search");
    const sector = document.getElementById("portfolio-sector-filter");
    const cap = document.getElementById("portfolio-cap-filter");
    const reset = document.getElementById("portfolio-reset-filters");

    const render = () => {
        portfolioPage = 1;
        pbRenderStockList();
    };

    search?.addEventListener("input", render);
    sector?.addEventListener("change", render);
    cap?.addEventListener("change", render);
    reset?.addEventListener("click", () => {
        if (search) search.value = "";
        if (sector) sector.value = "";
        if (cap) cap.value = "";
        render();
    });

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
        window.setTimeout(() => {
            if (button) button.textContent = "Continue to Portfolio Analysis";
        }, 1200);
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
        pbPopulateSectors();
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
    pbLoadUniverse();
}
