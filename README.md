# Market Analysis

Modular Indian market-analysis platform covering **Stock Analysis**, **Bond Analysis**, **Mutual Fund Analysis**, **Mutual Fund Portfolio Builder**, and **Stock Portfolio Builder**.

## Current Product Modules

- **Stock Analysis** — Nifty Total Market stock selection, sector/search/market-cap filters, fundamental analysis, statements, historical charts, comparison, pedigree analytics, valuation context, Fundamental Momentum, Quality × Growth × Valuation, Growth Funding & Capital Efficiency, Shareholding Intelligence and AI Insights.
- **Bond Analysis** — government and corporate bond research covering market observations, yields, cash flows, duration/convexity/DV01 analytics, ratings, source and freshness information.
- **Mutual Fund Analysis** — category-relative ranking, filters, fund details, comparison, rolling returns, drawdown analysis and deterministic scoring.
- **Mutual Fund Portfolio Builder** — select funds, allocate weights to exactly 100%, run historical portfolio analysis, review Portfolio Health Score, Return Contribution, Drawdown & Recovery, Rolling Performance and What-If Allocation.
- **Stock Portfolio Builder** — construct an allocation-based stock portfolio, analyse quality/valuation/concentration/performance, compare against market benchmarks, visualise quality versus growth, inspect historical risk/drawdown, run temporary what-if reallocations and review descriptive portfolio observations.

## Detailed Implementation References

- [`STOCK_ANALYSIS.md`](STOCK_ANALYSIS.md) — complete Stock Analysis implementation and parameter reference.
- [`BOND_ANALYSIS.md`](BOND_ANALYSIS.md) — complete Bond Analysis implementation and parameter reference.
- [`STOCK_PORTFOLIO_BUILDER.md`](STOCK_PORTFOLIO_BUILDER.md) — complete Stock Portfolio Builder methodology, calculations, visualisations, limitations and frontend module reference.

## Application Authentication

Market Analysis is a private application. All application pages, FastAPI APIs and frontend static assets are protected by the same authenticated session. The only unauthenticated surfaces are the login page and the login/logout endpoints required to establish or terminate that session.

### Login experience

- A decorative glass-style floating login card is shown before access is granted.
- The login surface uses an animated orbit/background treatment and responsive mobile styling.
- Successful login returns the user to the page they originally requested.
- Authenticated pages display a floating **Private access / Sign out** control.
- If the session expires while a page is open, the application displays a session-expiry overlay and provides a sign-in path.

### Session security

- Credentials are supplied only through server-side environment variables: `APP_USERNAME` and `APP_PASSWORD`.
- Sessions use cryptographically random bearer tokens stored server-side as SHA-256 hashes.
- Session cookies are HttpOnly, SameSite=Lax and Secure in production.
- Sessions expire after 12 hours.
- Logout invalidates the server-side session and clears the browser cookie.
- Login failures are rate-limited: five failed attempts trigger a 10-minute lockout for the client.
- Login/logout requests enforce same-origin checks.
- API requests without an authenticated session return HTTP 401; browser page requests redirect to the login surface.
- Static CSS, JavaScript, image and other frontend assets are also behind the authentication gate.

### Deployment configuration

Render requires the following environment variables to be configured as secrets:

- `APP_USERNAME`
- `APP_PASSWORD`

The session database defaults to `data/cache/auth_sessions.sqlite3`. It is used so sessions remain valid across Gunicorn workers while allowing server-side logout invalidation.

The authentication gate is implemented at the FastAPI application middleware layer, so newly added application routes are protected automatically unless they are explicitly part of the authentication surface.

## Stock Analysis

The Stock Analysis page uses the **Nifty Total Market universe — Nifty 500 + Nifty Microcap 250 source universe**. The universe includes large-, mid-, small- and micro-cap stocks.

### Stock selector

The selector supports:

- Sector multi-select.
- Company / symbol search.
- Large Cap, Mid Cap, Small Cap and Micro Cap presets.
- Local refinement of the already-loaded universe to avoid unnecessary repeated backend requests.
- Full-universe filtering before the visible result page is limited, so sector/cap filtering is not restricted to page 1.
- Independent Filter Results collapsing while keeping selector controls usable.
- Automatic addition of the selected stock to Compare Stocks.

### Individual stock analysis

The individual report includes:

