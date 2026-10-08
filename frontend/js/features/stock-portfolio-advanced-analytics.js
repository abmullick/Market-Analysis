// Stock Portfolio — Advanced Analytics
// Performance-first design:
//   * consumes the SAME rows + /charts payload already fetched by
//     stock-portfolio-analysis.js
//   * performs no network requests
//   * derives rolling performance, drawdown/recovery and health score
//     locally from the existing annual price series + fundamentals.
//   * intentionally uses annual closes, matching the existing portfolio
//     risk view. It is not an intraday/transaction-level backtest.

const esc = (value) => String(value ?? "")
    .replaceAll("&", "&amp;").replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");
const num = (v) => { const n = Number(v); return Number.isFinite(n) ? n : null; };
const pct = (v, d = 1) => num(v) == null ? "—" : `${num(v).toFixed(d)}%`;
const signedPct = (v, d = 1) => {
    const n = num(v);
    if (n == null) return "—";
    return `${n < 0 ? "−" : "+"}${Math.abs(n).toFixed(d)}%`;
};

let rollingChart = null;
let drawdownChart = null;

function destroyCharts() {
    if (rollingChart) { try { rollingChart.destroy(); } catch (_) {} rollingChart = null; }
    if (drawdownChart) { try { drawdownChart.destroy(); } catch (_) {} drawdownChart = null; }
}

function buildAnnualPriceMap(rows, chartsBySymbol) {
    const maps = new Map();
    rows.forEach(row => {
        const prices = chartsBySymbol.get(row.symbol)?.annual_prices || [];
        const map = {};
        prices.forEach(p => {
            const year = String(p?.date || "").slice(0, 4);
            const close = num(p?.close);
            if (/^\\d{4}$/.test(year) && close != null && close > 0) map[year] = close;
        });
        maps.set(row.symbol, map);
    });
    return maps;
}

function buildPortfolioPath(rows, priceMaps) {
    const years = [...new Set([...priceMaps.values()].flatMap(m => Object.keys(m)))].sort();
    if (years.length < 2) return null;

    // Keep the same common-history/covered-allocation principle as the
    // existing portfolio risk calculation, but normalize covered allocation
    // once rather than making repeated requests or calculations per metric.
    const usable = rows.filter(r => {
        const m = priceMaps.get(r.symbol);
        return m && years.some(y => m[y] != null);
    });
    const commonYears = years.filter(y =>
        usable.length > 0 && usable.every(r => priceMaps.get(r.symbol)?.[y] != null)
    );
    if (commonYears.length < 2) return null;

    const coverage = usable.reduce((s, r) => s + (num(r.allocation) || 0), 0);
    if (coverage <= 0) return null;

    const values = commonYears.map(year => usable.reduce((sum, r) => {
        const start = priceMaps.get(r.symbol)[commonYears[0]];
        const current = priceMaps.get(r.symbol)[year];
        if (start == null || current == null || start <= 0 || current <= 0) return sum;
        return sum + ((num(r.allocation) || 0) / coverage) * (current / start) * 100;
    }, 0));

    return { dates: commonYears.map(y => `${y}-12-31`), years: commonYears, values, coverage };
}

function cagr(start, end, years) {
    if (!(start > 0) || !(end > 0) || !(years > 0)) return null;
    return (Math.pow(end / start, 1 / years) - 1) * 100;
}

