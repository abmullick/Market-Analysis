const state = { keepOpen: false, timer: null };

function addCss(href) {
  if (document.querySelector(`link[href="${href}"]`)) return;
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = href;
  document.head.appendChild(link);
}

function op(id, value, label) {
  return `<select class="filter-op" id="${id}" aria-label="${label}"><option value=">=" ${value === ">=" ? "selected" : ""}>&ge;</option><option value="<=" ${value === "<=" ? "selected" : ""}>&le;</option></select>`;
}

function metricChip(minLabel, maxLabel) {
  const min = minLabel?.querySelector("input");
  const max = maxLabel?.querySelector("input");
  if (!min && !max) return "";
  const source = minLabel || maxLabel;
  const label = source.textContent.trim().replace(/\s+(Min|Max)\s*$/, "");
  const suffix = source.textContent.includes("₹ Cr") ? "₹ Cr" : source.textContent.includes("%") ? "%" : "";
  const minId = min?.id || "";
  const maxId = max?.id || "";
  if (min) min.className = "filter-input";
  if (max) max.className = "filter-input";
  return `<div class="filter-chip stock-filter-chip" data-min-id="${minId}" data-max-id="${maxId}"><span class="filter-chip-label">${label}</span><div class="filter-chip-controls">${op(`${minId}-op`, ">=", `${label} minimum operator`)}${min?.outerHTML || ""}<span class="filter-to">to</span>${op(`${maxId}-op`, "<=", `${label} maximum operator`)}${max?.outerHTML || ""}${suffix ? `<span class="filter-unit">${suffix}</span>` : ""}</div></div>`;
}

function simpleChip(el, label) {
  if (!el) return "";
  el.className = "filter-input stock-simple-filter-input";
  return `<div class="filter-chip stock-filter-chip"><span class="filter-chip-label">${label}</span><div class="filter-chip-controls stock-simple-filter-controls">${el.outerHTML}</div></div>`;
}

function syncValues(card) {
  card.querySelectorAll(".stock-filter-chip[data-min-id]").forEach(chip => {
    const min = document.getElementById(chip.dataset.minId);
    const max = document.getElementById(chip.dataset.maxId);
    const minOp = document.getElementById(`${chip.dataset.minId}-op`);
    const maxOp = document.getElementById(`${chip.dataset.maxId}-op`);
    if (!min && !max) return;
    const left = min?.value || "";
    const right = max?.value || "";
    if (min) min.value = "";
    if (max) max.value = "";
    if (left) (minOp?.value === ">=" ? min : max).value = left;
    if (right) (maxOp?.value === "<=" ? max : min).value = right;
  });
}

function apply(card) {
  const button = card.querySelector("#stock-apply-filters");
  if (!button) return;
  syncValues(card);
  state.keepOpen = true;
  button.click();
}

function transform(card) {
  if (!card || card.dataset.mfMirror === "1") return state.keepOpen && open(card);
  addCss("/css/features/mutual-fund-analysis.css");
  card.dataset.mfMirror = "1";
  card.classList.add("filter-panel");

  const toggle = card.querySelector(".stock-filter-toggle");
  const body = card.querySelector(".stock-filter-body");
  const top = body?.querySelector(".stock-filter-top");
  const groups = body?.querySelector(".stock-filter-groups");
  const applyButton = body?.querySelector("#stock-apply-filters");
  const clearButton = body?.querySelector("#stock-clear-filters");
  const footer = body?.querySelector(".stock-filter-footer");
  if (!toggle || !body || !groups) return;

  toggle.className = "filter-toggle";
  toggle.querySelector(".stock-filter-toggle-icon")?.classList.replace("stock-filter-toggle-icon", "filter-toggle-icon");
  toggle.querySelector(".stock-filter-toggle-label")?.classList.replace("stock-filter-toggle-label", "filter-toggle-label");
  toggle.querySelector(".stock-filter-toggle-count")?.classList.replace("stock-filter-toggle-count", "filter-toggle-count");
  body.className = "filter-body";

  const sector = top?.querySelector("#stock-sector");
  const search = top?.querySelector("#stock-filter-search");
  const labels = [...groups.querySelectorAll("label")];
  const originals = [sector, search, ...labels.map(x => x.querySelector("input"))].filter(Boolean);
  const pairs = new Map();
  labels.forEach(label => {
    const input = label.querySelector("input");
    if (!input) return;
    const key = input.id.replace(/^stock-(min|max)-/, "");
    if (!pairs.has(key)) pairs.set(key, {});
    pairs.get(key)[input.id.includes("stock-min-") ? "min" : "max"] = label;
  });

  const grid = document.createElement("div");
  grid.className = "filter-grid stock-filter-grid";
  grid.innerHTML = [simpleChip(sector, "Sector"), simpleChip(search, "Search"), ...[...pairs.values()].map(p => metricChip(p.min, p.max))].join("");
  top.replaceWith(grid);
  groups.remove();

  originals.forEach(original => {
    const clone = grid.querySelector(`#${CSS.escape(original.id)}`);
    if (clone) clone.replaceWith(original);
  });

  applyButton?.classList.add("stock-hidden-action");
  clearButton?.classList.add("stock-hidden-action");
  if (footer) {
    footer.className = "filter-footer";
    footer.innerHTML = `<button type="button" id="stock-mirror-clear" class="btn-text">Clear all</button><span>${toggle.querySelector(".filter-toggle-count")?.textContent || ""}</span>`;
  }

  toggle.addEventListener("click", () => {
    const isOpen = toggle.getAttribute("aria-expanded") === "true";
    toggle.setAttribute("aria-expanded", String(!isOpen));
    toggle.querySelector(".filter-toggle-icon").textContent = isOpen ? "▸" : "▾";
    body.hidden = isOpen;
  });
  card.querySelectorAll(".filter-input").forEach(input => input.addEventListener("input", () => { clearTimeout(state.timer); state.timer = setTimeout(() => apply(card), 350); }));
  card.querySelectorAll(".filter-input").forEach(input => input.addEventListener("change", () => apply(card)));
  card.querySelectorAll(".filter-op").forEach(select => select.addEventListener("change", () => apply(card)));
  card.querySelector("#stock-mirror-clear")?.addEventListener("click", () => { state.keepOpen = false; clearButton?.click(); });
  if (state.keepOpen) open(card);
}

function open(card) {
  const toggle = card.querySelector(".filter-toggle");
  const body = card.querySelector(".filter-body");
  if (!toggle || !body) return;
  toggle.setAttribute("aria-expanded", "true");
  toggle.querySelector(".filter-toggle-icon").textContent = "▾";
  body.hidden = false;
}

function init() {
  addCss("/css/features/mutual-fund-analysis.css");
  const screen = document.getElementById("stock-selection-screen");
  if (!screen) return;
  const observer = new MutationObserver(() => { const card = screen.querySelector(".stock-filter-card"); if (card) transform(card); });
  observer.observe(screen, { childList: true, subtree: true });
  const card = screen.querySelector(".stock-filter-card");
  if (card) transform(card);
}

if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init, { once: true });
else init();
