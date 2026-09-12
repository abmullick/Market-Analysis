// Portfolio Builder — Allocation UI & state
// Reads the selected funds persisted by /portfolio-select-funds.html from
// sessionStorage (same key), assigns default allocations, lets the user edit
// each percentage, validates the total reaches exactly 100%, and persists the
// allocation back alongside the selected funds (client-side only).
//
// Storage convention
// ------------------
//   sessionStorage["portfolio_builder_selected_funds"] = [
//     { scheme_code, scheme_name, amc?, category?, allocation? }, ...
//   ]
//   - "allocation" is a number in [0, 100] rounded to 2 decimal places, or null
//     when the fund has never been allocated (a default is assigned on load).
//   - No backend, no new storage keys, no caching introduced here.

const STORAGE_KEY = 'portfolio_builder_selected_funds';
const PRECISION = 2; // percentages support up to 2 decimal places
const EPS = 1e-4;    // tolerance for "exactly 100%"

const state = {
    funds: [],       // normalized list of { scheme_code, scheme_name, amc, category, allocation, invalid }
    initialized: false,
};

function round2(n) {
    return Math.round((n + Number.EPSILON) * 100) / 100;
}

function formatPct(n) {
    const r = round2(n);
    return (Number.isInteger(r) ? r.toFixed(0) : r.toFixed(PRECISION)) + '%';
}

function escapeHtml(s) {
    if (s == null) return '';
    return String(s)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

function escapeAttr(s) {
    if (s == null) return '';
    return String(s)
        .replace(/&/g, '&amp;')
        .replace(/"/g, '&quot;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
}

function $(id) { return document.getElementById(id); }

// Parse a user-entered percentage.
// Returns { valid, value } where value is a rounded 0..100 number.
// Empty, non-numeric and negative inputs are treated as invalid.
function parseAllocation(raw) {
    if (raw == null) return { valid: false, value: 0 };
    const s = String(raw).trim();
    if (s === '' || s === '-' || s === '.') return { valid: false, value: 0 };
    const num = Number(s);
    if (!Number.isFinite(num)) return { valid: false, value: 0 };
    if (num < 0) return { valid: false, value: 0 };
    return { valid: true, value: round2(Math.min(100, num)) };
}

function loadFunds() {
    const list = [];
    try {
        const raw = sessionStorage.getItem(STORAGE_KEY);
        if (!raw) return list;
        const arr = JSON.parse(raw);
        if (!Array.isArray(arr)) return list;
        for (let i = 0; i < arr.length; i++) {
            const f = arr[i];
            if (!f || typeof f.scheme_code !== 'string') continue;
            const hasAlloc = typeof f.allocation === 'number' && Number.isFinite(f.allocation);
            list.push({
                scheme_code: f.scheme_code,
                scheme_name: f.scheme_name || f.scheme_code,
                amc: f.amc || null,
                category: f.category || null,
                allocation: hasAlloc ? round2(Math.max(0, Math.min(100, f.allocation))) : null,
                invalid: false,
            });
        }
    } catch (e) {
        console.warn('Failed to load selected funds:', e);
    }
    return list;
}

// Assign default allocations to any fund without a stored allocation.
// Existing (stored) allocations are preserved; the unallocated remainder is
// split equally among the funds that need a default, with the rounding residual
// applied to the last of them so a fresh portfolio always sums to 100%.
function reconcileDefaults(list) {
    const needDefault = list.filter((f) => f.allocation == null);
    if (!needDefault.length) return list;

    let used = 0;
    list.forEach((f) => { if (f.allocation != null) used += f.allocation; });
    const remaining = Math.max(0, 100 - used);
    const per = round2(remaining / needDefault.length);

    needDefault.forEach((f) => { f.allocation = per; });

    let total = round2(used);
    needDefault.forEach((f) => { total = round2(total + f.allocation); });
    const diff = round2(100 - total);
    if (diff !== 0) {
        const last = needDefault[needDefault.length - 1];
        last.allocation = round2(last.allocation + diff);
    }
    return list;
}

function saveFunds() {
    try {
        const items = state.funds.map((f) => ({
            scheme_code: f.scheme_code,
            scheme_name: f.scheme_name,
            amc: f.amc || null,
            category: f.category || null,
            allocation: f.allocation,
        }));
        sessionStorage.setItem(STORAGE_KEY, JSON.stringify(items));
    } catch (e) {
        console.warn('Failed to save allocations:', e);
    }
}

function attachInputHandlers(listEl) {
    const inputs = listEl.querySelectorAll('.pb-alloc-input');
    for (let i = 0; i < inputs.length; i++) {
        const input = inputs[i];
        input.addEventListener('input', function () {
            const code = input.getAttribute('data-code');
            const fund = state.funds.find((f) => f.scheme_code === code);
            if (!fund) return;

            const parsed = parseAllocation(input.value);
            if (parsed.valid) {
                fund.allocation = parsed.value;
                fund.invalid = false;
                saveFunds();
            } else {
                // Flag the field visually and exclude it from the total until
                // the user enters a valid percentage.
                fund.allocation = null;
                fund.invalid = true;
            }
            updateTotal();
        });
    }
}

function renderList() {
    const listEl = $('pb-fund-list');
    if (!listEl) return;

    let html = '';
    for (let i = 0; i < state.funds.length; i++) {
        const f = state.funds[i];
        let metaHtml;
        if (f.amc || f.category) {
            const parts = [];
            if (f.category) parts.push('<span>' + escapeHtml(f.category) + '</span>');
            if (f.amc) parts.push('<span>' + escapeHtml(f.amc) + '</span>');
            parts.push('<span class="pb-fund-meta-scheme">' + escapeHtml(f.scheme_code) + '</span>');
            metaHtml = '<div class="pb-fund-meta">' + parts.join('') + '</div>';
        } else {
            metaHtml = '<div class="pb-fund-meta"><span class="pb-fund-meta-scheme">' + escapeHtml(f.scheme_code) + '</span></div>';
        }

        const disp = f.allocation == null ? '' : f.allocation;
        html += '<li class="pb-fund-item" data-code="' + escapeAttr(f.scheme_code) + '">' +
            '<div class="pb-fund-info">' +
            '<div class="pb-fund-name" title="' + escapeAttr(f.scheme_name) + '">' + escapeHtml(f.scheme_name) + '</div>' +
            metaHtml +
            '</div>' +
            '<div class="pb-alloc-control">' +
            '<div class="pb-input-wrap">' +
            '<input type="number" class="pb-alloc-input" min="0" max="100" step="0.01" inputmode="decimal" ' +
            'data-code="' + escapeAttr(f.scheme_code) + '" value="' + disp + '" ' +
            'aria-label="Allocation for ' + escapeAttr(f.scheme_name) + '">' +
            '<span class="pb-alloc-suffix">%</span>' +
            '</div>' +
            '</div>' +
            '</li>';
    }
    listEl.innerHTML = html;
    attachInputHandlers(listEl);
}
function updateTotal() {
    const valueEl = $('pb-total-value');
    const statusEl = $('pb-total-status');
    const continueBtn = $('pb-continue-btn');
    const listEl = $('pb-fund-list');

    let total = 0;
    let anyInvalid = false;
    for (let i = 0; i < state.funds.length; i++) {
        const f = state.funds[i];
        if (f.invalid) {
            anyInvalid = true;
        } else if (typeof f.allocation === 'number') {
            total = round2(total + f.allocation);
        }
    }

    if (valueEl) valueEl.textContent = formatPct(total);

    let statusText = '';
    let statusClass = 'pb-total-status';
    if (anyInvalid) {
        statusText = 'Enter valid percentages from 0 to 100 (max 2 decimals).';
        statusClass += ' pb-status-error';
    } else if (Math.abs(total - 100) < EPS) {
        statusText = 'Allocated — ready to continue.';
        statusClass += ' pb-status-success';
    } else if (total > 100) {
        statusText = 'Over-allocated by ' + formatPct(total - 100) + '.';
        statusClass += ' pb-status-error';
    } else {
        statusText = formatPct(100 - total) + ' remaining to reach 100%.';
        statusClass += ' pb-status-warn';
    }
    if (statusEl) {
        statusEl.textContent = statusText;
        statusEl.className = statusClass;
    }

    // Reflect per-field invalid state on the inputs.
    if (listEl) {
        const inputs = listEl.querySelectorAll('.pb-alloc-input');
        for (let i = 0; i < inputs.length; i++) {
            const input = inputs[i];
            const code = input.getAttribute('data-code');
            const fund = state.funds.find((f2) => f2.scheme_code === code);
            if (fund && fund.invalid) {
                input.classList.add('pb-input-invalid');
            } else {
                input.classList.remove('pb-input-invalid');
            }
        }
    }

    // Continue is enabled only when every field is valid and total = exactly 100%.
    const canContinue = !anyInvalid && Math.abs(total - 100) < EPS && state.funds.length > 0;
    if (continueBtn) continueBtn.disabled = !canContinue;

    // Hide the next-stage note whenever the state is no longer "locked at 100%".
    const nextStage = $('pb-next-stage');
    if (nextStage) nextStage.hidden = true;
}

async function runPortfolioAnalysis() {
    if (analyzing) return;

    const funds = state.funds
        .filter((f) => !f.invalid && typeof f.allocation === 'number')
        .map((f) => ({ scheme_code: f.scheme_code, allocation: f.allocation }));
    if (funds.length < 2) {
        setAnalysisView('error');
        const errEl = $('pb-analysis-error');
        if (errEl) errEl.textContent = 'Select at least two funds to analyze a portfolio.';
        return;
    }

    const btn = $('pb-continue-btn');
    setAnalysisBusy(true);
    if (btn) btn.textContent = 'Analyzing\u2026';
    setAnalysisView('loading');

    try {
        const response = await fetch(getApiBase() + '/portfolio/mutual-fund-analysis', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ funds: funds }),
        });
        const data = await response.json().catch(() => null);

        if (!response.ok) {
            // Backend validation/calculation errors arrive as HTTPException
            // detail: {"detail": {"code", "message"}} (or {"detail": "msg"}).
            const d = data && data.detail;
            const message = (d && d.message) || (typeof d === 'string' ? d : null)
                || (data && data.message) || null;
            showAnalysisError(message
                || 'The portfolio could not be analyzed. Please check your allocations and try again.');
            return;
        }
        renderAnalysis(data);
    } catch (e) {
        console.warn('Portfolio analysis request failed:', e);
        showAnalysisError('Could not reach the server. Please try again.');
    } finally {
        setAnalysisBusy(false);
    }
}