function rollingWindow(path, windowYears) {
    if (!path || path.values.length <= windowYears) return null;
    const dates = [], returns = [];
    for (let i = windowYears; i < path.values.length; i++) {
        const value = cagr(path.values[i - windowYears], path.values[i], windowYears);
        if (value == null) continue;
        dates.push(path.dates[i]);
        returns.push(value);
    }
    if (!returns.length) return null;
    const sorted = [...returns].sort((a, b) => a - b);
    const avg = returns.reduce((a, b) => a + b, 0) / returns.length;
    const median = sorted.length % 2
        ? sorted[(sorted.length - 1) / 2]
        : (sorted[sorted.length / 2 - 1] + sorted[sorted.length / 2]) / 2;
    const variance = returns.length > 1
        ? returns.reduce((s, r) => s + Math.pow(r - avg, 2), 0) / (returns.length - 1)
        : 0;
    return {
        dates,
        returns,
        summary: {
            count: returns.length,
            avg,
            median,
            min: sorted[0],
            max: sorted[sorted.length - 1],
            positive_pct: returns.filter(r => r > 0).length / returns.length * 100,
            std_dev: Math.sqrt(variance),
        }
    };
}

function calculateDrawdown(path) {
    if (!path || path.values.length < 2) return null;
    let peak = path.values[0], peakDate = path.dates[0];
    let maxDd = 0, maxPeakDate = peakDate, maxTroughDate = peakDate;
    let episode = null;
    const episodes = [];

    for (let i = 0; i < path.values.length; i++) {
        const value = path.values[i];
        const date = path.dates[i];

        if (value >= peak) {
            if (episode) {
                episode.recoveryDate = date;
                episode.recoveryDurationDays = daysBetween(episode.troughDate, date);
                episode.totalDurationDays = daysBetween(episode.peakDate, date);
                episode.isOngoing = false;
                episodes.push(episode);
                episode = null;
            }
            peak = value;
            peakDate = date;
            continue;
        }

        const dd = value / peak - 1;
        if (dd < maxDd) {
            maxDd = dd;
            maxPeakDate = peakDate;
            maxTroughDate = date;
        }

        if (!episode) {
            episode = {
                peakDate,
                troughDate: date,
                drawdown: dd,
                declineDurationDays: daysBetween(peakDate, date),
                recoveryDate: null,
                recoveryDurationDays: null,
                totalDurationDays: null,
                isOngoing: true,
            };
        } else if (dd < episode.drawdown) {
            episode.drawdown = dd;
            episode.troughDate = date;
            episode.declineDurationDays = daysBetween(episode.peakDate, date);
        }
    }

    if (episode) episodes.push(episode);
    const currentDd = path.values[path.values.length - 1] / Math.max(...path.values) - 1;
    const recovered = episodes.filter(e => !e.isOngoing && e.totalDurationDays != null);
    const longestRecovery = recovered.length
        ? Math.max(...recovered.map(e => e.totalDurationDays))
        : null;

    return {
        maximum_drawdown: maxDd * 100,
        current_drawdown: currentDd * 100,
        current_status: currentDd < -0.0001 ? "Still below peak" : "At / above peak",
        longest_recovery_days: longestRecovery,
        max_peak_date: maxPeakDate,
        max_trough_date: maxTroughDate,
        episodes: episodes.slice().sort((a, b) => a.drawdown - b.drawdown).slice(0, 8),
        series: path.values.map((v, i) => ({
            date: path.dates[i],
            drawdown: (v / Math.max(...path.values.slice(0, i + 1)) - 1) * 100
        }))
    };
}

function daysBetween(a, b) {
    const x = Date.parse(a), y = Date.parse(b);
    return Number.isFinite(x) && Number.isFinite(y) ? Math.max(0, Math.round((y - x) / 86400000)) : null;
}

function calculateAnnualVolatility(path) {
    if (!path || path.values.length < 3) return null;
    const returns = [];
    for (let i = 1; i < path.values.length; i++) {
        if (path.values[i - 1] > 0) returns.push(path.values[i] / path.values[i - 1] - 1);
    }
    if (returns.length < 2) return null;
    const mean = returns.reduce((a, b) => a + b, 0) / returns.length;
    return Math.sqrt(returns.reduce((s, r) => s + Math.pow(r - mean, 2), 0) / (returns.length - 1)) * 100;
}

