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
External Providers (Stoxim, Groq)
```

### Product Modules

- **Stock Selection** — Identify stocks using fundamental criteria and ranking strategies.
- **Portfolio Analysis** — Upload/import a portfolio and analyze existing holdings.
- **Mutual Fund Analysis** — Future module for mutual fund analysis (architectural boundary created).

### Key Principles

- **Data-provider abstraction**: Stoxim integration is isolated in `backend/services/data/`; other providers can be swapped in later.
- **AI-provider abstraction**: Groq integration is isolated in `backend/services/ai/`; other LLM providers can be swapped in later.
- **Deterministic scoring**: Numerical rankings are calculated independently of AI in `backend/services/stocks/`.
- **No hardcoded secrets**: All configuration comes from environment variables via `backend/config/settings.py`.
- **Dependency direction**: Frontend → Routes → Services → Models → External Providers. Never reversed.
- **Module isolation**: Stock Selection, Portfolio Analysis, and Mutual Fund Analysis do not depend on each other's business logic.

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
│   │   ├── features/               # Feature-specific logic
│   │   │   ├── stock-selection/
│   │   │   ├── portfolio-analysis/
│   │   │   ├── mutual-fund-analysis/
│   │   │   └── home/
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
│   │   │   └── fundamentals.py
│   │   ├── stocks/                 # Stock Selection module
│   │   │   └── screener.py
│   │   ├── portfolio/              # Portfolio Analysis module
│   │   │   ├── parser.py
│   │   │   └── analysis.py
│   │   ├── mutual_funds/           # Mutual Fund Analysis module
│   │   │   └── analysis.py
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
Owns fund-specific analysis. Architectural boundary exists; implementation is future work.

**Allowed to depend on:**
- `backend/services/data/` (fundamental data)
- `backend/services/ai/` (insights only, not analysis)

**Must NOT depend on:**
- `backend/services/stocks/`
- `backend/services/portfolio/`

### Shared Data Layer
Owns market/company/fundamental data retrieval, normalization, and caching. Provides `FundamentalDataProvider` abstraction with Stoxim implementation. Product modules depend on this layer, not on Stoxim directly.

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

## Notes

- No database is used yet; data flows from providers through cache to rankings.
- Authentication is not implemented yet.
- No portfolio management persistence yet.
- Service modules currently expose placeholder interfaces and raise `NotImplementedError` until real integrations are added.
- Python runtime is pinned to 3.12 via `.python-version` for deployment compatibility.
