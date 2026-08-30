# Market Analysis

Indian stock-market analysis web application providing stock screening, fundamental analysis, multiple ranking strategies, and AI-generated insights.

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

### Key Principles

- **Data-provider abstraction**: Stoxim integration is isolated; other providers can be swapped in later.
- **AI-provider abstraction**: Groq integration is isolated; other LLM providers can be swapped in later.
- **Deterministic scoring**: Numerical rankings are calculated independently of AI.
- **No hardcoded secrets**: All configuration comes from environment variables.
- **Dependency direction**: Frontend → Routes → Services → Models → External Providers. Never reversed.

## Directory Structure

```
Market-Analysis/
├── frontend/
│   ├── html/               # HTML pages
│   ├── js/
│   │   ├── core/           # API client, config, utilities
│   │   ├── components/     # Reusable UI components
│   │   ├── features/       # Feature-specific logic
│   │   └── pages/          # Page initialization
│   └── css/
│       ├── base.css
│       ├── layout.css
│       ├── components.css
│       └── pages/
│
├── backend/
│   ├── routes/             # HTTP route handlers
│   ├── services/           # Business logic
│   │   ├── stoxim.py       # Stoxim API client
│   │   ├── fundamentals.py # Data normalization
│   │   ├── screener.py     # Scoring/ranking logic
│   │   └── ai_insights.py  # Groq AI integration
│   ├── models/             # Data models
│   ├── utils/              # Logging, validation
│   └── config/
│       └── settings.py     # Environment-based config
│
├── data/
│   ├── cache/              # Normalized/cached fundamental data
│   ├── rankings/           # Pre-calculated rankings
│   └── raw/                # Raw data from providers
│
├── tests/
│   ├── backend/            # Python tests
│   └── frontend/           # Frontend tests
│
├── scripts/                # Data update / ranking scripts
├── .env.example            # Environment variable template
├── .gitignore
├── requirements.txt
└── run.py                  # Application entry point
```

## Environment Variables

Copy `.env.example` to `.env` and fill in your API keys:

```bash
cp .env.example .env
```

Required variables:
- `STOXIM_API_KEY` — Stoxim API key
- `GROQ_API_KEY` — Groq API key
- `APP_PORT` — Server port (default: 8000)
- `APP_DEBUG` — Debug mode (default: true)

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
pytest tests/backend/
```

## Extensibility

- **Data providers**: Add a new provider by implementing the interface in `backend/services/stoxim.py` and updating the data normalization layer.
- **AI providers**: Add a new LLM provider by implementing the interface in `backend/services/ai_insights.py`.
- **Screening strategies**: Add new strategies in `backend/services/screener.py` without touching the API or frontend.
- **Frontend framework**: The modular JS structure allows replacing the frontend framework later without major rewrites.

## Notes

- No database is used yet; data flows from providers through cache to rankings.
- Authentication is not implemented yet.
- No portfolio management yet.