function calculateHealth(rows, path, drawdown) {
    const allocations = rows.map(r => num(r.allocation) || 0).filter(v => v > 0);
    if (!allocations.length) return null;

    const hhi = allocations.reduce((s, w) => s + Math.pow(w / 100, 2), 0);
    const concentration = allocations.length > 1
        ? Math.max(0, Math.min(100, (1 - hhi) / (1 - 1 / allocations.length) * 100))
        : 0;

    const avgRoe = weightedFundamental(rows, "roe");
    const avgRevenue = weightedFundamental(rows, "revenue_growth");
    const avgProfit = weightedFundamental(rows, "profit_growth");
    const avgDebt = weightedFundamental(rows, "debt_equity");

    const qualityParts = [];
    if (avgRoe != null) qualityParts.push(clamp((avgRoe - 5) / 20 * 100));
    if (avgRevenue != null) qualityParts.push(clamp((avgRevenue + 5) / 25 * 100));
    if (avgProfit != null) qualityParts.push(clamp((avgProfit + 5) / 30 * 100));
    const quality = qualityParts.length ? average(qualityParts) : null;

    const cagrValue = path ? cagr(path.values[0], path.values[path.values.length - 1], path.values.length - 1) : null;
    const returnScore = cagrValue == null ? null : clamp((cagrValue + 5) / 20 * 100);
    const downsideScore = drawdown
        ? clamp(100 - Math.abs(drawdown.maximum_drawdown) / 50 * 100)
        : null;
    const leverageScore = avgDebt == null ? null : clamp(100 - Math.max(0, avgDebt - 0.5) / 2 * 100);

    const available = [
        ["Return", returnScore, 25],
        ["Downside Risk", downsideScore, 25],
        ["Quality", quality, 25],
        ["Diversification", concentration, 15],
        ["Balance Sheet", leverageScore, 10],
    ].filter(x => x[1] != null && Number.isFinite(x[1]));

    if (!available.length) return null;
    const weight = available.reduce((s, x) => s + x[2], 0);
    const score = available.reduce((s, x) => s + x[1] * x[2], 0) / weight;
    return {
        score,
        components: available.map(x => ({ name: x[0], score: x[1], weight: x[2] / weight * 100 })),
        inputs: { cagr: cagrValue, max_drawdown: drawdown?.maximum_drawdown ?? null, roe: avgRoe, revenue_growth: avgRevenue, profit_growth: avgProfit, debt_equity: avgDebt, hhi: hhi }
    };
}

function weightedFundamental(rows, key) {
    let total = 0, weight = 0;
    rows.forEach(r => {
        const v = num(r.data?.fundamentals?.[key]);
        const w = num(r.allocation) || 0;
        if (v != null && w > 0) { total += v * w; weight += w; }
    });
    return weight ? total / weight : null;
}

function clamp(v) { return Math.max(0, Math.min(100, v)); }
function average(values) { return values.length ? values.reduce((a, b) => a + b, 0) / values.length : null; }

function scoreClass(score) {
    if (score >= 75) return "good";
    if (score >= 55) return "watch";
    return "risk";
}

function renderHealth(root, health) {
    if (!health) return;
    const score = health.score;
    const cards = health.components.map(c =>
        `<div class="spa-health-component"><span>${esc(c.name)}</span><strong>${c.score.toFixed(0)}</strong><small>${c.weight.toFixed(0)}% weight</small><div class="spa-health-track"><i class="${scoreClass(c.score)}" style="width:${c.score.toFixed(1)}%"></i></div></div>`
    ).join("");
    root.insertAdjacentHTML("beforeend", `
        <section class="stock-section portfolio-analysis-section spa-health-section">
          <div class="stock-section-header"><div><h2>Portfolio Health Score</h2><span>0–100 historical portfolio construction and risk assessment</span></div><span class="spa-health-badge ${scoreClass(score)}">${score.toFixed(0)} / 100</span></div>
          <div class="spa-health-grid">${cards}</div>
          <p class="portfolio-analysis-note">Derived only from the portfolio data already loaded: historical return, drawdown, diversification, balance-sheet leverage and allocation-weighted fundamentals. It is not a forecast or investment advice.</p>
        </section>`);
}

