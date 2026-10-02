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

The selector is designed so quick filter changes operate against the loaded universe whenever possible. Identical lightweight universe requests are coalesced, and the filter UI avoids MutationObserver feedback loops and repeated full-page DOM rebuilds.

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
```

## 17. Help & Methodology

The in-application Help & Methodology page is the user-facing reference for selector controls, fundamental filters, displayed ratios, growth metrics, financial statements, charts, comparison fields and missing-data conventions.

## 18. Company Pedigree, Consistency & Trend Analytics

The individual report includes a separate historical analytics section built from the same normalized financial statements and ownership observations rather than simply copying additional headline ratios.

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

## 20. Calculation Discipline

Pedigree analytics are calculated from the normalized financial statements and ownership tables. They are presented as application metrics with transparent formulas rather than as copied headline ratios.

Missing observations remain missing. No historical ownership, earnings, cash-flow or trend value is invented to complete a chart.
