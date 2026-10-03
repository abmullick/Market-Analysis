# Stock Analysis — Implementation & Parameter Reference

## 1. Purpose

Stock Analysis is the application's stock-screening, individual-company analysis, and side-by-side comparison module. It uses the loaded Nifty Total Market source universe and lets the user refine the universe, select a stock, analyse it, and optionally compare it with other selected stocks.

This document describes the implementation currently exposed by the application. It is intentionally data-aware: a field is documented as available only where the underlying data provides a usable value.

## 2. Stock Universe

The selector uses the **Nifty Total Market** source universe represented by Nifty 500 and Nifty Microcap 250. The resulting universe is classified into Large Cap, Mid Cap, Small Cap and Micro Cap.

## 3. Selector Controls

### Sector
Sector is a multi-select control. Multiple selected sectors use OR semantics.

### Search
Search company or symbol performs local refinement against the loaded universe.

### Market-cap presets
Large Cap, Mid Cap, Small Cap and Micro Cap refine the loaded universe.

### Filter Results
The Filter Results bar is independently collapsible. Sector, Search and market-cap controls remain usable when detailed filters are hidden.

## 4. Fundamental Range Filters

The detailed Stock Analysis filter set contains minimum and maximum boundaries for Market Cap, P/E, P/B, PEG, ROE, ROA, Debt / Equity, Current Ratio, EV / EBITDA, EV / Revenue and Dividend Yield. An empty boundary means that side of the range is not constrained.

Quick market-cap controls and range filters are separate layers. Clear Filters removes detailed range constraints without intentionally erasing the stock universe.

## 5. Selection → Analysis → Comparison

1. Click Select on a stock result.
2. The stock becomes the Selected Stock.
3. The same stock is automatically added to Compare Stocks.
4. The user may remove it from comparison later.
5. Analyze Stock opens the individual report.
6. Comparison is a separate action for the staged stocks.

## 6. Individual Stock Summary

The individual analysis view can display Exchange, Symbol, Company name, Sector, Industry, Country, Current price, Currency, Market Cap, Enterprise Value, Latest Revenue, Latest Net Profit, Latest EBITDA, Latest Free Cash Flow, data-as-of information and data notes where available.

Financial statement values can be displayed in international B/T representation or, for INR companies, in ₹ Cr.

## 7. Valuation Metrics

The Valuation group contains P/E, Forward P/E, Price / Book, Price / Sales, PEG, EV / EBITDA, EV / Revenue, Dividend Yield and Payout Ratio where meaningful.

PEG uses the implemented relationship **P/E ÷ 3Y EPS CAGR** when the required values are available.

## 8. Profitability Metrics

The Profitability group contains ROE, ROA, Gross Margin, Operating Margin and Net Margin.

## 9. Financial Health Metrics

The Financial Health group contains Debt / Equity, Current Ratio, Quick Ratio and Beta where available. Debt / Equity is used in individual analysis, screening and comparison.

## 10. Growth Metrics

The Growth group contains Revenue Growth, Profit Growth, EPS Growth, Revenue CAGR 3Y/5Y, Profit CAGR 3Y/5Y, EPS CAGR 3Y/5Y, FCF CAGR 3Y/5Y and Operating Margin Change.

CAGR is an annualised historical growth measure and is not a forecast.

## 11. Financial Statements

The report contains Income Statement, Balance Sheet and Cash Flow tabs. Annual periods are displayed using the normalized financial statement model. EPS-like fields are displayed as numeric per-share values; other financial statement values follow the selected financial display convention.

The financial-unit selector supports B/T and ₹ Cr for INR companies.

## 12. Historical Charts

Stock Analysis includes historical price/performance and valuation-trend visualisations where sufficient observations are available. Supported valuation history includes Historical P/E and Historical P/B.

Charts are historical/descriptive. They are not forecasts and do not manufacture future prices or returns.

## 13. Comparison

The comparison view uses the same fundamental model as individual analysis. Core comparison metrics include valuation, profitability, financial health and growth measures, including Debt / Equity.

