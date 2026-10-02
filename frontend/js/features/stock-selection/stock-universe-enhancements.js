const CAP_BANDS = [
  { key: "large", label: "Large Cap", min: 100000 },
  { key: "mid", label: "Mid Cap", min: 20000, max: 99999.999999 },
  { key: "small", label: "Small Cap", min: 5000, max: 19999.999999 },
  { key: "micro", label: "Micro Cap", max: 4999.999999 },
];

const LIQUIDITY_BANDS = [
  { key: "high", label: "Highly liquid" },
  { key: "moderate", label: "Moderately liquid" },
  { key: "low", label: "Low liquidity" },
  { key: "illiquid", label: "Illiquid" },
];

let metricMap = new Map();

function capFor(cr) {
  const n = Number(cr);
  return Number.isFinite(n)
    ? CAP_BANDS.find((b) => (b.min == null || n >= b.min) && (b.max == null || n <= b.max)) || null
    : null;
}

function selectedValues(select) {
  return [...(select?.selectedOptions || [])].map((o) => o.value).filter(Boolean);
}

function sectorOptions(select) {
  return [...(select?.options || [])]
    .filter((o) => o.value)
    .map((o) => ({ value: o.value, label: o.textContent.trim() }));
}

function liquidityLabel(key) {
  return LIQUIDITY_BANDS.find((x) => x.key === key)?.label || "";
}

function tradedValueText(s) {
  const v = Number(s?.avg_daily_traded_value_3m_cr);
  return Number.isFinite(v)
    ? `₹${v.toLocaleString("en-IN", { maximumFractionDigits: 1 })} Cr/day`
    : "Trading value unavailable";
}