function showAnalysisError(message) {
    setAnalysisView('error');
    const errEl = $('pb-analysis-error');
    if (errEl) errEl.textContent = message;
}

function renderAnalysis(result) {
    const metrics = result && result.metrics ? result.metrics : null;
    const series = result && Array.isArray(result.series) ? result.series : null;
    if (!metrics || !series || series.length < 2) {
        showAnalysisError('The analysis returned no usable data for this portfolio.');
        return;
    }

    // Period / common-history info.
    const periodEl = $('pb-analysis-period');
    if (periodEl) {
        const parts = [];
        if (metrics.start_date) parts.push(metrics.start_date);
        if (metrics.end_date) parts.push(metrics.end_date);
        let text = parts.length ? parts.join(' \u2013 ') : '';
        if (metrics.observations) text += (text ? ' \u00b7 ' : '') + metrics.observations + ' observations';
        if (metrics.years != null && Number.isFinite(metrics.years)) {
            text += (text ? ' \u00b7 ' : '') + metrics.years.toFixed(2) + ' years';
        }
        periodEl.textContent = text;
        periodEl.classList.toggle('hidden', !text);
    }

    // Limited-history notice — severity from the analysis period's common-history
    // length (years). < 1 year: prominent; 1–3 years: informational; >= 3: none.
    const histEl = $('pb-history-warning');
    if (histEl) {
        const years = metrics.years != null && Number.isFinite(metrics.years) ? metrics.years : null;
        let histText = '';
        let histClass = 'pb-history-warning';
        if (years != null && years < 1) {
            histText = 'Limited history: This portfolio has less than 1 year of common history. Long-term performance and risk metrics may not be reliable.';
            histClass += ' pb-history-severe';
        } else if (years != null && years < 3) {
            histText = 'Limited history: Portfolio metrics are based on less than 3 years of common history.';
            histClass += ' pb-history-info';
        } else {
            histClass += ' hidden';
        }
        histEl.textContent = histText;
        histEl.className = histClass;
    }

    // Backend warnings (e.g. zero-weight funds).
    const warnEl = $('pb-analysis-warnings');
    if (warnEl) {
        const warnings = Array.isArray(result.warnings) ? result.warnings.filter(Boolean) : [];
        warnEl.textContent = warnings.join(' ');
        warnEl.classList.toggle('hidden', !warnings.length);
    }

    // Health Score (Phase 3B.2) — collapsible component breakdown.
    renderHealthScore(result && result.health_score ? result.health_score : null);

    const grid = $('pb-metric-grid');
    if (grid) grid.innerHTML = buildMetricCards(metrics);

    const bd = result && result.benchmark_data ? result.benchmark_data : null;

    setAnalysisView('results');
    renderGrowthChart(series, bd);
    renderBenchmarkComparison(bd);
    renderRollingPerformance(result);
    renderDrawdownRecovery(result);
    renderReturnContribution(result);
}

function renderGrowthChart(series, bd) {
    if (typeof Chart === 'undefined') return;
    const canvas = $('pb-growth-chart');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (growthChart) {
        growthChart.destroy();
        growthChart = null;
    }

    const useB = bd && bd.available && Array.isArray(bd.dates)
        && bd.dates.length > 1 && Array.isArray(bd.portfolio);
    const niftyOk = useB && bd.nifty50_tri_available && Array.isArray(bd.nifty50_tri);
    const spOk = useB && bd.sp500_available && Array.isArray(bd.sp500_total_return_inr);
    const labels = useB ? bd.dates : series.map((p) => p.date);

    const mk = (label, data, color) => ({
        label: label,
        data: data,
        borderColor: color,
        borderWidth: 1.75,
        fill: false,
        tension: 0,
        pointRadius: 0,
        pointHoverRadius: 5,
        pointHoverBackgroundColor: color,
        pointHoverBorderColor: '#ffffff',
        pointHoverBorderWidth: 2,
    });

    const datasets = [];
    datasets.push(mk('Portfolio', useB ? bd.portfolio : series.map((p) => p.value), BENCHMARK_COLORS.portfolio));
    if (niftyOk) datasets.push(mk('NIFTY 50 TRI', bd.nifty50_tri, BENCHMARK_COLORS.nifty));
    if (spOk) datasets.push(mk('S&P 500 Total Return', bd.sp500_total_return_inr, BENCHMARK_COLORS.sp500));

    const fmt = (v) => v.toFixed(2);
    const signed = (v) => (v >= 0 ? '+' : '\u2212') + Math.abs(v).toFixed(2) + '%';

    growthChart = new Chart(ctx, {
        type: 'line',
        data: { labels: labels, datasets: datasets },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { intersect: false, mode: 'index' },
            plugins: {
                legend: {
                    display: true,
                    position: 'top',
                    labels: { boxWidth: 12, boxHeight: 12, usePointStyle: true, font: { size: 11 }, color: '#64748b' },
                },
                tooltip: {
                    backgroundColor: 'rgba(15, 23, 42, 0.95)',
                    padding: 10,
                    titleFont: { size: 12, weight: '600' },
                    bodyFont: { size: 12 },
                    displayColors: true,
                    callbacks: {
                        title: (items) => (items && items[0] && items[0].label ? items[0].label : ''),
                        label: (c) => (c.dataset.label || 'Series') + ': ' + fmt(Number(c.parsed.y)),
                        afterBody: (items) => {
                            if (!bd || !useB) return null;
                            const i = items && items.length ? items[0].index : -1;
                            const out = [];
                            const pf = bd.portfolio && bd.portfolio[i];
                            const ny = bd.nifty50_tri && bd.nifty50_tri[i];
                            const sp = bd.sp500_total_return_inr && bd.sp500_total_return_inr[i];
                            if (typeof pf === 'number' && typeof ny === 'number') {
                                out.push('Portfolio vs NIFTY 50: ' + signed(pf - ny));
                            }
                            if (typeof pf === 'number' && typeof sp === 'number') {
                                out.push('Portfolio vs S&P 500: ' + signed(pf - sp));
                            }
                            return out.length ? out : null;
                        },
                    },
                },
            },
            scales: {
                x: { title: { display: true, text: 'Date', font: { size: 11, weight: '500' }, color: '#64748b' }, ticks: { maxTicksLimit: 8, color: '#64748b', font: { size: 11 } }, grid: { color: 'rgba(15, 23, 42, 0.04)' } },
                y: { title: { display: true, text: 'Growth (base 100)', font: { size: 11, weight: '500' }, color: '#64748b' }, ticks: { color: '#64748b', font: { size: 11 } }, grid: { color: 'rgba(15, 23, 42, 0.06)' }, grace: '5%' },
            },
        },
    });
}

