const esc = (v) => String(v ?? "—").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/\"/g, "&quot;");
const number = (v) => v == null || Number.isNaN(Number(v)) ? "—" : Number(v).toLocaleString("en-IN", { maximumFractionDigits: 2 });
const pct = (v) => v == null || Number.isNaN(Number(v)) ? "—" : `${Number(v).toFixed(2)}%`;
const money = (v) => v == null ? "—" : number(v);

function metric(label, value) {
    return `<div class="stock-metric"><span>${esc(label)}</span><strong>${esc(value)}</strong></div>`;
}

function table(title, rows) {
    return `<section class="stock-card"><h3>${esc(title)}</h3>${rows?.length ? `<div class="stock-table-wrap"><table class="stock-table"><thead><tr><th>Period</th><th>Metrics</th></tr></thead><tbody>${rows.map(r => `<tr><td>${esc(r.period)}</td><td>${esc(Object.entries(r.values || {}).map(([k,v]) => `${k}: ${number(v)}`).join(" · "))}</td></tr>`).join("")}</tbody></table></div>` : `<p class="pb-page-note">No historical data returned.</p>`}</section>`;
}

function render(data) {
    const f = data.fundamentals || {};
    const growth = (v) => v == null ? "—" : pct(Number(v) * 100);
    const kpis = [
        metric("Price", number(f.price)), metric("Market Cap", money(f.market_cap)),
        metric("P/E", number(f.pe)), metric("Forward P/E", number(f.forward_pe)),
        metric("P/B", number(f.pb)), metric("EV / EBITDA", number(f.ev_ebitda)),
        metric("ROE", pct(f.roe)), metric("Operating Margin", pct(f.operating_margin)),
        metric("Net Margin", pct(f.profit_margin)), metric("Debt / Equity", number(f.debt_equity)),
        metric("Free Cash Flow", money(f.free_cash_flow)), metric("Dividend Yield", pct(f.dividend_yield))
    ].join("");

    const trendRows = [
        ["Revenue CAGR", growth(f.revenue_cagr_3y), growth(f.revenue_cagr_5y)],
        ["Profit CAGR", growth(f.profit_cagr_3y), growth(f.profit_cagr_5y)],
        ["EPS CAGR", growth(f.eps_cagr_3y), growth(f.eps_cagr_5y)],
        ["FCF CAGR", growth(f.fcf_cagr_3y), growth(f.fcf_cagr_5y)],
        ["Operating margin change", pct(f.operating_margin_change), "available history"]
    ].map(r => `<tr><td>${esc(r[0])}</td><td>${esc(r[1])}</td><td>${esc(r[2])}</td></tr>`).join("");

    return `
      <section class="stock-card stock-hero"><div><span class="stock-kicker">${esc(f.exchange || "Yahoo Finance")}</span><h2>${esc(f.name || f.symbol)}</h2><p>${esc(f.symbol)} · ${esc(f.sector || "Sector unavailable")} · ${esc(f.industry || "Industry unavailable")}</p></div><div class="stock-data-date">Data as of ${esc(f.data_as_of)}</div></section>
      <section class="stock-kpi-grid">${kpis}</section>
      <section class="stock-card"><h3>Growth & Trend</h3><div class="stock-table-wrap"><table class="stock-table"><thead><tr><th>Metric</th><th>3Y</th><th>5Y</th></tr></thead><tbody>${trendRows}</tbody></table></div></section>
      <div class="stock-two-col">${table("Income Statement", data.income_statement)}${table("Balance Sheet", data.balance_sheet)}</div>
      ${table("Cash Flow", data.cash_flow)}
      <section class="stock-card stock-warning"><h3>Data Notes</h3><ul>${(data.warnings || []).map(w => `<li>${esc(w)}</li>`).join("")}</ul></section>`;
}

export function initStockAnalysis() {
    const input = document.getElementById("stock-symbol");
    const button = document.getElementById("analyze-stock");
    const content = document.getElementById("stock-analysis-content");
    const status = document.getElementById("stock-analysis-status");
    if (!input || !button || !content) return;

    async function analyze() {
        const symbol = input.value.trim();
        if (!symbol) return;
        button.disabled = true;
        status.textContent = "Loading Yahoo Finance data…";
        content.innerHTML = "";
        try {
            const response = await fetch(`/api/stocks/${encodeURIComponent(symbol)}`);
            const payload = await response.json();
            if (!response.ok) throw new Error(payload.detail || "Stock analysis failed.");
            content.innerHTML = render(payload);
            status.textContent = "";
        } catch (error) {
            status.textContent = error.message;
        } finally {
            button.disabled = false;
        }
    }

    button.addEventListener("click", analyze);
    input.addEventListener("keydown", e => { if (e.key === "Enter") analyze(); });
}