function addMutualFundStylePickerCSS() {
  if (document.getElementById("stock-universe-picker-styles")) return;
  const style = document.createElement("style");
  style.id = "stock-universe-picker-styles";
  style.textContent = `
    .category-picker { position: relative; width: 100%; }
    .category-picker-trigger {
      width: 100%; min-height: 42px; display:flex; align-items:center; justify-content:space-between;
      gap:12px; padding:10px 13px; border:1px solid var(--color-border,#cbd5e1); border-radius:10px;
      background:var(--color-surface,#fff); color:var(--color-text,#0f172a); font:inherit; font-size:13px;
      cursor:pointer; text-align:left; transition:border-color .15s ease, box-shadow .15s ease;
    }
    .category-picker-trigger:hover, .category-picker-trigger[aria-expanded="true"] {
      border-color:var(--color-primary,#2563eb); box-shadow:0 0 0 3px rgba(37,99,235,.08);
    }
    .category-picker-value { color:var(--color-text-light,#64748b); font-weight:500; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
    .category-picker-value.has-selection { color:var(--color-text,#0f172a); font-weight:600; }
    .category-picker-arrow { display:flex; color:var(--color-text-light,#64748b); flex-shrink:0; }
    .category-picker-dropdown {
      position:absolute; top:calc(100% + 6px); left:0; right:0; z-index:1000; overflow:hidden;
      background:var(--color-surface,#fff); border:1px solid var(--color-border,#dbe4f0); border-radius:12px;
      box-shadow:0 16px 36px rgba(15,23,42,.16); min-width:100%;
    }
    .category-picker-dropdown[hidden] { display:none; }
    .category-picker-search { display:flex; align-items:center; gap:8px; padding:10px; border-bottom:1px solid var(--color-border,#e2e8f0); background:#fff; }
    .category-picker-search-input { flex:1; min-width:0; border:0; outline:0; background:transparent; color:var(--color-text,#0f172a); font:inherit; font-size:13px; }
    .category-picker-search-icon { color:var(--color-text-light,#64748b); flex-shrink:0; }
    .category-picker-search-clear { border:0; background:transparent; color:var(--color-text-light,#64748b); cursor:pointer; padding:3px; }
    .category-picker-actions { display:flex; justify-content:space-between; padding:8px 10px; border-bottom:1px solid var(--color-border,#e2e8f0); }
    .category-picker-action { border:0; background:transparent; color:var(--color-primary,#2563eb); font:inherit; font-size:12px; font-weight:600; cursor:pointer; padding:3px 2px; }
    .category-picker-list { max-height:320px; overflow-y:auto; padding:5px 0; }
    .category-picker-group-header { padding:8px 12px 5px; color:var(--color-text-light,#64748b); font-size:10px; font-weight:700; text-transform:uppercase; letter-spacing:.06em; }
    .category-picker-item { display:flex; align-items:center; gap:9px; padding:9px 12px; cursor:pointer; color:var(--color-text,#334155); font-size:13px; }
    .category-picker-item:hover { background:var(--color-slate-50,#f8fafc); }
    .category-picker-item.selected { background:rgba(37,99,235,.06); color:var(--color-primary,#1d4ed8); font-weight:600; }
    .category-picker-checkbox { width:17px; height:17px; border:1px solid #cbd5e1; border-radius:4px; display:flex; align-items:center; justify-content:center; flex-shrink:0; background:#fff; }
    .category-picker-item.selected .category-picker-checkbox { border-color:var(--color-primary,#2563eb); background:var(--color-primary,#2563eb); color:#fff; }
    .category-picker-empty { padding:22px 12px; text-align:center; color:var(--color-text-light,#64748b); font-size:13px; }
    .category-picker-footer { padding:8px 12px; border-top:1px solid var(--color-border,#e2e8f0); color:var(--color-text-light,#64748b); font-size:11px; background:#f8fafc; }

    .stock-universe-extra-filters { display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-top:12px; }
    .stock-chip-filter { display:flex; align-items:center; gap:6px; flex-wrap:wrap; padding:10px 12px; border:1px solid var(--color-border,#dbe4f0); border-radius:12px; background:rgba(248,250,252,.72); }
    .stock-chip-filter-label { font-size:11px; font-weight:700; color:var(--color-text,#334155); margin-right:3px; white-space:nowrap; }
    .stock-chip-filter label { position:relative; cursor:pointer; }
    .stock-chip-filter input { position:absolute; opacity:0; pointer-events:none; }
    .stock-chip-filter label > span { display:inline-flex; align-items:center; gap:5px; padding:7px 10px; border-radius:999px; background:#eef2ff; color:#475569; font-size:11px; font-weight:600; border:1px solid transparent; transition:all .15s ease; white-space:nowrap; }
    .stock-chip-filter label > span:hover { border-color:#c7d2fe; }
    .stock-chip-filter input:checked + span { background:#172554; color:#fff; border-color:#172554; box-shadow:0 2px 6px rgba(15,23,42,.14); }
    .liquidity-choice { background:#f1f5f9 !important; }
    .liquidity-dot { width:10px; height:10px; border-radius:50%; display:inline-block; flex:0 0 10px; box-shadow:0 0 0 2px rgba(255,255,255,.8); }
    .liquidity-dot.high { background:#16a34a; }
    .liquidity-dot.moderate { background:#eab308; }
    .liquidity-dot.low { background:#f97316; }
    .liquidity-dot.illiquid { background:#dc2626; }
    .stock-liquidity-badge { display:inline-flex; align-items:center; gap:5px; font-size:11px; font-weight:600; white-space:nowrap; }
    .stock-cap-badge { display:inline-flex; margin-left:7px; padding:3px 7px; border-radius:999px; font-size:9px; font-weight:700; line-height:1.2; white-space:nowrap; background:#eef2ff; color:#3730a3; vertical-align:middle; }
    .stock-cap-badge.large { background:#dbeafe; color:#1d4ed8; }
    .stock-cap-badge.mid { background:#ede9fe; color:#6d28d9; }
    .stock-cap-badge.small { background:#fef3c7; color:#92400e; }
    .stock-cap-badge.micro { background:#fce7f3; color:#be185d; }
    @media (max-width:850px) { .stock-universe-extra-filters { grid-template-columns:1fr; } }
  `;
  document.head.appendChild(style);
}

