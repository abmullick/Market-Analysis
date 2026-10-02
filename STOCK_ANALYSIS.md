# Stock Analysis — Current Implementation

## Universe

The Stock Analysis selector uses the **Nifty Total Market** source universe: Nifty 500 + Nifty Microcap 250. The universe is broader than a large-cap-only universe and contains large-, mid-, small-, and micro-cap stocks.

## Selection & Screening

The selector provides:

- Multi-select **Sector** filtering.
- Company/symbol **Search**.
- **Market Cap** presets: Large Cap, Mid Cap, Small Cap, Micro Cap.
- Liquidity controls where supplied by the current selector implementation.
- Quick local refinement of the already-loaded universe where possible.

Sector, search, and quick-cap interactions should not repeatedly rebuild the entire page or trigger unnecessary backend universe loads.

## Selection → Analysis → Compare

Selecting a stock makes it the active analysis stock and automatically adds it to the Compare Stocks list. The user can subsequently remove it from comparison.

The individual analysis page and comparison page share the same fundamental-data model so that metrics remain consistent between views.

## Individual Analysis

The analysis page includes:

- Company summary.
- Market Cap, Enterprise Value, Revenue, Net Profit, EBITDA, and Free Cash Flow where available.
- Valuation metrics: P/E, Forward P/E, Price/Book, Price/Sales, PEG, EV/EBITDA, EV/Revenue, Dividend Yield, Payout Ratio.
- Profitability metrics: ROE, ROA, Gross Margin, Operating Margin, Net Margin.
- Financial Health metrics: **Debt / Equity**, Current Ratio, Quick Ratio, Beta.
- Growth metrics and CAGR measures.
- Annual Income Statement, Balance Sheet, and Cash Flow tables.
- Historical price/performance and valuation charts, including P/E and P/B history where source data is available.
- Data Notes positioned at the bottom of the analysis page.

## Data Source Policy

### Primary fundamental source

**Screener** is the primary Indian fundamental-data source for company financials and ratios.

### Supplemental market source

**Yahoo Finance** is supplemental and is used for market-data fields that are not treated as primary Screener fundamentals, including Forward P/E and Beta where available.

The application should never silently replace unavailable source values with invented estimates.

## Missing / Non-Meaningful Values

The UI distinguishes:

- **N/M — Not Meaningful** — the metric is not meaningful for the company's financial model, particularly for financial companies where certain enterprise-value metrics are not useful.
- **Unavailable / missing** — the source did not provide a usable value.

This prevents a plain `—` from incorrectly suggesting that a metric simply failed to load when the metric is actually not meaningful for the company type.

## Debt / Equity

Debt / Equity is a first-class Stock Analysis metric and is included in:

1. Individual stock analysis → Financial Health.
2. Stock screening/range filters where applicable.
3. Stock comparison.

## Comparison

The comparison page uses the same source-aware fundamental data model as individual analysis and includes Debt / Equity with the other core metrics. Table sizing is kept consistent across metric groups.

## UI / Stability

The Stock Analysis selector has been hardened against repeated DOM mutation:

- Enhancement observers do not watch their own DOM mutations.
- Lightweight stock-universe requests are coalesced.
- Quick filters use the loaded universe when possible.
- Sector/search/cap interactions do not repeatedly rebuild the whole page.
- Filter controls remain outside the collapsible Filter Results body.
- The filter results bar is visually distinct and collapsible without taking the quick controls with it.

## Action Button Styling

Stock Analysis action controls use a common visual language:

- Select
- Analyze Stock
- Apply Filters
- Clear Filters

Primary actions use the same dark/blue treatment and sizing; Clear Filters uses the corresponding secondary outline treatment.

## Documentation

The Help & Methodology page is kept synchronized with this implementation. Searchable Help content is client-side and does not require AI or a network request.