// Distinguishable, light/dark-safe line colors for the three comparison series.
const BENCHMARK_COLORS = {
    portfolio: '#2563eb', // blue-600
    nifty: '#f59e0b',     // amber-500
    sp500: '#16a34a',     // green-600
};

// Percentage-point formatter for benchmark OUTPERFORMANCE only.
// Backend outperformance is a fraction of annual rates (e.g. 0.015656 =
// portfolio CAGR 0.13394 − benchmark CAGR 0.11829); display it as
// "+1.57 pp". Zero renders unsigned ("0.00 pp"). Used solely by the
// benchmark comparison blocks — generic % formatters elsewhere are untouched.
function formatSignedPp(v) {
    if (v == null || !Number.isFinite(v)) return 'N/A';
    const pp = v * 100;
    if (pp === 0) return '0.00 pp';
    return (pp > 0 ? '+' : '-') + Math.abs(pp).toFixed(2) + ' pp';
}

// Fraction (e.g. 0.1363) -> "13.63%".
function formatMetricPctFrac(v) {
    if (v == null || !Number.isFinite(v)) return 'N/A';
    return (v * 100).toFixed(2) + '%';
}

// ---------------------------------------------------------------------------
// Portfolio vs Benchmark comparison (Phase 2E)
// Compact section directly under the growth chart.
// ---------------------------------------------------------------------------

function renderBenchmarkComparison(bd) {
    const el = $('pb-benchmark-comparison');
    if (!el) return;
    const ok = bd && bd.available;
    const niftyOk = ok && bd.nifty50_tri_available;
    const spOk = ok && bd.sp500_available;
    if (!ok) {
        el.classList.add('hidden');
        return;
    }

    const parts = [];
    parts.push('<div class="pb-benchmark-section-title">Benchmark Comparison</div>');
    if (bd.common_start && bd.common_end) {
        parts.push('<div class="pb-benchmark-period">' + bd.common_start + ' \u2013 ' + bd.common_end
            + ' \u00b7 ' + bd.observations + ' common observations</div>');
    }

    if (niftyOk) {
        parts.push(benchmarkBlock('Portfolio vs NIFTY 50', 'NIFTY 50 TRI CAGR',
            bd.portfolio_cagr, bd.nifty50_tri_cagr, bd.nifty50_outperformance));
    }

    // The S&P block is ALWAYS rendered when the comparison is available:
    // real values when S&P data exists, a clean unavailable state otherwise
    // (never silently removed, never fake/zero values, never raw provider,
    // HTTP or retry details).
    const spWarnings = (Array.isArray(bd.warnings) ? bd.warnings : [])
        .filter((w) => typeof w === 'string' && /S&P 500/i.test(w));
    if (spOk) {
        parts.push(benchmarkBlock('Portfolio vs S&P 500', 'S&P 500 Total Return CAGR',
            bd.portfolio_cagr, bd.sp500_total_return_cagr, bd.sp500_outperformance));
    } else {
        parts.push(spUnavailableBlock(spWarnings[0]));
    }

    // Show remaining (non-S&P) warnings once; the S&P explanation, when
    // displayed inside its block, is not repeated here.
    const otherWarnings = (Array.isArray(bd.warnings) ? bd.warnings : [])
        .filter((w) => typeof w === 'string' && w !== spWarnings[0]);
    if (otherWarnings.length) {
        parts.push('<div class="pb-benchmark-note">' + escapeHtml(otherWarnings.join(' ')) + '</div>');
    }

    el.innerHTML = parts.join('');
    el.classList.remove('hidden');
}

// Compact, user-facing S&P 500 unavailable state. Uses the backend's already-
// sanitized explanation when present; falls back to a neutral sentence. No
// HTTP status, attempt counter, endpoint name or exception text is shown.
function spUnavailableBlock(sanitizedReason) {
    const msg = sanitizedReason || 'S&P 500 Total Return temporarily unavailable.';
    return ''
        + '<div class="pb-benchmark-block pb-benchmark-unavailable">'
        + '<div class="pb-benchmark-title">' + escapeHtml('Portfolio vs S&P 500') + '</div>'
        + '<div class="pb-benchmark-note">' + escapeHtml(msg) + '</div>'
        + '</div>';
}

function benchmarkBlock(title, benchCagrLabel, portfolioCagr, benchmarkCagr, outperformance) {
    const outCls = (outperformance != null && outperformance < 0)
        ? 'pb-benchmark-negative' : 'pb-benchmark-positive';
    return ''
        + '<div class="pb-benchmark-block">'
        + '<div class="pb-benchmark-title">' + escapeHtml(title) + '</div>'
        + '<div class="pb-benchmark-grid">'
        + '<div class="pb-benchmark-item"><span class="pb-benchmark-item-label">Portfolio CAGR</span>'
        + '<span class="pb-benchmark-item-value">' + formatMetricPctFrac(portfolioCagr) + '</span></div>'
        + '<div class="pb-benchmark-item"><span class="pb-benchmark-item-label">' + escapeHtml(benchCagrLabel) + '</span>'
        + '<span class="pb-benchmark-item-value">' + formatMetricPctFrac(benchmarkCagr) + '</span></div>'
        + '<div class="pb-benchmark-item ' + outCls + '"><span class="pb-benchmark-item-label">Outperformance</span>'
        + '<span class="pb-benchmark-item-value">' + formatSignedPp(outperformance) + '</span></div>'
        + '</div>'
        + '</div>';
}
// ---------------------------------------------------------------------------
// Return Contribution (additive performance attribution)
// Renders the backend-computed per-fund contributions to the portfolio's
// total return. No calculations are duplicated in JavaScript: the backend
// derives contributions inside the existing daily-return pipeline and they
// reconcile to the portfolio's total return (see Help & Methodology).
// ---------------------------------------------------------------------------

// Signed percent for a fraction: 0.214 -> "+21.40%", -0.085 -> "\u22128.50%".
function formatSignedPercent(v) {
    if (v == null || !Number.isFinite(v)) return 'N/A';
    const pct = v * 100;
    if (pct === 0) return '0.00%';
    return (pct > 0 ? '+' : '\u2212') + Math.abs(pct).toFixed(2) + '%';
}

function renderReturnContribution(result) {
    const el = $('pb-return-contribution');
    if (!el) return;
    const rc = result && result.return_contribution;
    const items = rc && Array.isArray(rc.contributions) ? rc.contributions : [];
    if (!items.length) {
        el.classList.add('hidden');
        el.innerHTML = '';
        return;
    }

    // Backend sorts by contribution descending (largest positive first,
    // negative contributors last); render in that order.
    const maxAbs = Math.max.apply(null, items.map(function (i) { return Math.abs(i.contribution); })) || 1;
    const top = items[0];
    const bottom = items[items.length - 1];

    const parts = [];
    parts.push('<div class="pb-rc-title">Return Contribution</div>');
    parts.push('<div class="pb-rc-subtitle">See how each fund contributed to the portfolio\'s overall return.</div>');

    // Deterministic summary chips (no AI commentary). "Largest Drag" only
    // when a fund actually detracted from performance.
    const chips = [];
    if (top && top.contribution > 0) {
        chips.push('<div class="pb-rc-chip"><span class="pb-rc-chip-label">Top Contributor</span>'
            + '<span class="pb-rc-chip-value pb-rc-pos">' + escapeHtml(top.scheme_name || top.scheme_code)
            + ' \u00b7 ' + formatSignedPp(top.contribution) + '</span></div>');
    }
    if (bottom && bottom.contribution < 0) {
        chips.push('<div class="pb-rc-chip"><span class="pb-rc-chip-label">Largest Drag</span>'
            + '<span class="pb-rc-chip-value pb-rc-neg">' + escapeHtml(bottom.scheme_name || bottom.scheme_code)
            + ' \u00b7 ' + formatSignedPp(bottom.contribution) + '</span></div>');
    }
    if (chips.length) parts.push('<div class="pb-rc-summary">' + chips.join('') + '</div>');

    // Compact horizontal bars, proportional to |contribution|; positive and
    // negative are visually distinguishable via the app's semantic colors.
    const bars = items.map(function (it) {
        const cls = it.contribution >= 0 ? 'pb-rc-pos' : 'pb-rc-neg';
        const width = Math.max((Math.abs(it.contribution) / maxAbs) * 100, 1.5);
        const name = it.scheme_name || it.scheme_code;
        return ''
            + '<div class="pb-rc-row">'
            + '<div class="pb-rc-label" title="' + escapeAttr(name) + '">'
            + '<span class="pb-rc-name">' + escapeHtml(name) + '</span>'
            + (it.scheme_name ? '<span class="pb-rc-code">' + escapeHtml(it.scheme_code) + '</span>' : '')
            + '</div>'
            + '<div class="pb-rc-track"><div class="pb-rc-bar ' + cls + '" style="width:' + width.toFixed(2) + '%"></div></div>'
            + '<div class="pb-rc-value ' + cls + '">' + formatSignedPp(it.contribution) + '</div>'
            + '</div>';
    }).join('');
    parts.push('<div class="pb-rc-bars">' + bars + '</div>');

    // Compact table. Fund names are primary; scheme codes stay secondary.
    const rows = items.map(function (it) {
        const cls = it.contribution >= 0 ? 'pb-rc-pos' : 'pb-rc-neg';
        const name = it.scheme_name || it.scheme_code;
        return ''
            + '<tr>'
            + '<td class="pb-rc-fund-cell"><span class="pb-rc-name">' + escapeHtml(name) + '</span>'
            + (it.scheme_name ? '<span class="pb-rc-code">' + escapeHtml(it.scheme_code) + '</span>' : '')
            + '</td>'
            + '<td>' + formatPct(it.allocation) + '</td>'
            + '<td>' + formatSignedPercent(it.fund_return) + '</td>'
            + '<td class="' + cls + '">' + formatSignedPp(it.contribution) + '</td>'
            + '</tr>';
    }).join('');
    parts.push(
        '<table class="pb-rc-table">'
        + '<thead><tr><th>Fund</th><th>Allocation</th><th>Fund Return</th><th>Contribution</th></tr></thead>'
        + '<tbody>' + rows + '</tbody>'
        + '</table>'
    );

    parts.push('<div class="pb-rc-note">'
        + 'Contributions are derived from each fund\'s target allocation and daily returns over the portfolio\'s common analysis period. '
        + 'Sorted largest positive contribution first; they reconcile to the portfolio\'s overall return within rounding tolerance.</div>');

    el.innerHTML = parts.join('');
    el.classList.remove('hidden');
}

