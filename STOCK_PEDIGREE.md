# Stock Pedigree & Trend Analytics

This document describes the historical analytics added to Stock Analysis.

## Objective

The feature extends point-in-time valuation and profitability ratios with historical diagnostics:

- Is revenue growth reasonably consistent?
- Is profit growth consistent with revenue growth?
- Does free cash flow follow reported earnings?
- Are ROE and ROCE persistent or volatile?
- Are operating margins expanding or compressing?
- Is debt rising or falling?
- Is working capital absorbing more cash?
- How has the ownership structure changed?
- Is the shareholder base becoming more or less dispersed?
- Is cash generation keeping pace with accounting profit?
- How intensive is capital reinvestment?
- Is per-share growth being affected by changes in share count?

The feature is descriptive. It does not produce an investment recommendation or forecast.

## Derived metrics

### Growth consistency

`Positive Growth % = Positive YoY Growth Observations / Valid YoY Observations × 100`

This is shown separately for Revenue, Profit and FCF.

### ROE

`ROE = Net Profit / Average Shareholders' Equity × 100`

### ROCE

For non-financial operating businesses:

`ROCE = Operating Profit / (Net Block + Working Capital) × 100`

`Working Capital = Current Assets − Current Liabilities`

### Operating Margin

`Operating Margin = Operating Profit / Revenue × 100`

### Cash Conversion

`CFO / Net Profit = Cash from Operating Activities / Net Profit × 100`

### FCF Margin

`FCF Margin = Free Cash Flow / Revenue × 100`

### Cash Conversion Cycle

`CCC = Debtor Days + Inventory Days − Payable Days`

Each day metric is calculated from the corresponding annual balance relative to annual revenue and multiplied by 365.

### Indexed business scale

Revenue, Profit and FCF are independently rebased to 100 at the first positive observation. This allows historical trajectories to be compared without mixing their absolute units.

## Earnings quality

The quality panel compares Net Profit, Operating Cash Flow and Free Cash Flow using indexed historical series.

`CFO / Net Profit = Operating Cash Flow / Net Profit × 100`

`FCF / Net Profit = Free Cash Flow / Net Profit × 100`

`CFO / Profit CAGR Gap = CFO CAGR − Net Profit CAGR`

`FCF / Profit CAGR Gap = FCF CAGR − Net Profit CAGR`

A positive gap means the corresponding cash-flow measure has grown faster than reported profit over the selected period; a negative gap means it has grown more slowly.

## Capital allocation & reinvestment

The capital panel tracks:

- Operating Cash Flow.
- Capital Expenditure.
- Free Cash Flow.
- Capex / Operating Cash Flow.
- Capex / Revenue.
- FCF / Operating Cash Flow.
- Debt trajectory and annual debt change.

Capital expenditure is converted to absolute value for intensity ratios because it may be represented as a negative cash-flow item.

## EPS quality & dilution

When annual Net Profit and diluted EPS are available:

`Implied Shares = Net Profit / Diluted EPS`

With Net Profit in ₹ crore and EPS in ₹ per share, implied shares are expressed in crore shares.

The engine then calculates:

- Implied share-count history.
- Share-count growth.
- 3Y share-count CAGR.
- 5Y share-count CAGR.
- EPS CAGR.
- Profit CAGR − EPS CAGR.

This provides a historical dilution proxy and shows whether per-share growth has kept pace with overall profit growth.

## Shareholding history

The ownership table is parsed into dated observations for:

- Promoters
- FIIs
- DIIs
- Government
- Public
- Number of shareholders

Quarterly and longer annual observations are retained where available. Duplicate dates are merged. Missing observations remain missing rather than being interpolated.

## Individual analysis charts

The individual report contains:

1. Business Scale & Cash Generation — indexed Revenue, Profit and FCF.
2. ROE / ROCE / Operating Margin — capital efficiency and margin trajectory.
3. Cash Conversion & FCF Margin — earnings-to-cash quality.
4. Debt Trend — historical reported debt.
5. Working Capital Cycle — historical CCC.
6. Historical Shareholding Pattern — ownership structure over time.
7. Shareholder Base — shareholder-count trend.
8. Earnings Quality — indexed profit versus CFO/FCF and cash-conversion ratios.
9. Capital Allocation & Reinvestment — capex intensity and funding trajectory.
10. EPS Quality & Dilution — implied share count and profit/EPS growth relationship.

## Comparison charts

The same engine is applied independently to every selected company. Compare includes the existing pedigree charts plus:

1. Indexed profit/cash-generation comparison.
2. CFO / Profit comparison.
3. FCF / Profit comparison.
4. Capital intensity comparison.
5. Share-count growth comparison.
6. Profit versus EPS growth comparison.
7. A quality snapshot of 3Y/5Y cash-generation and dilution gaps.

The calculations are intentionally identical between individual and comparison views.

## Presentation rules

Charts are displayed as ordinary analysis metrics. Formula explanations belong in Help & Methodology, while the analysis page focuses on the resulting metric and trend.
