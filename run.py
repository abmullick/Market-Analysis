from backend.config.settings import Settings
from backend.routes.screener import router as screener_router
from backend.routes.stocks import router as stocks_router
from backend.routes.insights import router as insights_router
from backend.routes.portfolio import router as portfolio_router
from backend.routes.mutual_funds import router as mutual_funds_router
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

settings = Settings()

app = FastAPI(
    title="Market Analysis API",
    description="Indian stock-market analysis with screening, fundamentals, portfolio analysis, and AI insights.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(screener_router, prefix="/api/stocks", tags=["stocks"])
app.include_router(stocks_router, prefix="/api/stocks", tags=["stocks"])
app.include_router(portfolio_router, prefix="/api/portfolio", tags=["portfolio"])
app.include_router(mutual_funds_router, prefix="/api/mutual-funds", tags=["mutual-funds"])
app.include_router(insights_router, prefix="/api/insights", tags=["insights"])


@app.get("/health")
async def health_check():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "run:app",
        host="0.0.0.0",
        port=settings.app_port,
        reload=settings.app_debug,
    )
