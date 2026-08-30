from backend.config.settings import Settings
from backend.routes.screener import router as screener_router
from backend.routes.stocks import router as stocks_router
from backend.routes.insights import router as insights_router
from fastapi import FastAPI

settings = Settings()

app = FastAPI(
    title="Market Analysis API",
    description="Indian stock-market analysis with screening, fundamentals, and AI insights.",
    version="0.1.0",
)

app.include_router(screener_router, prefix="/api/screener", tags=["screener"])
app.include_router(stocks_router, prefix="/api/stocks", tags=["stocks"])
app.include_router(insights_router, prefix="/api/insights", tags=["insights"])


@app.get("/health")
async def health_check():
    return {"status": "ok"}
