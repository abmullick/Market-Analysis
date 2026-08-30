from typing import Any

from fastapi import APIRouter

router = APIRouter()


@router.post("/upload")
async def upload_portfolio():
    raise NotImplementedError("Portfolio upload not yet implemented.")


@router.get("/analysis")
async def get_portfolio_analysis():
    raise NotImplementedError("Portfolio analysis not yet implemented.")
