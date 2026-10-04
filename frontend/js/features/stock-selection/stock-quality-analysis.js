const QUALITY_API = "/api/stocks/pedigree";
const QUALITY_COLORS = ["#2563eb", "#10b981", "#f59e0b", "#8b5cf6"];

const escQ = (v) => String(v ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");
const numQ = (v) => Number.isFinite(Number(v)) ? Number(v) : null;
const fmtQ = (v, suffix = "", digits = 1) => { const n = numQ(v); return n == null ? "—" : `${n.toLocaleString("en-IN", { maximumFractionDigits: digits })}${suffix}`; };

function qCard(id, title, subtitle) {
  return `<div class="stock-pedigree-chart-card"><h3>${escQ(title)}</h3><small>${escQ(subtitle)}</small><div class="stock-pedigree-chart-wrap"><canvas id="${escQ(id)}"></canvas></div></div>`;
}

function qOptions(yTitle, suffix = "") {
  return { responsive:true, maintainAspectRatio:false, interaction:{mode:"index",intersect:false}, plugins:{legend:{position:"top",labels:{boxWidth:10,usePointStyle:true,font:{size:10}}},tooltip:{callbacks:{label:(ctx)=>`${ctx.dataset.label}: ${fmtQ(ctx.parsed.y,suffix)}`}}},scales:{x:{grid:{display:false},ticks:{font:{size:9},color:"#64748b",maxRotation:0}},y:{title:{display:true,text:yTitle,color:"#475569",font:{size:10,weight:"600"}},grid:{color:"#edf2f7"},ticks:{font:{size:9},color:"#64748b",callback:(v)=>`${v}${suffix}`}}} };
}

function qDraw(id, datasets, yTitle, suffix = "") {
  if (typeof Chart === "undefined") return;
  const canvas = document.getElementById(id);
  if (!canvas || !datasets?.some(d => d.series?.length)) return;
  const labels = [...new Set(datasets.flatMap(d => (d.series || []).map(x => x.year)))].sort();
  if (!labels.length) return;
  const old = Chart.getChart(canvas); if (old) old.destroy();
  new Chart(canvas, { type:"line", data:{labels, datasets:datasets.map((d,i)=>{const c=d.color||QUALITY_COLORS[i%QUALITY_COLORS.length]; const map=Object.fromEntries((d.series||[]).map(x=>[x.year,x.value])); return {label:d.label,data:labels.map(y=>map[y]??null),borderColor:c,backgroundColor:`${c}12`,borderWidth:2,pointRadius:2.5,pointHoverRadius:5,tension:.22,spanGaps:true};})}, options:qOptions(yTitle,suffix) });
}

function qStat(label, value, note) { return `<div class="stock-pedigree-stat"><span>${escQ(label)}</span><strong>${escQ(value)}</strong><small>${escQ(note)}</small></div>`; }

// Keep the existing quality observations narrative intact. The collapsible
// presentation must not change the data/rendering path for this section.
function qualityNarrative(data) {
  const e=data.earnings_quality||{}, d=data.dilution||{}, c=data.capital_allocation||{}, out=[];
  if(e.cfo_profit_gap_5y!=null) out.push(`Over five years, operating cash flow CAGR is ${e.cfo_profit_gap_5y>=0?"ahead of":"behind"} profit CAGR by ${fmtQ(Math.abs(e.cfo_profit_gap_5y)," pp")} .`);
  if(e.fcf_profit_gap_5y!=null) out.push(`Five-year FCF CAGR is ${e.fcf_profit_gap_5y>=0?"ahead of":"behind"} profit CAGR by ${fmtQ(Math.abs(e.fcf_profit_gap_5y)," pp")} .`);
  if(d.share_count_cagr_5y!=null) out.push(`Implied share count changed at ${fmtQ(d.share_count_cagr_5y*100,"%",1)} CAGR over five years.`);
  if(d.profit_vs_eps_cagr_gap_5y!=null) out.push(`Five-year profit CAGR and EPS CAGR differ by ${fmtQ(Math.abs(d.profit_vs_eps_cagr_gap_5y)*100," pp",1)}.`);
  const capex = c.capex_to_cfo||[]; if(capex.length) out.push(`Latest capex consumed ${fmtQ(capex[capex.length-1].value,"%",1)} of operating cash flow.`);
  return out.length ? out : ["Not enough historical observations are available for a quality summary."];
}

function initQualityCard(section) {
  const header = section?.querySelector(".stock-pedigree-trends-card-header");
  const body = section?.querySelector(".stock-pedigree-trends-card-body");
  const button = section?.querySelector(".stock-pedigree-trends-caret");
  if (!header || !body || section.dataset.qualityCollapsible === "1") return;
  section.dataset.qualityCollapsible = "1";

  const setOpen = (open) => {
    header.setAttribute("aria-expanded", open ? "true" : "false");
    button?.setAttribute("aria-expanded", open ? "true" : "false");
    button?.setAttribute("aria-label", `${open ? "Collapse" : "Expand"} earnings quality and capital allocation`);
    body.hidden = !open;
    section.classList.toggle("is-open", open);
    if (open && typeof Chart !== "undefined") {
      requestAnimationFrame(() => body.querySelectorAll("canvas").forEach(canvas => Chart.getChart(canvas)?.resize()));
    }
  };

  const toggle = () => setOpen(header.getAttribute("aria-expanded") !== "true");
  header.addEventListener("click", event => { if (!event.target.closest("button")) toggle(); });
  header.addEventListener("keydown", event => {
    if (event.target.closest("button")) return;
    if (event.key === "Enter" || event.key === " ") { event.preventDefault(); toggle(); }
  });
  button?.addEventListener("click", event => { event.preventDefault(); event.stopPropagation(); toggle(); });

  // Render the charts normally first, then collapse the container. This keeps
  // the original chart creation path intact and avoids drawing into a hidden box.
  setOpen(true);
  requestAnimationFrame(() => setOpen(false));
}

function renderQualityIndividual(data, details) {
  if (!details || details.querySelector(".stock-quality-analysis")) return;
  const e=data.earnings_quality||{}, d=data.dilution||{}, c=data.capital_allocation||{};
  const section=document.createElement("section"); section.className="stock-pedigree-section stock-quality-analysis";
  section.innerHTML=`<div class="stock-pedigree-header"><div><h2>Earnings Quality, Capital Allocation & Dilution</h2><p>Historical cash generation, reinvestment intensity and per-share growth relationships.</p></div></div><div class="stock-pedigree-stats">${qStat("5Y CFO / Profit CAGR gap",fmtQ(e.cfo_profit_gap_5y*100," pp"),"Operating cash flow CAGR minus profit CAGR")}${qStat("5Y FCF / Profit CAGR gap",fmtQ(e.fcf_profit_gap_5y*100," pp"),"FCF CAGR minus profit CAGR")}${qStat("5Y Share-count CAGR",fmtQ(d.share_count_cagr_5y*100,"%"),"Implied annual change in shares")}${qStat("5Y Profit vs EPS gap",fmtQ(d.profit_vs_eps_cagr_gap_5y*100," pp"),"Profit CAGR minus EPS CAGR")}</div><div class="stock-pedigree-trends-card"><div class="stock-pedigree-trends-card-header" role="button" tabindex="0" aria-expanded="true"><div class="stock-pedigree-trends-card-main"><span class="stock-pedigree-trends-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 17 8 12 12 14 21 5"></polyline><polyline points="15 5 21 5 21 11"></polyline></svg></span><span class="stock-pedigree-trends-title">Historical Earnings Quality & Capital Allocation<small>Six historical diagnostics covering cash generation, conversion, reinvestment, funding and per-share growth</small></span></div><div class="stock-pedigree-trends-controls"><button type="button" class="stock-pedigree-trends-caret" aria-expanded="true" aria-label="Collapse earnings quality and capital allocation"><svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M5 7.5L10 12.5L15 7.5"></path></svg></button></div></div><div class="stock-pedigree-trends-card-body"><div class="stock-pedigree-chart-grid">${qCard("quality-cash","Profit vs Cash Generation","Indexed to 100; profit, operating cash flow and free cash flow")}${qCard("quality-conversion","Cash Conversion","CFO / profit and FCF / profit")}${qCard("quality-capital","Capital Deployment","Capex relative to operating cash flow and revenue")}${qCard("quality-funding","Funding & Debt","Debt trajectory alongside free cash flow")}${qCard("quality-shares","Implied Share Count","Historical share-count proxy from profit and diluted EPS")}${qCard("quality-eps-profit","Profit vs EPS Growth","Annual profit growth versus EPS growth")}</div></div></div><div class="stock-pedigree-narrative"><h3>Quality observations</h3><ul>${qualityNarrative(data).map(x=>`<li>${escQ(x)}</li>`).join("")}</ul></div>`;
  details.appendChild(section);
  qDraw("quality-cash",[{label:"Net Profit",series:e.net_profit_indexed,color:QUALITY_COLORS[0]},{label:"Operating Cash Flow",series:e.cfo_indexed,color:QUALITY_COLORS[1]},{label:"Free Cash Flow",series:e.fcf_indexed,color:QUALITY_COLORS[2]}],"Index (100 = first positive observation)");
  qDraw("quality-conversion",[{label:"CFO / Net Profit",series:e.cfo_to_profit,color:QUALITY_COLORS[0]},{label:"FCF / Net Profit",series:e.fcf_to_profit,color:QUALITY_COLORS[2]}],"Percent","%");
  qDraw("quality-capital",[{label:"Capex / CFO",series:c.capex_to_cfo,color:QUALITY_COLORS[1]},{label:"Capex / Revenue",series:c.capex_to_revenue,color:QUALITY_COLORS[3]}],"Percent","%");
  qDraw("quality-funding",[{label:"Debt",series:c.debt,color:QUALITY_COLORS[3]},{label:"Free Cash Flow",series:c.fcf,color:QUALITY_COLORS[2]}],"Reported amount");
  qDraw("quality-shares",[{label:"Implied Share Count",series:d.implied_shares,color:QUALITY_COLORS[0]}],"Crore shares");
  qDraw("quality-eps-profit",[{label:"Profit growth",series:e.profit_growth,color:QUALITY_COLORS[0]},{label:"EPS growth",series:d.share_count_growth?.length?e.profit_growth:[],color:QUALITY_COLORS[1]}],"Growth","%");
  const epsCanvas=document.getElementById("quality-eps-profit");
  if(epsCanvas){ const old=Chart.getChart(epsCanvas); if(old) old.destroy(); qDraw("quality-eps-profit",[{label:"Profit growth",series:e.profit_growth,color:QUALITY_COLORS[0]},{label:"EPS growth",series:data.trends?.eps_growth||[],color:QUALITY_COLORS[1]}],"Growth","%"); }
  initQualityCard(section.querySelector(".stock-pedigree-trends-card"));
}

function renderQualityCompare(datas, details) {
  if (!details || details.querySelector(".stock-quality-compare")) return;
  const names=datas.map(d=>d.symbol), colors=names.map((_,i)=>QUALITY_COLORS[i%QUALITY_COLORS.length]);
  const section=document.createElement("section"); section.className="stock-pedigree-section stock-quality-compare";
  section.innerHTML=`<div class="stock-pedigree-header"><div><h2>Earnings Quality, Capital Allocation & Dilution Comparison</h2><p>The same historical calculations are applied across all selected companies.</p></div></div><div class="stock-pedigree-chart-grid">${qCard("quality-compare-cash","Cash Generation — Indexed","Profit, operating cash flow and FCF")}${qCard("quality-compare-conversion","Cash Conversion","CFO / profit")}${qCard("quality-compare-fcfconversion","FCF Conversion","FCF / profit")}${qCard("quality-compare-capex","Capital Intensity","Capex / revenue")}${qCard("quality-compare-shares","Share Count Growth","Implied annual share-count change")}${qCard("quality-compare-eps","Profit vs EPS Growth","Annual growth relationship")}</div><div class="stock-pedigree-compare-table"><h3>Quality Snapshot</h3><div class="stock-table-wrap"><table class="stock-table"><thead><tr><th>Metric</th>${names.map(x=>`<th>${escQ(x)}</th>`).join("")}</tr></thead><tbody>${[["5Y CFO / Profit CAGR gap",d=>d.earnings_quality?.cfo_profit_gap_5y*100," pp"],["5Y FCF / Profit CAGR gap",d=>d.earnings_quality?.fcf_profit_gap_5y*100," pp"],["5Y Share-count CAGR",d=>d.dilution?.share_count_cagr_5y*100,"%"],["5Y Profit vs EPS gap",d=>d.dilution?.profit_vs_eps_cagr_gap_5y*100," pp"]].map(([label,fn,suf])=>`<tr><td>${escQ(label)}</td>${datas.map(d=>`<td>${escQ(fmtQ(fn(d),suf))}</td>`).join("")}</tr>`).join("")}</tbody></table></div></div>`;
  details.appendChild(section);
  const seriesFor=(path)=>datas.map((d,i)=>{let x=d; for(const p of path.split(".")) x=x?.[p]; return {label:names[i],series:x||[],color:colors[i]};});
  qDraw("quality-compare-cash",datas.map((d,i)=>({label:`${names[i]} · Profit`,series:d.earnings_quality?.net_profit_indexed||[],color:colors[i]})),"Index");
  qDraw("quality-compare-conversion",seriesFor("earnings_quality.cfo_to_profit"),"Percent","%");
  qDraw("quality-compare-fcfconversion",seriesFor("earnings_quality.fcf_to_profit"),"Percent","%");
  qDraw("quality-compare-capex",seriesFor("capital_allocation.capex_to_revenue"),"Percent","%");
  qDraw("quality-compare-shares",seriesFor("dilution.share_count_growth"),"Growth","%");
  qDraw("quality-compare-eps",datas.map((d,i)=>({label:`${names[i]} · EPS`,series:d.trends?.eps_growth||[],color:colors[i]})).concat(datas.map((d,i)=>({label:`${names[i]} · Profit`,series:d.earnings_quality?.profit_growth||[],color:colors[i]}))),"Growth","%");
}

async function loadQuality() {
  const details=document.getElementById("stock-details"); if(!details) return;
  const params=new URLSearchParams(location.search), compare=params.get("compare");
  try {
    if(compare){
      const symbols=compare.split(",").map(x=>decodeURIComponent(x).trim().toUpperCase()).filter(Boolean).slice(0,4);
      if(!symbols.length) return;
      const r=await fetch(`${QUALITY_API}/compare?${symbols.map(s=>`symbols=${encodeURIComponent(s)}`).join("&")}`,{cache:"no-store",headers:{Accept:"application/json"}});
      if(!r.ok) return; const data=await r.json(); if(data.stocks?.length) renderQualityCompare(data.stocks,details);
    } else {
      const symbol=(params.get("symbol")||"").trim().toUpperCase(); if(!symbol) return;
      const r=await fetch(`${QUALITY_API}/${encodeURIComponent(symbol)}`,{cache:"no-store",headers:{Accept:"application/json"}});
      if(!r.ok) return; renderQualityIndividual(await r.json(),details);
    }
  } catch(e){ console.warn("Stock quality analytics unavailable:",e); }
}

function initQuality(){const details=document.getElementById("stock-details"); if(!details)return; const obs=new MutationObserver(()=>{if(!details.querySelector(".stock-quality-analysis,.stock-quality-compare")&&details.children.length)setTimeout(loadQuality,160);}); obs.observe(details,{childList:true,subtree:true}); setTimeout(loadQuality,220); window.addEventListener("popstate",()=>setTimeout(loadQuality,220));}
if(document.readyState==="loading") document.addEventListener("DOMContentLoaded",initQuality,{once:true}); else initQuality();