function loadMetrics() {
  return fetch("/api/stocks/universe?include_metrics=true", { headers: { Accept: "application/json" }, cache: "no-store" })
    .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
    .then((data) => {
      metricMap = new Map((data.stocks || []).map((s) => [s.symbol, s]));
      decorateRows();
    })
    .catch((e) => console.warn("Unable to load stock metrics:", e));
}

function installSectorMultiselect() {
  const old = document.getElementById("stock-sector");
  if (!old || old.dataset.enhanced === "true") return;
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
  trigger.id = "stock-sector-trigger";
  trigger.setAttribute("aria-haspopup", "listbox");
  trigger.setAttribute("aria-expanded", "false");
  trigger.innerHTML = `<span class="category-picker-value" id="stock-sector-value">All Sectors</span><span class="category-picker-arrow"><svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M3 4.5L6 7.5L9 4.5"/></svg></span>`;

  const dropdown = document.createElement("div");
  dropdown.className = "category-picker-dropdown";
  dropdown.id = "stock-sector-dropdown";
  dropdown.hidden = true;
  dropdown.innerHTML = `
    <div class="category-picker-search">
      <svg class="category-picker-search-icon" width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="6" cy="6" r="4.5"/><path d="M9.5 9.5L13 13"/></svg>
      <input type="text" class="category-picker-search-input" id="stock-sector-search" placeholder="Search sectors..." autocomplete="off">
      <button type="button" class="category-picker-search-clear" id="stock-sector-search-clear" hidden>×</button>
    </div>
    <div class="category-picker-actions"><button type="button" class="category-picker-action" id="stock-sector-select-all">Select All</button><button type="button" class="category-picker-action" id="stock-sector-clear-all">Clear</button></div>
    <div class="category-picker-list" id="stock-sector-list"></div>
    <div class="category-picker-footer"><span id="stock-sector-count">0 selected</span></div>`;

  wrap.append(trigger, dropdown);
  let isOpen = false;
  let searchText = "";

  function renderList() {
    const list = document.getElementById("stock-sector-list");
    if (!list) return;
    const opts = sectorOptions(old).filter((o) => o.label.toLowerCase().includes(searchText.toLowerCase()));
    list.innerHTML = opts.length ? opts.map((o) => {
      const selected = selectedValues(old).includes(o.value);
      return `<div class="category-picker-item ${selected ? "selected" : ""}" role="option" aria-selected="${selected}" data-value="${o.value.replaceAll('"', "&quot;")}"><span class="category-picker-checkbox">${selected ? '<svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor"><path d="M11.2 3.8L5.5 9.5 2.8 6.8l-.9.9L5.5 11.3 12.1 4.7l-.9-.9z"/></svg>' : ""}</span><span>${o.label}</span></div>`;
    }).join("") : `<div class="category-picker-empty">No sectors found</div>`;

    list.querySelectorAll(".category-picker-item").forEach((item) => item.addEventListener("click", (e) => {
      e.stopPropagation();
      const option = [...old.options].find((o) => o.value === item.dataset.value);
      if (!option) return;
      option.selected = !option.selected;
      updateTrigger();
      renderList();
      old.dispatchEvent(new Event("change", { bubbles: true }));
    }));
  }

  function updateTrigger() {
    const vals = selectedValues(old);
    const value = document.getElementById("stock-sector-value");
    const count = document.getElementById("stock-sector-count");
    if (value) {
      value.textContent = vals.length === 0 ? "All Sectors" : vals.length === 1 ? vals[0] : `${vals.length} sectors selected`;
      value.classList.toggle("has-selection", vals.length > 0);
    }
    if (count) count.textContent = `${vals.length} selected`;
  }

  function open() { isOpen = true; dropdown.hidden = false; trigger.setAttribute("aria-expanded", "true"); document.getElementById("stock-sector-search")?.focus(); }
  function close() { isOpen = false; dropdown.hidden = true; trigger.setAttribute("aria-expanded", "false"); }

  trigger.addEventListener("click", (e) => { e.stopPropagation(); if (isOpen) close(); else open(); });
  dropdown.addEventListener("click", (e) => e.stopPropagation());
  document.addEventListener("click", (e) => { if (!wrap.contains(e.target)) close(); });

  const search = document.getElementById("stock-sector-search");
  const clear = document.getElementById("stock-sector-search-clear");
  search?.addEventListener("input", () => { searchText = search.value; if (clear) clear.hidden = !searchText; renderList(); });
  clear?.addEventListener("click", () => { search.value = ""; searchText = ""; clear.hidden = true; renderList(); search.focus(); });

  document.getElementById("stock-sector-select-all")?.addEventListener("click", () => {
    [...old.options].forEach((o) => { if (o.value) o.selected = true; });
    updateTrigger(); renderList(); old.dispatchEvent(new Event("change", { bubbles: true }));
  });
  document.getElementById("stock-sector-clear-all")?.addEventListener("click", () => {
    [...old.options].forEach((o) => { o.selected = false; });
    updateTrigger(); renderList(); old.dispatchEvent(new Event("change", { bubbles: true }));
  });

  renderList();
  updateTrigger();
}

