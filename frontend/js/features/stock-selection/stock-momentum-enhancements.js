const num = (v) => Number.isFinite(Number(v)) ? Number(v) : null;
const clamp = (v) => Math.max(0, Math.min(100, v));
const avg = (a) => a.length ? a.reduce((s, v) => s + v, 0) / a.length : null;
const vals = (series) => (Array.isArray(series) ? series : []).filter(x => x && num(x.value) != null).map(x => ({ year: String(x.year), value: Number(x.value) }));
const esc = (v) => String(v ?? '').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'",'&#039;');

function score(delta, scale) { return delta == null ? null : clamp(50 + delta / scale * 50); }
function rollingDelta(series, year, window = 3) {
  const a = vals(series).filter(x => x.year <= year);
  if (a.length < window * 2) return null;
  return avg(a.slice(-window).map(x => x.value)) - avg(a.slice(-window * 2, -window).map(x => x.value));
}
function historicalConsistency(t, year) {
  const positive = ['revenue_growth','profit_growth','fcf_margin'].flatMap(k => vals(t[k]).filter(x => x.year <= year).map(x => x.value > 0 ? 100 : 0));
  const growthPersistence = avg(positive);
  const roe = vals(t.roe).filter(x => x.year <= year).map(x => x.value);
  const mean = avg(roe);
  const volatility = mean == null || !roe.length ? null : Math.sqrt(avg(roe.map(v => (v - mean) ** 2)));
  const stability = volatility == null ? null : clamp(100 - volatility * 10);
  return avg([growthPersistence, stability].filter(v => v != null));
}
function historicalShareDiscipline(data) {
  const shares = num(data?.dilution?.share_count_cagr_5y ?? data?.dilution?.share_count_cagr_3y);
  return shares == null ? null : clamp(80 - Math.max(0, shares * 100 - 1) * 12);
}
function buildTimeline(data, financial) {
  const t = data?.trends || {};
  const years = [...new Set(Object.values(t).flatMap(s => vals(s).map(x => x.year)))].sort();
  const out = [];
  years.forEach(year => {
    const growth = avg(['revenue_growth','profit_growth','eps_growth'].map(k => score(rollingDelta(t[k], year), 8)).filter(v => v != null));
    const returns = avg(['roe','roce'].map(k => score(rollingDelta(t[k], year), 5)).filter(v => v != null));
    const quality = financial
      ? historicalConsistency(t, year)
      : avg([score(rollingDelta(t.cash_conversion, year), 20), score(rollingDelta(t.fcf_margin, year), 5)].filter(v => v != null));
    let discipline = null;
    if (financial) {
      discipline = historicalShareDiscipline(data);
    } else {
      const debt = rollingDelta(t.debt, year), de = rollingDelta(t.debt_equity, year);
      const debtRecent = vals(t.debt).filter(x => x.year <= year).slice(-3).map(x => x.value);
      const deRecent = vals(t.debt_equity).filter(x => x.year <= year).slice(-3).map(x => x.value);
      const debtBase = Math.max(Math.abs(avg(debtRecent) || 1), 1);
      const deBase = Math.max(Math.abs(avg(deRecent) || .25), .25);
      discipline = avg([de == null ? null : clamp(50 - de / deBase * 100), debt == null ? null : clamp(50 - debt / debtBase * 100)].filter(v => v != null));
    }
    const consistency = historicalConsistency(t, year);
    const available = [[growth,.30],[returns,.25],[quality,.20],[discipline,.15],[consistency,.10]].filter(([,v]) => v != null);
    const weight = available.reduce((s,[,w]) => s + w, 0);
    if (!weight) return;
    const momentum = Math.round(available.reduce((s,[v,w]) => s + v * w, 0) / weight);
    out.push({ year, score: momentum, status: status(momentum) });
  });
  return out.slice(-7);
}
function status(score) { return score >= 65 ? 'Strengthening' : score >= 45 ? 'Stable' : 'Weakening'; }
function cls(score) { return score >= 65 ? 'strong' : score >= 45 ? 'stable' : 'weak'; }