// ---------------------------------------------------------------------------
// Drawdown & Recovery (additive analysis)
// Renders the backend-derived drawdown episodes from the existing portfolio
// growth series. The chart recomputes drawdown(t) = value/runningPeak - 1 in
// the browser from result.series — the same series and running-peak
// convention the backend maximum drawdown uses; no second data source.
// ---------------------------------------------------------------------------

function destroyDrawdownChart() {
    if (drawdownChart) {
        drawdownChart.destroy();
        drawdownChart = null;
    }
}

function renderDrawdownRecovery(result) {
    const el = $('pb-drawdown-recovery');
    if (!el) return;
    const dd = result && result.drawdown_recovery;
    const series = result && Array.isArray(result.series) ? result.series : null;
    if (!dd || !series || series.length < 2) {
        destroyDrawdownChart();
        el.classList.add('hidden');
        el.innerHTML = '';
        return;
    }

    const parts = [];
    parts.push('<div class="pb-rc-title">Drawdown &amp; Recovery</div>');
    parts.push('<div class="pb-rc-subtitle">See the portfolio\'s major declines and how long it took to recover from them.</div>');

    // Summary chips. Maximum Drawdown reconciles with the existing metric
    // (backend derives it from the same growth series).
    const chips = [];
    chips.push('<div class="pb-rc-chip"><span class="pb-rc-chip-label">Maximum Drawdown</span>'
        + '<span class="pb-rc-chip-value pb-rc-neg">' + formatSignedPercent(dd.maximum_drawdown) + '</span></div>');
    chips.push('<div class="pb-rc-chip"><span class="pb-rc-chip-label">Longest Recovery</span>'
        + '<span class="pb-rc-chip-value">' + (dd.longest_recovery_days != null ? dd.longest_recovery_days + ' days' : '\u2014') + '</span></div>');
    const currentCls = (dd.current_drawdown != null && dd.current_drawdown < 0) ? 'pb-rc-neg' : '';
    chips.push('<div class="pb-rc-chip"><span class="pb-rc-chip-label">Current Drawdown</span>'
        + '<span class="pb-rc-chip-value ' + currentCls + '">' + formatSignedPercent(dd.current_drawdown)
        + ' \u00b7 ' + escapeHtml(dd.current_status || '') + '</span></div>');
    parts.push('<div class="pb-rc-summary">' + chips.join('') + '</div>');

    parts.push('<div class="pb-dd-chart-container" id="pb-dd-chart-container"></div>');

    // Episode table: most severe first (backend order). Ongoing episodes
    // show Recovery = "Ongoing" and Recovery Time = "—".
    const rows = (Array.isArray(dd.episodes) ? dd.episodes : []).map(function (ep) {
        const status = ep.is_ongoing ? 'Ongoing' : 'Completed';
        const recoveryDate = ep.is_ongoing ? 'Ongoing' : (ep.recovery_date || '\u2014');
        const recoveryTime = ep.is_ongoing ? '\u2014' : (ep.recovery_duration_days != null ? ep.recovery_duration_days + ' days' : '\u2014');
        const cls = ep.drawdown < 0 ? 'pb-rc-neg' : '';
        return ''
            + '<tr>'
            + '<td>' + escapeHtml(status) + '</td>'
            + '<td>' + escapeHtml(ep.peak_date) + '</td>'
            + '<td>' + escapeHtml(ep.trough_date) + '</td>'
            + '<td>' + escapeHtml(recoveryDate) + '</td>'
            + '<td class="' + cls + '">' + formatSignedPercent(ep.drawdown) + '</td>'
            + '<td>' + escapeHtml(recoveryTime) + '</td>'
            + '</tr>';
    }).join('');
    parts.push(
        '<table class="pb-rc-table">'
        + '<thead><tr><th>Status</th><th>Peak</th><th>Trough</th><th>Recovery</th><th>Drawdown</th><th>Recovery Time</th></tr></thead>'
        + '<tbody>' + (rows || '<tr><td colspan="6">No significant drawdown episodes in this period.</td></tr>') + '</tbody>'
        + '</table>'
    );

    parts.push('<div class="pb-rc-note">'
        + 'Drawdown measures the decline from a previous portfolio high. Recovery is the time required to return to that previous high.</div>');

    destroyDrawdownChart();
    el.innerHTML = parts.join('');
    el.classList.remove('hidden');
    renderDrawdownChart(series);
}

function renderDrawdownChart(series) {
    // Drawdown chart: drawdown(t) = value(t)/runningPeak(t) - 1 over the
    // portfolio growth series (same series and convention as the backend
    // maximum drawdown). Uses Chart.js (already loaded for the growth chart).
    if (typeof Chart === 'undefined') return;
    const container = $('pb-dd-chart-container');
    if (!container) return;
    const canvas = document.createElement('canvas');
    container.appendChild(canvas);

    let peak = series[0].value;
    const ddData = series.map(function (p) {
        if (p.value > peak) peak = p.value;
        return (p.value / peak - 1) * 100;
    });

    drawdownChart = new Chart(canvas.getContext('2d'), {
        type: 'line',
        data: {
            labels: series.map(function (p) { return p.date; }),
            datasets: [{
                label: 'Drawdown',
                data: ddData,
                borderColor: '#ef4444',                     // app's semantic red-500
                backgroundColor: 'rgba(239, 68, 68, 0.12)', // translucent red-500 area
                fill: 'origin',
                borderWidth: 1.5,
                tension: 0,
                pointRadius: 0,
                pointHoverRadius: 4,
                pointHoverBackgroundColor: '#ef4444',
                pointHoverBorderColor: '#ffffff',
                pointHoverBorderWidth: 2,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { intersect: false, mode: 'index' },
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: 'rgba(15, 23, 42, 0.95)',
                    padding: 10,
                    titleFont: { size: 12, weight: '600' },
                    bodyFont: { size: 12 },
                    callbacks: {
                        title: function (items) { return items && items[0] ? items[0].label : ''; },
                        label: function (c) { return 'Drawdown: ' + Number(c.parsed.y).toFixed(2) + '%'; },
                    },
                },
            },
            scales: {
                x: { title: { display: true, text: 'Date', font: { size: 11, weight: '500' }, color: '#64748b' }, ticks: { maxTicksLimit: 8, color: '#64748b', font: { size: 11 } }, grid: { color: 'rgba(15, 23, 42, 0.04)' } },
                y: { title: { display: true, text: 'Drawdown (%)', font: { size: 11, weight: '500' }, color: '#64748b' }, ticks: { color: '#64748b', font: { size: 11 }, callback: function (v) { return v + '%'; } }, grid: { color: 'rgba(15, 23, 42, 0.06)' }, suggestedMin: -1 },
            },
        },
    });
}

