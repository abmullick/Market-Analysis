const STORAGE_KEY = "marketAnalysis.compareStocks";
const MAX_COMPARE = 4;

function readSaved() {
  try {
    const value = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
    return Array.isArray(value)
      ? [...new Set(value.map((x) => String(x || "").trim().toUpperCase()).filter(Boolean))].slice(0, MAX_COMPARE)
      : [];
  } catch {
    return [];
  }
}

function saveSaved(symbols) {
  const clean = [...new Set(symbols.map((x) => String(x || "").trim().toUpperCase()).filter(Boolean))].slice(0, MAX_COMPARE);
  localStorage.setItem(STORAGE_KEY, JSON.stringify(clean));
  return clean;
}

function addSymbol(symbol) {
  const current = readSaved();
  if (current.includes(symbol)) return current;

  // Keep the comparison list bounded while ensuring the stock the user just
  // selected for analysis is added automatically.
  const next = current.length >= MAX_COMPARE
    ? [...current.slice(1), symbol]
    : [...current, symbol];
  return saveSaved(next);
}

function removeSymbol(symbol) {
  return saveSaved(readSaved().filter((x) => x !== symbol));
}

function syncVisibleCheckboxes() {
  const saved = readSaved();
  document.querySelectorAll(".stock-picker-row .stock-compare-choice input").forEach((checkbox) => {
    const row = checkbox.closest(".stock-picker-row");
    if (!row) return;
    const symbol = String(row.dataset.symbol || "").trim().toUpperCase();
    if (symbol) checkbox.checked = saved.includes(symbol);
  });
}

function activateSavedCheckboxes() {
  const saved = readSaved();
  if (!saved.length) return;

  document.querySelectorAll(".stock-picker-row .stock-compare-choice input").forEach((checkbox) => {
    const row = checkbox.closest(".stock-picker-row");
    if (!row) return;
    const symbol = String(row.dataset.symbol || "").trim().toUpperCase();
    if (!symbol || !saved.includes(symbol) || checkbox.checked) return;

    // The comparison module owns the checkbox change handler. Triggering a
    // real change event keeps its internal compareSymbols state in sync.
    checkbox.checked = true;
    checkbox.dispatchEvent(new Event("change", { bubbles: true }));
  });
}

function addSelectedStockFromButton(button) {
  const row = button.closest(".stock-picker-row");
  const symbol = String(row?.dataset.symbol || "").trim().toUpperCase();
  if (!symbol) return;
  addSymbol(symbol);

  // stock-detail re-renders the selection list after the click. Wait for the
  // comparison module's MutationObserver to decorate the new row, then check
  // the corresponding Compare box.
  setTimeout(activateSavedCheckboxes, 0);
  setTimeout(activateSavedCheckboxes, 50);
  setTimeout(activateSavedCheckboxes, 150);
}

function addSymbolFromUrl() {
  const params = new URLSearchParams(location.search);
  const symbol = (params.get("symbol") || "").trim().toUpperCase();
  if (symbol) addSymbol(symbol);
}

document.addEventListener("click", (event) => {
  const selectButton = event.target.closest(".stock-picker-row .stock-select-btn");
  if (selectButton) {
    addSelectedStockFromButton(selectButton);
    return;
  }

  const removeButton = event.target.closest(".stock-compare-remove");
  if (removeButton) {
    const symbol = String(removeButton.dataset.removeSymbol || "").trim().toUpperCase();
    if (symbol) removeSymbol(symbol);
    return;
  }
});

document.addEventListener("change", (event) => {
  const checkbox = event.target.closest(".stock-picker-row .stock-compare-choice input");
  if (!checkbox) return;
  const symbol = String(checkbox.closest(".stock-picker-row")?.dataset.symbol || "").trim().toUpperCase();
  if (!symbol) return;
  checkbox.checked ? addSymbol(symbol) : removeSymbol(symbol);
});

const observer = new MutationObserver(() => {
  activateSavedCheckboxes();
});
observer.observe(document.body, { childList: true, subtree: true });

addSymbolFromUrl();
activateSavedCheckboxes();