function renderTimeline(data, details) {
  const section = details?.querySelector('.stock-fundamental-momentum');
  if (!section || section.querySelector('.stock-momentum-timeline')) return;
  const context = details.querySelector('.stock-hero p')?.textContent || '';
  const financial = /financial services|bank|nbfc|insurance/i.test(context);
  const points = buildTimeline(data, financial);
  if (points.length < 2) return;
  const min = Math.min(...points.map(p => p.score));
  const max = Math.max(...points.map(p => p.score));
  const range = Math.max(max - min, 1);
  const bars = points.map(p => {
    const height = 30 + ((p.score - min) / range) * 52;
    return `<div class="momentum-timeline-point" tabindex="0" title="${esc(p.year)}: ${p.score} — ${esc(status(p.score))}"><div class="momentum-timeline-bar ${cls(p.score)}" style="height:${height}px"><span>${p.score}</span></div><small>${esc(p.year)}</small></div>`;
  }).join('');
  const first = points[0], last = points.at(-1), direction = last.score - first.score;
  const sectionEl = document.createElement('div');
  sectionEl.className = 'stock-momentum-timeline';
  sectionEl.innerHTML = `<div class="momentum-timeline-head"><div><h3>Fundamental Trend Timeline <span class="momentum-timeline-info" tabindex="0" aria-label="How the Fundamental Trend Timeline relates to the Momentum Index">i</span><span class="momentum-timeline-tooltip" role="tooltip">The Momentum Index shown above is the current score, calculated from the latest available 3-year period versus the preceding 3-year period. This timeline does not use stored historical Momentum scores; it reconstructs the same 0–100 scoring framework at earlier historical points using the data available up to each point. The latest timeline point represents the most recent historical calculation, so it should generally be close to the current Momentum Index. It can differ when the current calculation has newer data or when a component has different historical data availability.</span></h3><p>Historical reconstruction of the same Fundamental Momentum framework. Each point compares the latest 3-year trend with the preceding 3-year period available at that point.</p></div><div class="momentum-timeline-direction ${cls(last.score)}"><span>${direction >= 5 ? '↗' : direction <= -5 ? '↘' : '→'}</span>${esc(status(last.score))}</div></div><div class="momentum-timeline-chart">${bars}</div><div class="momentum-timeline-foot"><span>${esc(first.year)} · ${first.score}</span><strong>Latest ${last.score}</strong><span>${esc(last.year)} · ${esc(status(last.score))}</span></div></div>`;
  const observations = section.querySelector('.stock-momentum-observations');
  if (observations) observations.insertAdjacentElement('beforebegin', sectionEl); else section.appendChild(sectionEl);
}

function enhanceIndex() {
  document.querySelectorAll('.stock-momentum-index').forEach(card => {
    if (card.querySelector('.momentum-score-ring')) return;
    const strong = card.querySelector('strong');
    const score = Number(strong?.textContent);
    if (!Number.isFinite(score)) return;
    const ring = document.createElement('span');
    ring.className = 'momentum-score-ring';
    ring.style.setProperty('--momentum-score', `${score * 3.6}deg`);
    ring.innerHTML = `<span>${score}</span>`;
    card.classList.add('momentum-index-enhanced');
    card.insertBefore(ring, card.querySelector('small'));
    if (strong) strong.style.display = 'none';
  });
  document.querySelectorAll('.stock-momentum-index-tooltip').forEach(tip => {
    if (tip.dataset.relationshipAdded) return;
    tip.insertAdjacentHTML('beforeend', ' <br><br><strong>Relationship to the timeline:</strong> this is the current Momentum Index. The timeline below reconstructs earlier historical scores using the same scoring framework, so it shows how the current score has evolved over time.');
    tip.dataset.relationshipAdded = '1';
  });
}

