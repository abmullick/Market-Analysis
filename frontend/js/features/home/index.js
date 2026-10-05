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

    // Landing-page cue: gently indicate that more options are available below.
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

        const updateCue = () => {
            cue.classList.toggle("is-hidden", window.scrollY > 120);
        };

        document.body.appendChild(cue);
        updateCue();
        window.addEventListener("scroll", updateCue, { passive: true });
    }
}