- Company summary and market-cap information.
- Valuation: P/E, Forward P/E, P/B, P/S, PEG, EV/EBITDA, EV/Revenue, Dividend Yield and Payout Ratio where meaningful.
- Profitability: ROE, ROA, Gross Margin, Operating Margin and Net Margin.
- Financial health: Debt / Equity, Current Ratio, Quick Ratio and Beta where available.
- Growth and CAGR metrics.
- Annual Income Statement, Balance Sheet and Cash Flow data.
- Historical price/performance and valuation charts, including P/E and P/B history where supported.
- Historical pedigree, consistency, shareholding, earnings-quality, capital-allocation and dilution analytics.
- Sector-aware Valuation Context.
- Fundamental Momentum.
- Quality × Growth × Valuation.
- Growth Funding & Capital Efficiency.
- Shareholding Intelligence.
- AI Insights as an interpretation layer over deterministic analysis.
- Data Notes at the bottom of the report.

### Stock analytical lenses

#### Sector-aware Valuation Context

Current P/E and/or P/B are compared with the company's own historical median. Each available multiple receives:

`Score = clamp(50 + ((Historical Median − Current Multiple) / Historical Median) × 100)`

Business-type weighting:

- Financial Services: P/B 70%, P/E 30%.
- Capital-intensive: P/E 60%, P/B 40%.
- Operating businesses: P/E 70%, P/B 30%.

Available components are re-normalized when data is missing. This is historical valuation context, not a cheap/expensive verdict or forecast.

#### Fundamental Momentum

The 0–100 Momentum Index uses five components:

- Growth momentum — 30%.
- Return momentum — 25%.
- Earnings consistency / cash conversion — 20%.
- Share/balance-sheet discipline — 15%.
- Business consistency — 10%.

For the main trajectory components, recent 3-year averages are compared with preceding 3-year averages. Available weights are normalized when data is missing. The resulting states are Strengthening (65+), Stable (45–64), or Weakening (<45).

#### Quality × Growth × Valuation

Operating businesses use P/E, ROE and 3Y earnings CAGR. Financial services use P/B, ROA and 3Y earnings CAGR. The lens is a structured analytical view rather than a new investment score.

#### Growth Funding & Capital Efficiency

Where supported, the report derives:

- `Retained-Earnings Capacity = ROE × (1 − Payout Ratio)`.
- `Growth Gap = 3Y Earnings CAGR − Retained-Earnings Capacity`.
- 3Y debt, operating-cash-flow and FCF CAGR.
- Debt / Equity, Interest Coverage, Net Debt / EBITDA and share-count CAGR.

A positive Growth Gap is an investigation signal only; it does not prove that external capital was raised.

#### Shareholding Intelligence

Latest Promoter, FII, DII, Government and Public ownership is shown. Institutional ownership is `FII + DII`. Historical changes are shown in percentage points using the available observation closest to the selected comparison period.

### Missing values

The UI distinguishes:

- **N/M — Not Meaningful** — a metric does not meaningfully apply to the business model.
- **Missing/unavailable data** — the underlying observation is unavailable.

The application does not invent fundamentals or arbitrary estimates to fill cards.

### Stock comparison and AI

Compare reuses the same stock-level engines independently for each company. It includes the Business–Valuation Matrix and Stock Comparison Summary without creating a blended comparison score.

AI Insights interpret the deterministic report and do not create new calculations, scores or numerical rankings. The deterministic report remains usable if the AI service is unavailable.

## Bond Analysis

Bond Analysis covers government and corporate bonds.

### Bond universes

- Government Bonds — G-Secs, Treasury Bills and State Development Loans.
- Corporate Bonds — normalized corporate securities from the application's source integrations.

### Discovery and filters

The selector supports search by security name, ISIN or issuer; instrument type; source; maturity; coupon; yield; trade date; issuer; weighted average yield; and corporate credit-rating filters, together with sorting and direction controls.

### Market observations

Normalized observations can contain clean/dirty price, Market YTM, bid/offer price and yield, last traded price/yield, traded value, quantity, trade count, VWAP, observation date/time, source, as-of date, data type and freshness.

### Bond analytics

The backend analytics engine can provide Current Yield, Calculated YTM, Market YTM, Accrued Interest, Macaulay Duration, Modified Duration, Convexity and DV01, together with settlement date, day-count convention and coupon frequency where available.

Missing inputs remain unavailable rather than being fabricated.

## Mutual Fund Analysis

Mutual Fund Analysis provides category-relative ranking, filters, Fund Details, comparison, rolling performance, drawdown analysis and deterministic scoring. Percentile calculations include only funds with valid data for the specific metric. AI Insights are interpretation-only.

## Mutual Fund Portfolio Builder

The portfolio builder supports 2–10 mutual funds, allocations totaling exactly 100%, historical portfolio simulation, Portfolio Health Score, Return Contribution, Drawdown & Recovery, Rolling Performance and temporary What-If Allocation scenarios.

Portfolio historical simulation combines contributing funds over their common published NAV dates without interpolation or forward filling. Zero-allocation funds do not contribute.

