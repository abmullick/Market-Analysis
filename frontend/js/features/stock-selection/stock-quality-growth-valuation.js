// Quality × Growth × Valuation + Growth Funding & Capital Efficiency.
// Uses only the existing stock, pedigree and chart endpoints. No new data source.
const API = "/api/stocks";
const n = v => Number.isFinite(Number(v)) ? Number(v) : null;
const esc = v => String(v ?? "").replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;").replaceAll("'","&#039;");
const pct = v => v == null ? "—" : `${Number(v).toFixed(1)}%`;
const ratio = v => v == null ? "—" : `${Number(v).toFixed(1)}x`;
const finite = a => a.filter(v => v != null && Number.isFinite(Number(v))).map(Number);

function financialLens(f) {
  return /financial services|bank|nbfc|insurance|capital markets|credit/i.test(`${f?.sector || ""} ${f?.industry || ""}`);
}
function arr(s) {
  return (Array.isArray(s) ? s : []).map(x => ({
    year: String(x?.year ?? x?.period ?? x?.date ?? ""),
    value: n(x?.value)
  })).filter(x => x.year && x.value != null);
}
function cagr(s, years = 3) {
  const a = arr(s);
  if (a.length < years + 1) return null;
  const start = a[a.length - 1 - years].value, end = a[a.length - 1].value;
  if (start <= 0 || end <= 0) return null;
  return (Math.pow(end / start, 1 / years) - 1) * 100;
}
function latest(s) { const a = arr(s); return a.length ? a[a.length - 1].value : null; }
function trend(data, key) { return data?.trends?.[key] || data?.pedigree?.trends?.[key] || []; }
function valuationMetric(f) { return financialLens(f) ? {label:"P/B", value:n(f?.pb)} : {label:"P/E", value:n(f?.pe)}; }
function qualityMetric(f) { return financialLens(f) ? {label:"ROA", value:n(f?.roa)} : {label:"ROE", value:n(f?.roe)}; }
function earningsGrowth(f, p) {
  return n(f?.profit_cagr_5y ?? f?.eps_cagr_5y ?? f?.profit_cagr_3y ?? f?.eps_cagr_3y) ?? cagr(trend(p,"profit"),5) ?? cagr(trend(p,"eps"),5);
}
function funding(f, p) {
  const financial = financialLens(f);
  const growth = earningsGrowth(f,p);
  const roe = n(f?.roe);
  const payout = n(f?.payout_ratio);
  const retention = payout == null ? null : Math.max(0, Math.min(100, 100 - payout));
  const retainedCapacity = roe != null && retention != null ? roe * retention / 100 : null;
  const growthGap = growth != null && retainedCapacity != null ? growth - retainedCapacity : (growth != null && roe != null ? growth - roe : null);
  const debtGrowth = cagr(trend(p,"debt"),3);
  const assetGrowth = cagr(trend(p,"assets"),3);
  const equityGrowth = cagr(trend(p,"equity"),3);
  const cfoGrowth = cagr(trend(p,"cfo"),3) ?? cagr(p?.capital_allocation?.cfo,3);
  const fcfGrowth = cagr(trend(p,"fcf"),3) ?? cagr(p?.capital_allocation?.fcf,3);
  const shareCagr = n(p?.dilution?.share_count_cagr_3y ?? p?.dilution?.share_count_cagr_5y);
  const debtEq = n(f?.debt_equity), interest = n(f?.interest_coverage), nde = n(f?.net_debt_ebitda);
  const cashConversion = latest(p?.earnings_quality?.cfo_to_profit);
  let label = "Funding evidence is limited";
  if (!financial) {
    if (growthGap != null && growthGap > 5 && debtGrowth != null && debtGrowth > 5) label = "Growth is accompanied by rising debt";
    else if (growthGap != null && growthGap > 5 && shareCagr != null && shareCagr > 1) label = "Growth is accompanied by share-count expansion";
    else if (growthGap != null && growthGap > 5 && cfoGrowth != null && growth != null && cfoGrowth >= growth && (debtGrowth == null || debtGrowth <= 5)) label = "Growth has strong operating-cash support";
    else if (growthGap != null && growthGap <= 5) label = "Growth is broadly within retained-earnings capacity";
    else if (growthGap != null && growthGap > 5) label = "Growth exceeds simple retained-earnings capacity";
  }
  return {financial,growth,roe,payout,retention,retainedCapacity,growthGap,debtGrowth,assetGrowth,equityGrowth,cfoGrowth,fcfGrowth,shareCagr,debtEq,interest,nde,cashConversion,label};
}
function metric(label, value, suffix, note) {
  return `<div class="qgv-metric"><span>${esc(label)}</span><strong>${value == null ? "—" : esc(Number(value).toFixed(1))}${suffix || ""}</strong>${note ? `<small>${esc(note)}</small>` : ""}</div>`;
}
function chip(label,value,kind="neutral") { return `<span class="qgv-chip ${kind}"><b>${esc(label)}</b><strong>${esc(value)}</strong></span>`; }
function scoreKind(v){return v == null ? "neutral" : v >= 15 ? "good" : v >= 5 ? "mid" : "weak";}

