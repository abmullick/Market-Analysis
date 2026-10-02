const CONTAINER_ID = "ranking-table-container";
const CONTROL_ID = "ranking-horizontal-scroll";

function syncScrollWidth(container, track) {
    const width = Math.max(container.scrollWidth, container.clientWidth);
    track.style.width = `${width}px`;
}

function installHorizontalScrollControl() {
    const container = document.getElementById(CONTAINER_ID);
    const control = document.getElementById(CONTROL_ID);
    if (!container || !control) return;

    if (!control.dataset.initialized) {
        control.innerHTML = `
            <div class="table-scroll-hint">
                <span class="table-scroll-icon" aria-hidden="true">↔</span>
                <span>Scroll horizontally for more information</span>
            </div>
            <div class="table-scroll-track" role="scrollbar" aria-label="Scroll table horizontally" tabindex="0">
                <div class="table-scroll-track-inner"></div>
            </div>
        `;

        const track = control.querySelector(".table-scroll-track");
        const inner = control.querySelector(".table-scroll-track-inner");

        track.addEventListener("scroll", () => {
            container.scrollLeft = track.scrollLeft;
        });

        container.addEventListener("scroll", () => {
            if (Math.abs(track.scrollLeft - container.scrollLeft) > 1) {
                track.scrollLeft = container.scrollLeft;
            }
            updateHorizontalScrollState(container, control);
        }, { passive: true });

        track.addEventListener("keydown", (event) => {
            if (event.key === "ArrowLeft") {
                event.preventDefault();
                track.scrollLeft -= 120;
            } else if (event.key === "ArrowRight") {
                event.preventDefault();
                track.scrollLeft += 120;
            }
        });

        control._track = track;
        control._inner = inner;
        control.dataset.initialized = "true";
    }

    const track = control._track;
    const inner = control._inner;
    syncScrollWidth(container, inner);
    track.scrollLeft = container.scrollLeft;
    updateHorizontalScrollState(container, control);
}

function updateHorizontalScrollState(container, control) {
    const canScroll = container.scrollWidth > container.clientWidth + 2;
    control.classList.toggle("is-scrollable", canScroll);
    control.classList.toggle("is-at-start", container.scrollLeft <= 2);
    control.classList.toggle(
        "is-at-end",
        container.scrollLeft + container.clientWidth >= container.scrollWidth - 2
    );
}

function refresh() {
    installHorizontalScrollControl();
}

const observer = new MutationObserver(refresh);

function init() {
    const container = document.getElementById(CONTAINER_ID);
    const control = document.getElementById(CONTROL_ID);
    if (!container || !control) return;

    observer.observe(container, { childList: true, subtree: true });
    window.addEventListener("resize", refresh);
    refresh();
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, { once: true });
} else {
    init();
}
