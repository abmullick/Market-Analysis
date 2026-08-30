export function openModal(container, title, content) {
    if (!container) return;
    container.innerHTML = "";

    const overlay = document.createElement("div");
    overlay.className = "modal-overlay";

    const dialog = document.createElement("div");
    dialog.className = "modal";

    const header = document.createElement("div");
    header.className = "modal-header";

    const titleEl = document.createElement("h3");
    titleEl.textContent = title;
    header.appendChild(titleEl);

    const close = document.createElement("button");
    close.textContent = "Close";
    close.className = "modal-close";
    close.addEventListener("click", () => closeModal(container));
    header.appendChild(close);

    dialog.appendChild(header);
    dialog.appendChild(content);
    overlay.appendChild(dialog);
    container.appendChild(overlay);
}

export function closeModal(container) {
    if (!container) return;
    container.innerHTML = "";
}
