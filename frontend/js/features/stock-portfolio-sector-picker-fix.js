/* Stock Selection parity fix: mobile-safe portal, reliable sector population and selection. */
(function installPortfolioSectorPickerFix() {
    let cachedSectors = null;
    let loading = null;

    function escapeHtml(value) {
        return String(value ?? "")
            .replaceAll("&", "&amp;")
            .replaceAll("<", "&lt;")
            .replaceAll(">", "&gt;")
            .replaceAll('"', "&quot;")
            .replaceAll("'", "&#039;");
    }

    async function loadSectors() {
        if (cachedSectors) return cachedSectors;
        if (loading) return loading;
        loading = fetch("/api/stocks/universe", { headers: { Accept: "application/json" }, cache: "no-store" })
            .then(response => response.json().then(data => {
                if (!response.ok) throw new Error(data?.detail || `HTTP ${response.status}`);
                const stocks = Array.isArray(data?.stocks) ? data.stocks : [];
                cachedSectors = [...new Set(stocks.map(stock => String(stock?.sector || "").trim()).filter(Boolean))]
                    .sort((a, b) => a.localeCompare(b));
                return cachedSectors;
            }))
            .catch(error => {
                console.warn("Unable to load portfolio sectors:", error);
                return [];
            })
            .finally(() => { loading = null; });
        return loading;
    }

    function selectedSectorItems() {
        return [...document.querySelectorAll("#portfolio-sector-list .category-picker-item.selected")];
    }

    function updateSelectionUi() {
        const items = selectedSectorItems();
        const values = items.map(item => String(item.dataset.value || "").trim()).filter(Boolean);
        const value = document.getElementById("portfolio-sector-value");
        const count = document.getElementById("portfolio-sector-count");

        document.querySelectorAll("#portfolio-sector-list .category-picker-item").forEach(item => {
            const selected = item.classList.contains("selected");
            const checkbox = item.querySelector(".category-picker-checkbox");
            if (checkbox) checkbox.textContent = selected ? "✓" : "";
        });

        if (value) {
            value.textContent = values.length === 0
                ? "All Sectors"
                : values.length === 1
                    ? values[0]
                    : `${values.length} sectors selected`;
            value.classList.toggle("has-selection", values.length > 0);
        }
        if (count) count.textContent = `${values.length} selected`;

        // Reuse the existing Stock Analysis filtering event. The portfolio
        // builder's stock-search listener calls pbRenderStockList(), which
        // reads the selected sector classes above.
        const search = document.getElementById("portfolio-stock-search");
        search?.dispatchEvent(new Event("input", { bubbles: true }));
    }

    async function populate() {
        const list = document.getElementById("portfolio-sector-list");
        if (!list) return;
        const sectors = await loadSectors();
        if (!sectors.length) return;

        const selected = new Set(selectedSectorItems().map(item => String(item.dataset.value || "").trim()).filter(Boolean));
        const search = String(document.getElementById("portfolio-sector-search")?.value || "").trim().toLowerCase();
        const visible = sectors.filter(sector => sector.toLowerCase().includes(search));

        list.innerHTML = visible.map(sector => `
            <div class="category-picker-item ${selected.has(sector) ? "selected" : ""}" data-value="${escapeHtml(sector)}">
                <span class="category-picker-checkbox">${selected.has(sector) ? "✓" : ""}</span>
                <span>${escapeHtml(sector)}</span>
            </div>`).join("") || `<div class="category-picker-footer">No sectors found</div>`;
    }

    function boot() {
        const trigger = document.getElementById("portfolio-sector-trigger");
        const dropdown = document.getElementById("portfolio-sector-dropdown");
        const wrap = document.querySelector(".portfolio-sector-picker");
        if (!trigger || !dropdown || !wrap || trigger.dataset.pbPortalFix === "1") return;

        trigger.dataset.pbPortalFix = "1";

        const style = document.createElement("style");
        style.id = "portfolio-sector-portal-fix-css";
        style.textContent = `
            .portfolio-sector-picker { overflow:visible !important; position:relative; z-index:100; }
            .portfolio-sector-picker .category-picker-trigger { position:relative; z-index:2; }
            .category-picker-dropdown.pb-sector-portal {
                position:fixed !important;
                left:auto;
                right:auto;
                top:auto;
                width:var(--pb-picker-width, 420px);
                max-height:min(430px, calc(100vh - 24px));
                z-index:2147483000 !important;
                overflow:hidden;
                transform:none !important;
            }
        `;
        document.head.appendChild(style);

        dropdown.classList.add("pb-sector-portal");
        document.body.appendChild(dropdown);

        const position = () => {
            if (dropdown.hidden) return;
            const rect = trigger.getBoundingClientRect();
            const width = Math.max(rect.width, 360);
            const maxLeft = Math.max(8, window.innerWidth - width - 8);
            const left = Math.min(Math.max(8, rect.left), maxLeft);
            const below = window.innerHeight - rect.bottom - 8;
            const above = rect.top - 8;
            const openBelow = below >= 280 || below >= above;
            const height = Math.min(430, Math.max(180, openBelow ? below : above));

            dropdown.style.setProperty("--pb-picker-width", `${width}px`);
            dropdown.style.left = `${left}px`;
            dropdown.style.width = `${width}px`;
            dropdown.style.maxHeight = `${height}px`;
            dropdown.style.top = openBelow
                ? `${Math.min(window.innerHeight - height - 8, rect.bottom + 6)}px`
                : `${Math.max(8, rect.top - height - 6)}px`;
        };

        window.addEventListener("resize", position, { passive: true });
        window.addEventListener("scroll", position, { passive: true, capture: true });

        // The portal moves the dropdown outside .portfolio-sector-picker.
        // Handle selection here in capture phase so the old document-level
        // click handler cannot swallow the sector click before filtering runs.
        document.addEventListener("click", event => {
            const item = event.target.closest?.("#portfolio-sector-list .category-picker-item");
            if (item) {
                event.preventDefault();
                event.stopImmediatePropagation();
                item.classList.toggle("selected");
                updateSelectionUi();
                return;
            }

            const selectAll = event.target.closest?.("#portfolio-sector-select-all");
            if (selectAll) {
                event.preventDefault();
                event.stopImmediatePropagation();
                document.querySelectorAll("#portfolio-sector-list .category-picker-item")
                    .forEach(option => option.classList.add("selected"));
                updateSelectionUi();
                return;
            }

            const clearAll = event.target.closest?.("#portfolio-sector-clear-all");
            if (clearAll) {
                event.preventDefault();
                event.stopImmediatePropagation();
                document.querySelectorAll("#portfolio-sector-list .category-picker-item.selected")
                    .forEach(option => option.classList.remove("selected"));
                updateSelectionUi();
                return;
            }

            if (event.target !== trigger && !trigger.contains(event.target)) return;
            event.preventDefault();
            event.stopImmediatePropagation();
            dropdown.hidden = !dropdown.hidden;
            trigger.setAttribute("aria-expanded", String(!dropdown.hidden));
            if (!dropdown.hidden) {
                requestAnimationFrame(() => {
                    populate();
                    position();
                });
            }
        }, true);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", boot, { once: true });
    } else {
        boot();
    }

    const observer = new MutationObserver(() => boot());
    observer.observe(document.documentElement, { childList: true, subtree: true });
})();
