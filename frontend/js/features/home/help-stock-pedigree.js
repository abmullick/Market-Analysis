function addStockPedigreeHelp() {
    const section = [...document.querySelectorAll(".help-section")].find((candidate) => {
        const heading = candidate.querySelector("h2, h3");
        return heading && heading.textContent.trim() === "Stock Analysis";
    });
    if (!section || section.dataset.pedigreeHelpAdded === "true") return;
    const grid = section.querySelector(".help-grid");
    if (!grid) return;

    const cards = [
        ["Company Pedigree & Consistency", "The individual Stock Analysis report includes historical diagnostics covering revenue, profit and free-cash-flow consistency, average ROE, ROE volatility and debt movement. These are descriptive statistics, not a forecast or investment score."],
        ["Historical Shareholding Pattern", "Shareholding history is displayed by observation date for Promoters, FIIs, DIIs, Government and Public shareholders where available. The chart helps identify changes in ownership structure rather than relying only on the latest period."],
        ["Business Scale & Cash Generation Trend", "Revenue, Net Profit and Free Cash Flow are shown as indexed series. Each series starts at 100 at its first positive observation, making long-term growth trajectories comparable even though the underlying rupee amounts differ."],
        ["ROE / ROCE / Margin Trend", "Annual ROE is Net Profit divided by average shareholders' equity. ROCE is Operating Profit divided by invested capital, where invested capital is Net Block plus working capital. Operating Margin is Operating Profit divided by Revenue. Historical trends reveal whether returns and margins are persistent or changing."],
        ["Cash Conversion & FCF Margin Trend", "CFO / Net Profit measures how much reported profit is being converted into operating cash. FCF Margin is Free Cash Flow divided by Revenue. These trends help distinguish accounting profit growth from cash-generation quality."],
        ["Debt & Working Capital Trend", "Debt is tracked historically from the balance sheet. The Cash Conversion Cycle is calculated as Debtor Days + Inventory Days − Payable Days, with each day metric based on the corresponding balance relative to annual revenue. A rising cycle can indicate that more cash is tied up in working capital."],
        ["Shareholder Base Trend", "The number of shareholders is charted historically. Changes can provide context for ownership dispersion and participation, but they should not be treated as a direct measure of business quality."],
        ["Earnings Quality", "The report compares Net Profit, Operating Cash Flow and Free Cash Flow over time using indexed charts. CFO / Net Profit and FCF / Net Profit show cash conversion, while the 3Y/5Y CAGR gaps show whether cash generation has kept pace with accounting profit."],
        ["Capital Allocation & Reinvestment", "Historical Capital Expenditure, Operating Cash Flow and Free Cash Flow are shown together with Capex / CFO, Capex / Revenue, FCF / CFO and debt movement. These measures help explain reinvestment intensity and how funding requirements have changed over time."],
        ["EPS Quality & Dilution", "When Net Profit and diluted EPS are available, the engine estimates historical share count as Net Profit divided by diluted EPS. Share-count CAGR and the difference between profit CAGR and EPS CAGR help identify whether dilution or share-count changes have affected per-share growth."],
        ["Quality Comparison", "The same earnings-quality, capital-allocation and dilution calculations are available in Compare, allowing companies to be examined side-by-side using identical historical definitions."],
        ["Comparison Trend Charts", "The same calculations are used in Compare. Selected companies can be compared on indexed business scale, ROE/ROCE, operating margin, FCF margin, debt, promoter holding, institutional holding and shareholder count. This keeps the methodology consistent between individual and side-by-side analysis."],
        ["Ownership History", "Ownership charts are historical observations. Missing periods remain missing rather than being interpolated, and category changes over time should be considered when comparing long historical series."],
    ];

    cards.forEach(([heading, body]) => {
        if ([...grid.querySelectorAll("h4")].some((h) => h.textContent.trim() === heading)) return;
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
