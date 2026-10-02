# Stock Analysis — Implementation & Parameter Reference

## 1. Purpose

Stock Analysis is the application's stock-screening, individual-company analysis, and side-by-side comparison module. It uses the loaded Nifty Total Market source universe and lets the user refine the universe, select a stock, analyse it, and optionally compare it with other selected stocks.

This document describes the implementation currently exposed by the application. It is intentionally source-aware: a field is documented as available only where the underlying provider supplies a usable value.

## 2. Stock Universe

The selector uses the **Nifty Total Market** source universe represented by:

- Nifty 500.
- Nifty Microcap 250.

The resulting universe is broader than a large-cap-only universe and is classified into:

- Large Cap
- Mid Cap
- Small Cap
- Micro Cap

The displayed result list is paginated for presentation, but filtering is performed against the loaded universe before pagination. A sector selection therefore is **not** limited to stocks appearing on page 1.

## 3. Selector Controls

### 3.1 Sector

**Sector** is a multi-select control. Multiple selected sectors use OR semantics: a stock is retained when its sector matches any selected sector.

### 3.2 Search

**Search company or symbol** performs local refinement against the loaded universe. It is intended for company-name and ticker/symbol discovery.

### 3.3 Market-cap presets

The quick market-cap controls are:

- **Large Cap**
- **Mid Cap**
- **Small Cap**
- **Micro Cap**

They refine the currently loaded universe and do not intentionally reload the entire backend universe for every click.

### 3.4 Filter Results

The **Filter Results** bar is independently collapsible. Sector, Search and market-cap controls remain outside the collapsible results body so that they remain usable when the detailed fundamental filters are hidden.

## 4. Fundamental Range Filters

The detailed Stock Analysis filter set currently contains the following range parameters. Each parameter has a minimum and maximum input; an empty boundary means that side of the range is not constrained.

| API / field parameter | UI label | Unit | Meaning |
|---|---|---:|---|
| `min_market_cap_cr` | Market Cap Min | ₹ Cr | Minimum market capitalisation |
| `max_market_cap_cr` | Market Cap Max | ₹ Cr | Maximum market capitalisation |
| `min_pe` | P/E Min | x | Minimum price-to-earnings ratio |
| `max_pe` | P/E Max | x | Maximum price-to-earnings ratio |
| `min_pb` | P/B Min | x | Minimum price-to-book ratio |
| `max_pb` | P/B Max | x | Maximum price-to-book ratio |
| `min_peg` | PEG Min | x | Minimum PEG ratio |
| `max_peg` | PEG Max | x | Maximum PEG ratio |
| `min_roe` | ROE Min | % | Minimum return on equity |
| `max_roe` | ROE Max | % | Maximum return on equity |
| `min_roa` | ROA Min | % | Minimum return on assets |
| `max_roa` | ROA Max | % | Maximum return on assets |
| `min_debt_equity` | D/E Min | x | Minimum debt/equity |
| `max_debt_equity` | D/E Max | x | Maximum debt/equity |
| `min_current_ratio` | Current Ratio Min | x | Minimum current ratio |
| `max_current_ratio` | Current Ratio Max | x | Maximum current ratio |
| `min_ev_ebitda` | EV/EBITDA Min | x | Minimum enterprise-value-to-EBITDA |
| `max_ev_ebitda` | EV/EBITDA Max | x | Maximum enterprise-value-to-EBITDA |
| `min_ev_revenue` | EV/Revenue Min | x | Minimum enterprise-value-to-revenue |
| `max_ev_revenue` | EV/Revenue Max | x | Maximum enterprise-value-to-revenue |
| `min_dividend_yield` | Dividend Yield Min | % | Minimum dividend yield |
| `max_dividend_yield` | Dividend Yield Max | % | Maximum dividend yield |

**Quick controls and range filters are different layers:** market-cap presets are quick selectors, while the range fields are explicit fundamental constraints applied when **Apply Filters** is used.

The selector displays **Apply Filters** and **Clear Filters** actions. Clear Filters removes the detailed range constraints; it does not intentionally erase the stock universe itself.

## 5. Selection → Analysis → Comparison

The workflow is deliberately separate:

1. Click **Select** on a stock result.
2. The stock becomes the **Selected Stock** on the left.
3. The same stock is automatically added to the **Compare Stocks** staging list.
4. The user may remove it from the comparison list later.
5. Clicking **Analyze Stock** opens the individual stock analysis view for the selected stock.
6. Comparison is a separate action and requires the appropriate number of staged stocks.

