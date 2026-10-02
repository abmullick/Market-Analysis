function addStockPedigreeHelp() {
    const section = [...document.querySelectorAll(".help-section")].find((candidate) => {
        const heading = candidate.querySelector("h2, h3");
        return heading && heading.textContent.trim() === "Stock Analysis";
    });
    if (!section || section.dataset.pedigreeHelpAdded === "true") return;

    const grid = section.querySelector(".help-grid");
    if (!grid) return;

    const cards = [
        ["Company Pedigree & Consistency", "The individual Stock Analysis report now includes a historical pedigree section. It describes how consistently revenue, profit and free cash flow have grown, together with average ROE, ROE volatility and long-term debt movement. These are descriptive statistics, not a forecast or investment score."],
        ["Historical Shareholding Pattern", "Shareholding history is read from Screener and displayed by observation date for Promoters, FIIs, DIIs, Government and Public shareholders where the source supplies the category. The chart helps identify changes in ownership structure rather than relying only on the latest quarter."],
        ["Business Scale & Cash Generation Trend", "Revenue, Net Profit and Free Cash Flow can be shown as indexed series. Each series starts at 100 at its first positive observation, making the long-term growth trajectory comparable even though the underlying rupee amounts differ."],
        ["ROE / ROCE / Margin Trend", "The report derives annual ROE from Net Profit divided by average shareholders' equity. ROCE is derived from Operating Profit divided by invested capital, where invested capital is Net Block plus working capital. Operating Margin is Operating Profit divided by Revenue. Historical trends reveal whether returns and margins are persistent or deteriorating."],
        ["Cash Conversion & FCF Margin Trend", "CFO / Net Profit measures how much reported profit is being converted into operating cash. FCF Margin is Free Cash Flow divided by Revenue. These trends help distinguish accounting profit growth from cash-generation quality."],
        ["Debt & Working Capital Trend", "Debt is tracked annually from the balance sheet. The Cash Conversion Cycle is calculated as Debtor Days + Inventory Days − Payable Days, with each day metric based on the corresponding balance relative to annual revenue. A rising cycle can indicate that more cash is tied up in working capital."],
        ["Shareholder Base Trend", "The number of shareholders reported by Screener is charted historically. Changes can provide context for ownership dispersion and retail participation, but they should not be treated as a direct measure of business quality."],
        ["Comparison Trend Charts", "The same derived trend engine is used in Compare. Selected companies can be compared on indexed business scale, ROE/ROCE, operating margin, FCF margin, debt, promoter holding, institutional holding (FII + DII), and shareholder count. This keeps the methodology consistent between individual and side-by-side analysis."],
        ["Shareholding Classification Note", "Screener notes that shareholding classifications may have changed from September 2022 because of the XBRL format. Historical FII/DII comparisons should therefore be interpreted with that source limitation in mind."],
    ];

    cards.forEach(([heading, body]) => {
        const exists = [...grid.querySelectorAll("h4")].some((h) => h.textContent.trim() === heading);
        if (exists) return;
        const card = document.createElement("div");
        card.className = "help-card";
        card.innerHTML = `<h4>${heading}</h4><p>${body}</p>`;
        grid.appendChild(card);
    });
    section.dataset.pedigreeHelpAdded = "true";
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", addStockPedigreeHelp, { once: true });
} else {
    addStockPedigreeHelp();
}