function renderRolling(root, rolling) {
    const windows = [
        { key: "1Y", data: rolling[1] },
        { key: "3Y", data: rolling[3] },
        { key: "5Y", data: rolling[5] },
    ].filter(w => w.data);
    if (!windows.length) return;

    const first = windows[0];
    root.insertAdjacentHTML("beforeend", `
        <section class="stock-section portfolio-analysis-section spa-rolling-section">
          <div class="stock-section-header"><div><h2>Rolling Performance</h2><span>Overlapping annualized returns from the existing price history</span></div><span class="spa-rolling-badge">CONSISTENCY</span></div>
          <div class="spa-window-buttons">${windows.map((w, i) => `<button type="button" class="spa-window-btn${i === 0 ? " active" : ""}" data-window="${w.key}">${w.key}</button>`).join("")}</div>
          <div class="spa-rolling-chart-wrap"><canvas id="spa-rolling-chart"></canvas></div>
          <div class="spa-rolling-stats"></div>
          <p class="portfolio-analysis-note">Each point is the annualized return over the preceding window. With the existing stock data this is based on annual closing prices, so it is a long-term consistency view rather than a daily backtest.</p>
        </section>`);

    const section = root.querySelector(".spa-rolling-section");
    const chartCanvas = section.querySelector("#spa-rolling-chart");
    const stats = section.querySelector(".spa-rolling-stats");

    function draw(windowData) {
        if (rollingChart) { try { rollingChart.destroy(); } catch (_) {} }
        rollingChart = typeof Chart !== "undefined" ? new Chart(chartCanvas, {
            type: "line",
            data: { labels: windowData.dates, datasets: [{ label: "Rolling CAGR", data: windowData.returns, borderWidth: 2, pointRadius: 0, tension: 0.15, fill: true }] },
            options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false }, tooltip: { callbacks: { label: c => ` Rolling CAGR: ${Number(c.parsed.y).toFixed(2)}%` } } }, scales: { x: { ticks: { maxTicksLimit: 8 } }, y: { ticks: { callback: v => `${v}%` } } } }
        }) : null;
        const s = windowData.summary;
        stats.innerHTML = [
            ["Median CAGR", signedPct(s.median)], ["Average CAGR", signedPct(s.avg)],
            ["Best", signedPct(s.max)], ["Worst", signedPct(s.min)],
            ["Positive Periods", pct(s.positive_pct, 0)], ["Observations", String(s.count)]
        ].map(x => `<div class="spa-stat"><span>${esc(x[0])}</span><strong>${esc(x[1])}</strong></div>`).join("");
    }

    draw(first.data);
    section.querySelectorAll(".spa-window-btn").forEach(btn => btn.addEventListener("click", () => {
        section.querySelectorAll(".spa-window-btn").forEach(b => b.classList.toggle("active", b === btn));
        const selected = windows.find(w => w.key === btn.dataset.window);
        if (selected) draw(selected.data);
    }));
}

