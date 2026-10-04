// Sector-aware presentation for pedigree metrics whose underlying accounting model
// is not meaningful for every business type. Keeps the existing calculations intact.

const STYLE_ID = "stock-pedigree-applicability-styles";

function ensureStyles() {
  if (document.getElementById(STYLE_ID)) return;
  const style = document.createElement("style");
  style.id = STYLE_ID;
  style.textContent = `
    .stock-pedigree-not-applicable,
    .stock-pedigree-no-data,
    .stock-chart-no-data {
      min-height: 238px; height: 100%; display: flex; align-items: center; justify-content: center;
      padding: 28px; box-sizing: border-box; text-align: center;
      background: radial-gradient(circle at 20% 15%, rgba(37,99,235,.08), transparent 38%), linear-gradient(135deg, #f8fbff, #ffffff 65%, #faf7ff);
      border: 1px solid #e1eaf4; border-radius: 14px;
    }
    .stock-pedigree-na-inner { max-width: 520px; }
    .stock-pedigree-na-icon { width:42px; height:42px; margin:0 auto 10px; display:grid; place-items:center; border-radius:50%; background:#edf4ff; color:#2563eb; font-size:18px; font-weight:900; }
    .stock-pedigree-na-inner strong { display:block; color:#17355d; font-size:13px; margin-bottom:6px; }
    .stock-pedigree-na-inner p { margin:0; color:#71849a; font-size:10px; line-height:1.55; }
    .stock-pedigree-na-badge { display:inline-flex; margin-top:11px; padding:4px 8px; border:1px solid #dbe7f3; border-radius:999px; background:#fff; color:#64758a; font-size:8px; font-weight:800; letter-spacing:.05em; text-transform:uppercase; }
  `;
  document.head.appendChild(style);
}

function isFinancialSector() {
  const hero = document.querySelector("#stock-details .stock-hero p");
  const text = String(hero?.textContent || "").toLowerCase();
  return text.includes("financial services") || text.includes("financials");
}

function replaceWorkingCapitalCard() {
  const section = document.querySelector("#stock-details .stock-pedigree-section:not(.stock-pedigree-compare)");
  if (!section || !isFinancialSector()) return;
  const cards = [...section.querySelectorAll(".stock-pedigree-chart-card")];
  const card = cards.find((candidate) => candidate.querySelector("h3")?.textContent?.trim().toLowerCase() === "working capital cycle");
  if (!card || card.dataset.applicabilityHandled === "1") return;
  const wrap = card.querySelector(".stock-pedigree-chart-wrap");
  if (!wrap) return;
  card.dataset.applicabilityHandled = "1";
  wrap.innerHTML = `<div class="stock-pedigree-not-applicable"><div class="stock-pedigree-na-inner"><div class="stock-pedigree-na-icon">≈</div><strong>Working Capital Cycle is not applicable</strong><p>This diagnostic is designed for businesses with operating receivables, inventory and trade payables. For financial-services companies, those balances do not represent the same operating cycle, so the engine does not calculate a conventional CCC.</p><span class="stock-pedigree-na-badge">Financial-sector lens</span></div></div>`;
}

function scan() {
  ensureStyles();
  replaceWorkingCapitalCard();
}

const observer = new MutationObserver(scan);
observer.observe(document.body, { childList: true, subtree: true });
scan();
