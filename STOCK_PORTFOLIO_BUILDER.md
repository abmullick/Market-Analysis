# Stock Portfolio Builder

The Stock Portfolio Builder lets users construct a portfolio of individual stocks from the Stock Analysis universe, assign allocation weights, and inspect the portfolio using the same fundamental and historical-price engines used by Stock Analysis.

## 1. Portfolio construction

### Stock universe

The builder reuses the Stock Analysis stock universe and selector logic. Users can refine the available stocks using:

- Company or symbol search.
- Sector multi-select.
- Large Cap, Mid Cap, Small Cap and Micro Cap quick filters.

Filtering is applied to the loaded universe before the visible result list is paginated. Sector selection therefore filters the actual loaded universe rather than only the currently displayed page.

### Allocation

Each selected holding receives a percentage allocation. The portfolio can proceed to analysis only when the allocation total is exactly 100% within the builder's validation tolerance.

The builder stores the selected portfolio in browser storage. It is an allocation-based analytical portfolio; it does not model individual purchase prices, quantities, tax lots, transaction costs or trade execution.

## 2. Portfolio snapshot

The opening analysis shows:

- Number of holdings.
- Largest position and its allocation.
- Number of sectors represented.
- Portfolio concentration using HHI.

The Herfindahl-Hirschman Index is calculated from allocation weights. Higher HHI means the allocation is more concentrated.

## 3. Portfolio Quality

The Quality section is allocation-weighted and reuses Stock Analysis fundamentals:

- ROE.
- ROCE.
- Revenue Growth.
- Profit Growth.
- Debt / Equity.

Every metric also exposes coverage. Coverage is the percentage of the portfolio allocation for which the underlying metric is available. Missing data is not replaced by arbitrary estimates.

## 4. Portfolio Valuation

The valuation section shows allocation-weighted exposure to:

- P/E.
- P/B.
- EV / EBITDA.
- Dividend Yield.

These are exposure indicators rather than mathematically aggregated portfolio valuation multiples. Financial companies can require a different valuation interpretation, so EV/EBITDA should not be treated as equally informative across all sectors.

## 5. Sector Allocation

Sector allocation is the sum of current portfolio weights for each sector. It is shown as proportional visual bars. Holdings without a usable sector classification are grouped under `Other`.

## 6. Holding Analysis and signals

The holding table shows, for each stock:

- Stock name and symbol.
- Allocation.
- P/E.
- ROE.
- Revenue Growth.
- Debt / Equity.
- Fundamental Signal.

The Signal reuses the shared Stock Analysis fundamental-signal engine. Possible states are:

- **Positive** — available positive fundamental observations without conflicting watch observations.
- **Watch** — available watch observations without positive observations.
- **Mixed** — both positive and watch observations are present.
- **No signal** — insufficient fundamental data for a directional signal.

The signal is descriptive and does not represent a return forecast or a buy/sell instruction.

## 7. Historical Portfolio Performance

The Performance section reports historical price CAGR for 1Y, 3Y, 5Y and 10Y where data is available. It also reports coverage for each period.

The section contains:

- CAGR KPI cards.
- A historical-period CAGR bar chart.
- A 3Y holding-level visual showing each available holding's CAGR and allocation.
- A methodology/data note.

### Calculation

For each holding with an available historical CAGR:

`Growth Factor = (1 + Holding CAGR) ^ n`

where `n` is the period in years.

The growth factors are combined using allocation-normalised weights:

`Portfolio Growth Factor = Σ(weight × Growth Factor)`

The portfolio CAGR is then:

`Portfolio CAGR = Portfolio Growth Factor ^ (1 / n) − 1`

If a holding does not have the required historical CAGR, the calculation uses the covered allocation only and displays the coverage percentage.

This is not a transaction-level backtest. It excludes dividends, taxes, transaction costs and portfolio rebalancing.

## 8. Portfolio vs Market

The benchmark module compares the portfolio's historical price CAGR with a selected market benchmark:

- NIFTY 50.
- NIFTY 500.
- BSE SENSEX.

The comparison includes:

- 1Y, 3Y, 5Y and 10Y CAGR.
- Portfolio coverage.
- Portfolio CAGR versus benchmark CAGR.
- Historical CAGR difference.
- Comparison bar chart.
- Benchmark selection control.

Portfolio CAGR uses the same allocation-weighted geometric-growth calculation as Portfolio Performance. Benchmark history is supplied by the benchmark backend endpoint.

Benchmark comparison is historical price return only. Dividends, taxes, transaction costs and portfolio rebalancing are excluded.

## 9. Quality × Growth Positioning Map

The Positioning Map is a visual representation of the current holdings using existing Holding Analysis data.

- **X-axis:** Revenue Growth.
- **Y-axis:** ROE.
- **Bubble size:** Current portfolio allocation.
- **Reference lines:** Portfolio median Revenue Growth and median ROE.

The map is relative to the portfolio's own holdings. It is a descriptive positioning visual and does not create a new investment score.

## 10. Portfolio Risk & Drawdown

The Risk & Drawdown view reconstructs a historical portfolio path using annual closing prices and the current allocation weights.

It reports:

- Maximum Drawdown.
- Annual Volatility.
- Current Drawdown.
- HHI Concentration.
- Largest-position exposure.
- Allocation in holdings with Debt / Equity above 1x.
- Allocation in holdings with negative Revenue Growth.

