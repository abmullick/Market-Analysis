const STOCK_FILTER_FIX_VERSION = "20261002-1";

function sfFixCapKey(stock) {
  if (stock?.market_cap_band) return stock.market_cap_band;
  const n = Number(stock?.market_cap_cr);
  if (!Number.isFinite(n)) return null;
  if (n >= 100000) return "large";
  if (n >= 20000) return "mid";
  if (n >= 5000) return "small";
  return "micro";
}

function sfFixCSS() {
  if (document.getElementById("stock-filter-interaction-fix-css")) return;
  const style = document.createElement("style");
  style.id = "stock-filter-interaction-fix-css";
  style.textContent = `
    .stock-filter-card,.stock-filter-body,.stock-filter-top,.stock-filter-context,.stock-sector-picker { overflow:visible !important; }
    .stock-sector-picker { position:relative; z-index:100; }
    .stock-sector-picker .category-picker-dropdown.sf-fix-portal {
      position:fixed !important;
      left:auto;
      right:auto;
      top:auto;
      width:var(--sf-picker-width, 420px);
      max-height:min(430px, calc(100vh - 24px));
      z-index:2147483000 !important;
      overflow:hidden;
      transform:none !important;
    }
    .stock-sector-picker .category-picker-list { max-height:300px; overflow-y:auto; }
    .stock-sector-picker .category-picker-trigger { position:relative; z-index:2; }
    .stock-filter-row-hidden { display:none !important; }
  `;
  document.head.appendChild(style);
}

async function sfFixGetUniverse() {
  if (window.__stockFilterFixUniversePromise) return window.__stockFilterFixUniversePromise;
  window.__stockFilterFixUniversePromise = fetch("/api/stocks/universe", { headers: { Accept: "application/json" } })
    .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
    .then(d => d.stocks || [])
    .catch(() => []);
  return window.__stockFilterFixUniversePromise;
}

function sfFixSelectedSectors(select) {
  return [...(select?.selectedOptions || [])].map(o => o.value).filter(Boolean);
}

function sfFixApply(select) {
  const rows = [...document.querySelectorAll("#stock-selection-screen .stock-picker-row")];
  if (!rows.length) return;

  const selectedSectors = sfFixSelectedSectors(select);
  const query = document.getElementById("stock-filter-search")?.value?.trim().toLowerCase() || "";
  const selectedCaps = [...document.querySelectorAll("#stock-cap-filter input:checked")].map(i => i.value);
  const universe = window.__stockFilterFixUniverse || [];
  const bySymbol = new Map(universe.map(s => [String(s.symbol || "").toUpperCase(), s]));

  let count = 0;
  rows.forEach(row => {
    const symbol = String(row.dataset.symbol || "").toUpperCase();
    const stock = bySymbol.get(symbol);
    const sectorOk = !selectedSectors.length || selectedSectors.includes(String(stock?.sector || ""));
    const searchOk = !query || symbol.toLowerCase().includes(query) || String(stock?.name || row.textContent || "").toLowerCase().includes(query);
    const capOk = !selectedCaps.length || selectedCaps.includes(sfFixCapKey(stock));
    const visible = sectorOk && searchOk && capOk;
    row.classList.toggle("stock-filter-row-hidden", !visible);
    if (visible) count += 1;
  });

  const countEl = document.getElementById("stock-filter-toggle-count");
  if (countEl) countEl.textContent = `${count} stocks`;
  const footerCount = document.querySelector("#stock-filter-body .stock-filter-footer span:last-child");
  if (footerCount) footerCount.textContent = `${count} stocks`;
  const summary = document.querySelector("#stock-selection-screen .stock-result-summary");
  if (summary) summary.textContent = `${count} stocks match the current filters.`;
}

async function sfFixEnsureUniverse() {
  if (window.__stockFilterFixUniverse) return window.__stockFilterFixUniverse;
  window.__stockFilterFixUniverse = await sfFixGetUniverse();
  return window.__stockFilterFixUniverse;
}

