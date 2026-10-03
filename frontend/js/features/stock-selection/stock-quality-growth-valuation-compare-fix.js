// Repairs QGV comparison cards from the same enriched stock-analysis endpoint used by individual analysis.
const API = "/api/stocks";
const num = v => (v == null || v === "" || !Number.isFinite(Number(v))) ? null : Number(v);
const pct = v => v == null ? "—" : `${Number(v).toFixed(1)}%`;
const ratio = v => v == null ? "—" : `${Number(v).toFixed(1)}x`;
function financial(f={}) { return /financial services|bank|nbfc|insurance|capital markets|credit/i.test(`${f.sector||""} ${f.industry||""}`); }
function values(data, statement, key) { return (data?.[statement]||[]).map(r=>num(r?.values?.[key])).filter(v=>v!=null); }
function cagr(a, y=3) { if(a.length<y+1) return null; const e=a[0], s=a[y]; return s>0&&e>0 ? (Math.pow(e/s,1/y)-1)*100 : null; }
function derive(data){
  const f=data?.fundamentals||{}, fin=financial(f), income=data?.income_statement||[], bal=data?.balance_sheet||[];
  const profit=num(f.net_profit)??num(income[0]?.values?.NetIncome), assets=num(bal[0]?.values?.TotalAssets), equity=num(bal[0]?.values?.StockholdersEquity);
  const roe=num(f.roe)??(profit!=null&&equity?profit/equity*100:null), roa=num(f.roa)??(profit!=null&&assets?profit/assets*100:null);
  const growth=num(f.profit_cagr_5y)??num(f.eps_cagr_5y)??num(f.profit_cagr_3y)??num(f.eps_cagr_3y)??cagr(values(data,"income_statement","NetIncome"),5)??cagr(values(data,"income_statement","DilutedEPS"),5);
  const payout=num(f.payout_ratio), retained=roe!=null&&payout!=null?roe*Math.max(0,Math.min(100,100-payout))/100:null;
  return {f,fin,growth,quality:fin?roa:roe,v:fin?num(f.pb):num(f.pe),retained,gap:growth!=null&&retained!=null?growth-retained:null,debtEq:num(f.debt_equity),debtGrowth:cagr(values(data,"balance_sheet","TotalDebt")),assetGrowth:cagr(values(data,"balance_sheet","TotalAssets")),equityGrowth:cagr(values(data,"balance_sheet","StockholdersEquity"))};
}
function setMetric(card,value,suffix=""){const s=card?.querySelector("strong");if(s)s.textContent=value==null?"—":`${Number(value).toFixed(1)}${suffix}`;}
async function repair(){
  const root=document.querySelector(".qgv-compare"); if(!root)return;
  const cards=[...root.querySelectorAll(".qgv-compare-card")];
  await Promise.all(cards.map(async card=>{
    const symbol=card.querySelector("header span")?.textContent?.trim(); if(!symbol)return;
    try{const r=await fetch(`${API}/${encodeURIComponent(symbol)}`,{headers:{Accept:"application/json"},cache:"no-store"});if(!r.ok)return;const x=derive(await r.json());
      const em=card.querySelector("header em"); if(em)em.textContent=x.fin?"Financial lens":"Operating lens";
      const metrics=[...card.querySelectorAll(".qgv-compare-metrics .qgv-metric")];
      if(metrics.length>=3){setMetric(metrics[0],x.v,"x");metrics[0].querySelector("span").textContent=x.fin?"P/B":"P/E";setMetric(metrics[1],x.quality,"%");metrics[1].querySelector("span").textContent=x.fin?"ROA":"ROE";setMetric(metrics[2],x.growth,"%");}
      const fund=card.querySelector(".qgv-compare-funding");if(fund){const spans=[...fund.querySelectorAll("span")];if(x.fin){const m=[x.assetGrowth,x.equityGrowth];spans.forEach((s,i)=>{if(s.querySelector("b")&&m[i]!=null)s.querySelector("b").textContent=pct(m[i]);});}else{const m=[x.retained,x.gap,x.debtGrowth,x.debtEq];spans.forEach((s,i)=>{if(s.querySelector("b"))s.querySelector("b").textContent=i===3?ratio(m[i]):pct(m[i]);});}}
    }catch(_){/* keep original card */}
  }));
}
function schedule(){let n=0;const t=()=>{if(document.querySelector(".qgv-compare"))repair();else if(++n<20)setTimeout(t,300);};t();}
if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",schedule);else schedule();