## Stock Portfolio Builder

The Stock Portfolio Builder is an active allocation-based analytical module. It deliberately reuses the Stock Analysis universe, fundamentals, fundamental-signal engine and historical price/chart inputs wherever possible.

### Portfolio construction

1. Search or filter the Stock Analysis universe.
2. Add the stocks required in the portfolio.
3. Assign allocation percentages.
4. Ensure total allocation is exactly 100%.
5. Continue to Portfolio Analysis.

Supported selector controls are Company/Symbol search, Sector multi-select and Large/Mid/Small/Micro Cap filters.

### Portfolio snapshot

The analysis starts with holdings count, largest position, sector count and allocation concentration. Concentration uses HHI over the stock weights.

### Portfolio Quality

Allocation-weighted metrics:

- ROE.
- ROCE.
- Revenue Growth.
- Profit Growth.
- Debt / Equity.

Coverage shows the percentage of portfolio allocation for which each metric is available.

### Portfolio Valuation

Allocation-weighted exposure metrics:

- P/E.
- P/B.
- EV / EBITDA.
- Dividend Yield.

These are exposure indicators, not mathematically aggregated portfolio valuation multiples.

### Sector Allocation

Sector exposure is the sum of holding allocations by sector and is presented as proportional visual bars. Missing sector classification is grouped as Other.

### Holding Analysis and signals

Each holding shows allocation, P/E, ROE, Revenue Growth, Debt / Equity and a shared Stock Analysis fundamental signal. Signal states are Positive, Watch, Mixed and No signal. The signal is descriptive and is not a return forecast or buy/sell instruction.

### Historical Portfolio Performance

The portfolio reports 1Y, 3Y, 5Y and 10Y historical price CAGR where available, with coverage, a CAGR bar chart and a 3Y holding view.

For each period:

`Growth Factor = (1 + Holding CAGR) ^ n`

`Portfolio Growth Factor = Σ(weight × Growth Factor)`

`Portfolio CAGR = Portfolio Growth Factor ^ (1 / n) − 1`

The calculation uses allocation-normalized geometric growth rather than allocation × CAGR. If some holdings lack the required history, only the covered allocation contributes and coverage is displayed.

This is not a transaction-level backtest and excludes dividends, taxes, transaction costs and rebalancing.

### Portfolio vs Market

The portfolio can be compared historically with:

- NIFTY 50.
- NIFTY 500.
- BSE SENSEX.

The comparison displays 1Y/3Y/5Y/10Y CAGR, coverage, CAGR difference, benchmark selection and a comparison chart. Portfolio returns reuse the existing Stock Analysis price-CAGR and geometric-growth calculation. Benchmark history is supplied by the benchmark backend endpoint.

The comparison is price-return based and excludes dividends, taxes, transaction costs and portfolio rebalancing.

### Quality × Growth Positioning Map

The positioning map consumes the existing Holding Analysis table:

- X-axis = Revenue Growth.
- Y-axis = ROE.
- Bubble size = current allocation.
- Reference lines = portfolio medians.

It is a descriptive visual rather than a new investment score.

### Portfolio Risk & Drawdown

The risk view reconstructs a historical portfolio path from annual closing prices and current allocation weights. It shows Maximum Drawdown, Annual Volatility, Current Drawdown, HHI, largest-position exposure, allocation in D/E > 1x holdings and allocation in negative-revenue-growth holdings.

Annual closing-price history can understate intra-year drawdowns. The view excludes dividends, taxes, transaction costs and rebalancing.

### What-If / Rebalancing

The temporary What-If module changes allocations across the same holdings and compares the proposed portfolio with the current portfolio. It recomputes P/E, ROE, Revenue Growth, Debt / Equity, HHI, sector exposure and allocation changes.

The proposed portfolio must total exactly 100%. The scenario is not saved and no trades are executed.

### Portfolio Action View

The Action View provides descriptive observations around position concentration, sector concentration, leverage exposure, growth exposure and valuation, plus allocation-weighted ROE, ROCE, Revenue Growth, Profit Growth, P/E, Debt / Equity and HHI.

It deliberately does not generate buy/sell recommendations or predict future returns.

### UI and visualization

Portfolio analysis is organized into distinct collapsible cards. Each card exposes key highlights while collapsed and detailed calculations or visualisations when expanded. The presentation follows the application's existing portfolio-builder interaction pattern and uses distinct visual accents and bold icons.

Visualisations include historical CAGR, holding-level performance, benchmark comparison, Quality × Growth positioning, historical portfolio path/drawdown, allocation exposure and What-If changes.

### Data notes and interpretation limits

Portfolio metrics reuse the same Stock Analysis data and calculations. Missing observations are not invented. Coverage must be read alongside any partially covered metric.

