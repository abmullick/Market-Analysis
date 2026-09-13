"""Endpoint test for POST /portfolio/stock-overlap (mocked holdings)."""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.routes import portfolio as portfolio_route


def test_stock_overlap_endpoint_one_overlapping_isin(monkeypatch):
    from backend.services.data import amfi_holdings as holdings_module

    class FakeFetcher:
        async def get_all_schemes(self):
            return []

    monkeypatch.setattr(portfolio_route, "_get_fetcher", lambda: FakeFetcher())

    async def fake_fetch_holdings(self, selections, str_month=None, **kwargs):
        from backend.services.data.amfi_holdings import (
            AmfiHolding,
            AmfiHoldingsResult,
        )

        by_code = {s["scheme_code"]: s for s in selections}
        # Only the two supplied funds' holdings are ever returned.
        assert set(by_code) == {"A", "B"}
        return AmfiHoldingsResult(
            holdings=[
                AmfiHolding(scheme_code="A", scheme_name="Fund A",
                            amfi_scheme_id="1", amfi_scheme_name="Fund A",
                            isin="INE001", security_name="Stock X",
                            security_type="Investment - Equities",
                            market_value=10.0, portfolio_weight=10.0),
                AmfiHolding(scheme_code="B", scheme_name="Fund B",
                            amfi_scheme_id="2", amfi_scheme_name="Fund B",
                            isin="INE001", security_name="Stock X",
                            security_type="Investment - Equities",
                            market_value=6.0, portfolio_weight=6.0),
            ]
        )

    monkeypatch.setattr(
        holdings_module.AmfiHoldingsService, "fetch_holdings",
        fake_fetch_holdings)

    app = FastAPI()
    app.include_router(portfolio_route.router, prefix="/api/portfolio")
    resp = TestClient(app).post(
        "/api/portfolio/stock-overlap",
        json={"funds": [{"scheme_code": "A", "scheme_name": "Fund A",
                         "allocation": 60},
                        {"scheme_code": "B", "scheme_name": "Fund B",
                         "allocation": 40}]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["overlapping_stock_count"] == 1