Comparison is intended to put the same metrics side-by-side rather than recomputing them with a different methodology.

## 14. Data Handling

Financial and market observations are normalized through the application's data layer. Supplemental market fields such as Forward P/E and Beta are retained separately where their underlying observations are available.

The application keeps different data roles distinct rather than silently replacing one value with another.

## 15. Missing and Non-Meaningful Values

The UI distinguishes:

- **N/M — Not Meaningful** — the metric does not meaningfully apply to the company's financial model, especially certain enterprise-value metrics for financial companies.
- **Unavailable / missing** — a usable observation is not available.
- **Data Notes** — warnings and data-quality information are shown at the bottom of the analysis report.

A missing value is not silently replaced with an invented estimate.

## 16. Performance and Stability

The selector is designed so quick filter changes operate against the loaded universe whenever possible. Identical stock-API requests are coalesced, successful stock analysis/chart/pedigree responses are reused briefly within the current page, and the filter UI avoids MutationObserver feedback loops and repeated full-page DOM rebuilds.

The backend keeps blocking financial-data retrieval out of FastAPI's async event loop by running the synchronous analysis, chart and pedigree builders in worker threads. This prevents a slow external financial-data request from blocking unrelated navigation or a fresh Stock Analysis page.

When leaving the page, outstanding stock-API requests are aborted so an abandoned analysis does not continue competing with the next selection view.

The intended architecture is:

```text
Loaded stock universe
        ↓
Sector / Search / Market-cap refinement
        ↓
Fundamental range filtering
        ↓
Pagination for display
        ↓
Select → Selected Stock + Compare Stocks
        ↓
Analyze Stock → Individual report
        ↓
Shared/coalesced analysis requests
        ↓
Historical / quality / pedigree enhancements
```

## 17. Help & Methodology

The in-application Help & Methodology page is the user-facing reference for selector controls, fundamental filters, displayed ratios, growth metrics, financial statements, charts, comparison fields and missing-data conventions.

## 18. Company Pedigree, Consistency & Trend Analytics

The individual report includes a separate historical analytics section built from the same normalized financial statements and ownership observations.

### 18.1 Growth consistency

For Revenue, Net Profit, EPS and Free Cash Flow, the engine counts available year-over-year observations and reports the percentage with positive growth. This is a descriptive consistency statistic, not a forecast.

### 18.2 Capital-efficiency history

The report charts annual:

- ROE = Net Profit ÷ Average Shareholders' Equity × 100.
- ROCE = Operating Profit ÷ (Net Block + Working Capital) × 100.
- Working Capital = Current Assets − Current Liabilities.
- Operating Margin = Operating Profit ÷ Revenue × 100.

Average ROE and ROE volatility are also shown as compact historical diagnostics.

### 18.3 Cash-generation quality

The report charts:

- CFO / Net Profit = Cash from Operating Activities ÷ Net Profit × 100.
- FCF Margin = Free Cash Flow ÷ Revenue × 100.
- Indexed Revenue, Net Profit and FCF, with each series starting at 100 at its first positive observation.

These measures help distinguish accounting earnings growth from cash-generation growth.

### 18.4 Leverage and working capital

Debt is charted historically. The Cash Conversion Cycle is derived as:

**CCC = Debtor Days + Inventory Days − Payable Days**

where each day metric uses the relevant annual balance divided by revenue and multiplied by 365.

### 18.5 Historical shareholding

The report charts Promoters, FIIs, DIIs, Government and Public holdings where available, plus the number of shareholders. Quarterly and longer annual observations can be shown.

The chart is presented as an ordinary analysis metric and focuses on the historical ownership trajectory.

## 19. Pedigree Analytics in Comparison

The same derived engine is applied independently to every selected stock in Compare. The comparison trend area includes:

- Indexed business scale.
- ROE / ROCE history.
- Operating Margin history.
- FCF Margin history.
- Debt history.
- Promoter holding history.
- Institutional holding history (FII + DII).
- Shareholder-count history.

