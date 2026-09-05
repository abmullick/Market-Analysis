# Market Analysis

Modular Indian stock-market analysis platform with three product areas: Stock Selection, Portfolio Analysis, and Mutual Fund Analysis.

## Architecture

The application follows a layered architecture with strict separation of concerns:

```
Frontend (HTML/CSS/JS)
    ↓
Routes/API (FastAPI)
    ↓
Services (business logic)
    ↓
Models (data structures)
    ↓
External Providers (Stoxim, Groq, MFAPI, TigZig)
```

### Product Modules

- **Stock Selection** — Identify stocks using fundamental criteria and ranking strategies.
- **Portfolio Analysis** — Upload/import a portfolio and analyze existing holdings.
- **Mutual Fund Analysis** — Rank mutual funds by normalized multi-metric scoring, compare funds side-by-side, inspect fund details with NAV history, rolling returns, category-relative percentile analysis, drawdown analysis, and a rich ranking page with top-3 highlights, per-fund strengths/trade-offs, holistic AI Ranking Insights, and a transparent "How ranking works" methodology breakdown.

### Key Principles

- **AI-provider abstraction**: Groq integration is isolated in `backend/services/ai/`; other LLM providers can be swapped in later.
- **Deterministic scoring**: Numerical rankings are calculated independently of AI in `backend/services/stocks/` and `backend/services/mutual_funds/`.
- **No hardcoded secrets**: All configuration comes from environment variables via `backend/config/settings.py`.
- **Dependency direction**: Frontend → Routes → Services → Models → External Providers. Never reversed.
- **Module isolation**: Stock Selection, Portfolio Analysis, and Mutual Fund Analysis do not depend on each other's business logic.

### AI Insights
- AI actions are interpretation-only. The deterministic ranking engine remains authoritative for metrics, scores, ranks, percentiles, screening, and weighting.
- **Fund Insights** uses `POST /api/mutual-funds/{scheme_code}/insights` and is available from Fund Details.
- **Ranking Insights** uses `POST /api/mutual-funds/ranking-insights` and interprets the whole currently displayed ranking.
- Both actions require an explicit click. Opening Fund Details, running a ranking, loading results, or changing controls does not trigger an AI request.
- Ranking Insights snapshots the exact configuration from the last successful ranking request: categories, screening filters, criteria, weights, and `auto_renormalize`.
- Ranking AI input is compact and allowlisted: at most 10 top funds and 5 bottom funds, with no full ranking list, NAV history, raw rolling-return series, complete holdings, or full fund-detail objects.
- Ranking AI context targets 12 KB and has a 16 KB serialized hard maximum. Optional ranking evidence is reduced before the request; essential configuration is never silently dropped.
- Responses are structured and rendered as interpretation, drivers/key points, trade-offs/risks, opportunities, and recommendations. AI does not recalculate or alter deterministic results.
- Provider configuration uses `GROQ_API_KEY` and optional `GROQ_MODEL`, defaulting to `openai/gpt-oss-120b`. Provider credentials are server-side only.

## Directory Structure