function addStyles() {
  if (document.getElementById('stock-momentum-enhancement-styles')) return;
  const style = document.createElement('style');
  style.id = 'stock-momentum-enhancement-styles';
  style.textContent = `
    .stock-momentum-index.momentum-index-enhanced{min-width:138px;padding:10px 12px 9px;overflow:visible;background:linear-gradient(180deg,#fff,#f8fbff)}
    .stock-momentum-index.momentum-index-enhanced > span:first-child{margin-bottom:5px}
    .momentum-score-ring{width:58px;height:58px;margin:0 auto 4px;border-radius:50%;display:grid;place-items:center;background:conic-gradient(#2563eb var(--momentum-score),#e7eef6 0deg);position:relative;box-shadow:0 3px 10px rgba(37,99,235,.12)}
    .momentum-score-ring::before{content:"";position:absolute;inset:5px;border-radius:50%;background:#fff}
    .momentum-score-ring span{position:relative;z-index:1;color:#102b4e;font-size:20px;font-weight:800;line-height:1}
    .stock-momentum-index.strong .momentum-score-ring{background:conic-gradient(#16a34a var(--momentum-score),#e7eef6 0deg)}
    .stock-momentum-index.stable .momentum-score-ring{background:conic-gradient(#d89b14 var(--momentum-score),#e7eef6 0deg)}
    .stock-momentum-index.weak .momentum-score-ring{background:conic-gradient(#dc4b4b var(--momentum-score),#e7eef6 0deg)}
    .stock-momentum-timeline{margin-top:13px;padding:14px 15px;border:1px solid #dbe6f1;border-radius:12px;background:linear-gradient(135deg,#fbfdff,#f6faff)}
    .momentum-timeline-head{display:flex;align-items:flex-start;justify-content:space-between;gap:15px}.momentum-timeline-head h3{margin:0;color:#17355d;font-size:13px}.momentum-timeline-head p{margin:4px 0 0;color:#7a8aa0;font-size:10px;line-height:1.45;max-width:680px}.momentum-timeline-info{display:inline-flex;align-items:center;justify-content:center;width:14px;height:14px;margin-left:4px;border:1px solid #8aa0bb;border-radius:50%;color:#52708f;font-size:9px;font-weight:800;line-height:1;cursor:help;vertical-align:middle}.momentum-timeline-head h3{position:relative}.momentum-timeline-tooltip{display:none;position:absolute;z-index:110;left:0;top:calc(100% + 9px);width:430px;padding:11px 13px;border:1px solid #cbd8e6;border-radius:9px;background:#10233f;color:#fff;font-size:11px;font-weight:400;line-height:1.5;text-align:left;box-shadow:0 8px 22px rgba(15,39,72,.18);box-sizing:border-box}.momentum-timeline-tooltip::before{content:"";position:absolute;left:78px;top:-5px;width:9px;height:9px;background:#10233f;border-left:1px solid #cbd8e6;border-top:1px solid #cbd8e6;transform:rotate(45deg)}.momentum-timeline-info:hover + .momentum-timeline-tooltip,.momentum-timeline-info:focus + .momentum-timeline-tooltip{display:block}
    .momentum-timeline-direction{padding:6px 9px;border-radius:999px;font-size:9px;font-weight:800;white-space:nowrap;background:#eef4fb;color:#49627e}.momentum-timeline-direction.strong{background:#ecfdf3;color:#15803d}.momentum-timeline-direction.stable{background:#fff8e7;color:#9a6700}.momentum-timeline-direction.weak{background:#fff1f2;color:#c0392b}.momentum-timeline-direction span{font-size:13px;margin-right:4px}
    .momentum-timeline-chart{height:104px;display:flex;align-items:flex-end;gap:12px;margin-top:13px;padding:0 8px;border-bottom:1px solid #dbe4ee}.momentum-timeline-point{height:100%;flex:1;min-width:35px;display:flex;flex-direction:column;justify-content:flex-end;align-items:center;gap:5px}.momentum-timeline-bar{min-height:30px;width:24px;border-radius:7px 7px 2px 2px;background:linear-gradient(180deg,#3b82f6,#2563eb);position:relative;box-shadow:0 3px 8px rgba(37,99,235,.12);transition:transform .15s ease}.momentum-timeline-bar:hover{transform:translateY(-3px)}.momentum-timeline-bar.strong{background:linear-gradient(180deg,#22c55e,#16a34a)}.momentum-timeline-bar.stable{background:linear-gradient(180deg,#f2b84b,#d89b14)}.momentum-timeline-bar.weak{background:linear-gradient(180deg,#ef6a6a,#dc4b4b)}.momentum-timeline-bar span{position:absolute;top:-16px;left:50%;transform:translateX(-50%);font-size:8px;font-weight:800;color:#48617d}.momentum-timeline-point small{font-size:8px;color:#71849a}.momentum-timeline-foot{display:flex;justify-content:space-between;gap:8px;margin-top:7px;color:#8492a2;font-size:9px}.momentum-timeline-foot strong{color:#17355d}
    @media(max-width:700px){.momentum-timeline-head{flex-direction:column}.momentum-timeline-tooltip{width:290px}.momentum-timeline-chart{gap:7px}.momentum-timeline-bar{width:20px}.momentum-timeline-foot{font-size:8px}}
  `;
  document.head.appendChild(style);
}

function init() {
  addStyles();
  enhanceIndex();
  const details = document.getElementById('stock-details');
  if (!details) return;
  const originalFetch = window.fetch.bind(window);
  window.fetch = async (...args) => {
    const response = await originalFetch(...args);
    const url = String(args[0]?.url || args[0] || '');
    if (url.includes('/api/stocks/pedigree/') && !url.includes('/compare?')) {
      response.clone().json().then(data => { renderTimeline(data, details); enhanceIndex(); }).catch(() => {});
    }
    return response;
  };
  const observer = new MutationObserver(() => { enhanceIndex(); });
  observer.observe(details, { childList:true, subtree:true });
}

if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, { once:true }); else init();
