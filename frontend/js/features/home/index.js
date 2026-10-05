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

    // Landing-page cue: keep the scroll indicator visible until the options are actually reached.
    const hero = document.querySelector(".hero");
    const options = document.querySelector(".cards-grid");

    if (hero && options && !document.querySelector(".landing-scroll-cue")) {
        const cue = document.createElement("button");
        cue.type = "button";
        cue.className = "landing-scroll-cue";
        cue.setAttribute("aria-label", "Scroll down to explore more options");
        cue.title = "Scroll to explore more options";
        cue.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5v13"></path><path d="m6 12 6 6 6-6"></path></svg>';

        cue.addEventListener("click", () => {
            options.scrollIntoView({ behavior: "smooth", block: "start" });
        });

        // The app can have a wider layout viewport than the phone's visual viewport.
        // Explicitly position the cue from visualViewport.width so it cannot end up
        // outside the visible mobile screen or require horizontal scrolling to find.
        const positionCueInVisualViewport = () => {
            const viewportWidth = window.visualViewport?.width || window.innerWidth;
            cue.style.setProperty("--landing-cue-left", `${Math.max(8, viewportWidth - 62)}px`);
        };

        const updateCue = () => {
            // Do not hide merely because the user has started scrolling.
            // Hide only after the options section has reached the top portion of the viewport.
            const optionsTop = options.getBoundingClientRect().top;
            const hasReachedOptions = optionsTop <= 120;
            cue.classList.toggle("is-hidden", hasReachedOptions);
            positionCueInVisualViewport();
        };

        document.body.appendChild(cue);
        updateCue();
        window.addEventListener("scroll", updateCue, { passive: true });
        window.addEventListener("resize", updateCue, { passive: true });
        window.visualViewport?.addEventListener("resize", positionCueInVisualViewport, { passive: true });
        window.visualViewport?.addEventListener("scroll", positionCueInVisualViewport, { passive: true });
    }
}