```
Market-Analysis/
├── frontend/
│   ├── html/                       # HTML pages
│   │   ├── index.html
│   │   ├── stocks.html
│   │   ├── portfolio.html
│   │   └── mutual-funds.html
│   ├── js/
│   │   ├── core/                   # API client, config, navigation, utilities
│   │   │   ├── api.js
│   │   │   ├── config.js
│   │   │   ├── navigation.js
│   │   │   └── utils.js
│   │   ├── components/             # Reusable UI components
│   │   │   ├── table.js
│   │   │   ├── filters.js
│   │   │   ├── modal.js
│   │   │   └── loading.js
│       │   ├── features/               # Feature-specific logic
│       │   │   ├── stock-selection/
│       │   │   ├── portfolio-analysis/
│       │   │   ├── mutual-fund-analysis/  # Ranking page + fund-detail modal + comparison
│       │   │   │   ├── index.js          # Ranking page entry, controls, table, top-3, why-dialog
│       │   │   │   ├── fund-detail.js    # Fund Details modal (sections, KPIs, N/A treatment)
│       │   │   │   ├── ranking-ai-context.js  # Bounded ranking-level AI context
│       │   │   │   ├── ranking-ai-request.js  # Ranking Insights API request
│       │   │   │   ├── ranking-ai-response.js # Ranking Insights presentation
│       │   │   │   ├── comparison/       # Compare Funds sub-modules (identity, KPI, chart, drawdown, rolling returns, performance summary, NAV history)
│       │   │   │   └── fund-detail/      # Fund Details sub-modules (drawdown chart, holdings, category analysis)
│       │   │   └── home/
│   │   └── pages/                  # Page initialization
│   │       ├── stocks.js
│   │       ├── portfolio.js
│   │       └── mutual-funds.js
│   └── css/
│       ├── base.css
│       ├── layout.css
│       ├── components.css
│       └── features/
│           ├── stock-selection.css
│           ├── portfolio-analysis.css
│           ├── mutual-fund-analysis.css
│           └── home.css
│
├── backend/
│   ├── routes/                     # HTTP route handlers
│   │   ├── screener.py
│   │   ├── stocks.py
│   │   ├── portfolio.py
│   │   ├── mutual_funds.py
│   │   └── insights.py
│   ├── services/                   # Business logic
│   │   ├── data/                   # Shared data provider layer
│   │   │   ├── stoxim.py
│   │   │   ├── fundamentals.py
│   │   │   ├── mfapi.py
│   │   │   └── tigzig.py
│   │   ├── stocks/                 # Stock Selection module
│   │   │   └── screener.py
│   │   ├── portfolio/              # Portfolio Analysis module
│   │   │   ├── parser.py
│   │   │   └── analysis.py
│   │   ├── mutual_funds/           # Mutual Fund Analysis module
│   │   │   ├── fetcher.py
│   │   │   ├── calculator.py       # NAV → metrics (CAGR, vol, drawdown, etc.)
│   │   │   ├── ranking.py          # RankingEngine + CRITERIA / LABELS / lookback
│   │   │   ├── lookback.py         # CRITERIA_LOOKBACK_YEARS map
│   │   │   ├── fund_grouper.py     # Variant grouping & ranking candidate selection
│   │   │   ├── analysis.py         # Category-relative percentile analysis
│   │   │   ├── cache.py            # Per-fund metric & category cache
│   │   │   ├── normalizer.py
│   │   │   └── category_normalizer.py
│   │   └── ai/                     # AI insight service
│   │       └── groq.py
│   ├── models/                     # Data models
│   │   ├── stock.py
│   │   ├── fundamentals.py
│   │   └── portfolio.py
│   ├── utils/                      # Logging, validation
│   │   ├── logging.py
│   │   └── validation.py
│   └── config/
│       └── settings.py             # Environment-based config
│
├── data/
│   ├── cache/                      # Normalized/cached fundamental data
│   ├── rankings/                   # Pre-calculated rankings
│   └── raw/                        # Raw data from providers
│
├── tests/
│   ├── stocks/                     # Stock Selection tests
│   ├── portfolio/                  # Portfolio Analysis tests
│   ├── mutual_funds/               # Mutual Fund Analysis tests
│   ├── ai/                         # AI service tests
│   └── data/                       # Data provider tests
│
├── scripts/                        # Data update / ranking scripts
│   ├── update_data.py
│   └── calculate_rankings.py
│
├── .env.example                     # Environment variable template
├── .gitignore
├── .python-version                  # Python runtime version (3.12)
├── requirements.txt
└── run.py                          # Application entry point
```

## Environment Variables

Copy `.env.example` to `.env` and fill in your API keys:

```bash
cp .env.example .env
```

Required variables:
- `STOXIM_API_KEY` — Stoxim API key
- `GROQ_API_KEY` — Groq API key
- `GROQ_MODEL` — optional Groq model override; defaults to `openai/gpt-oss-120b`
- `APP_ENV` — Application environment (default: `development`)
- `APP_PORT` — Server port (default: `20090`)
- `APP_DEBUG` — Debug mode (default: `true`)