function renderDrawdown(root, dd) {
    if (!dd) return;
    const cards = `
      <div class="portfolio-risk-metrics">
        <div class="portfolio-risk-card"><span>Max drawdown</span><strong>${signedPct(dd.maximum_drawdown)}</strong><small>${esc(dd.max_peak_date?.slice(0,4) || "—")} peak → ${esc(dd.max_trough_date?.slice(0,4) || "—")} trough</small></div>
        <div class="portfolio-risk-card"><span>Current drawdown</span><strong>${signedPct(dd.current_drawdown)}</strong><small>${esc(dd.current_status || "—")}</small></div>
        <div class="portfolio-risk-card"><span>Longest recovery</span><strong>${dd.longest_recovery_days == null ? "Ongoing" : `${Math.round(dd.longest_recovery_days / 30.44)} mo`}</strong><small>Peak-to-recovery duration</small></div>
      </div>`;
    root.insertAdjacentHTML("beforeend", `
      <section class="stock-section portfolio-analysis-section spa-drawdown-section">
        <div class="stock-section-header"><div><h2>Drawdown &amp; Recovery</h2><span>Historical peak-to-trough and recovery behaviour</span></div><span class="portfolio-risk-badge">RISK VIEW</span></div>
        ${cards}
        <div class="portfolio-risk-chart-wrap spa-dd-chart"><canvas id="spa-drawdown-chart"></canvas></div>
        <div class="spa-episodes">${dd.episodes.slice(0, 5).map(e => `<div><strong>${signedPct(e.drawdown)}</strong><span>${esc(e.peakDate.slice(0,4))} peak → ${esc(e.troughDate.slice(0,4))} trough${e.recoveryDate ? ` → ${esc(e.recoveryDate.slice(0,4))} recovered` : " · ongoing"} </span></div>`).join("")}</div>
        <p class="portfolio-analysis-note">Drawdown uses the same annual portfolio price path already loaded for the analysis. Annual closes can understate intra-year drawdowns; dividends, taxes, costs and rebalancing are excluded.</p>
      </section>`);

    const canvas = root.querySelector("#spa-drawdown-chart");
    if (canvas && typeof Chart !== "undefined") {
        drawdownChart = new Chart(canvas, {
            type: "line",
            data: { labels: dd.series.map(p => p.date), datasets: [{ label: "Drawdown", data: dd.series.map(p => p.drawdown), borderWidth: 1.5, pointRadius: 0, tension: 0, fill: true }] },
            options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false }, tooltip: { callbacks: { label: c => ` Drawdown: ${Number(c.parsed.y).toFixed(2)}%` } } }, scales: { x: { ticks: { maxTicksLimit: 8 } }, y: { ticks: { callback: v => `${v}%` } } } }
        });
    }
}

function renderAnalytics(payload) {
    const root = document.getElementById("portfolio-analysis-results");
    if (!root || !payload) return;
    const old = document.getElementById("stock-portfolio-advanced-analytics");
    if (old) old.remove();
    destroyCharts();

    // Render the advanced sections as DIRECT children of the results container.
    // The existing Stock Portfolio UI enhancer recognises direct
    // .portfolio-analysis-section elements and turns them into the same
    // collapsible cards as the rest of the builder. Keeping these sections
    // direct also makes their placement predictable on mobile.
    const wrapper = document.createElement("div");

    const rows = Array.isArray(payload.rows) ? payload.rows : [];
    const chartsBySymbol = payload.chartsBySymbol instanceof Map
        ? payload.chartsBySymbol
        : new Map(Object.entries(payload.chartsBySymbol || {}));
    const priceMaps = buildAnnualPriceMap(rows, chartsBySymbol);
    const path = buildPortfolioPath(rows, priceMaps);
    const drawdown = calculateDrawdown(path);
    const rolling = path ? {
        1: rollingWindow(path, 1),
        3: rollingWindow(path, 3),
        5: rollingWindow(path, 5),
    } : {};
    const health = calculateHealth(rows, path, drawdown);

    renderHealth(wrapper, health);
    renderRolling(wrapper, rolling);
    renderDrawdown(wrapper, drawdown);

    // Put the new analytics immediately after Portfolio Performance so users
    // do not have to scroll through the lower portfolio sections to find them.
    const performance = [...root.children].find(section =>
        String(section.querySelector?.("h2")?.textContent || "").trim() === "Portfolio Performance"
    );
    const nodes = [...wrapper.childNodes];
    if (performance?.parentNode === root) {
        let anchor = performance;
        nodes.forEach(node => {
            root.insertBefore(node, anchor.nextSibling);
            anchor = node;
        });
    } else {
        nodes.forEach(node => root.appendChild(node));
    }
}

window.addEventListener("stock-portfolio-analysis-ready", event => {
    const payload = event.detail;
    renderAnalytics(payload);
});
