# Market Analysis

Modular Indian market-analysis platform covering **Stock Analysis**, **Bond Analysis**, **Mutual Fund Analysis**, **Mutual Fund Portfolio Builder**, and the Stock Portfolio Builder roadmap.

## Current Product Modules

- **Stock Analysis** — active implementation for screening the Nifty Total Market universe, selecting and comparing stocks, and opening detailed individual-stock analysis.
- **Bond Analysis** — active government and corporate bond research covering market observations, yields, cash flows, duration/convexity/DV01 analytics, corporate ratings, and source/freshness information.
- **Mutual Fund Analysis** — category-aware ranking, screening, fund details, comparison, rolling returns, drawdown analysis, and deterministic scoring.
- **Mutual Fund Portfolio Builder** — select funds, allocate weights to exactly 100%, run portfolio analysis, review Portfolio Health Score, Return Contribution, Drawdown & Recovery, Rolling Performance, and What-If Allocation.
- **Stock Portfolio Builder** — planned product area.

## Detailed Implementation References

- [`STOCK_ANALYSIS.md`](STOCK_ANALYSIS.md) — complete Stock Analysis implementation and parameter reference, including selector controls, every fundamental range filter, displayed metrics, statements, charts, comparison, pedigree analytics, AI Insights and missing-data conventions.
- [`BOND_ANALYSIS.md`](BOND_ANALYSIS.md) — complete Bond Analysis implementation and parameter reference, including Government/Corporate universes, selector filters, market observations, contract terms, yields, duration/convexity/DV01, ratings, source/freshness handling and missing-data conventions.

## Stock Analysis

The Stock Analysis page uses the **Nifty Total Market universe — Nifty 500 + Nifty Microcap 250 source universe**. The universe is broader than the large-cap market and includes large-, mid-, small-, and micro-cap stocks.

### Stock selector and screening

The selector supports:

- **Sector multi-select** — selecting multiple sectors includes stocks from any selected sector.
- **Company / symbol search**.
- **Market-cap presets** — Large Cap, Mid Cap, Small Cap, and Micro Cap.
- Local refinement of the already-loaded universe for quick controls, avoiding unnecessary repeated backend requests.
- Filter Results is independently collapsible; Sector, Search, and quick filters remain usable when results are collapsed.
- The complete loaded universe is filtered before the displayed result page is limited for presentation, so selecting a sector or cap is not restricted to the first page of the universe.
- A selected stock becomes the active analysis stock and is also added automatically to the **Compare Stocks** list. The user can remove it later.
- Comparison supports staging multiple stocks for side-by-side fundamental comparison.

### Individual stock analysis

The individual analysis page includes company fundamentals and financial analysis, including:

- Company summary and market-cap information.
- Valuation: P/E, Forward P/E, Price/Book, Price/Sales, PEG, EV/EBITDA, EV/Revenue, Dividend Yield, and Payout Ratio where meaningful.
- Profitability: ROE, ROA, Gross Margin, Operating Margin, and Net Margin.
- Financial Health: **Debt / Equity**, Current Ratio, Quick Ratio, and Beta where available.
- Growth and CAGR metrics.
- Annual Income Statement, Balance Sheet, and Cash Flow data.
- Historical price/performance and valuation trend charts, including P/E and P/B history where data supports them.
- Historical pedigree, consistency, shareholding, earnings-quality, capital-allocation and dilution analytics.
- **AI Insights** that interpret the deterministic report without replacing its calculations or rankings.
- Data Notes at the bottom of the analysis page rather than interrupting the financial-statement sections.

### Metric interpretation

- **P/E** compares market price with earnings per share.
- **Forward P/E** uses forward earnings expectations where available.
- **P/B** compares market price with book value per share.
- **P/S** compares market value with sales.
- **PEG** relates valuation to a supported earnings-growth measure.
- **ROE** measures return generated on shareholders' equity; **ROA** measures return relative to the asset base.
- **Margins** show the share of revenue retained at gross, operating, and net-profit levels.
- **Debt / Equity** measures debt relative to shareholders' equity and is treated as a core financial-health metric.
- **Current Ratio** and **Quick Ratio** are liquidity indicators derived from balance-sheet data.
- **Beta** is a market-sensitivity measure where available.
- **CAGR** annualizes historical growth over a supported period; it is descriptive of the historical period, not a forecast.

