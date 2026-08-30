from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.config.settings import Settings
from backend.routes.screener import router as screener_router
from backend.routes.stocks import router as stocks_router
from backend.routes.insights import router as insights_router
from backend.routes.portfolio import router as portfolio_router
from backend.routes.mutual_funds import router as mutual_funds_router

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

# Serve frontend HTML pages
@app.get("/")
async def read_root():
    return FileResponse("frontend/html/index.html")


@app.get("/stocks.html")
async def read_stocks():
    return FileResponse("frontend/html/stocks.html")


@app.get("/portfolio.html")
async def read_portfolio():
    return FileResponse("frontend/html/portfolio.html")


@app.get("/mutual-funds.html")
async def read_mutual_funds():
    return FileResponse("frontend/html/mutual-funds.html")

# Serve static assets
app.mount("/css", StaticFiles(directory="frontend/css"), name="css")
app.mount("/js", StaticFiles(directory="frontend/js"), name="js")
app.mount("/static", StaticFiles(directory="static"), name="static")

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
