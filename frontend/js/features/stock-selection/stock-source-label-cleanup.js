function cleanStockProviderLabels(root) {
  if (!root) return;
  const nodes = root.querySelectorAll("small, li, p, span, div");
  nodes.forEach((node) => {
    const text = node.textContent || "";
    if (!/screener/i.test(text)) return;
    if (node.matches("small") && /source\s*:/i.test(text)) {
      node.remove();
      return;
    }
    if (node.matches("li") && /screener/i.test(text)) {
      node.remove();
      return;
    }
    if (node.children.length === 0) {
      node.textContent = text.replace(/\bScreener(?:\.in)?\b/gi, "financial data provider").replace(/\bprimary\s+Indian\s+fundamental[- ]data\s+source\b/gi, "financial data provider");
    }
  });
}

function initStockProviderLabelCleanup() {
  const details = document.getElementById("stock-details");
  if (!details) return;
  cleanStockProviderLabels(details);
  const observer = new MutationObserver(() => cleanStockProviderLabels(details));
  observer.observe(details, { childList: true, subtree: true, characterData: true });
}

if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", initStockProviderLabelCleanup, { once: true });
else initStockProviderLabelCleanup();
