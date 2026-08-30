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
│   │   │   └── mutual-fund-analysis/
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
│           └── mutual-fund-analysis.css
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
- `APP_PORT` — Server port (default: `8000`)
- `APP_DEBUG` — Debug mode (default: `true`)

## Running Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Run the application
python run.py
```

The API will be available at `http://localhost:8000`.

## Testing

```bash
pytest tests/
```

## Module Responsibilities

### Stock Selection
Owns screening criteria, scoring, ranking, and selection strategies. Consumes normalized fundamental data and produces ranked stock lists. Independent from portfolio analysis and mutual fund logic.

### Portfolio Analysis
Owns portfolio upload, parsing, holdings, portfolio weights, holding-level analysis, and portfolio-level analysis. May share the scoring engine with Stock Selection but has its own analysis layer.

### Mutual Fund Analysis
Owns fund-specific analysis. Architectural boundary exists; implementation is future work.

### Shared Data Layer
Owns market/company/fundamental data retrieval, normalization, and caching. Provides `FundamentalDataProvider` abstraction with Stoxim implementation. Product modules depend on this layer, not on Stoxim directly.

### AI Layer
Owns prompt construction, AI provider communication, and structured AI response handling. Provides `AIProvider` abstraction with Groq implementation. AI is an interpretation layer only; it does not determine numerical rankings or retrieve fundamental data.

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