The purpose is to compare trajectory and consistency, not merely the latest point-in-time ratio.

## 20. Earnings Quality

The individual and comparison views include a dedicated Earnings Quality panel.

### 20.1 Profit versus cash generation

Historical Net Profit, Operating Cash Flow and Free Cash Flow are indexed to 100 at their first positive observation so their trajectories can be compared directly.

### 20.2 Cash conversion

The engine calculates:

- **CFO / Net Profit** = Operating Cash Flow ÷ Net Profit × 100.
- **FCF / Net Profit** = Free Cash Flow ÷ Net Profit × 100.
- **CFO / Profit CAGR gap** = CFO CAGR − Net Profit CAGR.
- **FCF / Profit CAGR gap** = FCF CAGR − Net Profit CAGR.

These measures show whether cash generation has kept pace with accounting profit over time.

## 21. Capital Allocation & Reinvestment

The report includes historical capital-deployment indicators:

- Operating Cash Flow.
- Capital Expenditure.
- Free Cash Flow.
- Capex / Operating Cash Flow.
- Capex / Revenue.
- FCF / Operating Cash Flow.
- Debt trajectory and annual debt change.

Capex is treated by absolute value when calculating intensity because capital expenditure may be represented as a negative cash-flow number. The charts help show how much internally generated cash is being reinvested in the business and how funding requirements have evolved.

## 22. EPS Quality & Dilution

When annual Net Profit and diluted EPS are both available, the engine calculates an **implied share count**:

**Implied Shares = Net Profit ÷ Diluted EPS**

With Net Profit expressed in ₹ crore and EPS in ₹ per share, the resulting share count is expressed in crore shares.

The analysis then shows:

- Implied share-count history.
- Share-count growth.
- 3Y and 5Y share-count CAGR.
- EPS CAGR.
- Profit CAGR minus EPS CAGR.

This helps identify whether per-share growth is keeping pace with overall profit growth. The implied share count is a historical analytical proxy and is shown only when the required observations are available.

## 23. Quality Comparison

Compare contains the same three analytical areas for every selected company:

- Profit versus cash-generation trajectory.
- CFO / Profit and FCF / Profit conversion.
- Capital intensity.
- Share-count growth.
- Profit growth versus EPS growth.
- 3Y/5Y cash-generation and dilution gaps.

All selected companies use the same formulas and observation rules, making the charts directly comparable.

## 24. Calculation Discipline

Historical analytics are calculated from normalized financial statements and ownership tables. They are presented as ordinary application metrics with transparent formulas.

Missing observations remain missing. No historical ownership, earnings, cash-flow or trend value is invented to complete a chart.

## 25. AI Insights

Both the individual Stock Analysis report and the Compare view provide an **AI Insights** action using the same shared AI architecture used elsewhere in the application.

### 25.1 Individual analysis

The AI receives a compact context containing the displayed fundamentals, deterministic derived metrics and a bounded historical trend. It returns:

- Summary.
- Key Points.
- Risks.
- Opportunities.
- Recommendation / next-step context.

The AI interprets the existing analysis; it does not calculate new metrics, create a score, or replace the application's deterministic values.

### 25.2 Stock comparison

Compare sends a bounded context for the selected companies and asks the AI to explain the supplied business-quality, growth, cash-generation, financial-health, capital-efficiency and valuation trade-offs. It does not create a new numerical ranking or score.

### 25.3 Reliability and privacy boundaries

AI requests use a compact payload with an explicit size guard. Provider credentials remain server-side. If the AI service is unavailable, the deterministic Stock Analysis report remains usable and the AI section exposes a retry action.

## 26. Desktop Presentation

The application uses a normal **100% desktop presentation scale** by default. Responsive layouts continue to apply on smaller screens.

## 27. Sector-aware Valuation Context

The individual report now contains a dedicated historical valuation-context engine. It does not attempt to estimate intrinsic value. Instead, it asks how the current valuation multiple compares with the company's own historical range.