function installLiquidityAndCapFilters() {
  const filterTop = document.querySelector(".stock-filter-top");
  if (!filterTop || document.getElementById("stock-liquidity-filter")) return;
  const block = document.createElement("div");
  block.className = "stock-universe-extra-filters";
  block.innerHTML = `
    <div class="stock-chip-filter" id="stock-cap-filter">
      <span class="stock-chip-filter-label">Market Cap</span>
      ${CAP_BANDS.map((b) => `<label><input type="checkbox" value="${b.key}"><span>${b.label}</span></label>`).join("")}
    </div>
    <div class="stock-chip-filter" id="stock-liquidity-filter">
      <span class="stock-chip-filter-label">Liquidity</span>
      ${LIQUIDITY_BANDS.map((b) => `<label><input type="checkbox" value="${b.key}"><span class="liquidity-choice"><span class="liquidity-dot ${b.key}"></span>${b.label}</span></label>`).join("")}
    </div>`;
  filterTop.appendChild(block);
}

function stockRowDecoration(s) {
  const cap = capFor(s.market_cap_cr);
  const liq = s.liquidity_status;
  return { cap, liq };
}

function decorateRows() {
  document.querySelectorAll(".stock-picker-row").forEach((row) => {
    const symbol = row.dataset.symbol;
    const data = metricMap.get(symbol);
    if (!data) return;
    const { cap, liq } = stockRowDecoration(data);
    row.dataset.marketCapCr = data.market_cap_cr ?? "";
    const name = row.querySelector("strong");
    const metrics = row.querySelector(".stock-picker-metrics");
    if (name && cap && !name.parentElement.querySelector(".stock-cap-badge")) {
      const badge = document.createElement("span");
      badge.className = `stock-cap-badge ${cap.key}`;
      badge.textContent = cap.label;
      name.after(badge);
    }
    if (metrics && liq && !metrics.querySelector(".stock-liquidity-badge")) {
      const badge = document.createElement("span");
      badge.className = `stock-liquidity-badge ${liq}`;
      badge.title = `3M average daily traded value: ${tradedValueText(data)}`;
      badge.innerHTML = `<span class="liquidity-dot ${liq}"></span>${liquidityLabel(liq)}`;
      metrics.appendChild(badge);
    }
  });
}

function run() {
  addMutualFundStylePickerCSS();
  installSectorMultiselect();
  installLiquidityAndCapFilters();
  decorateRows();
}

const observer = new MutationObserver(() => {
  window.clearTimeout(window.__stockUniverseEnhancementTimer);
  window.__stockUniverseEnhancementTimer = window.setTimeout(run, 0);
});

if (document.body) observer.observe(document.body, { childList: true, subtree: true });
run();
loadMetrics();
