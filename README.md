# Market Analysis

Modular Indian market-analysis platform covering **Stock Analysis**, **Bond Analysis**, **Mutual Fund Analysis**, **Mutual Fund Portfolio Builder**, and the Stock Portfolio Builder roadmap.

## Current Product Modules

- **Stock Analysis** — active implementation for screening the Nifty Total Market universe, selecting and comparing stocks, and opening detailed individual-stock analysis.
- **Bond Analysis** — active government and corporate bond research covering market observations, yields, cash flows, duration/convexity/DV01 analytics, corporate ratings, and source/freshness information.
- **Mutual Fund Analysis** — category-aware ranking, screening, fund details, comparison, rolling returns, drawdown analysis, and deterministic scoring.
- **Mutual Fund Portfolio Builder** — select funds, allocate weights to exactly 100%, run portfolio analysis, review Portfolio Health Score, Return Contribution, Drawdown & Recovery, Rolling Performance, and What-If Allocation.
- **Stock Portfolio Builder** — planned product area.

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

The individual analysis page includes source-aware company fundamentals and financial analysis, including:

- Company summary and market-cap information.
- Valuation: P/E, Forward P/E, Price/Book, Price/Sales, PEG, EV/EBITDA, EV/Revenue, Dividend Yield, and Payout Ratio where meaningful.
- Profitability: ROE, ROA, Gross Margin, Operating Margin, and Net Margin.
- Financial Health: **Debt / Equity**, Current Ratio, Quick Ratio, and Beta where available.
- Growth and CAGR metrics.
- Annual Income Statement, Balance Sheet, and Cash Flow data.
- Historical price/performance and valuation trend charts, including P/E and P/B history where source data supports them.
- Data Notes at the bottom of the analysis page rather than interrupting the financial-statement sections.

### Metric interpretation

- **P/E** compares market price with earnings per share.
- **Forward P/E** uses forward earnings expectations where Yahoo market data provides the field; it is supplemental market data rather than the primary Screener fundamental field.
- **P/B** compares market price with book value per share.
- **P/S** compares market value with sales.
- **PEG** relates valuation to a supported earnings-growth measure.
- **ROE** measures return generated on shareholders' equity; **ROA** measures return relative to the asset base.
- **Margins** show the share of revenue retained at gross, operating, and net-profit levels.
- **Debt / Equity** measures debt relative to shareholders' equity and is treated as a core financial-health metric.
- **Current Ratio** and **Quick Ratio** are liquidity indicators derived from balance-sheet data.
- **Beta** is a market-sensitivity measure supplied as supplemental Yahoo market data where available.
- **CAGR** annualizes historical growth over a supported period; it is descriptive of the historical period, not a forecast.

### Charts and reports

Stock charts are descriptive historical views. Depending on source availability, the application can show price/performance trends and valuation histories such as P/E and P/B. Individual-stock analysis combines summary metrics, ratio cards, financial statements, historical charts, and Data Notes into a research report. Comparison presents the same core metrics in a side-by-side view.

### Data-source policy

**Screener is the primary Indian fundamental-data source** for stock financials and ratios. **Yahoo market data is supplemental** and is used for market-data fields such as Forward P/E and Beta where available.

The UI distinguishes different reasons for a value not being displayed:

- **N/M — Not Meaningful** — the metric does not meaningfully apply to the business/financial model, such as certain enterprise-value metrics for financial companies.
- **Missing/unavailable data** — the relevant source did not provide a usable value.

The application does not invent fundamentals or substitute arbitrary estimates simply to fill a card.

### Stock comparison

The comparison page uses the same source-aware fundamental model and includes **Debt / Equity** alongside the other core valuation, profitability, growth, and financial-health metrics. Table dimensions are kept consistent across metric groups.

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

For the detailed Bond Analysis implementation notes, see [`BOND_ANALYSIS.md`](BOND_ANALYSIS.md).

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
- `frontend/js/features/stock-selection/` — Stock Analysis selector, filtering, comparison, analysis, charts, and UI enhancements.
- `frontend/js/features/bond-analysis/` — Bond Analysis selection, filtering, bond details, analytics, and UI behaviour.
- `frontend/js/features/mutual-fund-analysis/` — Mutual Fund Analysis and comparison.
- `frontend/js/features/portfolio-builder/` — Mutual Fund Portfolio Builder.
- `frontend/js/features/home/` — Home page and Help & Methodology.
- `frontend/css/features/` — feature-specific styling.

Important Stock Analysis frontend modules include:

