const API = "/api/stocks/pedigree";
const COLORS = ["#2563eb", "#10b981", "#f59e0b", "#8b5cf6", "#64748b"];
let lastKey = "";
let busy = false;

const n = (v) => Number.isFinite(Number(v)) ? Number(v) : null;
const esc = (v) => String(v ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");
const fmt = (v, digits = 1) => n(v) == null ? "—" : Number(v).toLocaleString("en-IN", { maximumFractionDigits: digits, minimumFractionDigits: digits });

function rows(data) {
  return Array.isArray(data?.shareholding?.combined) ? data.shareholding.combined.filter(r => r && r.date) : [];
}
function latestPair(series) {
  const a = series.filter(x => n(x.value) != null);
  if (!a.length) return null;
  const last = a.at(-1);
  const prior = a.length > 4 ? a.at(-5) : a[0];
  return { last: n(last.value), prior: n(prior.value), date: last.date || last.year, priorDate: prior.date || prior.year, delta: n(last.value) - n(prior.value) };
}
function value(r, keys) { for (const k of keys) { const v = n(r?.[k]); if (v != null) return v; } return null; }
function ownership(r) {
  return {
    promoters: value(r, ["promoters", "promoter"]),
    fiis: value(r, ["fiis", "fii"]),
    diis: value(r, ["diis", "dii"]),
    government: value(r, ["government", "govt"]),
    public: value(r, ["public"]),
  };
}
function classify(p, i, publicDelta) {
  if (p != null && i != null) {
    if (p <= -2 && i >= 2) return ["Ownership shift", "Promoter holding is declining while institutional ownership is increasing.", "watch"];
    if (p >= 2 && i >= 2) return ["Broad ownership support", "Both promoter and institutional ownership have increased over the comparison period.", "positive"];
    if (i >= 2) return ["Institutional accumulation", "FII + DII ownership has increased over the comparison period.", "positive"];
    if (i <= -2) return ["Institutional reduction", "FII + DII ownership has declined over the comparison period.", "watch"];
    if (Math.abs(p) < 2 && Math.abs(i) < 2) return ["Ownership stable", "Promoter and institutional ownership have remained broadly stable.", "neutral"];
  }
  if (publicDelta != null && publicDelta <= -2) return ["Public float declining", "Public ownership has reduced over the comparison period.", "watch"];
  return ["Mixed ownership movement", "Ownership categories have moved without a dominant shift in the available history.", "neutral"];
}
function stat(label, value, delta, cls = "neutral") {
  const sign = delta == null ? "" : `${delta > 0 ? "+" : ""}${fmt(delta)} pp`;
  return `<div class="share-intel-stat"><span>${esc(label)}</span><strong>${value == null ? "—" : `${fmt(value)}%`}</strong><small class="${cls}">${esc(sign || "Latest available")}</small></div>`;
}
function bar(label, value, color) {
  return value == null ? "" : `<div class="share-intel-bar-row"><span>${esc(label)}</span><div><i style="width:${Math.max(0, Math.min(100, value))}%;background:${color}"></i></div><b>${fmt(value)}%</b></div>`;
}
function ownershipPanel(data) {
  const rs = rows(data); if (!rs.length) return "";
  const latest = ownership(rs.at(-1));
  const first = ownership(rs.length > 4 ? rs.at(-5) : rs[0]);
  const institutional = (latest.fiis ?? 0) + (latest.diis ?? 0);
  const institutionalPrior = (first.fiis ?? 0) + (first.diis ?? 0);
  const instDelta = latest.fiis != null || latest.diis != null ? institutional - institutionalPrior : null;
  const promoterDelta = latest.promoters != null && first.promoters != null ? latest.promoters - first.promoters : null;
  const publicDelta = latest.public != null && first.public != null ? latest.public - first.public : null;
  const [title, text, cls] = classify(promoterDelta, instDelta, publicDelta);
  const period = `${first.date || ""} → ${latest.date || ""}`;
  return `<div class="share-intel-card"><div class="share-intel-top"><div><div class="share-intel-eyebrow">OWNERSHIP INTELLIGENCE</div><h3>${title}</h3><p>${esc(text)}</p></div><span class="share-intel-period">${esc(period)}</span></div><div class="share-intel-composition"><div class="share-intel-bars">${bar("Promoters", latest.promoters, COLORS[0])}${bar("FIIs", latest.fiis, COLORS[1])}${bar("DIIs", latest.diis, COLORS[2])}${bar("Government", latest.government, COLORS[4])}${bar("Public", latest.public, COLORS[3])}</div><div class="share-intel-stats">${stat("Promoters",latest.promoters,promoterDelta,promoterDelta < -2 ? "watch" : "positive")}${stat("Institutional",latest.fiis != null || latest.diis != null ? institutional : null,instDelta,instDelta < -2 ? "watch" : "positive")}${stat("Public",latest.public,publicDelta,publicDelta < -2 ? "watch" : "positive")}</div></div><div class="share-intel-note"><span>Reading the ownership trend</span><small>Changes are percentage-point movements over the available comparison window, not investment signals. Institutional ownership combines FII + DII where both are available.</small></div></div>`;
}
function individual(data, details) {
  if (details.querySelector(".stock-shareholding-intelligence")) return;
  const section = document.createElement("section"); section.className = "stock-section stock-shareholding-intelligence";
  section.innerHTML = `<div class="stock-section-header"><div><h2>Shareholding Intelligence</h2><p>Ownership composition and changes derived from the same historical shareholding data shown above.</p></div></div>${ownershipPanel(data)}`;
  const pedigree = details.querySelector(".stock-pedigree-section");
  if (pedigree) pedigree.after(section); else details.appendChild(section);
}
function compare(datas, details) {
  if (details.querySelector(".stock-shareholding-compare")) return;
  const names = datas.map(d => d.symbol || d.name || "Stock");
  const entries = datas.map(d => { const rs = rows(d); const latest = rs.at(-1), prior = rs.length > 4 ? rs.at(-5) : rs[0]; const a=ownership(latest), b=ownership(prior); const instA=(a.fiis??0)+(a.diis??0), instB=(b.fiis??0)+(b.diis??0); return {a,b,inst:instA,instDelta:instA-instB,promoterDelta:(a.promoters??0)-(b.promoters??0),publicDelta:(a.public??0)-(b.public??0)}; });
  const metric = (label, fn) => `<tr><td>${esc(label)}</td>${entries.map(e=>`<td>${fn(e) == null ? "—" : `${fmt(fn(e))}%`}</td>`).join("")}</tr>`;
  const cards = entries.map((e,i)=>{ const [title,text,cls]=classify(e.promoterDelta,e.instDelta,e.publicDelta); return `<div class="share-intel-compare-card"><div class="share-intel-eyebrow">${esc(names[i])}</div><h3>${title}</h3><p>${esc(text)}</p><div class="share-intel-mini-bars">${bar("Promoters",e.a.promoters,COLORS[0])}${bar("FIIs",e.a.fiis,COLORS[1])}${bar("DIIs",e.a.diis,COLORS[2])}${bar("Public",e.a.public,COLORS[3])}</div></div>`; }).join("");
  const section=document.createElement("section"); section.className="stock-section stock-shareholding-compare"; section.innerHTML=`<div class="stock-section-header"><div><h2>Shareholding Intelligence</h2><p>Compare ownership composition and the direction of promoter, institutional and public holdings.</p></div></div><div class="share-intel-compare-grid">${cards}</div><div class="share-intel-compare-table"><h3>Ownership Comparison</h3><div class="stock-table-wrap"><table class="stock-table"><thead><tr><th>Metric</th>${names.map(n=>`<th>${esc(n)}</th>`).join("")}</tr></thead><tbody>${metric("Promoters — latest",e=>e.a.promoters)}${metric("FII — latest",e=>e.a.fiis)}${metric("DII — latest",e=>e.a.diis)}${metric("Institutional (FII + DII)",e=>e.inst)}${metric("Public — latest",e=>e.a.public)}${metric("Promoter change",e=>e.promoterDelta)}${metric("Institutional change",e=>e.instDelta)}${metric("Public change",e=>e.publicDelta)}</tbody></table></div></div>`; details.appendChild(section);
}
function addStyles(){ if(document.getElementById("shareholding-intelligence-styles")) return; const s=document.createElement("style"); s.id="shareholding-intelligence-styles"; s.textContent=`.stock-shareholding-intelligence,.stock-shareholding-compare{margin-top:18px}.share-intel-card{padding:18px;border:1px solid #dbe6f1;border-radius:16px;background:linear-gradient(135deg,#fbfdff,#f5f9ff);box-shadow:0 10px 30px rgba(15,35,65,.07);overflow:hidden}.share-intel-top{display:flex;justify-content:space-between;gap:18px;align-items:flex-start}.share-intel-eyebrow{font-size:9px;letter-spacing:.12em;font-weight:800;color:#2563eb}.share-intel-top h3,.share-intel-compare-card h3{margin:4px 0;color:#102b4e;font-size:18px}.share-intel-top p,.share-intel-compare-card p{margin:0;color:#64748b;font-size:11px;line-height:1.5}.share-intel-period{padding:6px 9px;border-radius:999px;background:#eef4fb;color:#49627e;font-size:9px;font-weight:800;white-space:nowrap}.share-intel-composition{display:grid;grid-template-columns:minmax(0,1.7fr) minmax(250px,1fr);gap:20px;margin-top:18px}.share-intel-bars{padding:4px 0}.share-intel-bar-row{display:grid;grid-template-columns:86px 1fr 52px;align-items:center;gap:9px;margin:11px 0;font-size:10px;color:#49627e}.share-intel-bar-row div{height:8px;background:#e9eff6;border-radius:99px;overflow:hidden}.share-intel-bar-row i{display:block;height:100%;border-radius:99px}.share-intel-bar-row b{text-align:right;font-size:10px;color:#17355d}.share-intel-stats{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}.share-intel-stat{padding:12px;border:1px solid #dce6f0;border-radius:12px;background:#fff}.share-intel-stat span{display:block;font-size:9px;color:#64748b}.share-intel-stat strong{display:block;margin-top:3px;font-size:17px;color:#102b4e}.share-intel-stat small{display:block;margin-top:4px;font-size:9px;font-weight:800}.share-intel-stat small.positive{color:#15803d}.share-intel-stat small.watch{color:#b45309}.share-intel-stat small.neutral{color:#64748b}.share-intel-note{margin-top:15px;padding-top:11px;border-top:1px solid #dce6f0}.share-intel-note span{display:block;font-size:10px;font-weight:800;color:#17355d}.share-intel-note small{display:block;margin-top:3px;color:#71849a;font-size:9px;line-height:1.45}.share-intel-compare-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:12px}.share-intel-compare-card{padding:15px;border:1px solid #dbe6f1;border-radius:14px;background:linear-gradient(135deg,#fff,#f7faff);box-shadow:0 8px 22px rgba(15,35,65,.05)}.share-intel-compare-card h3{font-size:14px}.share-intel-mini-bars{margin-top:10px}.share-intel-mini-bars .share-intel-bar-row{grid-template-columns:65px 1fr 43px;margin:7px 0;font-size:9px}.share-intel-mini-bars .share-intel-bar-row div{height:6px}.share-intel-compare-table{margin-top:14px}.share-intel-compare-table h3{font-size:13px;color:#17355d}.share-intel-compare-table .stock-table td:not(:first-child),.share-intel-compare-table .stock-table th:not(:first-child){text-align:right}@media(max-width:760px){.share-intel-composition{grid-template-columns:1fr}.share-intel-stats{grid-template-columns:1fr 1fr 1fr}.share-intel-top{display:block}.share-intel-period{display:inline-block;margin-top:8px}}`; document.head.appendChild(s); }
async function load(){ const details=document.getElementById("stock-details"); if(!details||busy)return; const p=new URLSearchParams(location.search), compare=p.get("compare"), symbol=(p.get("symbol")||"").trim().toUpperCase(), key=compare||symbol; if(!key||lastKey===key)return; if(!details.children.length)return; busy=true; lastKey=key; try{ if(compare){const symbols=compare.split(",").map(x=>decodeURIComponent(x).trim().toUpperCase()).filter(Boolean).slice(0,4);const r=await fetch(`${API}/compare?${symbols.map(s=>`symbols=${encodeURIComponent(s)}`).join("&")}`,{cache:"no-store",headers:{Accept:"application/json"}});if(!r.ok)throw new Error(r.status);const payload=await r.json();if(payload.stocks?.length)compare(payload.stocks,details);}else{const r=await fetch(`${API}/${encodeURIComponent(symbol)}`,{cache:"no-store",headers:{Accept:"application/json"}});if(!r.ok)throw new Error(r.status);individual(await r.json(),details);}}catch(e){console.warn("Shareholding intelligence unavailable:",e);lastKey="";}finally{busy=false;}}
function init(){addStyles();const details=document.getElementById("stock-details");if(!details)return;const observer=new MutationObserver(()=>{if(!details.querySelector(".stock-shareholding-intelligence,.stock-shareholding-compare"))setTimeout(load,180);});observer.observe(details,{childList:true,subtree:true});setTimeout(load,400);window.addEventListener("popstate",()=>{lastKey="";setTimeout(load,250);});}
if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",init,{once:true});else init();