function individualHtml(data) {
  const f = data?.fundamentals || {};
  const p = data?.pedigree || {};
  const financial = financialLens(f);
  const v = valuationMetric(f), q = qualityMetric(f), g = earningsGrowth(f,p), fund = funding(f,p);
  const lens = financial ? "FINANCIAL SERVICES LENS" : "OPERATING BUSINESS LENS";
  const fundingTitle = financial ? "Capital & Growth Context" : "Growth Funding & Capital Efficiency";
  const fundingDescription = financial
    ? "For lenders, debt is an operating input. The engine therefore focuses on P/B, ROA, earnings growth and the way assets/book value are expanding."
    : "Connects earnings growth with retained-earnings capacity, leverage, cash generation and share-count expansion using only observable data.";
  const growthSignal = fund.growthGap == null ? "Insufficient funding comparison" : fund.growthGap > 5 ? "Growth is above simple internal capacity" : "Growth is broadly supported by internal capacity";
  const signalKind = fund.growthGap == null ? "neutral" : fund.growthGap > 5 ? "watch" : "good";
  const fundingBlocks = financial ? `
    <div class="qgv-financial-strip">
      ${chip("P/B", ratio(v.value), "blue")}
      ${chip("ROA", pct(q.value), q.value != null && q.value >= 2 ? "good" : "neutral")}
      ${chip("Earnings growth", pct(g), g != null && g >= 10 ? "good" : "neutral")}
      ${chip("Asset growth", pct(fund.assetGrowth), "neutral")}
      ${chip("Book growth", pct(fund.equityGrowth), "neutral")}
      ${chip("Share-count CAGR", pct(fund.shareCagr), fund.shareCagr != null && fund.shareCagr > 1 ? "watch" : "good")}
    </div>
    <div class="qgv-capital-note"><b>How to read it</b><span>For a lender, a high P/B is more meaningful when ROA and earnings growth are weak; a lower P/B paired with stronger ROA and growth represents a different quality/valuation relationship. Asset and book growth provide the capital-growth context.</span></div>` : `
    <div class="qgv-funding-grid">
      ${metric("Earnings growth",fund.growth,"%","5Y/3Y CAGR available")}
      ${metric("ROE",fund.roe,"%","Current return on equity")}
      ${metric("Retained-earnings capacity",fund.retainedCapacity,"%","ROE × (1 − payout)")}
      ${metric("Growth gap",fund.growthGap," pp","Growth minus retained-earnings capacity")}
      ${metric("Debt / Equity",fund.debtEq,"x","Current leverage")}
      ${metric("Interest coverage",fund.interest,"x","Current coverage where available")}
      ${metric("Net Debt / EBITDA",fund.nde,"x","Current debt burden")}
      ${metric("Debt growth 3Y",fund.debtGrowth,"%","Historical debt CAGR")}
      ${metric("Operating cash growth 3Y",fund.cfoGrowth,"%","Historical CFO CAGR")}
      ${metric("FCF growth 3Y",fund.fcfGrowth,"%","Historical FCF CAGR")}
      ${metric("Share-count CAGR",fund.shareCagr,"%","Potential dilution signal")}
    </div>
    <div class="qgv-funding-path">
      <div class="qgv-path-node"><span>Growth</span><b>${pct(fund.growth)}</b></div><i>→</i><div class="qgv-path-node"><span>Internal capacity</span><b>${pct(fund.retainedCapacity)}</b></div><i>→</i><div class="qgv-path-node"><span>Debt growth</span><b>${pct(fund.debtGrowth)}</b></div><i>→</i><div class="qgv-path-node"><span>Share count</span><b>${pct(fund.shareCagr)}</b></div>
    </div>`;
  return `<section class="qgv-section qgv-individual">
    <div class="qgv-head"><div><div class="qgv-eyebrow">DECISION LENS</div><h2>Quality × Growth × Valuation</h2><p>${financial ? "P/B × ROA × earnings growth" : "P/E × ROE × earnings growth"}. The engine connects the factors investors often read together instead of presenting them as isolated ratios.</p></div><span class="qgv-lens">${lens}</span></div>
    <div class="qgv-top-grid">
      <div class="qgv-score-card"><div class="qgv-kicker">CURRENT RELATIONSHIP</div><div class="qgv-three"><div><b>${ratio(v.value)}</b><small>${esc(v.label)}</small></div><div><b>${pct(q.value)}</b><small>${esc(q.label)}</small></div><div><b>${pct(g)}</b><small>Earnings growth</small></div></div><div class="qgv-flow"><span>Valuation</span><i></i><span>Quality</span><i></i><span>Growth</span></div><p>${financial ? `Current ${v.label} ${ratio(v.value)} is being read together with ${q.label} ${pct(q.value)} and earnings growth ${pct(g)}.` : `${growthSignal}. A positive gap is an investigation signal, not proof that the company raised external capital.`}</p></div>
      <div class="qgv-story-card"><div class="qgv-kicker">THE QUESTION THIS ENGINE ANSWERS</div><div class="qgv-story-line"><strong>${esc(v.label)}</strong><span>×</span><strong>${esc(q.label)}</strong><span>×</span><strong>Earnings growth</strong></div><p>Lower valuation with stronger business quality and sustained growth is fundamentally different from a low multiple caused by weak returns or deteriorating earnings.</p><div class="qgv-story-badge ${signalKind}">${esc(growthSignal)}</div></div>
    </div>
    <div class="qgv-funding"><div class="qgv-subhead"><div><h3>${fundingTitle}</h3><p>${fundingDescription}</p></div><span class="qgv-info" title="Growth above ROE is an investigation signal, not proof that external capital was raised.">i</span></div>${fundingBlocks}<div class="qgv-conclusion"><b>Engine read:</b> ${esc(financial ? "Use P/B, ROA and earnings growth together, then inspect asset/book growth and dilution." : fund.label + ".")}</div></div>
    <div class="qgv-method"><b>Method</b><span>${esc(financial ? "Financial services use P/B + ROA + earnings growth. Debt is not treated like industrial leverage." : "Retained-earnings capacity = ROE × (1 − payout). The gap is descriptive. Debt, cash-flow and share-count trends are used only as observable funding evidence; no external funding event is assumed without evidence.")}</span></div>
  </section>`;
}

