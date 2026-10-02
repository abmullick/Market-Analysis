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
  return Number.isFinite(n) ? CAP_BANDS.find(b => (b.min == null || n >= b.min) && (b.max == null || n <= b.max)) || null : null;
}
function selectedValues(select) { return [...(select?.selectedOptions || [])].map(o => o.value).filter(Boolean); }
function sectorOptions(old) { return [...old.options].map(o => ({ value: o.value, label: o.textContent })); }

async function loadMetrics() {
  try {
    const r = await fetch('/api/stocks/universe?include_metrics=true', { headers: { Accept: 'application/json' }, cache: 'no-store' });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const data = await r.json();
    metricMap = new Map((data.stocks || []).map(s => [s.symbol, s]));
    decorateRows();
  } catch (e) { console.warn('Unable to load stock liquidity metrics:', e); }
}

async function fetchSectorStocks(sectors) {
  const urlFor = sector => `/api/stocks/universe?include_metrics=true${sector ? `&sector=${encodeURIComponent(sector)}` : ''}`;
  if (!sectors.length) {
    const r = await fetch(urlFor(''), { headers: { Accept: 'application/json' }, cache: 'no-store' });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return (await r.json()).stocks || [];
  }
  const responses = await Promise.all(sectors.map(async sector => {
    const r = await fetch(urlFor(sector), { headers: { Accept: 'application/json' }, cache: 'no-store' });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return (await r.json()).stocks || [];
  }));
  const map = new Map(); responses.flat().forEach(s => map.set(s.symbol, s)); return [...map.values()];
}

function liquidityForSymbol(symbol) { return metricMap.get(symbol)?.liquidity_status || null; }
function liquidityLabel(key) { return LIQUIDITY_BANDS.find(x => x.key === key)?.label || ''; }
function tradedValueText(s) {
  const v = Number(s?.avg_daily_traded_value_3m_cr);
  return Number.isFinite(v) ? `₹${v.toLocaleString('en-IN',{maximumFractionDigits:1})} Cr/day` : 'Trading value unavailable';
}

function stockRowHtml(s) {
  const cap = capFor(s.market_cap_cr), liq = s.liquidity_status;
  const esc = v => String(v ?? '').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
  return `<div class="stock-picker-row" data-symbol="${esc(s.symbol)}" data-market-cap-cr="${s.market_cap_cr ?? ''}">
    <div><strong>${esc(s.name)}</strong>${cap ? `<span class="stock-cap-badge ${cap.key}">${cap.label}</span>` : ''}<small>${esc(s.symbol)}</small></div>
    <div class="stock-picker-metrics">
      <span>Market Cap <b>${s.market_cap_cr == null ? '—' : `₹${Number(s.market_cap_cr).toLocaleString('en-IN',{maximumFractionDigits:0})} Cr`}</b></span>
      <span>P/E <b>${s.pe == null ? '—' : `${Number(s.pe).toFixed(2)}x`}</b></span>
      <span>P/B <b>${s.pb == null ? '—' : `${Number(s.pb).toFixed(2)}x`}</b></span>
      <span>ROE <b>${s.roe == null ? '—' : `${Number(s.roe).toFixed(2)}%`}</b></span>
      <span>ROA <b>${s.roa == null ? '—' : `${Number(s.roa).toFixed(2)}%`}</b></span>
      <span>PEG <b>${s.peg == null ? '—' : `${Number(s.peg).toFixed(2)}x`}</b></span>
      ${liq ? `<span class="stock-liquidity-badge ${liq}" title="3M average daily traded value: ${esc(tradedValueText(s))}"><span class="liquidity-dot ${liq}"></span>${liquidityLabel(liq)}</span>` : ''}
    </div>
    <button class="stock-select-btn" type="button">Select</button>
  </div>`;
}

async function renderMultiSectorResults(sectors) {
  const list = document.querySelector('.stock-picker-list'), summary = document.querySelector('.stock-result-summary');
  if (!list) return;
  list.innerHTML = '<div class="stock-loading">Loading selected sectors…</div>';
  try {
    let stocks = await fetchSectorStocks(sectors);
    const q = document.getElementById('stock-filter-search')?.value.trim().toLowerCase() || '';
    if (q) stocks = stocks.filter(s => String(s.symbol||'').toLowerCase().includes(q) || String(s.name||'').toLowerCase().includes(q));
    list.innerHTML = stocks.map(stockRowHtml).join('') || '<div class="stock-no-data">No stocks match these sectors.</div>';
    if (summary) summary.textContent = `${stocks.length} stocks match the selected sectors.`;
    installLocalRowSelection(list); decorateRows();
  } catch (e) { list.innerHTML = `<div class="stock-error"><p>Unable to load selected sectors: ${String(e.message || e)}</p></div>`; }
}