### Risk methodology

Maximum Drawdown is the largest decline from a previous historical portfolio peak.

Annual Volatility is derived from successive annual portfolio-price returns using sample standard deviation.

Current Drawdown is the latest indexed portfolio value relative to its historical peak.

Because the risk path uses annual closing prices, an intra-year drawdown can be understated. This is a historical exposure view rather than a transaction-level backtest and excludes dividends, taxes, transaction costs and rebalancing.

## 11. What-If / Rebalancing

The What-If / Rebalancing module allows the user to change allocations across the same holdings and immediately compare the proposed portfolio with the current portfolio.

The proposed allocation must total exactly 100%.

The comparison recomputes:

- P/E.
- ROE.
- Revenue Growth.
- Debt / Equity.
- HHI concentration.
- Sector exposure.
- Individual allocation changes.

The scenario is temporary. It does not overwrite the saved portfolio and it does not execute trades.

## 12. Portfolio Action View

The Action View provides a concise descriptive summary of portfolio characteristics that may warrant review.

It highlights:

- Position concentration.
- Sector concentration.
- Leverage exposure.
- Growth exposure.
- Valuation exposure.
- Allocation-weighted ROE.
- Allocation-weighted ROCE.
- Revenue Growth.
- Profit Growth.
- P/E.
- Debt / Equity.
- HHI.

The Action View intentionally does not generate buy/sell recommendations or predict future returns.

## 13. Data Notes and coverage

Portfolio fundamentals reuse the same Stock Analysis data and calculations. Holding-level signals reuse the shared fundamental-signal engine. Historical price calculations reuse the Stock Analysis chart data. Benchmark and risk views reuse the same historical-price inputs where applicable.

Coverage is shown whenever a portfolio metric is calculated from an incomplete subset of holdings. A result with partial coverage should always be interpreted together with that coverage percentage.

The application does not invent fundamental values, historical prices or missing observations merely to complete a portfolio card.

## 14. UI and visualization

Portfolio analysis is presented as distinct collapsible analysis cards. Each card provides key highlights while collapsed and detailed calculations or visualisations when expanded.

The analysis uses visualisations for:

- Historical portfolio CAGR.
- Holding-level performance.
- Portfolio versus benchmark CAGR.
- Quality × Growth positioning.
- Historical portfolio path and drawdown.
- Allocation and sector exposure.
- What-if allocation changes.

The presentation layer does not introduce an independent calculation engine; charts and cards consume the existing analysis results.

## 15. Shared-engine principle

The Stock Portfolio Builder deliberately reuses the existing Stock Analysis engine and endpoints wherever possible. This keeps the definitions of fundamentals, signals and historical price metrics consistent between an individual stock report and the portfolio containing that stock.

The principal frontend modules are:

- `frontend/js/features/stock-portfolio-builder.js` — portfolio construction, stock selection and allocations.
- `frontend/js/features/stock-portfolio-analysis.js` — portfolio snapshot, quality, valuation, sector allocation, holding analysis and historical performance.
- `frontend/js/features/stock-portfolio-benchmark.js` — benchmark comparison.
- `frontend/js/features/stock-portfolio-positioning-map.js` — quality × growth visualisation.
- `frontend/js/features/stock-portfolio-risk-drawdown.js` — historical risk and drawdown.
- `frontend/js/features/stock-portfolio-rebalancing.js` — temporary what-if allocation analysis.
- `frontend/js/features/stock-portfolio-action-view.js` — descriptive portfolio action summary.
- `frontend/js/features/stock-portfolio-analysis-ui.js` — presentation/collapsible-card integration.

## 16. Interpretation limits

Stock Portfolio Builder is historical and descriptive. It does not forecast future returns, guarantee portfolio outcomes, model transaction execution, include tax effects, or turn historical differences into recommendations. A portfolio metric is meaningful only in the context of its definition, historical period, available coverage and underlying data quality.

## 17. Recent UI and interaction refinements

### 17.1 Independent chart cards

Portfolio visualisations can be presented as independently collapsible chart cards. Collapsing a chart hides only the presentation area; it does not remove the underlying calculation or chart data. When a chart is reopened, the existing Chart.js instance is resized so the visual renders correctly after being displayed again.

### 17.2 Portfolio analysis loading state

The **Continue to Portfolio Analysis** action now presents a blocking busy state while the analysis is being prepared. This prevents accidental repeated submissions and gives clear feedback that the portfolio analysis is in progress. The loading layer does not change the underlying analytical calculations.

### 17.3 Consistent portfolio-style presentation

The stock portfolio analysis cards use a consistent collapsible-card visual language, including clear section headers, prominent icons, expand/collapse controls and compact summary presentation. These changes are presentation-layer improvements and do not introduce a separate scoring or calculation engine.

### 17.4 Chart integrity

Chart grouping and collapsible presentation are implemented so existing chart data, canvases and Chart.js instances are retained. Opening a previously collapsed card triggers chart resizing where necessary; charts are not recreated merely because the user expands a section.

### 17.5 Interpretation boundary

The recent UI changes do not alter portfolio formulas, historical periods, benchmark definitions, coverage rules, or the descriptive nature of the analysis. They improve navigation and readability while preserving the existing calculation engine.
