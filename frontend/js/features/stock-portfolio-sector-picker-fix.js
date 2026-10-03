/* Stock Selection parity fix: use the same mobile-safe portal behavior as Stock Analysis. */
(function installPortfolioSectorPickerFix() {
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

        document.addEventListener("click", event => {
            if (event.target !== trigger && !trigger.contains(event.target)) return;
            event.preventDefault();
            event.stopImmediatePropagation();
            dropdown.hidden = !dropdown.hidden;
            trigger.setAttribute("aria-expanded", String(!dropdown.hidden));
            if (!dropdown.hidden) requestAnimationFrame(position);
        }, true);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", boot, { once: true });
    } else {
        boot();
    }

    // The application mounts feature HTML dynamically during navigation.
    const observer = new MutationObserver(() => boot());
    observer.observe(document.documentElement, { childList: true, subtree: true });
})();
