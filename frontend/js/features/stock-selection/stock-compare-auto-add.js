const STORAGE_KEY = "marketAnalysis.compareStocks";
const MAX_COMPARE = 4;

function isFreshSelectionPage() {
  const params = new URLSearchParams(location.search);
  return /\/stocks\.html$/i.test(location.pathname) && !params.has("symbol") && !params.has("compare");
}

// The comparison list is a working selection, not a persistent watchlist.
// Older versions restored the previous list from localStorage, which made
// unrelated stocks appear pre-selected every time the Stock Analysis page
// was opened. Start a fresh selection page empty; stocks are still added
// automatically when the user actually selects one for analysis.
if (isFreshSelectionPage()) {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    // Ignore storage restrictions; the in-memory comparison state still works.
  }
}

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

  const next = current.length >= MAX_COMPARE
    ? [...current.slice(1), symbol]
    : [...current, symbol];
  return saveSaved(next);
}

function removeSymbol(symbol) {
  return saveSaved(readSaved().filter((x) => x !== symbol));
}

function activateSavedCheckboxes() {
  const saved = readSaved();
  if (!saved.length) return;

  document.querySelectorAll(".stock-picker-row .stock-compare-choice input").forEach((checkbox) => {
    const row = checkbox.closest(".stock-picker-row");
    if (!row) return;
    const symbol = String(row.dataset.symbol || "").trim().toUpperCase();
    if (!symbol || !saved.includes(symbol) || checkbox.checked) return;

    checkbox.checked = true;
    checkbox.dispatchEvent(new Event("change", { bubbles: true }));
  });
}

function addSelectedStockFromButton(button) {
  const row = button.closest(".stock-picker-row");
  const symbol = String(row?.dataset.symbol || "").trim().toUpperCase();
  if (!symbol) return;
  addSymbol(symbol);

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