function sfFixPortalDropdown(wrap, trigger, dropdown) {
  if (!dropdown || dropdown.dataset.sfPortal === "1") return;
  dropdown.dataset.sfPortal = "1";
  dropdown.classList.add("sf-fix-portal");
  document.body.appendChild(dropdown);

  const position = () => {
    if (dropdown.hidden) return;
    const r = trigger.getBoundingClientRect();
    const width = Math.max(r.width, 360);
    const maxLeft = Math.max(8, window.innerWidth - width - 8);
    const left = Math.min(Math.max(8, r.left), maxLeft);
    const availableBelow = window.innerHeight - r.bottom - 8;
    const availableAbove = r.top - 8;
    const openBelow = availableBelow >= 280 || availableBelow >= availableAbove;
    const height = Math.min(430, Math.max(180, openBelow ? availableBelow : availableAbove));
    dropdown.style.setProperty("--sf-picker-width", `${width}px`);
    dropdown.style.left = `${left}px`;
    dropdown.style.width = `${width}px`;
    dropdown.style.maxHeight = `${height}px`;
    dropdown.style.top = openBelow ? `${Math.min(window.innerHeight - height - 8, r.bottom + 6)}px` : `${Math.max(8, r.top - height - 6)}px`;
  };

  window.addEventListener("resize", position, { passive:true });
  window.addEventListener("scroll", position, { passive:true, capture:true });
  trigger.addEventListener("click", () => requestAnimationFrame(position));
}

function sfFixInstallSector(select) {
  if (!select || select.dataset.sfFixInstalled === "1") return true;
  select.dataset.sfFixInstalled = "1";
  select.multiple = true;
  select.style.display = "none";

  const oldWrap = select.closest(".stock-sector-picker");
  if (oldWrap) {
    const oldDropdown = oldWrap.querySelector(".category-picker-dropdown");
    const oldTrigger = oldWrap.querySelector(".category-picker-trigger");
    if (oldDropdown) oldDropdown.remove();
    if (oldTrigger) oldTrigger.remove();
    oldWrap.className = "stock-sector-picker category-picker";
    var wrap = oldWrap;
  } else {
    wrap = document.createElement("div");
    wrap.className = "stock-sector-picker category-picker";
    select.parentNode.insertBefore(wrap, select);
    wrap.appendChild(select);
  }

  const trigger = document.createElement("button");
  trigger.type = "button";
  trigger.className = "category-picker-trigger";
  trigger.setAttribute("aria-expanded", "false");
  trigger.innerHTML = `<span class="category-picker-value">All Sectors</span><span aria-hidden="true">⌄</span>`;

  const dropdown = document.createElement("div");
  dropdown.className = "category-picker-dropdown";
  dropdown.hidden = true;
  dropdown.innerHTML = `<div class="category-picker-search"><span aria-hidden="true">⌕</span><input class="category-picker-search-input" placeholder="Search sectors..." autocomplete="off"></div><div class="category-picker-actions"><button type="button" class="category-picker-action sf-fix-select-all">Select All</button><button type="button" class="category-picker-action sf-fix-clear-all">Clear</button></div><div class="category-picker-list"></div><div class="category-picker-footer">0 selected</div>`;
  wrap.append(trigger);
  document.body.append(dropdown);

  const valueEl = trigger.querySelector(".category-picker-value");
  const listEl = dropdown.querySelector(".category-picker-list");
  const countEl = dropdown.querySelector(".category-picker-footer");
  const searchEl = dropdown.querySelector(".category-picker-search-input");
  let sectorQuery = "";

  const update = () => {
    const selected = sfFixSelectedSectors(select);
    valueEl.textContent = selected.length === 0 ? "All Sectors" : selected.length === 1 ? selected[0] : `${selected.length} sectors selected`;
    valueEl.classList.toggle("has-selection", selected.length > 0);
    countEl.textContent = `${selected.length} selected`;
    const options = [...select.options].filter(o => o.value && o.textContent.toLowerCase().includes(sectorQuery.toLowerCase()));
    listEl.innerHTML = options.map(o => `<div class="category-picker-item ${o.selected ? "selected" : ""}" data-value="${o.value.replaceAll('"','&quot;')}"><span class="category-picker-checkbox">${o.selected ? "✓" : ""}</span><span>${o.textContent}</span></div>`).join("") || `<div class="category-picker-footer">No sectors found</div>`;
  };

  const apply = async () => {
    await sfFixEnsureUniverse();
    sfFixApply(select);
  };

  listEl.addEventListener("click", async e => {
    const item = e.target.closest(".category-picker-item");
    if (!item) return;
    e.preventDefault();
    e.stopPropagation();
    const option = [...select.options].find(o => o.value === item.dataset.value);
    if (!option) return;
    option.selected = !option.selected;
    update();
    await apply();
  });

  trigger.addEventListener("click", e => {
    e.preventDefault();
    e.stopPropagation();
    dropdown.hidden = !dropdown.hidden;
    trigger.setAttribute("aria-expanded", String(!dropdown.hidden));
    if (!dropdown.hidden) requestAnimationFrame(() => sfFixPortalDropdown(wrap, trigger, dropdown));
  });

  dropdown.addEventListener("click", e => e.stopPropagation());
  document.addEventListener("click", e => {
    if (!wrap.contains(e.target) && !dropdown.contains(e.target)) {
      dropdown.hidden = true;
      trigger.setAttribute("aria-expanded", "false");
    }
  });
  searchEl.addEventListener("input", e => { sectorQuery = e.target.value; update(); });
  dropdown.querySelector(".sf-fix-select-all").addEventListener("click", async () => {
    [...select.options].forEach(o => { if (o.value) o.selected = true; });
    update();
    await apply();
  });
  dropdown.querySelector(".sf-fix-clear-all").addEventListener("click", async () => {
    [...select.options].forEach(o => o.selected = false);
    update();
    await apply();
  });

  select.addEventListener("change", e => {
    e.stopImmediatePropagation();
    e.preventDefault();
    update();
    apply();
  }, true);

  sfFixPortalDropdown(wrap, trigger, dropdown);
  update();
  return true;
}

