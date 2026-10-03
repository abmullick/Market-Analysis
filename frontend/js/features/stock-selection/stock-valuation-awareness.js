function addValuationAwareness() {
  const section = document.querySelector(".stock-valuation-engine");
  if (!section || section.querySelector(".stock-valuation-awareness")) return;
  const lens = section.querySelector(".stock-valuation-lens");
  if (!lens) return;
  const note = document.createElement("div");
  note.className = "stock-valuation-awareness";
  note.innerHTML = `<span>Why the lens changes by business type</span><div><b>Financial services</b> P/B 70% · P/E 30% &nbsp; <b>Capital-intensive</b> P/E 60% · P/B 40% &nbsp; <b>Operating businesses</b> P/E 70% · P/B 30%</div><small>The engine changes the weighting because different business models rely on different valuation anchors. The score still compares the available multiples with the company's own historical medians; it is not a peer-relative valuation or an investment recommendation.</small>`;
  lens.after(note);
  if (!document.getElementById("stock-valuation-awareness-styles")) {
    const style = document.createElement("style");
    style.id = "stock-valuation-awareness-styles";
    style.textContent = `.stock-valuation-awareness{margin-top:8px;padding:9px 11px;border:1px dashed #cbd9e8;border-radius:10px;background:#f8fbff;color:#526b85;font-size:9px;line-height:1.45}.stock-valuation-awareness>span{display:block;margin-bottom:3px;color:#17355d;font-size:9px;font-weight:800;text-transform:uppercase;letter-spacing:.05em}.stock-valuation-awareness b{color:#315a83}.stock-valuation-awareness small{display:block;margin-top:4px;color:#71849a;font-size:8px;line-height:1.45}`;
    document.head.appendChild(style);
  }
}
function watchValuationAwareness() {
  const details = document.getElementById("stock-details");
  if (!details) return;
  const observer = new MutationObserver(() => addValuationAwareness());
  observer.observe(details, { childList: true, subtree: true });
  addValuationAwareness();
}
if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", watchValuationAwareness, { once: true });
else watchValuationAwareness();