The Stock Portfolio Builder is historical and descriptive. It does not forecast future returns, guarantee outcomes, model trade execution or turn historical comparisons into recommendations.

See [`STOCK_PORTFOLIO_BUILDER.md`](STOCK_PORTFOLIO_BUILDER.md) for the complete methodology and implementation reference.

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
- `frontend/js/core/` — application-wide API, navigation, configuration and utilities.
- `frontend/js/components/` — reusable UI components.
- `frontend/js/features/stock-selection/` — Stock Analysis selector, filtering, comparison, analysis, charts, AI Insights and UI enhancements.
- `frontend/js/features/bond-analysis/` — Bond Analysis selection, filtering, bond details, analytics and UI behaviour.
- `frontend/js/features/mutual-fund-analysis/` — Mutual Fund Analysis and comparison.
- `frontend/js/features/portfolio-builder/` — Mutual Fund Portfolio Builder.
- `frontend/js/features/home/` — Home page and Help & Methodology.
- `frontend/css/features/` — feature-specific styling.

### Stock Portfolio frontend modules

- `stock-portfolio-builder.js` — portfolio construction, stock selection, filtering and allocations.
- `stock-portfolio-analysis.js` — portfolio snapshot, quality, valuation, sector allocation, holding analysis and historical performance.
- `stock-portfolio-benchmark.js` — Portfolio vs Market comparison.
- `stock-portfolio-positioning-map.js` — Quality × Growth positioning map.
- `stock-portfolio-risk-drawdown.js` — historical risk and drawdown.
- `stock-portfolio-rebalancing.js` — temporary What-If / Rebalancing analysis.
- `stock-portfolio-action-view.js` — descriptive portfolio Action View.
- `stock-portfolio-analysis-ui.js` — presentation and collapsible-card integration.
- `help-stock-portfolio.js` — Stock Portfolio Builder Help & Methodology content and legacy-help cleanup.

### Backend structure

- `backend/routes/` — thin HTTP handlers.
- `backend/services/data/` — provider and normalization layer.
- `backend/services/stocks/` — stock universe, market-cap classification, screening and stock-selection logic.
- `backend/services/bonds/` — bond normalization, selection, observations and analytics.
- `backend/services/mutual_funds/` — mutual-fund calculations and ranking.
- `backend/services/portfolio/` — mutual-fund portfolio analysis and Health Score.
- `backend/services/ai/` — AI interpretation layer.
- `backend/models/` — normalized data structures.

## Stock Analysis Stability Rules

- Mutation observers must not watch DOM changes produced by their own enhancement code.
- Quick filter interactions should operate against the loaded universe whenever possible.
- Identical lightweight stock-universe requests should be coalesced.
- Sector, search, cap and other quick controls should not rebuild the entire page repeatedly.
- Backend stock-universe loading remains independent from purely visual filter changes.
- Derived analytics reuse existing stock/pedigree/chart endpoints rather than introducing unnecessary market-data sources.

## Help & Methodology

The Help & Methodology page documents the application's screens, metrics, ratios, filters, charts, comparison tables and reports. It covers:

- Mutual Fund Analysis ranking, percentiles, risk metrics, rolling returns, drawdown and scoring.
- Mutual Fund Portfolio Builder allocation rules, historical simulation, Health Score, Return Contribution, Drawdown & Recovery, Rolling Performance and What-If scenarios.
- Stock Analysis selection, fundamental metrics, historical pedigree, shareholding, earnings quality, capital allocation, dilution, valuation context, Fundamental Momentum, Quality × Growth × Valuation, Growth Funding & Capital Efficiency, Shareholding Intelligence, comparison and AI Insights.
- Stock Portfolio Builder construction, allocation validation, portfolio quality, valuation, sector allocation, holding signals, historical performance, benchmark comparison, positioning map, risk/drawdown, What-If/Rebalancing, Action View, coverage and interpretation limits.

The Help search indexes the **visible Help DOM dynamically**, so newly added Stock Portfolio Builder help cards are searchable without maintaining a separate hard-coded search list. Selecting a search result opens the corresponding Help card/section and highlights it. Legacy "Coming Soon" Stock Portfolio Builder help is removed so search results describe the live feature rather than the old placeholder.

## Data and methodology principles

- Historical metrics are descriptive of the supported observation period and are not forecasts.
- Missing data remains missing; the application does not invent fundamentals or historical prices.
- Coverage is shown when a portfolio calculation uses only part of the allocation.
- Where a metric is not meaningful for a business model, the UI can show N/M rather than a misleading value.
- Portfolio visualisations are presentation layers over existing calculations rather than independent scoring engines.
