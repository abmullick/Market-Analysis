export function initHome() {
    const cards = document.querySelectorAll(".card");
    cards.forEach((card) => {
        card.addEventListener("click", () => {
            const href = card.getAttribute("data-href");
            if (href) {
                window.location.href = href;
            }
        });
    });

    // Landing-page cue: a persistent two-way page navigator.
    // Down arrow at the top/middle of the page -> jump to the bottom.
    // Up arrow near the bottom -> return to the top.
    const hero = document.querySelector(".hero");
    const options = document.querySelector(".cards-grid");

    if (hero && options && !document.querySelector(".landing-scroll-cue")) {
        const cue = document.createElement("button");
        cue.type = "button";
        cue.className = "landing-scroll-cue";
        cue.setAttribute("aria-label", "Scroll to the bottom of the page");
        cue.title = "Scroll to the bottom";
        cue.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5v14"></path><path d="m6 13 6 6 6-6"></path></svg>';

        const positionCueInVisualViewport = () => {
            const viewportWidth = window.visualViewport?.width || window.innerWidth;
            cue.style.setProperty("--landing-cue-left", `${Math.max(8, viewportWidth - 62)}px`);
        };

        const updateCue = () => {
            const doc = document.documentElement;
            const scrollTop = window.scrollY || doc.scrollTop || 0;
            const viewportHeight = window.innerHeight;
            const maxScroll = Math.max(0, doc.scrollHeight - viewportHeight);
            const nearBottom = maxScroll - scrollTop <= 80;

            cue.classList.toggle("is-up", nearBottom);
            cue.setAttribute(
                "aria-label",
                nearBottom ? "Scroll to the top of the page" : "Scroll to the bottom of the page"
            );
            cue.title = nearBottom ? "Back to top" : "Scroll to the bottom";
            cue.innerHTML = nearBottom
                ? '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 19V5"></path><path d="m6 11 6-6 6 6"></path></svg>'
                : '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5v14"></path><path d="m6 13 6 6 6-6"></path></svg>';

            positionCueInVisualViewport();
        };

        cue.addEventListener("click", () => {
            const doc = document.documentElement;
            const scrollTop = window.scrollY || doc.scrollTop || 0;
            const maxScroll = Math.max(0, doc.scrollHeight - window.innerHeight);
            const nearBottom = maxScroll - scrollTop <= 80;

            window.scrollTo({
                top: nearBottom ? 0 : maxScroll,
                behavior: "smooth"
            });
        });

        document.body.appendChild(cue);
        updateCue();
        window.addEventListener("scroll", updateCue, { passive: true });
        window.addEventListener("resize", updateCue, { passive: true });
        window.visualViewport?.addEventListener("resize", positionCueInVisualViewport, { passive: true });
        window.visualViewport?.addEventListener("scroll", positionCueInVisualViewport, { passive: true });
    }
}