### Charts and reports

Stock charts are descriptive historical views. Depending on data availability, the application can show price/performance trends and valuation histories such as P/E and P/B. Individual-stock analysis combines summary metrics, ratio cards, financial statements, historical charts, pedigree analytics and Data Notes into a research report. Comparison presents the same core metrics in a side-by-side view and also exposes the same quality, consistency and trend analytics.

### Missing values

The UI distinguishes different reasons for a value not being displayed:

- **N/M — Not Meaningful** — the metric does not meaningfully apply to the business/financial model, such as certain enterprise-value metrics for financial companies.
- **Missing/unavailable data** — the relevant observation is not available.

The application does not invent fundamentals or substitute arbitrary estimates simply to fill a card.

### Stock comparison

The comparison page uses the same fundamental model and derived analytics as the individual report. It includes **Debt / Equity** alongside the other core valuation, profitability, growth, and financial-health metrics, plus historical trend and quality comparisons.

### Stock AI Insights

The Stock Analysis report and Compare view include an **AI Insights** action. The AI receives a compact representation of the existing deterministic analysis and returns a summary, key points, risks, opportunities and a recommendation/next-step view. It is an interpretation layer only: it does not create new calculations, scores or numerical rankings. AI credentials remain server-side and the deterministic report remains usable when the AI service is unavailable.

## Bond Analysis

Bond Analysis is an active research module for **government and corporate bonds**. The page separates the two universes and loads only the active universe.

### Bond universes

- **Government Bonds** — G-Secs, Treasury Bills (T-Bills), and State Development Loans (SDLs).
- **Corporate Bonds** — corporate securities normalized through the application's corporate-bond source integrations.

Bond identity uses the source-published **ISIN** where available. Government/source records without an ISIN use the backend-provided source-scoped `record_id`; the browser never fabricates identifiers.

### Bond discovery and filters

The selector supports:

- Search by security name, ISIN, or issuer.
- Government instrument-type filtering: G-Sec, SDL, T-Bill.
- Source filtering where applicable: CCIL, NSE, RBI.
- Sorting by Maturity Date, Market YTM, Clean Price, Coupon Rate, Security Name, or Instrument Type.
- Ascending/descending sort direction.
- Coupon-rate range and maturity-date range filters.
- Corporate Weighted Average Yield range.
- Corporate Trade Date and Issuer filters.
- Corporate Credit Rating multi-select.

### Bond market observations

The normalized market model can contain:

- Clean Price and Dirty Price.
- Source-reported Market YTM.
- Bid/offer price and yield.
- Last traded price/yield.
- Traded value, quantity, and trade count.
- Volume-weighted average price/yield where supplied.
- Trade/observation date and time.
- Source, as-of date, data type, and freshness.

### Bond analytics

The backend bond analytics engine can provide:

- **Current Yield** — annual coupon relative to clean price.
- **Calculated YTM** — independently calculated yield to maturity.
- **Market YTM** — source-reported yield retained separately from calculated YTM.
- **Accrued Interest** and accrued-interest days.
- **Macaulay Duration** — weighted-average time to receive the bond's cash flows.
- **Modified Duration** — approximate percentage price change for a 1% change in yield.
- **Convexity** — second-order price/yield sensitivity.
- **DV01** — approximate price/value change for a 0.01% (one basis point) yield move per 100 of face value.
- Settlement date, day-count convention, and coupon frequency where available.

Bond calculations are performed in the backend analytics service rather than duplicated in browser JavaScript.

### Cash flows and corporate terms

The detail view can expose coupon schedules and redemption cash flows. Corporate details can additionally include credit rating observations, rating agency/date, outlook, secured status, seniority, call/put options, issue size, outstanding amount, issue price, coupon type/basis, issuance mode, guarantee status, perpetual status, and exchange/listing information where supplied.

### Bond data sources and freshness

The bond layer normalizes multiple source feeds behind the service/model layer. The UI can expose source health for **CCIL, NSE, and RBI**, while corporate detail uses the application's CDSL/Bond Central integrations where applicable.

Market observations can be classified as traded, indicative, MTM, reference, auction, historical, or unknown. Missing inputs do not result in fabricated analytics; unavailable calculations remain unavailable.

