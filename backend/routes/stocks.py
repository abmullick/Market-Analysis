from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from backend.config.settings import Settings
from backend.services.data.fundamentals import get_stock_analysis
from backend.services.data.yahoo import YahooFinanceClient, YahooFinanceError
from backend.services.stocks.nifty_universe import (
    NiftyUniverseError,
    load_nifty_total_market,
    nifty_sectors,
)
from backend.services.stocks.screening import list_stocks

router = APIRouter()
client: YahooFinanceClient | None = None


def _get_client() -> YahooFinanceClient:
    """Create the Yahoo client lazily so Yahoo outages/rate limits cannot crash startup."""
    global client

    if client is None:
        client = YahooFinanceClient(Settings())

    return client


@router.get("/universe")
async def get_stock_universe(
    sector: Optional[str] = Query(default=None),
    query: Optional[str] = Query(default=None),
    min_market_cap_cr: Optional[float] = Query(default=None, ge=0),
    max_market_cap_cr: Optional[float] = Query(default=None, ge=0),
    min_pe: Optional[float] = Query(default=None, gt=0),
    max_pe: Optional[float] = Query(default=None, gt=0),
    min_roe: Optional[float] = Query(default=None),
    max_roe: Optional[float] = Query(default=None),
    min_pb: Optional[float] = Query(default=None, gt=0),
    max_pb: Optional[float] = Query(default=None, gt=0),
    min_peg: Optional[float] = Query(default=None, gt=0),
    max_peg: Optional[float] = Query(default=None, gt=0),
    min_roa: Optional[float] = Query(default=None),
    max_roa: Optional[float] = Query(default=None),
    include_metrics: bool = Query(default=False),
):
    try:
        # Any of these parameters means that we need to run the
        # fundamental screening logic instead of returning the
        # lightweight NSE universe.
        has_fundamental_filter = any(
            value is not None
            for value in (
                min_market_cap_cr,
                max_market_cap_cr,
                min_pe,
                max_pe,
                min_roe,
                max_roe,
                min_pb,
                max_pb,
                min_peg,
                max_peg,
                min_roa,
                max_roa,
            )
        )

        # Sector/search selection without fundamental filters uses only
        # the official NSE/Nifty classification. This keeps the selector
        # fast and avoids requesting fundamental data for every stock.
        if not include_metrics and not has_fundamental_filter:
            stocks = load_nifty_total_market()

            if sector:
                stocks = [
                    stock
                    for stock in stocks
                    if stock["sector"] == sector
                ]

            if query:
                q = query.strip().lower()

                stocks = [
                    stock
                    for stock in stocks
                    if q in stock["symbol"].lower()
                    or q in stock["name"].lower()
                ]

            return {
                "sector": sector,
                "sectors": nifty_sectors(),
                "stocks": stocks,
                "count": len(stocks),
                "universe": "Nifty Total Market",
                "classification_source": (
                    "NSE Indices / Nifty Total Market constituent CSV"
                ),
            }

        # Fundamental screening.
        #
        # PB, PEG and ROA are now passed all the way through to the
        # screening service along with the existing PE, ROE and
        # market-cap filters.
        return list_stocks(
            _get_client(),
            sector=sector,
            query=query,
            min_market_cap_cr=min_market_cap_cr,
            max_market_cap_cr=max_market_cap_cr,
            min_pe=min_pe,
            max_pe=max_pe,
            min_roe=min_roe,
            max_roe=max_roe,
            min_pb=min_pb,
            max_pb=max_pb,
            min_peg=min_peg,
            max_peg=max_peg,
            min_roa=min_roa,
            max_roa=max_roa,
        )

    except (NiftyUniverseError, YahooFinanceError) as exc:
        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc


@router.get("/{symbol}")
async def get_stock(symbol: str):
    try:
        return get_stock_analysis(
            _get_client(),
            symbol,
        )
    except YahooFinanceError as exc:
        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc


@router.get("/{symbol}/fundamentals")
async def get_fundamentals(symbol: str):
    try:
        return get_stock_analysis(
            _get_client(),
            symbol,
        )["fundamentals"]
    except YahooFinanceError as exc:
        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc