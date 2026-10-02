const CAP_BANDS = [
  { key: "large", label: "Large Cap", min: 100000 },
  { key: "mid", label: "Mid Cap", min: 20000, max: 99999.999999 },
  { key: "small", label: "Small Cap", min: 5000, max: 19999.999999 },
  { key: "micro", label: "Micro Cap", max: 4999.999999 },
];

const LIQUIDITY_BANDS = [
  { key: "high", label: "Highly liquid", dot: "🟢" },
  { key: "moderate", label: "Moderately liquid", dot: "🟡" },
  { key: "low", label: "Low liquidity", dot: "🟠" },
  { key: "illiquid", label: "Illiquid", dot: "🔴" },
];

function capFor(cr) {
  const n = Number(cr);
  if (!Number.isFinite(n)) return null;
  return CAP_BANDS.find((b) => (b.min == null || n >= b.min) && (b.max == null || n <= b.max)) || null;
}

// The current Nifty universe payload does not contain traded-value history.
// Until a dedicated NSE traded-value feed is wired in, liquidity is a clearly
// labelled screening proxy based on market-cap segment. This avoids presenting
// an invented turnover figure as if it came from NSE.
function liquidityFor(stock) {
  const cap = capFor(stock.market_cap_cr)?.key;
  if (cap === "large") return "high";
  if (cap === "mid") return "moderate";
  if (cap === "small") return "low";
  if (cap === "micro") return "illiquid";
  return null;
}

function selectedValues(select) {
  return [...(select?.selectedOptions || [])].map((o) => o.value).filter(Boolean);
}

function installSectorMultiselect() {
  const old = document.getElementById("stock-sector");
  if (!old || old.dataset.enhanced === "true") return;
  old.dataset.enhanced = "true";
  old.multiple = true;
  old.classList.add("stock-multiselect-native");
  old.size = 1;
  old.title = "Select one or more sectors";

  const wrap = document.createElement("div");
  wrap.className = "stock-multiselect-wrap";
  old.parentNode.insertBefore(wrap, old);
  wrap.appendChild(old);

  const summary = document.createElement("button");
  summary.type = "button";
  summary.className = "stock-multiselect-trigger";
  summary.setAttribute("aria-haspopup", "listbox");
  summary.innerHTML = '<span>All sectors</span><b>▾</b>';
  wrap.appendChild(summary);

  const menu = document.createElement("div");
  menu.className = "stock-multiselect-menu";
  menu.hidden = true;
  wrap.appendChild(menu);

  const rebuild = () => {
    menu.innerHTML = [...old.options].map((o) => {
      if (!o.value) return `<label><input type="checkbox" data-value=""><span>${o.textContent}</span></label>`;
      return `<label><input type="checkbox" data-value="${o.value.replaceAll('"', '&quot;')}" ${o.selected ? "checked" : ""}><span>${o.textContent}</span></label>`;
    }).join("");
    const values = selectedValues(old);
    summary.querySelector("span").textContent = values.length
      ? `${values.length} sector${values.length > 1 ? "s" : ""} selected`
      : "All sectors";
  };

  summary.addEventListener("click", () => { menu.hidden = !menu.hidden; });
  menu.addEventListener("change", (e) => {
    const input = e.target;
    if (!input.matches("input")) return;
    if (input.dataset.value === "") {
      [...old.options].forEach((o) => { o.selected = false; });
      menu.querySelectorAll("input").forEach((x) => { x.checked = x.dataset.value === ""; });
    } else {
      const option = [...old.options].find((o) => o.value === input.dataset.value);
      if (option) option.selected = input.checked;
      const all = menu.querySelector('input[data-value=""]');
      if (all) all.checked = selectedValues(old).length === 0;
    }
    rebuild();
    old.dispatchEvent(new Event("change", { bubbles: true }));
  });

  old.style.display = "none";
  rebuild();
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
      <span class="stock-chip-filter-label">Liquidity <small>(proxy)</small></span>
      ${LIQUIDITY_BANDS.map((b) => `<label><input type="checkbox" value="${b.key}"><span class="liquidity-dot ${b.key}"></span>${b.label}</label>`).join("")}
    </div>`;
  filterTop.appendChild(block);

  const applyLocal = () => {
    const cap = [...document.querySelectorAll('#stock-cap-filter input:checked')].map((x) => x.value);
    const liq = [...document.querySelectorAll('#stock-liquidity-filter input:checked')].map((x) => x.value);
    const rows = [...document.querySelectorAll(".stock-picker-row")];
    rows.forEach((row) => {
      const cr = Number(row.dataset.marketCapCr);
      const capBand = capFor(cr)?.key;
      const liquidity = liquidityFor({ market_cap_cr: cr });
      row.hidden = (cap.length && !cap.includes(capBand)) || (liq.length && !liq.includes(liquidity));
    });
    const visible = rows.filter((r) => !r.hidden).length;
    const summary = document.querySelector(".stock-result-summary");
    if (summary && (cap.length || liq.length)) summary.textContent = `${visible} stocks match the current filters.`;
  };

  block.addEventListener("change", applyLocal);
}

function decorateRows() {
  document.querySelectorAll(".stock-picker-row").forEach((row) => {
    if (row.dataset.universeEnhanced === "true") return;
    const metrics = row.querySelector(".stock-picker-metrics");
    const capText = [...(metrics?.querySelectorAll("span") || [])].find((x) => x.textContent.includes("Market Cap"));
    const capMatch = capText?.textContent.match(/₹([\d,.]+)\s*Cr/);
    const capCr = capMatch ? Number(capMatch[1].replaceAll(",", "")) : NaN;
    row.dataset.marketCapCr = Number.isFinite(capCr) ? String(capCr) : "";
    const cap = capFor(capCr);
    const liquidity = liquidityFor({ market_cap_cr: capCr });
    const name = row.querySelector("strong");
    if (name && cap) {
      const badge = document.createElement("span");
      badge.className = `stock-cap-badge ${cap.key}`;
      badge.textContent = cap.label;
      name.after(badge);
    }
    if (metrics && liquidity) {
      const badge = document.createElement("span");
      badge.className = `stock-liquidity-badge ${liquidity}`;
      badge.innerHTML = `<span class="liquidity-dot ${liquidity}"></span>${LIQUIDITY_BANDS.find((x) => x.key === liquidity)?.label}`;
      metrics.appendChild(badge);
    }
    row.dataset.universeEnhanced = "true";
  });
}

function run() {
  installSectorMultiselect();
  installLiquidityAndCapFilters();
  decorateRows();
}

const observer = new MutationObserver(run);
observer.observe(document.body, { childList: true, subtree: true });
run();