### 27.1 Historical reference

For P/E and P/B, the engine takes the available positive historical observations and calculates the median. The current P/E/P/B is then compared with that company-specific median.

### 27.2 Component score

For a multiple M and historical median H:

**Relative Valuation Score = clamp(50 + ((H − M) / H) × 100)**

50 means the current multiple is at its own historical median. A score above 50 means the current multiple is lower than the median; a score below 50 means it is higher.

### 27.3 Business-type weighting

The engine changes the weighting by business type:

- **Financial-services lens:** P/B 70%, P/E 30%.
- **Capital-intensive lens:** P/E 60%, P/B 40%.
- **Operating-business lens:** P/E 70%, P/B 30%.

The final Valuation Context score is the weighted average of available component scores. If one component is unavailable, the remaining weights are normalized. The timeline reconstructs the same framework for earlier observations using the company's historical median as the reference.

This is descriptive historical context. It is not a peer-relative valuation, intrinsic-value estimate, return forecast, or investment recommendation.

## 28. Fundamental Momentum Index

Fundamental Momentum is a 0–100 measure of the direction of the company's underlying business trajectory. It is separate from market-price momentum.

### 28.1 Core trend scoring

For each supported trend series, the engine compares the latest three-year average with the preceding three-year average.

**Component Score = clamp(50 + (Recent 3Y Average − Previous 3Y Average) / Scale × 50)**

A scale of 8 is used for growth-rate series such as Revenue Growth, Profit Growth and EPS Growth. A scale of 5 is used for ROE and ROCE. A scale of 20 is used for cash-conversion measures where applicable, and 5 for FCF margin.

### 28.2 Component weights

The final index uses:

- Growth Momentum — 30%.
- Return Momentum — 25%.
- Earnings Consistency / Cash Conversion — 20%.
- Share Discipline / Balance-sheet Discipline — 15%.
- Business Consistency — 10%.

Missing components are excluded and the available weights are normalized.

### 28.3 Component definitions

**Growth Momentum** is the average of the independently scored changes in Revenue Growth, Profit Growth and EPS Growth.

**Return Momentum** is the average of scored changes in ROE and ROCE.

For financial services, **Earnings Consistency** combines positive-growth persistence and ROE stability. For operating businesses, the 20% quality component uses Cash Conversion and FCF Margin trend.

For financial services, **Share Discipline** uses historical share-count CAGR. Stable or declining share count scores higher; share-count expansion reduces the score. For operating businesses, **Balance-sheet Discipline** uses the direction of Debt and Debt / Equity relative to their recent levels; falling leverage scores higher and rising leverage scores lower.

**Business Consistency** combines positive-growth persistence with ROE stability. Growth persistence is the average percentage of available annual Revenue, Profit and FCF observations with positive growth. ROE stability is:

**ROE Stability Score = clamp(100 − ROE Volatility × 10)**

where ROE Volatility is the population standard deviation of the available annual ROE observations.

### 28.4 Interpretation

- **65–100:** Strengthening.
- **45–64:** Stable.
- **0–44:** Weakening.

The Momentum Index is a historical trajectory indicator. It is not a price signal, forecast or investment recommendation.

## 29. Fundamental Trend Timeline

The individual report reconstructs the Momentum Index at earlier historical points rather than storing historical Momentum values.

At each historical point, only observations available up to that point are used. The same three-year-versus-preceding-three-year comparison, component scoring and weights are applied. The most recent timeline point should therefore broadly correspond to the current Momentum Index, although differences can occur when newer data or different component availability is present.

## 30. Quality × Growth × Valuation

The decision lens connects three dimensions that are normally viewed separately.

### 30.1 Operating-business lens

For operating businesses the primary relationship is:

**P/E × ROE × 3Y Earnings CAGR**

P/E is the valuation anchor, ROE is the quality anchor, and 3Y earnings CAGR is the growth anchor.

### 30.2 Financial-services lens