## Running Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Run the application
python run.py
```

The API will be available at `http://localhost:20090`.

## Testing

```bash
pytest tests/
```

## Module Responsibilities

### Stock Selection
Owns screening criteria, scoring, ranking, and selection strategies. Consumes normalized fundamental data and produces ranked stock lists. Independent from portfolio analysis and mutual fund logic.

**Allowed to depend on:**
- `backend/services/data/` (fundamental data)
- `backend/services/ai/` (insights only, not scoring)

**Must NOT depend on:**
- `backend/services/portfolio/`
- `backend/services/mutual_funds/`

### Portfolio Analysis
Owns portfolio upload, parsing, holdings, portfolio weights, holding-level analysis, and portfolio-level analysis. Has its own analysis layer separate from Stock Selection.

**Allowed to depend on:**
- `backend/services/data/` (fundamental data)
- `backend/services/ai/` (insights only, not analysis)

**Must NOT depend on:**
- `backend/services/stocks/`
- `backend/services/mutual_funds/`

### Mutual Fund Analysis
Owns fund-specific analysis including metric calculation from NAV history, category-relative percentile ranking, multi-fund comparison, fund detail modal with rolling returns and drawdown analysis, and screening/preset workflows.

**Allowed to depend on:**
- `backend/services/data/` (fundamental data, NAV history, TigZig dataset)
- `backend/services/ai/` (insights only, not scoring)

**Must NOT depend on:**
- `backend/services/stocks/`
- `backend/services/portfolio/`

### Shared Data Layer
Owns market/company/fundamental data retrieval, normalization, and caching. Provides `FundamentalDataProvider` abstraction with Stoxim implementation and `MutualFundFetcher` abstraction with MFAPI/TigZig implementations. Product modules depend on this layer, not on providers directly.

**Must NOT depend on:**
- Any product module (`stocks/`, `portfolio/`, `mutual_funds/`)

### AI Layer
Owns prompt construction, AI provider communication, and structured AI response handling. Provides `AIProvider` abstraction with Groq implementation. AI is an interpretation layer only; it does not compute numerical scores or fetch fundamentals directly.

**Must NOT depend on:**
- Any product module (`stocks/`, `portfolio/`, `mutual_funds/`)
- `backend/services/data/` (data retrieval)

## Architectural Rules for New Enhancements

These rules are mandatory for all contributors. Any enhancement that violates these rules must be refactored before merging.

### 1. Dependency Direction
All dependencies must flow in this direction only:
```
Frontend → Routes → Services → Models → External Providers
```
Never create reverse dependencies. For example:
- **FORBIDDEN**: `backend/services/stocks/` importing from `backend/services/portfolio/`
- **FORBIDDEN**: Frontend calling external providers directly
- **FORBIDDEN**: Routes containing business logic

### 2. Module Isolation
Product modules must remain isolated:
- **Stock Selection** must not import from **Portfolio Analysis**
- **Portfolio Analysis** must not import from **Stock Selection**
- **Mutual Fund Analysis** must not import from either product module
- All three may share `backend/services/data/` and `backend/services/ai/`

### 3. Frontend Structure
- **`core/`** — Application-wide infrastructure only (`api.js`, `config.js`, `navigation.js`, `utils.js`). Never put feature-specific business logic here.
- **`components/`** — Reusable UI components (`table.js`, `filters.js`, `modal.js`, `loading.js`). Keep them generic.
- **`features/`** — Feature-specific logic. Each product area gets its own directory:
  - `stock-selection/`
  - `portfolio-analysis/`
  - `mutual-fund-analysis/`
  - `home/`
- **`pages/`** — Page initialization only. Coordinates features and components for a single page.
- **`css/features/`** — Feature-specific styles. Do not put feature styles in `base.css` or `layout.css`.