function installLocalRowSelection(list) {
  list.querySelectorAll('.stock-select-btn').forEach(btn => btn.addEventListener('click', () => {
    const symbol = btn.closest('.stock-picker-row')?.dataset.symbol;
    if (symbol) window.location.href = `/stocks.html?symbol=${encodeURIComponent(symbol)}`;
  }));
}

function installSectorMultiselect() {
  const old = document.getElementById('stock-sector');
  if (!old || old.dataset.enhanced === 'true') return;
  old.dataset.enhanced = 'true'; old.multiple = true;
  const wrap = document.createElement('div'); wrap.className = 'stock-multiselect-wrap'; old.parentNode.insertBefore(wrap, old); wrap.appendChild(old);
  const summary = document.createElement('button'); summary.type='button'; summary.className='stock-multiselect-trigger'; summary.innerHTML='<span>All sectors</span><b>▾</b>';
  const menu = document.createElement('div'); menu.className='stock-multiselect-menu'; menu.hidden=true; wrap.append(summary,menu); old.style.display='none';
  const rebuild = () => { menu.innerHTML=sectorOptions(old).map(o=>`<label><input type="checkbox" data-value="${o.value.replaceAll('"','&quot;')}" ${o.value&&o.selected?'checked':''}><span>${o.label}</span></label>`).join(''); const vals=selectedValues(old); summary.querySelector('span').textContent=vals.length?`${vals.length} sector${vals.length>1?'s':''} selected`:'All sectors'; };
  summary.addEventListener('click',()=>{menu.hidden=!menu.hidden;});
  menu.addEventListener('change',async e=>{const input=e.target;if(!input.matches('input'))return;const option=[...old.options].find(o=>o.value===input.dataset.value);if(option)option.selected=input.checked;rebuild();await renderMultiSectorResults(selectedValues(old));});
  rebuild();
}

function installLiquidityAndCapFilters() {
  const filterTop=document.querySelector('.stock-filter-top');
  if(!filterTop||document.getElementById('stock-liquidity-filter'))return;
  const block=document.createElement('div'); block.className='stock-universe-extra-filters';
  block.innerHTML=`<div class="stock-chip-filter" id="stock-cap-filter"><span class="stock-chip-filter-label">Market Cap</span>${CAP_BANDS.map(b=>`<label><input type="checkbox" value="${b.key}"><span>${b.label}</span></label>`).join('')}</div><div class="stock-chip-filter" id="stock-liquidity-filter"><span class="stock-chip-filter-label">Liquidity</span>${LIQUIDITY_BANDS.map(b=>`<label><input type="checkbox" value="${b.key}"><span class="liquidity-choice"><span class="liquidity-dot ${b.key}"></span>${b.label}</span></label>`).join('')}</div>`;
  filterTop.appendChild(block);
  block.addEventListener('change',()=>{
    const caps=[...document.querySelectorAll('#stock-cap-filter input:checked')].map(x=>x.value), liqs=[...document.querySelectorAll('#stock-liquidity-filter input:checked')].map(x=>x.value), rows=[...document.querySelectorAll('.stock-picker-row')];
    rows.forEach(row=>{const cap=capFor(Number(row.dataset.marketCapCr))?.key, liq=liquidityForSymbol(row.dataset.symbol);row.hidden=(caps.length&&!caps.includes(cap))||(liqs.length&&!liqs.includes(liq));});
    const visible=rows.filter(r=>!r.hidden).length, summary=document.querySelector('.stock-result-summary');
    if(summary&&(caps.length||liqs.length))summary.textContent=`${visible} stocks match the current filters.`;
  });
}

function decorateRows() {
  document.querySelectorAll('.stock-picker-row').forEach(row=>{
    const symbol=row.dataset.symbol, data=metricMap.get(symbol); if(!data)return;
    const cap=capFor(Number(data.market_cap_cr)), liq=data.liquidity_status, name=row.querySelector('strong'), metrics=row.querySelector('.stock-picker-metrics');
    row.dataset.marketCapCr=data.market_cap_cr ?? '';
    if(name&&cap&&!name.parentElement.querySelector('.stock-cap-badge')){const b=document.createElement('span');b.className=`stock-cap-badge ${cap.key}`;b.textContent=cap.label;name.after(b);}
    if(metrics&&liq&&!metrics.querySelector('.stock-liquidity-badge')){const b=document.createElement('span');b.className=`stock-liquidity-badge ${liq}`;b.title=`3M average daily traded value: ${tradedValueText(data)}`;b.innerHTML=`<span class="liquidity-dot ${liq}"></span>${liquidityLabel(liq)}`;metrics.appendChild(b);}
    row.dataset.universeEnhanced='true';
  });
}

function run(){installSectorMultiselect();installLiquidityAndCapFilters();decorateRows();}
const observer=new MutationObserver(run); observer.observe(document.body,{childList:true,subtree:true}); run(); loadMetrics();
