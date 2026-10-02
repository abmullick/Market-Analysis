const SF_CAP_BANDS = [
  { key: "large", label: "Large Cap" },
  { key: "mid", label: "Mid Cap" },
  { key: "small", label: "Small Cap" },
  { key: "micro", label: "Micro Cap" },
];

function addStockUniverseLiteCSS() {
  if (document.getElementById("stock-universe-lite-styles")) return;
  const style = document.createElement("style");
  style.id = "stock-universe-lite-styles";
  style.textContent = `
    .stock-filter-card,.stock-filter-body,.stock-filter-top,.category-picker { overflow:visible !important; }
    .category-picker { position:relative; width:100%; z-index:20; }
    .category-picker-trigger { width:100%; min-height:42px; display:flex; align-items:center; justify-content:space-between; gap:12px; padding:10px 13px; border:1px solid #cbd5e1; border-radius:10px; background:#fff; color:#0f172a; font:inherit; font-size:13px; cursor:pointer; text-align:left; }
    .category-picker-trigger:hover,.category-picker-trigger[aria-expanded="true"] { border-color:#2563eb; box-shadow:0 0 0 3px rgba(37,99,235,.08); }
    .category-picker-value { color:#64748b; font-weight:500; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
    .category-picker-value.has-selection { color:#0f172a; font-weight:600; }
    .category-picker-dropdown { position:absolute; top:calc(100% + 6px); left:0; right:0; z-index:99999; max-height:430px; overflow:hidden; background:#fff; border:1px solid #dbe4f0; border-radius:12px; box-shadow:0 16px 36px rgba(15,23,42,.20); }
    .category-picker-dropdown[hidden] { display:none; }
    .category-picker-search { display:flex; align-items:center; gap:8px; padding:10px; border-bottom:1px solid #e2e8f0; }
    .category-picker-search-input { flex:1; min-width:0; border:0; outline:0; background:transparent; font:inherit; font-size:13px; }
    .category-picker-actions { display:flex; justify-content:space-between; padding:8px 10px; border-bottom:1px solid #e2e8f0; }
    .category-picker-action { border:0; background:transparent; color:#2563eb; font:inherit; font-size:12px; font-weight:600; cursor:pointer; }
    .category-picker-list { max-height:320px; overflow-y:auto; padding:5px 0; }
    .category-picker-item { display:flex; align-items:center; gap:9px; padding:9px 12px; cursor:pointer; color:#334155; font-size:13px; }
    .category-picker-item:hover { background:#f8fafc; }
    .category-picker-item.selected { background:rgba(37,99,235,.06); color:#1d4ed8; font-weight:600; }
    .category-picker-checkbox { width:17px; height:17px; border:1px solid #cbd5e1; border-radius:4px; display:flex; align-items:center; justify-content:center; flex-shrink:0; background:#fff; }
    .category-picker-item.selected .category-picker-checkbox { border-color:#2563eb; background:#2563eb; color:#fff; }
    .category-picker-footer { padding:8px 12px; border-top:1px solid #e2e8f0; color:#64748b; font-size:11px; background:#f8fafc; }
    .stock-universe-extra-filters { display:block; margin-top:12px; }
    .stock-chip-filter { display:flex; align-items:center; gap:7px; flex-wrap:wrap; padding:10px 12px; border:1px solid #dbe4f0; border-radius:12px; background:#f8fafc; }
    .stock-chip-filter-label { font-size:11px; font-weight:700; color:#334155; margin-right:4px; }
    .stock-chip-filter label { position:relative; cursor:pointer; }
    .stock-chip-filter input { position:absolute; opacity:0; pointer-events:none; }
    .stock-chip-filter label > span { display:inline-flex; align-items:center; padding:7px 11px; border-radius:999px; background:#eef2ff; color:#475569; font-size:11px; font-weight:600; border:1px solid transparent; white-space:nowrap; }
    .stock-chip-filter input:checked + span { background:#172554; color:#fff; border-color:#172554; box-shadow:0 2px 6px rgba(15,23,42,.14); }
  `;
  document.head.appendChild(style);
}