- `stock-detail/index.js` — stock analysis page, financial metrics, statements, filters, and rendering.
- `stock-comparison.js` — side-by-side stock comparison.
- `stock-compare-auto-add.js` — automatically adds an analyzed/selected stock to comparison.
- `stock-filter-controller*.js` — stock filtering and screening behaviour.
- `stock-filter-controls-layout.js` — filter-control placement.
- `stock-filter-interaction-fix.js` — stable sector/search/cap interaction layer.
- `stock-api-coalescer.js` — prevents duplicate lightweight universe requests.
- `stock-universe-enhancements*.js` — stock-universe UI enhancements.
- `stock-valuation-trends.js` — historical valuation trend charts.
- `stock-trends.js` — stock performance/trend visualizations.

### Backend structure

- `backend/routes/` — thin HTTP handlers.
- `backend/services/data/` — provider and normalization layer, including Screener/Yahoo-backed stock data.
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
- **Bond Analysis** government/corporate universes, selection identity, search and filters, market price/yield terminology, calculated versus market YTM, accrued interest, duration, convexity, DV01, coupon/redemption cash flows, corporate ratings, source/freshness information, and missing-data conventions.
- **Stock Analysis** universe selection, sector/search/cap filtering, full-universe filtering before pagination, stock selection, automatic comparison, valuation ratios, profitability ratios, Debt / Equity, liquidity ratios, Beta, CAGR/growth, financial statements, historical charts, comparison, data-source policy, and missing-value conventions.
- **N/M — Not Meaningful** versus genuinely unavailable source data.

Help search is client-side and does not make network or AI requests. Stock and Bond Analysis help entries are synchronized at runtime so obsolete Stock Analysis placeholder documentation is removed and the current implementations remain searchable.

## Environment Variables

Copy `.env.example` to `.env` and configure the required provider credentials:

```bash
cp .env.example .env
```

Typical configuration includes:

- `STOXIM_API_KEY`
- `GROQ_API_KEY`
- `GROQ_MODEL` (optional)
- `APP_ENV`
- `APP_PORT` (default `20090`)
- `APP_DEBUG`

## Running Locally

```bash
pip install -r requirements.txt
python run.py
```

The application is normally available at `http://localhost:20090`.

## Testing

```bash
pytest tests/
```

Stock-specific tests live under `tests/stocks/`; bond tests and frontend tests live under `tests/` and `tests/frontend/` respectively.

## Key Engineering Principles

- Keep dependencies flowing **Frontend → Routes → Services → Models → Providers**.
- Keep product modules isolated.
- Keep routes thin and business logic in services.
- Keep provider access in the shared data layer.
- Never expose provider credentials to frontend JavaScript.
- Keep deterministic calculations independent of AI.
- Prefer cached/local data and client-side refinement for quick UI filters over repeated expensive backend work.
- Do not invent missing financial or bond data merely to populate a UI field.
- Keep documentation synchronized with implemented behaviour.

## Recent Stock Analysis Developments

- Activated the Stock Analysis selector and individual-stock analysis workflow.
- Expanded the stock universe to the Nifty Total Market source universe.
- Added Large/Mid/Small/Micro Cap classification and selection.
- Added multi-sector selection and responsive local filtering.
- Ensured filtering is performed across the full loaded universe rather than only the first displayed page.
- Added automatic Compare Stocks inclusion when a stock is selected for analysis.
- Added Debt / Equity throughout stock analysis and comparison.
- Added supplemental Yahoo Forward P/E and Beta while retaining Screener as the primary Indian fundamental source.
- Added source-aware `N/M — Not Meaningful` treatment for financial-company-specific metrics.
- Added/maintained historical P/E and P/B valuation trend charts.
- Stabilized the stock filter UI by eliminating MutationObserver feedback loops and repeated DOM rebuilds.
- Unified the visual language of Stock Analysis action controls (Select, Analyze, Apply Filters, and Clear Filters).
- Updated Help & Methodology to describe the current Stock Analysis implementation rather than treating it as a placeholder.
- Updated the home-page Stock Analysis card to **Explore Stocks**.

## Recent Bond Analysis Documentation

- Documented the separate Government and Corporate Bond universes.
- Documented ISIN/record-ID identity handling and lazy loading.
- Documented bond search, sorting, instrument/source filters, range filters, and corporate credit-rating filters.
- Documented clean/dirty price, Market YTM, Calculated YTM, Current Yield, accrued interest, duration, convexity, and DV01.
- Documented coupon/redemption cash flows, corporate bond terms, rating observations, and source/freshness classifications.
- Added a dedicated `BOND_ANALYSIS.md` implementation reference.

## Notes

- No database is used yet; provider data is normalized and cached where applicable.
- Authentication is not implemented yet.
- Stock Portfolio Builder remains a planned product area.
- Financial and market data are presented for research and informational purposes and should not be treated as personalized investment advice.
