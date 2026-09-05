export function initHelp() {
    const triggers = document.querySelectorAll(".metric-trigger");
    triggers.forEach(trigger => {
        trigger.addEventListener("click", () => {
            const item = trigger.parentElement;
            const isOpen = item.classList.contains("open");

            document.querySelectorAll(".metric-item.open").forEach(openItem => {
                openItem.classList.remove("open");
                openItem.querySelector(".metric-panel").setAttribute("hidden", "");
                openItem.querySelector(".metric-chevron").style.transform = "";
            });

            if (!isOpen) {
                item.classList.add("open");
                const panel = item.querySelector(".metric-panel");
                panel.removeAttribute("hidden");
                trigger.querySelector(".metric-chevron").style.transform = "rotate(180deg)";
            }
        });
    });

    const feedbackForm = document.getElementById("feedback-form");
    const feedbackInput = document.getElementById("feedback-message");
    const feedbackError = document.getElementById("feedback-error");
    if (!feedbackForm || !feedbackInput || !feedbackError) return;

    feedbackForm.addEventListener("submit", (event) => {
        event.preventDefault();
        const message = feedbackInput.value.trim();
        if (!message) {
            feedbackError.textContent = "Please enter feedback before opening your email client.";
            feedbackError.removeAttribute("hidden");
            feedbackInput.focus();
            return;
        }

        feedbackError.setAttribute("hidden", "");
        const subject = encodeURIComponent("Market Analysis Feedback");
        const body = encodeURIComponent(message);
        window.location.href = `mailto:abmullick@gmail.com?subject=${subject}&body=${body}`;
    });
}
