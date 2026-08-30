from typing import Any

from fastapi import APIRouter

from backend.services.screener import ScreenerEngine

router = APIRouter()
screener_engine = ScreenerEngine()


@router.get("/strategies")
async def list_strategies():
    return {"strategies": ["growth", "roe", "value", "quality", "overall"]}


@router.post("/run")
async def run_screener(payload: dict[str, Any]):
    raise NotImplementedError("Screener endpoint not yet implemented.")
