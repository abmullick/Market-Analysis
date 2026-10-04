/* Cosmetic-only enhancer for the Additional Ratio comparison table. */
(function () {
  function decorate() {
    const tables = document.querySelectorAll("#stock-details table");
    tables.forEach((table) => {
      const firstHeader = table.querySelector("thead th, thead td");
      if (!firstHeader || firstHeader.textContent.trim().toLowerCase() !== "additional ratio") return;

      table.classList.add("stock-additional-ratio-table");
      const wrapper = table.closest(".stock-table-wrap, .stock-comparison-table-wrap, div") || table.parentElement;
      if (wrapper) wrapper.classList.add("stock-additional-ratio-table-wrap");
    });
  }

  const observer = new MutationObserver(decorate);
  observer.observe(document.body, { childList: true, subtree: true });
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", decorate, { once: true });
  } else {
    decorate();
  }
})();