function render() {
    const panel = $('pb-panel');
    const empty = $('pb-empty');
    const countEl = $('pb-count');
    if (!state.funds.length) {
        if (panel) panel.classList.add('hidden');
        if (empty) empty.classList.remove('hidden');
        updateTotal();
        return;
    }

    if (empty) empty.classList.add('hidden');
    if (panel) panel.classList.remove('hidden');
    if (countEl) countEl.textContent = state.funds.length + (state.funds.length === 1 ? ' fund' : ' funds');

    renderList();
    updateTotal();
}

function initPortfolioBuilder() {
    if (state.initialized) return;
    state.initialized = true;
    state.funds = reconcileDefaults(loadFunds());
    if (state.funds.length) saveFunds(); // persist the assigned default allocations
    render();

    const continueBtn = $('pb-continue-btn');
    const nextStage = $('pb-next-stage');
    if (continueBtn) {
        continueBtn.addEventListener('click', function () {
            if (continueBtn.disabled) return;
            if (nextStage) nextStage.hidden = true;
            runPortfolioAnalysis();
        });
    }
}

// ---------------------------------------------------------------------------
// Portfolio analysis (Phase 2D)
// Sends the current allocation to the backend portfolio-analysis endpoint
// and renders the returned metrics + growth series. No calculations are
// duplicated in JavaScript; no per-fund /detail or /nav-history calls.
// ---------------------------------------------------------------------------

let growthChart = null;   // Chart.js instance, destroyed before re-render
let drawdownChart = null; // Chart.js instance for the Drawdown & Recovery chart
let analyzing = false;    // guards against double-submit
let lastHealthScore = null; // latest HealthScoreData from backend (single source of truth)

function getApiBase() {
    return (window.APP_CONFIG && window.APP_CONFIG.API_BASE_URL) || '/api';
}

function formatMetricPercent(v, negativeSign) {
    if (v == null || !Number.isFinite(v)) return 'N/A';
    return (negativeSign ? '\u2212' : '') + (v * 100).toFixed(2) + '%';
}

function formatMetricRatio(v) {
    if (v == null || !Number.isFinite(v)) return 'N/A';
    return v.toFixed(2);
}

function buildMetricCards(metrics) {
    const cards = [
        { label: 'Portfolio CAGR', value: formatMetricPercent(metrics.cagr, false) },
        { label: 'Annualized Volatility', value: formatMetricPercent(metrics.annualized_volatility, false) },
        { label: 'Sharpe Ratio', value: formatMetricRatio(metrics.sharpe_ratio) },
        { label: 'Sortino Ratio', value: formatMetricRatio(metrics.sortino_ratio) },
        // Backend returns max drawdown as a positive fraction; display as a loss.
        { label: 'Maximum Drawdown', value: formatMetricPercent(metrics.maximum_drawdown, true), negative: metrics.maximum_drawdown != null && metrics.maximum_drawdown > 0 },
        { label: 'Downside Deviation', value: formatMetricPercent(metrics.downside_deviation, false) },
    ];
    return cards.map((c) =>
        '<div class="pb-metric">' +
        '<div class="pb-metric-label">' + escapeHtml(c.label) + '</div>' +
        '<div class="pb-metric-value' + (c.negative ? ' negative' : '') + '">' + escapeHtml(c.value) + '</div>' +
        '</div>'
    ).join('');
}

// ---------------------------------------------------------------------------
// Health Score rendering (Phase 3B.2)
// Renders a collapsible Health Score section. All data comes from the
// backend; no calculations are performed in the frontend.
// ---------------------------------------------------------------------------

const HEALTH_COMPONENT_LABELS = {
    return_quality: 'Return Quality',
    downside_risk: 'Downside Risk',
    risk_adjusted_return: 'Risk-Adjusted Return',
    concentration: 'Allocation Concentration',
    fund_mix: 'Fund Mix (category/AMC spread)',
};

function healthBarClass(value) {
    if (value == null || !Number.isFinite(value)) return '';
    if (value < 33) return ' pb-health-component-bar-fill--low';
    if (value < 66) return ' pb-health-component-bar-fill--medium';
    return ' pb-health-component-bar-fill--high';
}

// ---------------------------------------------------------------------------
// Health Score explainability (Phase 3B.3)
// Pure rendering of backend-provided `explanation` data. No scores,
// weights, or formulas are computed here.
// ---------------------------------------------------------------------------

const HEALTH_COMPONENT_KEYS = [
    'return_quality',
    'downside_risk',
    'risk_adjusted_return',
    'concentration',
    'fund_mix',
];

function formatExplainWeight(w) {
    if (w == null || !Number.isFinite(w)) return 'N/A';
    // Backend may send weight as fraction (0.25) or percent (25).
    const pct = w <= 1 ? w * 100 : w;
    return (Number.isInteger(pct) ? pct.toFixed(0) : pct.toFixed(1)) + '%';
}

function renderExplainList(lines) {
    if (!Array.isArray(lines) || lines.length === 0) return '';
    return '<ul class="pb-why-lines">' + lines.map(function (line) {
        return '<li>' + escapeHtml(line) + '</li>';
    }).join('') + '</ul>';
}

function renderExplainDict(obj) {
    if (!obj || typeof obj !== 'object') return '';
    const keys = Object.keys(obj);
    if (keys.length === 0) return '';
    return '<ul class="pb-why-lines">' + keys.map(function (k) {
        const v = obj[k];
        let vText;
        if (v == null) vText = 'Not available';
        else if (Array.isArray(v)) vText = v.length > 0 ? v.map(function (x) { return String(x); }).join(', ') : 'Not available';
        else if (typeof v === 'object') vText = JSON.stringify(v);
        else if (typeof v === 'number' && Number.isFinite(v)) vText = String(Math.round(v * 10000) / 10000);
        else vText = String(v);
        return '<li>' + escapeHtml(k) + ': ' + escapeHtml(vText) + '</li>';
    }).join('') + '</ul>';
}

function componentExplanationHtml(key) {
    const hs = lastHealthScore;
    if (!hs || !hs.explanation || !hs.explanation.components) return '';
    const comp = hs.explanation.components[key];
    if (!comp) return '';
    const label = HEALTH_COMPONENT_LABELS[key] || comp.component_name || key;
    const scoreText = (comp.component_score != null && Number.isFinite(comp.component_score))
        ? comp.component_score.toFixed(1) + ' / 100' : 'Not available';
    let html = '<div class="pb-why-section">' +
        '<div class="pb-why-title">' + escapeHtml(label) + ' — ' + escapeHtml(scoreText) + '</div>';
    if (comp.summary_text) {
        html += '<div class="pb-why-label">Why this score?</div>' +
            '<div class="pb-why-summary">' + escapeHtml(comp.summary_text) + '</div>';
    }
    if (comp.inputs && typeof comp.inputs === 'object' && Object.keys(comp.inputs).length > 0) {
        html += '<div class="pb-why-label">Key inputs</div>' + renderExplainDict(comp.inputs);
    }
    if (comp.intermediate_scores && typeof comp.intermediate_scores === 'object' && Object.keys(comp.intermediate_scores).length > 0) {
        html += '<div class="pb-why-label">Intermediate scores</div>' + renderExplainDict(comp.intermediate_scores);
    }
    html += '<div class="pb-why-label">Calculation</div>' + renderExplainList(comp.calculation_details);
    html += '</div>';
    return html;
}

function overallExplanationHtml() {
    const hs = lastHealthScore;
    if (!hs || !hs.explanation) return '';
    const ex = hs.explanation;
    let html = '<div class="pb-why-section">' +
        '<div class="pb-why-title">Portfolio Health Score — ' +
        escapeHtml(hs.score != null && Number.isFinite(hs.score) ? hs.score.toFixed(1) + ' / 100' : 'Not available') +
        '</div>' +
        '<div class="pb-why-label">How this score is calculated</div>' +
        renderExplainList(ex.overall_weight_details);
    if (ex.total_weighted_contribution != null && Number.isFinite(ex.total_weighted_contribution)) {
        html += '<div class="pb-why-summary">Total contribution: ' +
            escapeHtml(ex.total_weighted_contribution.toFixed(2)) + '</div>';
    }
    html += '</div>';
    return html;
}

