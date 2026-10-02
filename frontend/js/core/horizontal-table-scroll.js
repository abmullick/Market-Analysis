const TABLE_SCROLL_SELECTORS = [
    "#ranking-table-container",
    ".comparison-table-wrapper",
    ".stock-table-wrap",
    ".stock-comparison-table-wrap",
    ".ba-table-wrap",
];

function isHorizontallyScrollable(element) {
    if (!element || element.offsetParent === null) return false;
    return element.scrollWidth > element.clientWidth + 2;
}

function createScrollControl(container) {
    if (container.previousElementSibling?.classList.contains("table-horizontal-scroll")) {
        return container.previousElementSibling;
    }

    const control = document.createElement("div");
    control.className = "table-horizontal-scroll";
    control.innerHTML = `
        <div class="table-scroll-hint">
            <span class="table-scroll-icon" aria-hidden="true">↔</span>
            <span>Scroll horizontally for more information</span>
        </div>
        <div class="table-scroll-track" role="scrollbar" aria-label="Scroll table horizontally" tabindex="0">
            <div class="table-scroll-track-inner"></div>
        </div>
    `;

    container.parentNode.insertBefore(control, container);
    return control;
}

function syncControl(container, control) {
    const track = control.querySelector(".table-scroll-track");
    const inner = control.querySelector(".table-scroll-track-inner");
    if (!track || !inner) return;

    const maxScroll = Math.max(0, container.scrollWidth - container.clientWidth);
    const scrollable = maxScroll > 2;

    control.classList.toggle("is-scrollable", scrollable);
    inner.style.width = `${container.scrollWidth}px`;

    if (!scrollable) return;

    const ratio = maxScroll > 0 ? container.scrollLeft / maxScroll : 0;
    const trackMax = Math.max(0, track.scrollWidth - track.clientWidth);
    if (Math.abs(track.scrollLeft - ratio * trackMax) > 1) {
        track.scrollLeft = ratio * trackMax;
    }

    control.classList.toggle("is-at-end", container.scrollLeft >= maxScroll - 2);
    control.setAttribute("aria-valuenow", String(Math.round(container.scrollLeft)));
    control.setAttribute("aria-valuemax", String(Math.round(maxScroll)));
}

function wireContainer(container) {
    if (!container || container.dataset.horizontalScrollWired === "true") return;
    if (!container.querySelector("table")) return;

    const control = createScrollControl(container);
    const track = control.querySelector(".table-scroll-track");
    if (!track) return;

    container.dataset.horizontalScrollWired = "true";

    let syncing = false;
    container.addEventListener("scroll", () => {
        if (syncing) return;
        syncing = true;
        const maxScroll = Math.max(0, container.scrollWidth - container.clientWidth);
        const trackMax = Math.max(0, track.scrollWidth - track.clientWidth);
        track.scrollLeft = maxScroll ? (container.scrollLeft / maxScroll) * trackMax : 0;
        control.classList.toggle("is-at-end", container.scrollLeft >= maxScroll - 2);
        syncing = false;
    }, { passive: true });

    track.addEventListener("scroll", () => {
        if (syncing) return;
        syncing = true;
        const trackMax = Math.max(0, track.scrollWidth - track.clientWidth);
        const containerMax = Math.max(0, container.scrollWidth - container.clientWidth);
        container.scrollLeft = trackMax ? (track.scrollLeft / trackMax) * containerMax : 0;
        syncing = false;
    }, { passive: true });

    track.addEventListener("keydown", (event) => {
        if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
        event.preventDefault();
        container.scrollBy({ left: event.key === "ArrowRight" ? 180 : -180, behavior: "smooth" });
    });

    const refresh = () => syncControl(container, control);
    window.addEventListener("resize", refresh, { passive: true });
    if (window.ResizeObserver) new ResizeObserver(refresh).observe(container);
    refresh();
}

function scanForWideTables(root = document) {
    const candidates = new Set();

    TABLE_SCROLL_SELECTORS.forEach((selector) => {
        root.querySelectorAll?.(selector).forEach((element) => candidates.add(element));
    });

    root.querySelectorAll?.("table").forEach((table) => {
        let parent = table.parentElement;
        while (parent && parent !== document.body) {
            const overflow = getComputedStyle(parent).overflowX;
            if (overflow === "auto" || overflow === "scroll") {
                candidates.add(parent);
                break;
            }
            parent = parent.parentElement;
        }
    });

    candidates.forEach(wireContainer);
}

function initHorizontalTableScroll() {
    scanForWideTables();

    const observer = new MutationObserver((mutations) => {
        let shouldScan = false;
        for (const mutation of mutations) {
            if (mutation.addedNodes.length) {
                shouldScan = true;
                break;
            }
        }
        if (shouldScan) requestAnimationFrame(() => scanForWideTables());
    });

    observer.observe(document.body, { childList: true, subtree: true });
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initHorizontalTableScroll, { once: true });
} else {
    initHorizontalTableScroll();
}
