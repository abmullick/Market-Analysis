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
}