function confidenceExplanationHtml() {
    const hs = lastHealthScore;
    if (!hs || !hs.explanation || !hs.explanation.confidence_explanation) return '';
    const c = hs.explanation.confidence_explanation;
    let html = '<div class="pb-why-section">' +
        '<div class="pb-why-title">Confidence — ' +
        escapeHtml((c.tier || '') + (c.label ? ' · ' + c.label : '')) + '</div>';
    if (c.reason) {
        html += '<div class="pb-why-label">Why this confidence level?</div>' +
            '<div class="pb-why-summary">' + escapeHtml(c.reason) + '</div>';
    }
    const pieces = [];
    if (c.history_years != null && Number.isFinite(c.history_years)) pieces.push('History: ' + c.history_years.toFixed(2) + ' years');
    if (c.has_legacy != null) pieces.push('Legacy scheme: ' + (c.has_legacy ? 'Yes' : 'No'));
    if (c.score_withheld != null) pieces.push('Score withheld: ' + (c.score_withheld ? 'Yes' : 'No'));
    if (c.thresholds && typeof c.thresholds === 'object') {
        Object.keys(c.thresholds).forEach(function (tier) {
            pieces.push('Tier ' + tier + ': ' + c.thresholds[tier]);
        });
    }
    if (pieces.length > 0) {
        html += '<div class="pb-why-label">Details</div>' + renderExplainList(pieces);
    }
    html += '</div>';
    return html;
}

function renderHealthComponent(key, value, weight) {
    const label = HEALTH_COMPONENT_LABELS[key] || key;
    const displayValue = (value != null && Number.isFinite(value)) ? value.toFixed(1) : 'Unavailable';
    const barWidth = (value != null && Number.isFinite(value)) ? Math.max(0, Math.min(100, value)) : 0;
    const barClass = healthBarClass(value);
    const hs = lastHealthScore;
    const hasWhy = !!(hs && hs.explanation && hs.explanation.components && hs.explanation.components[key]);
    const whyBtn = hasWhy
        ? '<button type="button" class="pb-why-btn" data-why-component="' + escapeAttr(key) + '" aria-expanded="false" aria-label="Why is ' + escapeAttr(label) + ' ' + escapeAttr(displayValue) + '?">Why?</button>'
        : '';
    const panelId = 'pb-why-panel-' + key;
    return (
        '<div class="pb-health-component">' +
        '<div class="pb-health-component-header">' +
        '<span class="pb-health-component-name">' + escapeHtml(label) + '</span>' +
        '<span class="pb-health-component-meta"><span class="pb-health-component-value">' + escapeHtml(displayValue) + '</span>' + whyBtn + '</span>' +
        '</div>' +
        '<div class="pb-health-component-bar">' +
        '<div class="pb-health-component-bar-fill' + barClass + '" style="width:' + barWidth + '%"></div>' +
        '</div>' +
        '<div class="pb-health-component-weight">Weight: ' + escapeHtml(formatExplainWeight(weight)) + '</div>' +
        (hasWhy ? '<div class="pb-why-panel" id="' + panelId + '" hidden></div>' : '') +
        '</div>'
    );
}

function renderHealthScore(healthScore) {
    const container = $('pb-health-score');
    if (!container) return;

    lastHealthScore = healthScore || null;

    if (!healthScore) {
        container.classList.add('hidden');
        container.innerHTML = '';
        return;
    }

    const confidence = healthScore.confidence || {};
    const components = healthScore.components || {};
    const weights = healthScore.component_weights || {};
    const available = Array.isArray(healthScore.available_components) ? healthScore.available_components : [];

    const isWithheld = healthScore.score_withheld === true;
    const scoreDisplay = isWithheld
        ? 'Not enough history to score'
        : ((healthScore.score != null && Number.isFinite(healthScore.score)) ? healthScore.score.toFixed(1) + ' / 100' : 'N/A');
    const confidenceTier = confidence.tier || 'D';
    const confidenceLabel = confidence.label || 'Low confidence';

    let contentHtml = '';

    if (healthScore.single_fund_portfolio === true) {
        contentHtml += '<div class="pb-health-note pb-health-note--single">Single-fund portfolio — concentration score is 0.</div>';
    }
    if (healthScore.has_legacy_scheme === true) {
        contentHtml += '<div class="pb-health-note pb-health-note--legacy">Limited confidence — includes a scheme AMFI no longer publishes NAVs for.</div>';
    }

    if (!isWithheld && available.length > 0) {
        contentHtml += '<div class="pb-health-components">';
        for (let i = 0; i < available.length; i++) {
            const key = available[i];
            const value = components[key];
            const weight = weights[key];
            contentHtml += renderHealthComponent(key, value, weight);
        }
        contentHtml += '</div>';
    }

    const scoreParts = scoreDisplay.split('/');
    const scoreValue = scoreParts[0] || scoreDisplay;
    const scoreDenominator = scoreParts[1] ? '/' + scoreParts.slice(1).join('/') : '';

    const hasOverallWhy = !!(healthScore.explanation && Array.isArray(healthScore.explanation.overall_weight_details) && healthScore.explanation.overall_weight_details.length > 0);
    const hasConfidenceWhy = !!(healthScore.explanation && healthScore.explanation.confidence_explanation);
    const overallWhyBtn = hasOverallWhy
        ? '<button type="button" class="pb-why-btn pb-why-btn--header" data-why-overall="1" aria-expanded="false" aria-label="Why is the Portfolio Health Score ' + escapeAttr(scoreDisplay.trim()) + '?">Why?</button>'
        : '';
    const confidenceWhyBtn = hasConfidenceWhy
        ? '<button type="button" class="pb-why-btn pb-why-btn--header" data-why-confidence="1" aria-expanded="false" aria-label="Why is confidence ' + escapeAttr(confidenceTier + ' ' + confidenceLabel) + '?">Why?</button>'
        : '';

    const html =
        '<div class="pb-health-card">' +
        '<div class="pb-health-header">' +
            '<div class="pb-health-header-left">' +
                '<span class="pb-health-summary-label">' +
                    'Portfolio Health Score' +
                    (isWithheld ? '<small>Score withheld - insufficient history</small>' : '<small>Overall portfolio assessment</small>') +
                '</span>' +
                '<span class="pb-health-summary-score">' +
                    '<span class="pb-health-score-value">' + escapeHtml(scoreValue) + '</span>' +
                    '<span class="pb-health-score-denominator">' + escapeHtml(scoreDenominator) + '</span>' + overallWhyBtn +
                '</span>' +
                (hasOverallWhy ? '<div class="pb-why-panel pb-why-panel--header" id="pb-why-panel-overall" hidden></div>' : '') +
            '</div>' +
            '<div class="pb-health-header-right">' +
                '<span class="pb-health-summary-confidence">' +
                    '<span class="confidence-tier">' + escapeHtml(confidenceTier) + '</span>' +
                    escapeHtml(confidenceLabel) + confidenceWhyBtn +
                '</span>' +
                (hasConfidenceWhy ? '<div class="pb-why-panel pb-why-panel--header" id="pb-why-panel-confidence" hidden style="display:none"></div>' : '') +
                '<button type="button" class="pb-health-caret-button" aria-expanded="false" aria-controls="pb-health-builder-content" aria-label="Expand Portfolio Health Score components" title="Expand Health Score details">' +
                    '<svg class="pb-health-caret" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
                        '<path d="M5 7.5L10 12.5L15 7.5"></path>' +
                    '</svg>' +
                '</button>' +
            '</div>' +
        '</div>' +
        '<div class="pb-health-content" id="pb-health-builder-content" hidden>' + contentHtml + '</div>' +
        '</div>';

    container.innerHTML = html;
    container.classList.remove('hidden');

    // Health Score is the single accordion: the header (title + score +
    // confidence + chevron) is always visible; only the component details
    // below the header toggle. No outer "Details" layer.
    const card = container.querySelector('.pb-health-card');
    const caretButton = container.querySelector('.pb-health-caret-button');
    const content = container.querySelector('.pb-health-content');

    function setHealthOpen(open) {
        if (content) content.hidden = !open;
        if (card) card.classList.toggle('is-open', open);
        if (caretButton) caretButton.setAttribute('aria-expanded', open ? 'true' : 'false');
    }
    // OPEN by default — the entire Health Score section (score, confidence,
    // component breakdown) is visible. Only the component details panel
    // below the header starts collapsed; the header and score are always visible.
    setHealthOpen(true);

    if (caretButton && content) {
        caretButton.addEventListener('click', function () {
            setHealthOpen(!!content.hidden);
        });
    }

    // Wire up Why? toggles: overall, confidence, and per-component.
    // No calculations here — panels render backend explanation strings.
    function toggleWhyPanel(btn, panel, buildHtml) {
        if (!btn || !panel) return;
        const expanded = btn.getAttribute('aria-expanded') === 'true';
        if (expanded) {
            panel.hidden = true;
            if (panel.classList.contains('pb-why-panel--header') && panel.id === 'pb-why-panel-confidence') {
                panel.style.display = 'none';
            }
            btn.setAttribute('aria-expanded', 'false');
            return;
        }
        panel.innerHTML = buildHtml();
        panel.hidden = false;
        if (panel.classList.contains('pb-why-panel--header') && panel.id === 'pb-why-panel-confidence') {
            panel.style.display = 'block';
        }
        btn.setAttribute('aria-expanded', 'true');
    }

    const overallBtn = container.querySelector('[data-why-overall]');
    const overallPanel = container.querySelector('#pb-why-panel-overall');
    if (overallBtn && overallPanel) {
        overallBtn.addEventListener('click', function () {
            toggleWhyPanel(overallBtn, overallPanel, overallExplanationHtml);
        });
    }

    const confBtn = container.querySelector('[data-why-confidence]');
    // Confidence panel lives in the header-right block; place inline after the badge.
    const confPanel = container.querySelector('#pb-why-panel-confidence');
    if (confBtn && confPanel) {
        confBtn.addEventListener('click', function () {
            toggleWhyPanel(confBtn, confPanel, confidenceExplanationHtml);
        });
    }

    const compBtns = container.querySelectorAll('[data-why-component]');
    for (let bi = 0; bi < compBtns.length; bi++) {
        (function (btn) {
            const key = btn.getAttribute('data-why-component');
            const compRoot = btn.closest('.pb-health-component');
            const panel = compRoot ? compRoot.querySelector('.pb-why-panel') : null;
            btn.addEventListener('click', function () {
                toggleWhyPanel(btn, panel, function () { return componentExplanationHtml(key); });
            });
        })(compBtns[bi]);
    }
}

