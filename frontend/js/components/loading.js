export function showLoading(container) {
    if (!container) return;
    container.innerHTML = '<div class="loading">Loading...</div>';
}

export function hideLoading(container) {
    if (!container) return;
    container.innerHTML = "";
}
