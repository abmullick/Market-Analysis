import base64
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, Response

from backend.config.settings import Settings
from backend.routes.screener import router as screener_router
from backend.routes.stocks import router as stocks_router
from backend.routes.stock_pedigree import router as stock_pedigree_router
from backend.routes.stock_supplemental import router as stock_supplemental_router
from backend.routes.stock_market_cap import router as stock_market_cap_router
from backend.routes.insights import router as insights_router
from backend.routes.portfolio import router as portfolio_router
from backend.routes.stock_portfolio_benchmarks import router as stock_portfolio_benchmarks_router
from backend.routes.mutual_funds import router as mutual_funds_router
from backend.routes.bonds import router as bonds_router

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

OG_PREVIEW_BASE64 = "PLACEHOLDER"

# Serve frontend HTML pages
@app.get("/")
async def read_root():
    with open("frontend/html/index.html", "r", encoding="utf-8") as f:
        html = f.read()
    preview_url = "https://market-analysis-g4ow.onrender.com/og-preview-20261005.jpg"
    html = html.replace(
        'https://wsrv.nl/?url=https%3A%2F%2Fcdn.jsdelivr.net%2Fgh%2Fabmullick%2FMarket-Analysis%40main%2Fstatic%2Fimages%2Fhero-market-analysis.png&amp;w=1200&amp;h=630&amp;fit=cover&amp;output=jpg',
        preview_url,
    )
    html = html.replace(
        'https://cdn.jsdelivr.net/gh/abmullick/Market-Analysis@main/static/images/hero-market-analysis.png?v=20261005',
        '/favicon.ico?v=20261005',
    )
    return HTMLResponse(content=html)


@app.get("/stocks.html")
async def read_stocks():
    return FileResponse("frontend/html/stocks.html")


@app.get("/portfolio.html")
async def read_portfolio():
    return FileResponse("frontend/html/portfolio.html")


@app.get("/stock-portfolio-builder.html")
async def read_stock_portfolio_builder():
    return FileResponse("frontend/html/stock-portfolio-builder.html")


@app.get("/portfolio-builder.html")
async def read_portfolio_builder():
    return FileResponse("frontend/html/portfolio-builder.html")


@app.get("/portfolio-select-funds.html")
async def read_portfolio_select_funds():
    return FileResponse("frontend/html/portfolio-select-funds.html")


@app.get("/mutual-funds.html")
async def read_mutual_funds():
    return FileResponse("frontend/html/mutual-funds.html")


@app.get("/help.html")
async def read_help():
    return FileResponse("frontend/html/help.html")


@app.get("/bond-analysis.html")
async def read_bond_analysis():
    return FileResponse("frontend/html/bond-analysis.html")


@app.get("/favicon.ico")
async def favicon():
    return Response(
        content=base64.b64decode(OG_PREVIEW_BASE64),
        media_type="image/jpeg",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )


@app.get("/og-preview-20261005.jpg")
async def og_preview_image():
    return Response(
        content=base64.b64decode(OG_PREVIEW_BASE64),
        media_type="image/jpeg",
        headers={
            "Cache-Control": "public, max-age=31536000, immutable",
            "Content-Disposition": "inline",
        },
    )


@app.get("/static/images/hero-market-analysis.png")
async def social_preview_image():
    return FileResponse(
        "static/images/hero-market-analysis.png",
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=86400"},
    )

# Serve static assets
app.mount("/css", StaticFiles(directory="frontend/css"), name="css")
app.mount("/js", StaticFiles(directory="frontend/js"), name="js")
app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(screener_router, prefix="/api/stocks", tags=["stocks"])
# Must precede the generic /{symbol} route in stocks_router.
app.include_router(stock_pedigree_router, prefix="/api/stocks", tags=["stocks"])
app.include_router(stocks_router, prefix="/api/stocks", tags=["stocks"])
app.include_router(stock_supplemental_router, prefix="/api/stocks", tags=["stocks"])
app.include_router(stock_market_cap_router, prefix="/api/stocks", tags=["stocks"])
app.include_router(portfolio_router, prefix="/api/portfolio", tags=["portfolio"])
app.include_router(stock_portfolio_benchmarks_router, prefix="/api/stock-benchmarks", tags=["stock-benchmarks"])
app.include_router(mutual_funds_router, prefix="/api/mutual-funds", tags=["mutual-funds"])
app.include_router(insights_router, prefix="/api/insights", tags=["insights"])
app.include_router(bonds_router, prefix="/api/bonds", tags=["bonds"])


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