Selecting a result should not directly navigate away from the selector.

## 6. Individual Stock Summary

The individual analysis view can display the following company-level fields where supplied:

- Exchange
- Symbol
- Company name
- Sector
- Industry
- Country
- Current price
- Currency
- Market Cap
- Enterprise Value
- Latest Revenue
- Latest Net Profit
- Latest EBITDA
- Latest Free Cash Flow
- Data-as-of date
- Source
- Data warnings / notes

Financial statement values can be displayed in the source/international B/T representation or, for INR companies, in **₹ Cr**.

## 7. Valuation Metrics

The Valuation group contains:

| Parameter | Display label | Unit | Description |
|---|---|---:|---|
| `pe` | P/E | x | Price relative to earnings per share |
| `forward_pe` | Forward P/E | x | Price relative to forward earnings expectation supplied by supplemental market data |
| `pb` | Price / Book | x | Price relative to book value per share |
| `ps` | Price / Sales | x | Price relative to sales |
| `peg` | PEG | x | P/E relative to the supported earnings-growth measure |
| `ev_ebitda` | EV / EBITDA | x | Enterprise value relative to EBITDA |
| `ev_revenue` | EV / Revenue | x | Enterprise value relative to revenue |
| `dividend_yield` | Dividend Yield | % | Dividend yield |
| `payout_ratio` | Payout Ratio | % | Portion of earnings distributed as dividends |

Where the application can show the PEG calculation note, it uses the implemented relationship **P/E ÷ 3Y EPS CAGR**.

## 8. Profitability Metrics

| Parameter | Display label | Unit | Description |
|---|---|---:|---|
| `roe` | ROE | % | Return on shareholders' equity |
| `roa` | ROA | % | Return on assets |
| `gross_margin` | Gross Margin | % | Gross profit as a percentage of revenue |
| `operating_margin` | Operating Margin | % | Operating profit as a percentage of revenue |
| `profit_margin` | Net Margin | % | Net profit as a percentage of revenue |

## 9. Financial Health Metrics

| Parameter | Display label | Unit | Description |
|---|---|---:|---|
| `debt_equity` | Debt / Equity | x | Debt relative to shareholders' equity |
| `current_ratio` | Current Ratio | x | Current assets relative to current liabilities |
| `quick_ratio` | Quick Ratio | x | More liquid current assets relative to current liabilities |
| `beta` | Beta | number | Supplemental market-sensitivity measure relative to the market benchmark |

Debt / Equity is a first-class metric used in individual analysis, screening where the corresponding range parameters are present, and comparison.

## 10. Growth Metrics

The Growth group contains:

| Parameter | Display label | Unit |
|---|---|---:|
| `revenue_growth` | Revenue Growth | % |
| `profit_growth` | Profit Growth | % |
| `eps_growth` | EPS Growth | % |
| `revenue_cagr_3y` | Revenue CAGR 3Y | % |
| `revenue_cagr_5y` | Revenue CAGR 5Y | % |
| `profit_cagr_3y` | Profit CAGR 3Y | % |
| `profit_cagr_5y` | Profit CAGR 5Y | % |
| `eps_cagr_3y` | EPS CAGR 3Y | % |
| `eps_cagr_5y` | EPS CAGR 5Y | % |
| `fcf_cagr_3y` | FCF CAGR 3Y | % |
| `fcf_cagr_5y` | FCF CAGR 5Y | % |
| `operating_margin_change` | Operating Margin Change | percentage points (pp) |

CAGR is an annualised historical growth measure. It is descriptive of the selected historical period and is not a forecast.

## 11. Financial Statements

The report contains three statement tabs:

- **Income Statement**
- **Balance Sheet**
- **Cash Flow**

The statement renderer derives the displayed row names from the returned provider fields and displays annual periods. EPS-like fields are displayed as numeric per-share values; other financial statement values follow the selected financial display convention.

The financial-unit selector is:

- **B / T** — international/broad financial-unit display.
- **₹ Cr** — Indian crore representation when the underlying company currency is INR.

## 12. Historical Charts

The Stock Analysis implementation includes historical stock trend/price data and valuation-trend visualisations where the source provides sufficient observations. Supported valuation history includes:

