export function showLoading(container, message = "Loading...") {
    if (!container) return;
    container.innerHTML = `
        <div class="loading-overlay">
            <div class="loading-content">
                <div class="loading-spinner-large"></div>
                <div class="loading-text">${message}</div>
            </div>
        </div>
    `;
}

export function hideLoading(container) {
    if (!container) return;
    container.innerHTML = "";
}