function relativeValuationScore(f, charts) {
  const financial = financialLens(f);
  const key = financial ? "pb_history" : "pe_history";
  const current = financial ? n(f?.pb) : n(f?.pe);
  const values = finite((charts?.[key] || []).map(x => x?.value));
  if (current == null || !values.length) return null;
  values.sort((a,b)=>a-b); const m = values[Math.floor(values.length/2)];
  return m > 0 ? Math.max(0,Math.min(100,50 + ((m-current)/m)*100)) : null;
}
function compareHtml(rows) {
  const items = rows.map(r => { const f=r.core?.fundamentals||{}, p=r.pedigree||{}, charts=r.charts||{}; return {r,f,p,charts,financial:financialLens(f),v:valuationMetric(f),q:qualityMetric(f),g:earningsGrowth(f,p),fund:funding(f,p),rel:relativeValuationScore(f,charts),name:f.name||f.longName||r.symbol,short:String(r.symbol).replace(/\.NS$|\.BO$/i,"")}; });
  const valid = items.filter(x => x.q.value != null && x.rel != null && x.g != null);
  const dots = valid.map(x => { const xs=valid.map(i=>i.rel), ys=valid.map(i=>i.q.value), gs=valid.map(i=>i.g); const xmin=Math.min(...xs), xmax=Math.max(...xs), ymin=Math.min(...ys), ymax=Math.max(...ys), gmin=Math.min(...gs), gmax=Math.max(...gs); const left=xmax===xmin?50:8+((x.rel-xmin)/(xmax-xmin))*84, top=ymax===ymin?50:92-((x.q.value-ymin)/(ymax-ymin))*84, size=18+(gmax===gmin?7:Math.max(0,Math.min(22,(x.g-gmin)/(gmax-gmin)*22))); return `<button class="qgv-dot" style="left:${left}%;top:${top}%;width:${size}px;height:${size}px" title="${esc(x.name)} · relative valuation ${x.rel.toFixed(0)}/100 · ${x.q.label} ${x.q.value.toFixed(1)}% · earnings growth ${x.g.toFixed(1)}%"><span>${esc(x.short)}</span></button>`; }).join("");
  const cards=items.map(x=>`<article class="qgv-compare-card"><header><div><h3>${esc(x.name)}</h3><span>${esc(x.short)}</span></div><em>${x.financial?"Financial lens":"Operating lens"}</em></header><div class="qgv-compare-metrics">${metric(x.v.label,x.v.value,"x")}${metric(x.q.label,x.q.value,"%")}${metric("Earnings growth",x.g,"%")}</div>${x.financial?`<div class="qgv-compare-funding"><span>Asset growth <b>${pct(x.fund.assetGrowth)}</b></span><span>Book growth <b>${pct(x.fund.equityGrowth)}</b></span><span>Share count <b>${pct(x.fund.shareCagr)}</b></span></div>`:`<div class="qgv-compare-funding"><span>Retained capacity <b>${pct(x.fund.retainedCapacity)}</b></span><span>Growth gap <b>${pct(x.fund.growthGap)}</b></span><span>Debt growth <b>${pct(x.fund.debtGrowth)}</b></span><span>D/E <b>${ratio(x.fund.debtEq)}</b></span></div>`}</article>`).join("");
  return `<section class="qgv-section qgv-compare"><div class="qgv-head"><div><div class="qgv-eyebrow">COMPARATIVE DECISION LENS</div><h2>Quality × Growth × Valuation</h2><p>Each stock keeps its own sector-aware lens. Relative valuation is normalized to each company's own historical multiple so mixed-sector comparisons remain meaningful.</p></div><span class="qgv-lens">${items.length} stocks</span></div>${valid.length>=2?`<div class="qgv-map"><div class="qgv-plot"><div class="qgv-quadrant qgv-q1">Stronger quality<br><small>Lower relative valuation</small></div><div class="qgv-quadrant qgv-q2">Stronger quality<br><small>Higher relative valuation</small></div><div class="qgv-quadrant qgv-q3">Weaker quality<br><small>Lower relative valuation</small></div><div class="qgv-quadrant qgv-q4">Weaker quality<br><small>Higher relative valuation</small></div>${dots}<div class="qgv-axis-x"><span>Higher valuation attractiveness</span><span>Lower valuation attractiveness</span></div><div class="qgv-axis-y"><span>Higher quality</span><span>Lower quality</span></div></div><div class="qgv-legend"><span>Bubble size = earnings growth</span><span>Horizontal = relative valuation · Vertical = quality</span></div></div>`:`<div class="qgv-empty">Not enough historical valuation data to plot the normalized comparison.</div>`}<div class="qgv-compare-grid">${cards}</div><div class="qgv-compare-note"><b>Funding lens:</b> Financial companies are read through ROA, asset/book growth and dilution context. Non-lenders add retained-earnings capacity, debt growth, leverage and cash-growth evidence. Nothing here assumes an external funding event without observable evidence.</div></section>`;
}