function sfLiteCapKey(stock) {
  if (stock?.market_cap_band) return stock.market_cap_band;
  const n = Number(stock?.market_cap_cr);
  if (!Number.isFinite(n)) return null;
  if (n >= 100000) return "large";
  if (n >= 20000) return "mid";
  if (n >= 5000) return "small";
  return "micro";
}

function applyStockUniverseLiteFilters(old) {
  if (typeof universeStocks === "undefined" || !Array.isArray(universeStocks)) return;
  const selectedSectors = [...old.selectedOptions].map(o => o.value).filter(Boolean);
  const search = document.getElementById("stock-filter-search")?.value?.trim().toLowerCase() || "";
  const selectedCaps = [...document.querySelectorAll("#stock-cap-filter input:checked")].map(i => i.value);
  let stocks = universeStocks.slice();

  if (selectedSectors.length) stocks = stocks.filter(s => selectedSectors.includes(String(s.sector || "")));
  if (search) stocks = stocks.filter(s => String(s.symbol || "").toLowerCase().includes(search) || String(s.name || "").toLowerCase().includes(search));
  if (selectedCaps.length) stocks = stocks.filter(s => selectedCaps.includes(sfLiteCapKey(s)));

  const list = document.querySelector("#stock-selection-screen .stock-picker-list");
  if (list) {
    list.innerHTML = stocks.length
      ? (typeof stockRow === "function" ? stocks.map(stockRow).join("") : stocks.map(s => `<div class="stock-picker-row" data-symbol="${String(s.symbol || "").replaceAll('"','&quot;')}"><strong>${String(s.name || s.symbol || "")}</strong></div>`).join(""))
      : `<div class="stock-no-data">No stocks match these filters.</div>`;
  }

  const count = document.getElementById("stock-filter-toggle-count");
  if (count) count.textContent = `${stocks.length} stocks`;
  const footer = document.querySelector("#stock-filter-body .stock-filter-footer span:last-child");
  if (footer) footer.textContent = `${stocks.length} stocks`;
  const summary = document.querySelector("#stock-selection-screen .stock-result-summary");
  if (summary) summary.firstChild.textContent = `${stocks.length} stocks match the current filters.`;
}

