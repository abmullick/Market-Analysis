# Market Analysis

Modular Indian market-analysis platform covering **Stock Analysis**, **Mutual Fund Analysis**, **Mutual Fund Portfolio Builder**, and the Stock Portfolio Builder roadmap.

## Current Product Modules

- **Stock Analysis** — active implementation for screening the Nifty Total Market universe, selecting and comparing stocks, and opening detailed individual-stock analysis.
- **Mutual Fund Analysis** — category-aware ranking, screening, fund details, comparison, rolling returns, drawdown analysis, and deterministic scoring.
- **Mutual Fund Portfolio Builder** — select funds, allocate weights to exactly 100%, run portfolio analysis, review Portfolio Health Score, Return Contribution, Drawdown & Recovery, Rolling Performance, and What-If Allocation.
- **Stock Portfolio Builder** — planned/coming-soon product area.

## Stock Analysis

The Stock Analysis page uses the **Nifty Total Market universe — Nifty 500 + Nifty Microcap 250 source universe**. The universe is broader than the large-cap market and includes large-, mid-, small-, and micro-cap stocks.

### Stock selector

The selector supports:

- **Sector multi-select** — selecting multiple sectors includes stocks from any selected sector.
- **Company / symbol search**.
- **Market-cap presets** — Large Cap, Mid Cap, Small Cap, and Micro Cap.
- **Liquidity controls** where supplied by the current stock-selection implementation.
- Local refinement of the already-loaded universe for quick controls, avoiding unnecessary repeated backend requests.
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
- Historical valuation/performance trend charts, including P/E and P/B history where source data supports them.
- Data Notes at the bottom of the analysis page rather than interrupting the financial-statement sections.

### Data-source policy

**Screener is the primary Indian fundamental-data source** for stock financials and ratios. **Yahoo market data is supplemental** and is used for market-data fields such as Forward P/E and Beta where available.

The UI distinguishes different reasons for a value not being displayed:

- **N/M — Not Meaningful** — the metric does not meaningfully apply to the business/financial model, such as certain enterprise-value metrics for financial companies.
- **Missing/unavailable data** — the relevant source did not provide a usable value.

The application does not invent fundamentals or substitute arbitrary estimates simply to fill a card.

### Stock comparison

The comparison page uses the same source-aware fundamental model and includes **Debt / Equity** alongside the other core valuation, profitability, growth, and financial-health metrics. Table dimensions are kept consistent across metric groups.

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
- `backend/services/mutual_funds/` — mutual-fund calculations and ranking.
- `backend/services/portfolio/` — mutual-fund portfolio analysis and Health Score.
- `backend/services/ai/` — AI interpretation layer.
- `backend/models/` — data structures.

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

The Help & Methodology page documents the application's formulas, data-source conventions, freshness treatment, mutual-fund methodology, portfolio methodology, and the current Stock Analysis workflow. The Help page's search is client-side and does not make network or AI requests.

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

Stock-specific tests live under `tests/stocks/`; frontend tests live under `tests/frontend/`.

## Key Engineering Principles

- Keep dependencies flowing **Frontend → Routes → Services → Models → Providers**.
- Keep product modules isolated.
- Keep routes thin and business logic in services.
- Keep provider access in the shared data layer.
- Never expose provider credentials to frontend JavaScript.
- Keep deterministic calculations independent of AI.
- Prefer cached/local data and client-side refinement for quick UI filters over repeated expensive backend work.
- Do not invent missing financial data merely to populate a UI field.
- Keep documentation synchronized with implemented behaviour.

## Recent Stock Analysis Developments

- Activated the Stock Analysis selector and individual-stock analysis workflow.
- Expanded the stock universe to the Nifty Total Market source universe.
- Added Large/Mid/Small/Micro Cap classification and selection.
- Added multi-sector selection and responsive local filtering.
- Added automatic Compare Stocks inclusion when a stock is selected for analysis.
- Added Debt / Equity throughout stock analysis and comparison.
- Added supplemental Yahoo Forward P/E and Beta while retaining Screener as the primary Indian fundamental source.
- Added source-aware `N/M — Not Meaningful` treatment for financial-company-specific metrics.
- Added/maintained historical P/E and P/B valuation trend charts.
- Stabilized the stock filter UI by eliminating MutationObserver feedback loops and repeated DOM rebuilds.
- Unified the visual language of Stock Analysis action controls (Select, Analyze, Apply Filters, and Clear Filters).
- Updated Help & Methodology to describe the current Stock Analysis implementation rather than treating it as a placeholder.

## Notes

- No database is used yet; provider data is normalized and cached where applicable.
- Authentication is not implemented yet.
- Stock Portfolio Builder remains a planned product area.
- Financial and market data are presented for research and informational purposes and should not be treated as personalized investment advice.