// ---------------------------------------------------------------------------
// Rolling Performance & Consistency (additive analysis)
// Renders rolling 1Y/3Y/5Y CAGR from the backend-derived rolling_performance
// data, which reuses MetricsCalculator.get_rolling_returns_series on the SAME
// portfolio growth series as every other section. One rolling-CAGR series is
// shown at a time via a period selector. No new data or calculation engine.
// ---------------------------------------------------------------------------

let rollingChart = null;

function destroyRollingChart() {
    if (rollingChart) {
        rollingChart.destroy();
        rollingChart = null;
    }
}

function _rollingInsight(positivePct) {
    if (positivePct == null || !Number.isFinite(positivePct)) return null;
    if (positivePct >= 90) return 'Most historical rolling periods were positive.';
    if (positivePct >= 50) return 'Historical rolling returns were positive in a majority of periods, but losses occurred in some periods.';
    return 'Historical rolling returns were positive in fewer than half of the measured periods.';
}

function _formatStatPct(v) {
    if (v == null || !Number.isFinite(v)) return 'N/A';
    return formatSignedPercent(v);
}

function _renderRpSummary(win) {
    const s = win.data.summary;
    const rows = [
        { label: 'Median CAGR', value: _formatStatPct(s.median) },
        { label: 'Average CAGR', value: _formatStatPct(s.avg) },
        { label: 'Best Period', value: _formatStatPct(s.max) },
        { label: 'Worst Period', value: _formatStatPct(s.min) },
        { label: 'Positive Periods', value: (s.positive_pct != null && Number.isFinite(s.positive_pct)) ? s.positive_pct.toFixed(0) + '%' : 'N/A' },
        { label: 'Observations', value: String(s.count) },
    ];
    const items = rows.map(function (r) {
        return '<div class="pb-rp-stat"><span class="pb-rp-stat-label">' + escapeHtml(r.label) + '</span>'
            + '<span class="pb-rp-stat-value">' + escapeHtml(r.value) + '</span></div>';
    }).join('');
    return '<div class="pb-rp-summary"><div class="pb-rp-summary-title">' + escapeHtml(win.label) + ' Rolling Returns</div>'
        + '<div class="pb-rp-stats">' + items + '</div></div>';
}

function _renderRollingChartCanvas(winData) {
    const canvas = $('pb-rolling-chart');
    if (!canvas || !winData || !Array.isArray(winData.dates) || !Array.isArray(winData.returns)) return;
    destroyRollingChart();
    const labels = winData.dates;
    const dataPct = winData.returns.map(function (r) { return +(r * 100).toFixed(4); });
    rollingChart = new Chart(canvas.getContext('2d'), {
        type: 'line',
        data: { labels: labels, datasets: [{
            label: 'Rolling CAGR (%)', data: dataPct, borderColor: '#2563eb',
            backgroundColor: 'rgba(37,99,235,0.12)', fill: true, tension: 0.2,
            pointRadius: 0, pointHitRadius: 6, borderWidth: 2,
        }] },
        options: {
            responsive: true, maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: { legend: { display: false }, tooltip: { callbacks: {
                title: function (items) { return items[0] ? ('Date: ' + items[0].label) : ''; },
                label: function (item) {
                    const v = item.parsed.y;
                    const sign = v >= 0 ? '+' : '\u2212';
                    return 'Rolling CAGR: ' + sign + Math.abs(v).toFixed(2) + '%';
                },
            } } },
            scales: {
                x: { ticks: { maxTicksLimit: 6, color: '#6b7280', font: { size: 10 } }, grid: { display: false } },
                y: { ticks: { color: '#6b7280', font: { size: 10 }, callback: function (v) { return (v >= 0 ? '+' : '') + v + '%'; } }, grid: { color: '#e5e7eb' } },
            },
        },
    });
}

function renderRollingPerformance(result) {
    const el = $('pb-rolling-performance');
    if (!el) return;
    const rp = result && result.rolling_performance;

    destroyRollingChart();

    if (!rp || (!rp.one_year && !rp.three_year && !rp.five_year)) {
        el.classList.add('hidden');
        el.innerHTML = '';
        return;
    }

    const windows = [
        { key: 'one_year', years: 1, label: '1 Year', data: rp.one_year },
        { key: 'three_year', years: 3, label: '3 Years', data: rp.three_year },
        { key: 'five_year', years: 5, label: '5 Years', data: rp.five_year },
    ];
    const available = windows.filter(function (w) { return w.data && !w.data.insufficient_history && w.data.summary; });
    if (!available.length) {
        el.classList.add('hidden');
        el.innerHTML = '';
        return;
    }

    const parts = [];
    parts.push('<div class="pb-rc-title">Rolling Performance</div>');
    parts.push('<div class="pb-rc-subtitle">See how consistently this portfolio has generated returns across different rolling periods.</div>');

    if (rp.portfolio_cagr != null && Number.isFinite(rp.portfolio_cagr)) {
        parts.push('<div class="pb-rc-note" style="margin-bottom:10px">'
            + '<strong>Portfolio CAGR</strong> &mdash; the annualized return over the entire selected analysis period: '
            + formatSignedPercent(rp.portfolio_cagr) + '. '
            + '<strong>Rolling CAGR</strong> &mdash; the annualized return measured across many overlapping historical windows.</div>');
    }

    const buttons = available.map(function (w, idx) {
        const cls = idx === 0 ? 'pb-rp-btn pb-rp-active' : 'pb-rp-btn';
        return '<button type="button" class="' + cls + '" data-years="' + w.years + '">' + w.label + '</button>';
    }).join('');
    parts.push('<div class="pb-rp-selector">' + buttons + '</div>');
    parts.push('<div class="pb-rp-chart-container"><canvas id="pb-rolling-chart"></canvas></div>');
    parts.push(_renderRpSummary(available[0]));

    const insight = available[0].data.summary ? _rollingInsight(available[0].data.summary.positive_pct) : null;
    if (insight) parts.push('<div class="pb-rp-insight">' + escapeHtml(insight) + '</div>');

    parts.push('<div class="pb-rc-note">'
        + 'Rolling returns are calculated from the portfolio\'s existing daily-return methodology over the common analysis period. '
        + 'Each point is the annualized return over the preceding window. '
        + 'Historical rolling performance does not predict future returns.</div>');

    el.innerHTML = parts.join('');
    el.classList.remove('hidden');

    _renderRollingChartCanvas(available[0].data);

    const selector = el.querySelector('.pb-rp-selector');
    if (selector) {
        selector.addEventListener('click', function (ev) {
            const btn = ev.target.closest('.pb-rp-btn');
            if (!btn) return;
            const years = parseInt(btn.getAttribute('data-years'), 10);
            const win = windows.find(function (w) { return w.years === years; });
            if (!win || !win.data || win.data.insufficient_history || !win.data.summary) return;

            const allBtns = selector.querySelectorAll('.pb-rp-btn');
            for (let i = 0; i < allBtns.length; i++) {
                allBtns[i].classList.toggle('pb-rp-active', allBtns[i] === btn);
            }

            const existingSummary = el.querySelector('.pb-rp-summary');
            const existingInsight = el.querySelector('.pb-rp-insight');
            if (existingSummary) existingSummary.remove();
            if (existingInsight) existingInsight.remove();

            const insertRef = el.querySelector('.pb-rc-note');
            const summaryNode = document.createElement('div');
            summaryNode.innerHTML = _renderRpSummary(win);
            const newInsight = _rollingInsight(win.data.summary.positive_pct);
            const insightNode = document.createElement('div');
            insightNode.className = 'pb-rp-insight';
            if (newInsight) insightNode.textContent = newInsight;

            if (insertRef && insertRef.parentNode) {
                if (newInsight) insertRef.parentNode.insertBefore(insightNode, insertRef);
                insertRef.parentNode.insertBefore(summaryNode.firstElementChild, newInsight ? insightNode : insertRef);
            }
            _renderRollingChartCanvas(win.data);
        });
    }
}