## Architecture

The application follows a layered architecture:

```text
Frontend (HTML/CSS/JS)
        ↓
Routes / API (FastAPI)
        ↓
Services (business logic)
        ↓
Models (data structures)
        ↓
External / source data providers
```

### Frontend structure

- `frontend/html/` — page shells.
- `frontend/js/core/` — application-wide API, navigation, configuration, and utilities.
- `frontend/js/components/` — reusable UI components.
- `frontend/js/features/stock-selection/` — Stock Analysis selector, filtering, comparison, analysis, charts, AI Insights and UI enhancements.
- `frontend/js/features/bond-analysis/` — Bond Analysis selection, filtering, bond details, analytics, and UI behaviour.
- `frontend/js/features/mutual-fund-analysis/` — Mutual Fund Analysis and comparison.
- `frontend/js/features/portfolio-builder/` — Mutual Fund Portfolio Builder.
- `frontend/js/features/home/` — Home page and Help & Methodology.
- `frontend/css/features/` — feature-specific styling.

Important Stock Analysis frontend modules include:

- `stock-detail/index.js` — stock analysis page, financial metrics, statements, filters, and rendering.
- `stock-comparison.js` — side-by-side stock comparison.
- `stock-ai-context.js` — bounded deterministic context builder for AI interpretation.
- `stock-ai-request.js` — individual and comparison AI API requests.
- `stock-ai-response.js` — AI loading, error and response renderers.
- `stock-ai-ui.js` — AI Insights actions for individual analysis and comparison.
- `stock-compare-auto-add.js` — automatically adds an analyzed/selected stock to comparison.
- `stock-filter-controller*.js` — stock filtering and screening behaviour.
- `stock-api-coalescer.js` — prevents duplicate lightweight universe requests.
- `stock-universe-enhancements*.js` — stock-universe UI enhancements.
- `stock-valuation-trends.js` — historical valuation trend charts.
- `stock-trends.js` — stock performance/trend visualizations.

### Backend structure

- `backend/routes/` — thin HTTP handlers.
- `backend/services/data/` — provider and normalization layer.
- `backend/services/stocks/` — stock universe, market-cap classification, screening, and stock-selection business logic.
- `backend/services/bonds/` — bond source normalization, selection, market observations, and bond analytics.
- `backend/services/mutual_funds/` — mutual-fund calculations and ranking.
- `backend/services/portfolio/` — mutual-fund portfolio analysis and Health Score.
- `backend/services/ai/` — AI interpretation layer.
- `backend/models/` — data structures, including the normalized Bond model.

## Stock Analysis Stability Rules

The stock selector is deliberately designed to avoid the DOM feedback loop that previously caused the page to continuously mutate and appear to load forever.

- Mutation observers must not watch DOM changes produced by their own enhancement code.
- Quick filter interactions should operate against the loaded universe whenever possible.
- Identical lightweight stock-universe requests should be coalesced.
- Sector, search, cap, and other quick controls should not rebuild the entire page repeatedly.
- Backend stock-universe loading must remain independent from purely visual filter changes.

## Mutual Fund Analysis

Mutual Fund Analysis provides category-relative ranking, screening, Fund Details, comparison, rolling performance, drawdown analysis, and deterministic scoring. AI Insights are interpretation-only and do not replace numerical calculations.

## Mutual Fund Portfolio Builder

The portfolio builder supports 2–10 mutual funds, allocations totaling exactly 100%, historical portfolio analysis, Portfolio Health Score, Return Contribution, Drawdown & Recovery, Rolling Performance, and temporary What-If Allocation scenarios.

## Help & Methodology

The Help & Methodology page is the application's reference guide for how the screens, metrics, ratios, filters, charts, comparison tables, and reports should be interpreted. It covers:

- Mutual Fund Analysis ranking, percentiles, risk metrics, rolling returns, drawdown, and scoring.
- Mutual Fund Portfolio Builder allocation rules, historical simulation methodology, Health Score, Return Contribution, Drawdown & Recovery, Rolling Performance, and What-If scenarios.
- Stock Analysis selection, fundamental metrics, historical pedigree and consistency analytics, shareholding trends, earnings quality, capital allocation, dilution analytics, comparison and AI Insights.