- Historical P/E trend.
- Historical P/B trend.
- Historical price/performance trend data.

Charts are historical/descriptive. They are not forecasts and do not manufacture future prices or returns.

## 13. Comparison

The comparison view uses the same source-aware fundamental model as individual analysis. Core comparison metrics include valuation, profitability, financial-health and growth measures, including Debt / Equity. Comparison is intended to put the same metrics side-by-side rather than recomputing them with a different methodology.

The comparison UI also distinguishes metrics where lower values are generally preferable (for example P/E, P/B, PEG, EV multiples and Debt / Equity) from metrics where higher values are generally preferable (for example dividend yield, ROE, ROA, margins, liquidity ratios and supported growth measures). This is presentation guidance rather than an investment recommendation.

## 14. Data Sources

### Primary fundamental source

**Screener** is the primary Indian fundamental-data source for company financials and ratios.

### Supplemental market source

**Yahoo Finance** is supplemental and is used for market-data fields such as Forward P/E and Beta where available.

The application keeps source roles distinct rather than silently replacing one provider's value with another provider's value.

## 15. Missing and Non-Meaningful Values

The UI distinguishes:

- **N/M — Not Meaningful** — the metric does not meaningfully apply to the company's financial model. This is especially relevant to certain enterprise-value metrics for financial companies.
- **Unavailable / missing** — the source did not provide a usable value.
- **Data Notes** — source/warning information is shown at the bottom of the analysis report.

A missing value is not silently replaced with an invented estimate.

## 16. Performance and Stability

The selector is designed so that quick filter changes operate against the loaded universe whenever possible. Identical lightweight universe requests are coalesced, and the filter UI avoids MutationObserver feedback loops and repeated full-page DOM rebuilds.

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

The in-application Help & Methodology page is intended to expose the same terminology as this document, including every selector control, fundamental filter, displayed ratio, growth metric, financial statement, chart, comparison field, source convention, and missing-data convention.

The detailed UI help should be treated as the user-facing version of this implementation reference; this file is the repository-level engineering reference.

## 18. Company Pedigree, Consistency & Trend Analytics

The individual report now includes a separate historical analytics section built from the same Screener financial statements rather than copying additional headline ratios.

### 18.1 Growth consistency

For Revenue, Net Profit, EPS and Free Cash Flow, the engine counts the available year-over-year observations and reports the percentage of observations with positive growth. This is a descriptive consistency statistic, not a forecast.

### 18.2 Capital-efficiency history

The report charts annual:

- ROE = Net Profit ÷ Average Shareholders' Equity × 100.
- ROCE = Operating Profit ÷ (Net Block + Working Capital) × 100, where Working Capital = Current Assets − Current Liabilities.
- Operating Margin = Operating Profit ÷ Revenue × 100.

Average ROE and ROE volatility are also shown as compact historical diagnostics.

### 18.3 Cash-generation quality

The report charts:

- CFO / Net Profit = Cash from Operating Activities ÷ Net Profit × 100.
- FCF Margin = Free Cash Flow ÷ Revenue × 100.
- Indexed Revenue, Net Profit and FCF, with each series starting at 100 at its first positive observation.

These measures help distinguish accounting earnings growth from cash-generation growth.

### 18.4 Leverage and working capital

Debt is charted historically from the reported balance sheet. The Cash Conversion Cycle is derived as:

**CCC = Debtor Days + Inventory Days − Payable Days**

where each day metric uses the relevant annual balance divided by revenue and multiplied by 365.

### 18.5 Historical shareholding

The report reads Screener's Shareholding Pattern and charts Promoters, FIIs, DIIs, Government and Public holdings where available, plus the number of shareholders. The data can include quarterly and longer annual observations.

Screener notes that shareholding classifications may have changed from September 2022 following the XBRL format change. Historical FII/DII comparisons therefore carry that source limitation.

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

The purpose is to compare **trajectory and consistency**, not merely the latest point-in-time ratio.

## 20. Source and Calculation Discipline

Pedigree analytics are explicitly calculated from Screener financial statements and shareholding tables. They are not presented as additional Screener-provided ratios. Where a calculation uses a methodology that can differ from another provider's convention, the application describes the formula rather than silently substituting a different value.

Missing source observations remain missing. No historical ownership, earnings, cash-flow or trend value is invented to complete a chart.
