function markNegativeValues(root) {
  root.querySelectorAll(".stock-summary-grid .stock-metric-card, .stock-metrics-grid .stock-metric-card").forEach((card) => {
    const value = card.querySelector(".stock-metric-value");
    const text = value?.textContent?.trim() || "";
    card.classList.toggle("stock-negative-card", /^-/.test(text) || /₹-/.test(text) || /\$-/.test(text));
  });

  root.querySelectorAll(".stock-table td").forEach((cell) => {
    const text = cell.textContent?.trim() || "";
    cell.classList.toggle("stock-negative-cell", /^-/.test(text) || /₹-/.test(text) || /\$-/.test(text));
  });
}

function init() {
  const details = document.getElementById("stock-details");
  if (!details) return;

  const observer = new MutationObserver(() => markNegativeValues(details));
  observer.observe(details, { childList: true, subtree: true, characterData: true });
  markNegativeValues(details);
}

if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init, { once: true });
else init();