function sfFixBindOtherFilters(select) {
  const search = document.getElementById("stock-filter-search");
  if (search && search.dataset.sfFixBound !== "1") {
    search.dataset.sfFixBound = "1";
    search.addEventListener("input", e => {
      e.stopImmediatePropagation();
      sfFixEnsureUniverse().then(() => sfFixApply(select));
    }, true);
  }

  document.querySelectorAll("#stock-cap-filter input").forEach(input => {
    if (input.dataset.sfFixBound === "1") return;
    input.dataset.sfFixBound = "1";
    input.addEventListener("change", e => {
      e.stopImmediatePropagation();
      sfFixEnsureUniverse().then(() => sfFixApply(select));
    }, true);
  });
}

function sfFixBoot() {
  sfFixCSS();
  const screen = document.getElementById("stock-selection-screen");
  const select = document.getElementById("stock-sector");
  if (!screen || !select || !select.options.length) return false;
  if (!select.dataset.sfFixInstalled) sfFixInstallSector(select);
  sfFixBindOtherFilters(select);
  return true;
}

function sfFixObserve() {
  const screen = document.getElementById("stock-selection-screen");
  if (!screen || screen.dataset.sfFixObserver === "1") return;
  screen.dataset.sfFixObserver = "1";
  const observer = new MutationObserver(() => setTimeout(sfFixBoot, 0));
  observer.observe(screen, { childList:true, subtree:false });
}

function sfFixStart() {
  if (sfFixBoot()) sfFixObserve();
  else setTimeout(sfFixStart, 50);
}

if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", sfFixStart, { once:true });
else sfFixStart();