async function getJson(path) { const r=await fetch(path,{headers:{Accept:"application/json","X-Stock-Decision-Lens":"1"},cache:"no-store"}); if(!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); }
async function bundle(symbol) {
  const [core,pedigree,charts] = await Promise.all([
    getJson(`${API}/${encodeURIComponent(symbol)}`),
    getJson(`${API}/pedigree/${encodeURIComponent(symbol)}`),
    getJson(`${API}/${encodeURIComponent(symbol)}/charts`)
  ]);
  return {symbol,core,pedigree,charts:charts?.charts||charts||{}};
}

function styles() {
  if(document.getElementById("qgv-styles")) return;
  const s=document.createElement("style"); s.id="qgv-styles"; s.textContent=`
.qgv-section{margin:20px 0;padding:19px;border:1px solid #d8e4f0;border-radius:18px;background:linear-gradient(135deg,#fff 0%,#f5f9ff 100%);box-shadow:0 10px 30px rgba(15,23,42,.07);position:relative;overflow:hidden}.qgv-section:before{content:"";position:absolute;left:0;right:0;top:0;height:3px;background:linear-gradient(90deg,#2563eb,#7c3aed,#06b6d4)}.qgv-head{display:flex;justify-content:space-between;gap:18px;align-items:flex-start}.qgv-eyebrow,.qgv-kicker{font-size:9px;font-weight:900;letter-spacing:.12em;color:#2563eb}.qgv-head h2{margin:3px 0 4px;color:#102b4e;font-size:19px}.qgv-head p{margin:0;color:#64748b;font-size:11px;line-height:1.5;max-width:850px}.qgv-lens{padding:7px 10px;border-radius:999px;background:#edf5ff;color:#315a83;font-size:9px;font-weight:900;white-space:nowrap}.qgv-top-grid{display:grid;grid-template-columns:1.35fr 1fr;gap:12px;margin-top:14px}.qgv-score-card,.qgv-story-card{padding:14px;border:1px solid #dfe8f2;border-radius:13px;background:rgba(255,255,255,.9)}.qgv-three{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:9px}.qgv-three div{padding:11px;border-radius:11px;background:linear-gradient(135deg,#f7fbff,#fff);border:1px solid #e4edf6}.qgv-three b{display:block;color:#102b4e;font-size:21px}.qgv-three small{color:#708299;font-size:8px;font-weight:800;text-transform:uppercase}.qgv-flow{display:flex;align-items:center;gap:7px;margin-top:11px;color:#49627e;font-size:8px;font-weight:800}.qgv-flow i{height:1px;flex:1;background:linear-gradient(90deg,#b9cce1,#7c3aed,#b9cce1)}.qgv-score-card p,.qgv-story-card p{margin:10px 0 0;color:#5f7187;font-size:10px;line-height:1.5}.qgv-story-line{display:flex;align-items:center;gap:7px;flex-wrap:wrap;margin-top:12px}.qgv-story-line strong{padding:6px 8px;border-radius:8px;background:#f1f6fc;color:#17355d;font-size:9px}.qgv-story-line span{color:#94a3b8;font-weight:900}.qgv-story-badge{display:inline-block;margin-top:12px;padding:6px 9px;border-radius:999px;font-size:8px;font-weight:900}.qgv-story-badge.good{background:#ecfdf3;color:#15803d}.qgv-story-badge.watch{background:#fff7ed;color:#b45309}.qgv-story-badge.neutral{background:#f1f5f9;color:#64748b}.qgv-funding{margin-top:12px;padding:14px;border-radius:13px;background:linear-gradient(135deg,#f8fbff,#fff);border:1px solid #dce7f2}.qgv-subhead{display:flex;justify-content:space-between;gap:12px}.qgv-subhead h3{margin:0;color:#17355d;font-size:13px}.qgv-subhead p{margin:3px 0 0;color:#71849a;font-size:9px}.qgv-info{width:17px;height:17px;display:grid;place-items:center;border:1px solid #9bb0c7;border-radius:50%;color:#315a83;font-size:9px;font-weight:900;cursor:help}.qgv-funding-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:7px;margin-top:10px}.qgv-metric{padding:9px;border:1px solid #e2eaf3;border-radius:9px;background:#fff;min-width:0}.qgv-metric span{display:block;color:#74859a;font-size:8px;font-weight:800}.qgv-metric strong{display:block;margin-top:3px;color:#17355d;font-size:13px}.qgv-metric small{display:block;margin-top:3px;color:#94a3b8;font-size:7px;line-height:1.3}.qgv-funding-path{display:flex;align-items:center;gap:7px;margin-top:10px;padding:10px;border:1px solid #e1eaf3;border-radius:10px;background:#fff}.qgv-path-node{flex:1;text-align:center;padding:7px;border-radius:8px;background:#f7faff}.qgv-path-node span{display:block;color:#7b8da1;font-size:7px;font-weight:800;text-transform:uppercase}.qgv-path-node b{display:block;margin-top:3px;color:#17355d;font-size:12px}.qgv-funding-path>i{font-style:normal;color:#8aa0b7;font-weight:900}.qgv-financial-strip{display:grid;grid-template-columns:repeat(6,1fr);gap:7px;margin-top:10px}.qgv-chip{display:flex;flex-direction:column;padding:9px;border:1px solid #e2eaf3;border-radius:9px;background:#fff}.qgv-chip b{font-size:7px;color:#7b8da1;text-transform:uppercase}.qgv-chip strong{margin-top:3px;font-size:13px;color:#17355d}.qgv-chip.good{background:#f2fbf5;border-color:#c7ead2}.qgv-chip.watch{background:#fff8ef;border-color:#f2d3a6}.qgv-chip.blue{background:#f1f7ff;border-color:#cfe0f6}.qgv-capital-note{margin-top:9px;padding:10px;border-radius:9px;background:#eef7ff;border:1px solid #d5e7f7}.qgv-capital-note b{display:block;color:#17436b;font-size:8px}.qgv-capital-note span{display:block;margin-top:3px;color:#60758c;font-size:8px;line-height:1.45}.qgv-conclusion{margin-top:10px;padding-top:9px;border-top:1px solid #e3ebf3;color:#3f5871;font-size:9px;line-height:1.5}.qgv-method{display:flex;gap:8px;margin-top:11px;padding-top:9px;border-top:1px dashed #d8e2ed}.qgv-method b{font-size:8px;color:#52708f;text-transform:uppercase}.qgv-method span{color:#7a8b9f;font-size:8px;line-height:1.45}.qgv-map{margin-top:14px}.qgv-plot{height:350px;position:relative;border:1px solid #dbe5ef;border-radius:13px;overflow:hidden;background:radial-gradient(circle at 25% 25%,rgba(37,99,235,.09),transparent 30%),linear-gradient(135deg,#f8fbff,#fff)}.qgv-plot:before{content:"";position:absolute;left:50%;top:0;bottom:0;border-left:1px dashed #cbd5e1}.qgv-plot:after{content:"";position:absolute;left:0;right:0;top:50%;border-top:1px dashed #cbd5e1}.qgv-quadrant{position:absolute;padding:9px 10px;color:#66788d;font-size:9px;font-weight:900;z-index:1}.qgv-quadrant small{font-size:7px;font-weight:600}.qgv-q1{left:2%;top:2%}.qgv-q2{right:2%;top:2%;text-align:right}.qgv-q3{left:2%;bottom:12%}.qgv-q4{right:2%;bottom:12%;text-align:right}.qgv-dot{position:absolute;transform:translate(-50%,-50%);border-radius:50%;border:3px solid #fff;background:radial-gradient(circle at 35% 30%,#60a5fa,#2563eb);box-shadow:0 7px 18px rgba(37,99,235,.28);z-index:3;padding:0;cursor:help}.qgv-dot:hover{transform:translate(-50%,-50%) scale(1.18)}.qgv-dot span{position:absolute;left:50%;top:100%;transform:translateX(-50%);margin-top:3px;font-size:8px;color:#35516e;font-weight:900;white-space:nowrap}.qgv-axis-x{position:absolute;left:12px;right:12px;bottom:6px;display:flex;justify-content:space-between;color:#8a99aa;font-size:7px;font-weight:800}.qgv-axis-y{position:absolute;left:5px;top:10px;bottom:32px;display:flex;flex-direction:column;justify-content:space-between;color:#8a99aa;font-size:7px;font-weight:800;writing-mode:vertical-rl}.qgv-legend{display:flex;justify-content:space-between;margin-top:6px;color:#8291a3;font-size:8px}.qgv-compare-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin-top:12px}.qgv-compare-card{padding:12px;border:1px solid #dfe7f0;border-radius:12px;background:#fff}.qgv-compare-card header{display:flex;justify-content:space-between;gap:8px}.qgv-compare-card h3{margin:0;color:#17355d;font-size:12px}.qgv-compare-card header span{display:block;color:#8796a7;font-size:8px;margin-top:2px}.qgv-compare-card em{font-style:normal;color:#2563eb;background:#eef5ff;border-radius:999px;padding:4px 6px;font-size:7px;font-weight:900}.qgv-compare-metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin-top:9px}.qgv-compare-metrics .qgv-metric{padding:7px}.qgv-compare-funding{display:flex;gap:6px;flex-wrap:wrap;margin-top:8px}.qgv-compare-funding span{padding:5px 7px;border-radius:7px;background:#f6f9fc;color:#71849a;font-size:8px}.qgv-compare-funding b{color:#294766}.qgv-compare-note{margin-top:11px;padding:10px 11px;border-radius:9px;background:#f4f8fc;color:#60758c;font-size:8px;line-height:1.45}.qgv-compare-note b{color:#315a83;margin-right:5px}.qgv-empty{padding:30px;text-align:center;color:#8493a4;border:1px dashed #cbd5e1;border-radius:10px;font-size:10px}
@media(max-width:900px){.qgv-top-grid,.qgv-compare-grid{grid-template-columns:1fr}.qgv-funding-grid{grid-template-columns:repeat(2,1fr)}.qgv-financial-strip{grid-template-columns:repeat(3,1fr)}}@media(max-width:600px){.qgv-three{grid-template-columns:1fr}.qgv-funding-grid,.qgv-financial-strip{grid-template-columns:1fr 1fr}.qgv-funding-path{overflow:auto}.qgv-path-node{min-width:110px}.qgv-head{display:block}.qgv-lens{display:inline-block;margin-top:8px}.qgv-legend{display:block}.qgv-legend span{display:block;margin-top:3px}}
`;
  document.head.appendChild(s);
}