function installSectorMultiSelectLite() {
  const old = document.getElementById("stock-sector");
  if (!old || old.dataset.enhanced) return;
  old.dataset.enhanced = "true";
  old.multiple = true;
  old.style.display = "none";

  const wrap = document.createElement("div");
  wrap.className = "category-picker stock-sector-picker";
  old.parentNode.insertBefore(wrap, old);
  wrap.appendChild(old);

  const trigger = document.createElement("button");
  trigger.type = "button";
  trigger.className = "category-picker-trigger";
  trigger.innerHTML = `<span class="category-picker-value" id="stock-sector-value">All Sectors</span><span>⌄</span>`;

  const dropdown = document.createElement("div");
  dropdown.className = "category-picker-dropdown";
  dropdown.hidden = true;
  dropdown.innerHTML = `<div class="category-picker-search"><span>⌕</span><input class="category-picker-search-input" id="stock-sector-search" placeholder="Search sectors..." autocomplete="off"></div><div class="category-picker-actions"><button type="button" class="category-picker-action" id="stock-sector-select-all">Select All</button><button type="button" class="category-picker-action" id="stock-sector-clear-all">Clear</button></div><div class="category-picker-list" id="stock-sector-list"></div><div class="category-picker-footer" id="stock-sector-count">0 selected</div>`;
  wrap.append(trigger, dropdown);

  let query = "";
  const update = () => {
    const selected = [...old.selectedOptions].map(o => o.value).filter(Boolean);
    const value = document.getElementById("stock-sector-value");
    if (!value) return;
    value.textContent = selected.length === 0 ? "All Sectors" : selected.length === 1 ? selected[0] : `${selected.length} sectors selected`;
    value.classList.toggle("has-selection", selected.length > 0);
    document.getElementById("stock-sector-count").textContent = `${selected.length} selected`;
    const opts = [...old.options].filter(o => o.value && o.textContent.toLowerCase().includes(query.toLowerCase()));
    document.getElementById("stock-sector-list").innerHTML = opts.map(o => `<div class="category-picker-item ${o.selected ? "selected" : ""}" data-value="${o.value.replaceAll('"','&quot;')}"><span class="category-picker-checkbox">${o.selected ? "✓" : ""}</span><span>${o.textContent}</span></div>`).join("") || `<div class="category-picker-footer">No sectors found</div>`;
  };

  document.getElementById("stock-sector-list").addEventListener("click", e => {
    const item = e.target.closest(".category-picker-item");
    if (!item) return;
    e.stopPropagation();
    const option = [...old.options].find(o => o.value === item.dataset.value);
    if (!option) return;
    option.selected = !option.selected;
    update();
    if (typeof selectedStock !== "undefined") selectedStock = null;
    applyStockUniverseLiteFilters(old);
  });

  trigger.addEventListener("click", e => { e.stopPropagation(); dropdown.hidden = !dropdown.hidden; trigger.setAttribute("aria-expanded", String(!dropdown.hidden)); });
  dropdown.addEventListener("click", e => e.stopPropagation());
  document.addEventListener("click", e => { if (!wrap.contains(e.target)) { dropdown.hidden = true; trigger.setAttribute("aria-expanded", "false"); } });
  document.getElementById("stock-sector-search").addEventListener("input", e => { query = e.target.value; update(); });
  document.getElementById("stock-sector-select-all").addEventListener("click", () => { [...old.options].forEach(o => { if (o.value) o.selected = true; }); update(); applyStockUniverseLiteFilters(old); });
  document.getElementById("stock-sector-clear-all").addEventListener("click", () => { [...old.options].forEach(o => o.selected = false); update(); applyStockUniverseLiteFilters(old); });
  const search = document.getElementById("stock-filter-search");
  if (search && search.dataset.liteFilterBound !== "1") {
    search.dataset.liteFilterBound = "1";
    search.addEventListener("input", e => { e.stopImmediatePropagation(); applyStockUniverseLiteFilters(old); }, true);
  }
  update();
}

function installCapLite() {
  const top = document.querySelector(".stock-filter-top");
  if (!top || document.getElementById("stock-cap-filter")) return;
  const block = document.createElement("div");
  block.className = "stock-universe-extra-filters";
  block.innerHTML = `<div class="stock-chip-filter" id="stock-cap-filter"><span class="stock-chip-filter-label">Market Cap</span>${SF_CAP_BANDS.map(b => `<label><input type="checkbox" value="${b.key}"><span>${b.label}</span></label>`).join("")}</div>`;
  top.appendChild(block);
  block.querySelectorAll("input").forEach(i => i.addEventListener("change", () => {
    const old = document.getElementById("stock-sector");
    if (old) applyStockUniverseLiteFilters(old);
  }));
}

function runStockUniverseLite() {
  addStockUniverseLiteCSS();
  installSectorMultiSelectLite();
  installCapLite();
  const card = document.querySelector("#stock-selection-screen .stock-filter-card");
  const body = card?.querySelector("#stock-filter-body");
  const top = card?.querySelector(".stock-filter-top");
  const toggle = card?.querySelector("#stock-filter-toggle");
  if (card && body && top && toggle && top.parentElement !== card) card.insertBefore(top, toggle);
}

function installStockUniverseLiteObserver() {
  const screen = document.getElementById("stock-selection-screen");
  if (!screen || screen.dataset.liteObserverInstalled === "1") return;
  screen.dataset.liteObserverInstalled = "1";
  const observer = new MutationObserver(() => {
    clearTimeout(window.__stockUniverseLiteTimer);
    window.__stockUniverseLiteTimer = setTimeout(runStockUniverseLite, 0);
  });
  observer.observe(screen, { childList:true, subtree:false });
}

function bootStockUniverseLite() {
  runStockUniverseLite();
  installStockUniverseLiteObserver();
}

if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", bootStockUniverseLite, { once:true });
else bootStockUniverseLite();