### 4. Backend Structure
- **`routes/`** — Thin HTTP handlers. Validate input, call services, return responses. No business logic.
- **`services/data/`** — Provider implementations and normalization. Everything else depends on this, never the reverse.
- **`services/stocks/`** — Stock Selection business logic.
- **`services/portfolio/`** — Portfolio Analysis business logic.
- **`services/mutual_funds/`** — Mutual Fund Analysis business logic.
- **`services/ai/`** — AI provider abstraction and prompt construction.
- **`models/`** — Pure data structures (Pydantic models). No business logic.
- **`utils/`** — Shared utilities (logging, validation). No feature-specific code.

### 5. Data Ownership
- **Stock Selection** owns: screening criteria, scoring, ranking, selection strategies
- **Portfolio Analysis** owns: portfolio upload, parsing, holdings, weights, holding-level analysis, portfolio-level analysis
- **Mutual Fund Analysis** owns: fund-specific analysis
- **Shared data layer** owns: data retrieval, normalization, caching
- **AI layer** owns: prompt construction, provider communication, structured response handling

### 6. AI Constraints
- AI must NOT determine numerical rankings or scores
- AI must NOT retrieve fundamental data directly
- AI must NOT replace the scoring engine
- AI is an interpretation/explanation layer only
- All AI calls must happen server-side; never expose API keys to frontend

### 7. Testing Requirements
- Tests must be organized by feature boundary: `tests/stocks/`, `tests/portfolio/`, `tests/mutual_funds/`, `tests/ai/`, `tests/data/`
- Stock scoring tests must not require real Stoxim calls
- AI tests must not require real Groq calls
- Portfolio parser tests must use test fixtures
- Use mocks/dependency injection where appropriate
- All tests must pass before merging: `pytest tests/`

### 8. Prohibited Patterns
- **FORBIDDEN**: One giant Python/JS/HTML file
- **FORBIDDEN**: Mixing API calls, business logic, and UI logic in the same module
- **FORBIDDEN**: Hardcoding API keys or configuration
- **FORBIDDEN**: Duplicating common functions across features
- **FORBIDDEN**: Tight coupling between data providers, scoring, and UI
- **FORBIDDEN**: Product modules depending on each other's business logic
- **FORBIDDEN**: Exposing secrets to frontend JavaScript
- **FORBIDDEN**: Creating duplicate implementations of existing functionality

### 9. Adding New Features
When adding a new feature:
1. Determine which product module it belongs to (Stock Selection, Portfolio Analysis, or Mutual Fund Analysis)
2. Place backend code in the appropriate `backend/services/<module>/` subdirectory
3. Place frontend code in the appropriate `frontend/js/features/<module>/` directory
4. Place tests in the corresponding `tests/<module>/` directory
5. Add routes in `backend/routes/` with the appropriate prefix
6. Do not modify other product modules' business logic
7. If the feature requires new shared infrastructure, add it to `backend/services/data/` or `backend/services/ai/`

### 10. Replacing Providers
To replace Stoxim or Groq:
1. Implement the existing abstraction interface (`FundamentalDataProvider` or `AIProvider`)
2. Add the new implementation to the appropriate `backend/services/` subdirectory
3. Update configuration in `backend/config/settings.py` if needed
4. Do not modify product modules (`stocks/`, `portfolio/`, `mutual_funds/`)

## Extensibility

- **Data providers**: Add a new provider by implementing the interface in `backend/services/data/`.
- **AI providers**: Add a new LLM provider by implementing the interface in `backend/services/ai/`.
- **Screening strategies**: Add new strategies in `backend/services/stocks/screener.py` without touching the API or frontend.
- **Frontend framework**: The modular JS structure allows replacing the frontend framework later without major rewrites.

## Deployment

### Render