function setAnalysisView(mode) {
    // mode: 'hidden' | 'loading' | 'error' | 'results'
    const section = $('pb-analysis');
    const loading = $('pb-analysis-loading');
    const error = $('pb-analysis-error');
    const results = $('pb-analysis-results');
    if (!section) return;
    section.classList.remove('hidden');
    if (loading) loading.classList.toggle('hidden', mode !== 'loading');
    if (error) error.classList.toggle('hidden', mode !== 'error');
    if (results) results.classList.toggle('hidden', mode !== 'results');
}

function setAnalysisBusy(busy) {
    analyzing = busy;
    const btn = $('pb-continue-btn');
    if (!btn) return;
    if (busy) {
        btn.disabled = true;
        return;
    }
    // Restore the normal gating (valid inputs + total exactly 100%).
    let total = 0;
    let anyInvalid = false;
    for (let i = 0; i < state.funds.length; i++) {
        const f = state.funds[i];
        if (f.invalid) anyInvalid = true;
        else if (typeof f.allocation === 'number') total = round2(total + f.allocation);
    }
    const canContinue = !anyInvalid && Math.abs(total - 100) < EPS && state.funds.length > 0;
    btn.disabled = !canContinue;
    btn.textContent = 'Continue';
}

export { initPortfolioBuilder };

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initPortfolioBuilder);
} else {
    initPortfolioBuilder();
}


// ===================================================================
// Collapsible section toggle logic (reuses Health Score pattern)
// All sections use the same interaction model as pb-health-card.
// Chart.js instances are preserved; only visibility changes.
//
// CRITICAL: Section VISIBILITY (card wrapper being in DOM and visible)
// is SEPARATE from section EXPANDED/COLLAPSED STATE (content hidden).
//
// - A collapsed section: card wrapper is VISIBLE, header visible,
//   but .pb-section-content has the `hidden` attribute.
// - The card wrapper MUST NEVER receive the analysis-level `.hidden`
//   class (which maps to `display: none !important` in components.css).
//   That class is reserved for loading/error/results state management
//   via setAnalysisView().
// ===================================================================

const COLLAPSIBLE_SECTIONS_CONFIG = [
    { id: 'pb-health-score', defaultOpen: true },   // 1. Health Score — OPEN by default
    { id: 'pb-metric-section', defaultOpen: true },  // 2. Portfolio Metrics — OPEN by default
    { id: 'pb-growth-section', defaultOpen: true },  // 3. Growth & Benchmark — OPEN by default
    { id: 'pb-rolling-section', defaultOpen: false }, // 4. Rolling Performance — COLLAPSED
    { id: 'pb-drawdown-section', defaultOpen: false }, // 5. Drawdown & Recovery — COLLAPSED
    { id: 'pb-contribution-section', defaultOpen: false }, // 6. Return Contribution — COLLAPSED
    { id: 'pb-whatif-section', defaultOpen: false },  // 7. What-If Allocation — COLLAPSED
];

// Track whether collapsible sections have been initialized to avoid
// duplicate event listeners on repeated analysis runs.
let collapsibleSectionsInitialized = false;

function initCollapsibleSections() {
    // Guard: only initialize once. Re-rendering content via innerHTML
    // in renderHealthScore() etc. does not require re-initialization
    // because the section wrappers (with their headers) persist in the DOM
    // across analysis runs.
    if (collapsibleSectionsInitialized) {
        return;
    }

    COLLAPSIBLE_SECTIONS_CONFIG.forEach(function(sectionConfig) {
        const card = document.getElementById(sectionConfig.id);
        if (!card) return;

        // Ensure the card wrapper itself is never hidden via the
        // analysis-level `.hidden` class. This class is reserved for
        // setAnalysisView() to show/hide the entire results container,
        // not for accordion state.
        card.classList.remove('hidden');

        // Set initial open/closed state
        const isOpen = sectionConfig.defaultOpen;
        card.classList.toggle('is-open', isOpen);

        // Find the content element and toggle the `hidden` attribute
        // (NOT the `.hidden` class — the `hidden` HTML attribute is
        // the native way to hide content while keeping the element in DOM).
        const content = card.querySelector('.pb-section-content') || card.querySelector('.pb-health-content');
        if (content) {
            content.hidden = !isOpen;
        }

        // Update aria-expanded on caret button
        const caretBtn = card.querySelector('.pb-section-caret-btn') || card.querySelector('.pb-health-caret-button');
        if (caretBtn) {
            caretBtn.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
        }

        // Add click handler to the header (entire header is clickable)
        const header = card.querySelector('.pb-section-header');
        if (header && caretBtn) {
            // Prevent double-firing if clicked directly on button
            header.addEventListener('click', function(e) {
                // If click is directly on the button, let the button handle it
                // Otherwise, trigger the toggle
                if (!e.target.closest('.pb-section-caret-btn') &&
                    !e.target.closest('.pb-health-caret-button')) {
                    toggleSection(card);
                }
            });

            // Button click handler
            caretBtn.addEventListener('click', function(e) {
                e.stopPropagation();
                toggleSection(card);
            });
        }
    });

    collapsibleSectionsInitialized = true;
}

function toggleSection(card) {
    const isCurrentlyOpen = card.classList.contains('is-open');
    const newOpenState = !isCurrentlyOpen;
    
    // Toggle the is-open class
    card.classList.toggle('is-open', newOpenState);
    
    // Toggle content visibility
    const content = card.querySelector('.pb-section-content') || card.querySelector('.pb-health-content');
    if (content) {
        content.hidden = !newOpenState;
        
        // If opening and content has a chart, trigger resize after a brief delay
        // to allow the DOM to update and container to have proper dimensions
        if (newOpenState && content.querySelector('canvas')) {
            setTimeout(function() {
                // Notify Chart.js instances to resize if needed
                if (typeof window !== 'undefined' && window.Chart) {
                    const canvases = content.querySelectorAll('canvas');
                    canvases.forEach(function(canvas) {
                        const chart = Chart.getChart(canvas.id);
                        if (chart) {
                            chart.resize();
                        }
                    });
                }
            }, 50);
        }
    }
    
    // Update aria-expanded
    const caretBtn = card.querySelector('.pb-section-caret-btn') || card.querySelector('.pb-health-caret-button');
    if (caretBtn) {
        caretBtn.setAttribute('aria-expanded', newOpenState ? 'true' : 'false');
    }
    
    // Update aria-expanded on the header if it's a button
    const header = card.querySelector('.pb-section-header');
    if (header && header.tagName === 'BUTTON') {
        header.setAttribute('aria-expanded', newOpenState ? 'true' : 'false');
    }
}

// Initialize collapsible sections when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initCollapsibleSections);
} else {
    initCollapsibleSections();
}

// Reinitialize after analysis results are rendered (in case sections are re-rendered)
// This is a safe no-op because initCollapsibleSections() has a guard that prevents
// duplicate initialization. The section wrappers persist in the DOM across analysis
// runs; only their inner content is re-rendered.
function reinitializeCollapsibleSections() {
    // No-op: collapsible sections are initialized once on DOMContentLoaded.
    // The section cards (with their headers) are static HTML; only the content
    // inside .pb-section-content is re-rendered by the analysis renderers.
    // Event handlers attached to the headers persist across re-renders.
    initCollapsibleSections();
}
