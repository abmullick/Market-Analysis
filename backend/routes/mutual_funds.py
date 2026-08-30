from typing import Any

from fastapi import APIRouter

router = APIRouter()


@router.get("/{fund_id}")
async def get_mutual_fund(fund_id: str):
    raise NotImplementedError("Mutual fund endpoint not yet implemented.")


@router.get("/{fund_id}/analysis")
async def get_fund_analysis(fund_id: str):
    raise NotImplementedError("Mutual fund analysis not yet implemented.")