1. Push the repository to GitHub.
2. Create a new **Web Service** on Render and connect your repository.
3. Configure the service with these settings:
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn run:app --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT`
4. Set the following environment variables in the Render dashboard:
   - `STOXIM_API_KEY`
   - `GROQ_API_KEY`
   - `APP_ENV` — set to `production`
   - `APP_DEBUG` — set to `false`
5. Deploy the service.

## Mutual Fund Analysis Features

### Ranking Methodology
- **Multi-metric scoring** across 10 normalized metrics grouped into four buckets: Performance (1Y/3Y/5Y/10Y CAGR + 1Y return), Risk-Adjusted (Sharpe, Sortino), Risk (annualized volatility, maximum drawdown, downside deviation), and Consistency (1Y rolling-return positive percentage).
- Per-metric min/max normalization within the current category, with lower-is-better metrics (volatility, drawdown, downside) inverted so higher always means better.
- **`CRITERIA_LOOKBACK_YEARS`** (`backend/services/mutual_funds/lookback.py`) — canonical lookback window per criterion (1Y → 1 year, 5Y → 5 years, etc.). The fund detail endpoint fetches NAV for `max(lookback) + 90-day buffer`.
- **Built-in presets** (`frontend/js/features/mutual-fund-analysis/index.js` `PRESETS`): Best Overall, Highest Returns, Lowest Risk, Best Consistency, and Custom.
- **Auto-renormalization** of weights to sum to 100% — the RankingEngine never returns a sub-100% weighted overall score.
- **Per-fund component scores** (`criteria_scores[].score` & `criteria_scores[].weight`) are returned by `/api/mutual-funds/rank` and are the basis for the in-UI "Why this fund ranks here" dialog (top-2 strengths, bottom-2 trade-offs).

### Pages
- **Ranking Page** (`mutual-funds.html`)
  - Category multi-select + AUM / AMC / first-NAV-date screening filters.
  - Preset selector, custom criteria-weight editor, screening toggle.
  - "How ranking works" sidebar panel that shows the four groups with live weight bars and total active weight, sourced from the active preset (or computed from Custom criteria).
  - Header: title + description + `N funds matching current filters` count pill.
  - **Top 3 strip** — highlighted podium cards (#1 with a subtle green wash, #2/#3 side-by-side), each with a "Why?" dialog.
  - **Summary explanation** explaining which metric groups contribute to the active preset.
  - **Active filter chips bar** — removable pills for each selected category and screener filter, with a "Clear All" action.
  - **Ranking table** — rank pill (green/amber for top 3), category-context indicator (top decile / upper third / mid / lower third / bottom quintile), per-row strengths/trade-offs chips, and a "Why?" column opening a per-fund detail dialog.
  - **AI Ranking Insights** — an explicit summary action that interprets the currently displayed ranking, its exact successful configuration, the top 10 funds, and a bounded bottom-five sample. It does not run automatically when ranking results load or when controls change.
  - **Data freshness strip** below the summary — "Data as of DD MMM YYYY" (max of all `nav_date` in the ranked set) and "Fund inception range" with tooltip.
  - **Empty state** — dashed-border card with "Clear All Filters" CTA that resets categories and screener filters and re-runs the ranking.
- **Fund Details Modal**
  - Identity badges (AMC, category, plan, option), inception / fund age / history / data points.
  - **Data-status strip** — "Data as of" (from `data_end_date`), "History from" (from `data_start_date`), "Coverage" (range + data points), with a soft green dot.
  - "At a Glance" KPI cards (3Y/5Y CAGR, Volatility, Sharpe, Sortino, Max Drawdown) — each shows its period label (3Y / 5Y / Full history) and explains "Not available" via a tooltip when fund age < required period or data points < 2.
  - Performance Summary table (1Y / 3Y / 5Y / 10Y / Since-Inception) with the same N/A reason treatment.
  - Historical NAV chart with period toggle, Risk & Risk-Adjusted section, Drawdown subsection, Rolling Returns with 1Y/3Y/5Y controls and "Insufficient history" state, Category-relative percentile table, Portfolio (asset allocation + top holdings), and Fund Details metadata grid.
  - **AI Insights** — an explicit action that interprets the selected fund using its deterministic metrics, ranking evidence, category analysis, and the exact ranking configuration that produced the displayed result.
- **Compare Funds** (`showComparisonView` in `index.js`)
  - Header with a compact **Comparison period** strip — `DD MMM YYYY – DD MMM YYYY (YYYY → YYYY)` computed as the *intersection* of the selected funds' histories (`max(starts)` to `min(ends)`).
  - Amber "Some funds have shorter histories" pill when the common period is narrower than the union, with a tooltip explaining the overlap.
  - Identity grid, F1/F2/F3 legend chips, KPI cards, full metric comparison table, drawdown / rolling returns / NAV history / risk-return modules.
  - Existing compare-checkbox selection (max 5) and `Compare Funds` action bar preserved.

### Transparency & Data Freshness
- **"Data as of" / "History from"** indicators on the Ranking page summary, Fund Details header, and Comparison header — every date is sourced from existing API fields (`data_end_date`, `data_start_date`, `nav_date`, `first_nav_date`).
- **N/A treatment** distinguishes between "Insufficient history" (fund age < required years), "Insufficient data points", and "Data unavailable" using only data already returned by the API.
- **Calculation periods** are made explicit via per-KPI period labels and the `How ranking works` methodology panel — no new formulas or lookback logic introduced.
- **Common comparison period** is computed and shown to make it obvious when funds have different available histories; no calculation change.
- No freshness threshold is invented — dates are shown without an arbitrary "stale" classification, per the constraint to avoid guessing.

### Caching & Data
- **Per-fund metric cache** keyed by `(scheme_code, lookback_years)` — `backend/services/mutual_funds/cache.py`.
- **Category-level cache** for percentile calculations, refreshed on data source changes.
- **24-hour category-level cache** for percentile calculations and per-fund metric cache to minimize recalculation.
- **TigZig** metadata dataset supplies AUM, first NAV date, and other fund-level attributes that enrich the ranking payload.

## Recent Enhancements

These were added on top of the existing architecture without changing any calculation, ranking, or API behaviour:

- **Ranking Page Polish** — Visual and transparency refinements to the Mutual Fund Ranking page only: top-3 podium strip, "How ranking works" methodology panel, per-fund strengths/trade-offs chips, "Why this fund ranks here" dialog, category-context indicator, active filter chips bar, and a richer summary header. Same scores, same order, same API contract.
- **Compare Funds Polish** — F1/F2/F3 legend chips, identity card per fund, KPI cards with best-value highlighting, sticky metric label, and a Comparison period strip showing the common `max(starts) → min(ends)` overlap across selected funds.
- **Fund Details Polish** — Restructured into 8 sections (Identity, At a Glance, Performance, NAV, Risk & Risk-Adjusted, Rolling Returns, Portfolio, Fund Details) with consistent typography, spacing, and semantic colors. No new analytics or metrics added.
- **Screener Polish** — Sidebar section grouping (Fund / Preset / Criteria / Screener), active filter chips with "Clear All" action, and improved empty state.
- **Data Transparency & Freshness** — Compact "Data as of" / "History from" / "Coverage" indicators on the Ranking summary, Fund Details header, and Comparison header. Calculation periods made explicit on each KPI card. "Not available" treatment now distinguishes "Insufficient history" from "Data unavailable" using only data already returned by the API. The application defines no freshness threshold, so dates are shown without an arbitrary "stale" label.
- **Backend additions** — `backend/services/mutual_funds/lookback.py` (`CRITERIA_LOOKBACK_YEARS`) and `backend/services/mutual_funds/fund_grouper.py` (variant grouping + ranking-candidate selection) were added; the public API contract is unchanged.

## Notes

- No database is used yet; data flows from providers through cache to rankings.
- Authentication is not implemented yet.
- No portfolio management persistence yet.
- The Mutual Fund Analysis service layer is fully implemented (`fetcher`, `calculator`, `ranking`, `analysis`, `cache`, `lookback`, `fund_grouper`). The Stock Selection and Portfolio Analysis service modules continue to evolve.
- Python runtime is pinned to 3.12 via `.python-version` for deployment compatibility.
