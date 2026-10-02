# Stock Pedigree & Trend Analytics

This document describes the historical analytics added to Stock Analysis.

## Objective

The feature uses Screener financial statements and shareholding history to answer a different set of questions from point-in-time valuation ratios:

- Is revenue growth reasonably consistent?
- Is profit growth consistent with revenue growth?
- Does free cash flow follow reported earnings?
- Are ROE and ROCE persistent or volatile?
- Are operating margins expanding or compressing?
- Is debt rising or falling?
- Is working capital absorbing more cash?
- How has the ownership structure changed?
- Is the shareholder base becoming more or less dispersed?

The feature is descriptive. It does not produce an investment recommendation or forecast.

## Derived metrics

### Growth consistency

For each historical series, the engine counts positive year-over-year observations:

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

with each day metric calculated from the corresponding annual balance divided by revenue and multiplied by 365.

### Indexed business scale

Revenue, Profit and FCF are independently rebased to 100 at the first positive observation. This allows their historical trajectories to be compared without mixing their absolute units.

## Shareholding history

The Screener Shareholding Pattern is parsed into dated observations for:

- Promoters
- FIIs
- DIIs
- Government
- Public
- Number of shareholders

Quarterly and longer annual observations are retained where available. Duplicate dates are merged.

Screener notes that classification can change from September 2022 following the XBRL format change. This limitation is displayed in the application and should be considered when comparing historical FII/DII classifications.

## Individual analysis charts

The individual report contains:

1. Business Scale & Cash Generation — indexed Revenue, Profit and FCF.
2. ROE / ROCE / Operating Margin — capital efficiency and margin trajectory.
3. Cash Conversion & FCF Margin — earnings-to-cash quality.
4. Debt Trend — historical reported debt.
5. Working Capital Cycle — historical CCC.
6. Historical Shareholding Pattern — ownership structure.
7. Shareholder Base — shareholder-count trend.

## Comparison charts

The same engine is applied separately to every selected company. Compare includes:

1. Indexed business scale.
2. ROE / ROCE trend.
3. Operating Margin trend.
4. FCF Margin trend.
5. Debt trend.
6. Promoter holding trend.
7. Institutional holding trend (FII + DII).
8. Shareholder-count trend.

The calculations are intentionally identical between individual and comparison views.

## Source discipline

The pedigree API uses Screener as the source for the underlying annual financial statements and shareholding history. The application calculates the secondary metrics itself so that formulas remain transparent.

Missing observations remain missing. The engine does not interpolate or fabricate historical ownership, financial or cash-flow observations merely to make a chart complete.
