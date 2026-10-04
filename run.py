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

OG_PREVIEW_BASE64 = "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"

# Serve frontend HTML pages
@app.get("/")
async def read_root():
    with open("frontend/html/index.html", "r", encoding="utf-8") as f:
        html = f.read()
    preview_url = "https://market-analysis-g4ow.onrender.com/og-preview-20261005.png"
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
        media_type="image/png",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )


@app.get("/og-preview-20261005.png")
async def og_preview_image():
    return Response(
        content=base64.b64decode(OG_PREVIEW_BASE64),
        media_type="image/png",
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