let lastIndividualKey="", lastCompareKey="", running=false;
async function renderIndividual() {
  const symbol=(new URLSearchParams(location.search).get("symbol")||"").trim().toUpperCase();
  const details=document.getElementById("stock-details");
  if(!symbol || !details || !details.querySelector(".stock-hero")) return;
  if(lastIndividualKey===symbol && details.querySelector(".qgv-individual")) return;
  try { const data=await bundle(symbol); if(!details.isConnected) return; details.querySelector(".qgv-individual")?.remove(); const anchor=details.querySelector(".stock-valuation-engine")||details.querySelector(".stock-fundamental-momentum")||details.querySelector(".stock-hero"); if(anchor) anchor.insertAdjacentHTML("afterend",individualHtml(data)); lastIndividualKey=symbol; } catch(e){ console.warn("Decision lens unavailable",e); }
}
async function renderCompare() {
  const compare=(new URLSearchParams(location.search).get("compare")||"").split(",").map(x=>decodeURIComponent(x).trim().toUpperCase()).filter(Boolean);
  const host=document.getElementById("stock-analysis-screen");
  if(compare.length<2 || !host || !host.querySelector(".stock-comparison-table")) return;
  const key=compare.join(",");
  if(lastCompareKey===key && host.querySelector(".qgv-compare")) return;
  try { const rows=await Promise.all(compare.slice(0,6).map(bundle)); host.querySelector(".qgv-compare")?.remove(); const anchor=host.querySelector(".advanced-summary")||host.querySelector(".advanced-matrix")||host.querySelector(".stock-comparison-table-wrap"); if(anchor) anchor.insertAdjacentHTML("beforebegin",compareHtml(rows)); lastCompareKey=key; } catch(e){ console.warn("Decision lens comparison unavailable",e); }
}
async function refresh(){ if(running) return; running=true; try{ await Promise.all([renderIndividual(),renderCompare()]); } finally{ running=false; } }
styles();
const observer=new MutationObserver(()=>{ clearTimeout(observer._t); observer._t=setTimeout(refresh,250); });
observer.observe(document.body,{childList:true,subtree:true});
document.addEventListener("DOMContentLoaded",refresh);
window.addEventListener("popstate",()=>{lastIndividualKey="";lastCompareKey="";refresh();});
refresh();