For banks, NBFCs, insurers and similar financial-services businesses the relationship becomes:

**P/B × ROA × 3Y Earnings CAGR**

Debt is not treated as ordinary industrial leverage for this lens because borrowings are part of the operating model.

### 30.3 Earnings CAGR

Where annual statement history supports it:

**3Y Earnings CAGR = ((Ending Earnings / Starting Earnings) ^ (1 / 3) − 1) × 100**

The implementation prefers a stable annual profit CAGR and uses supported EPS CAGR as a fallback where appropriate. Starting and ending values must be positive for the CAGR calculation.

## 31. Growth Funding & Capital Efficiency

For operating businesses the engine examines whether earnings growth is broadly consistent with internally retained earnings and then displays observable funding evidence.

### 31.1 Retained-earnings capacity

**Retained-Earnings Capacity = ROE × (1 − Payout Ratio)**

Payout Ratio is bounded to 0–100% for this calculation, so retention is the complementary percentage.

### 31.2 Growth gap

**Growth Gap = 3Y Earnings CAGR − Retained-Earnings Capacity**

A positive gap means historical earnings growth is above the simple retained-earnings capacity implied by current ROE and payout. It is an investigation signal only. The engine does not infer that a company raised debt or equity without observable evidence.

### 31.3 Funding evidence

Where data exists, the report also shows:

- Debt CAGR over 3 years.
- Asset CAGR over 3 years.
- Equity/book-value CAGR over 3 years.
- Operating Cash Flow CAGR over 3 years.
- Free Cash Flow CAGR over 3 years.
- Debt / Equity.
- Interest Coverage.
- Net Debt / EBITDA.
- Share-count CAGR.

For financial services, the panel instead emphasizes asset growth, book growth, earnings growth and share-count movement and avoids interpreting debt as industrial leverage.

## 32. Shareholding Intelligence

Shareholding Intelligence is a separate historical ownership lens built from the same shareholding observations used by the pedigree section.

### 32.1 Latest ownership

The latest available observation is displayed for Promoters, FIIs, DIIs, Government and Public shareholders. Institutional ownership is:

**Institutional Ownership = FII Holding + DII Holding**

### 32.2 Historical change

For a selected period:

**Ownership Change (percentage points) = Latest Holding − Historical Holding**

The 1Y and 3Y controls select the historical observation closest to one or three calendar years before the latest observation. The All control compares the latest with the earliest available observation.

The panel describes ownership movement. It does not infer buying intent, selling intent, conviction or causality from the ownership changes.

## 33. Advanced Stock Comparison

Compare now reuses the individual stock engines independently for every selected company.

### 33.1 Business–Valuation Matrix

Each stock is plotted using:

- X-axis = Valuation Context, where 0 means above the company's own historical valuation, 50 means near its own history and 100 means below its own history.
- Y-axis = Fundamental Momentum, from 0 to 100.

No combined score is created. The matrix is a visualization of two independent historical indicators.

### 33.2 Stock Comparison Summary

The summary reports the observed Momentum and Valuation Context ranges across the selected stocks and identifies the strongest and weakest available Momentum components for each company. It reuses the same individual calculations and does not create a new ranking.

### 33.3 Comparison calculation consistency

The comparison cards call the same `buildMomentum` engine and the same historical valuation-context logic used by the individual report. This prevents the comparison view from silently using a different formula or weighting model.

## 34. Help & Methodology Coverage

The in-application Help & Methodology page has been expanded to document the new Stock Analysis engines. New formula cards cover Sector-aware Valuation Context, Fundamental Momentum, Momentum Consistency & Stability, Fundamental Trend Timeline, Quality × Growth × Valuation, Growth Funding & Capital Efficiency, Shareholding Intelligence, Business–Valuation Matrix and Stock Comparison Summary.

The Help search indexes visible cards and metric accordions. Searching for a new metric or formula opens the matching collapsible card and highlights it. The formulas shown in Help are intended to match the calculations implemented by the frontend engines and the normalized data model.
