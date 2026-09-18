"""Minimum tests for source-scoped ``record_id`` retrieval.

Covers the three paths required for CCIL records that carry no ISIN:
  1. ``record_id`` generation (Bond model, no ISIN)
  2. service lookup by ``record_id``
  3. API lookup via ``GET /api/bonds/record/{record_id}``

No network access: providers are stubbed and the loaded bond is in-memory.
"""

from __future__ import annotations

from datetime import date

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.models.bonds import Bond, DataType, InstrumentType
from backend.routes import bonds as bonds_route
from backend.services.bonds.bond_identity import record_id_for
from backend.services.bonds.bond_service import BondService

MISSING_RECORD_ID = "ccil|t_bill|000000000000"


def _ccil_tbill(**overrides) -> Bond:
    """A CCIL T-Bill record with no ISIN (the case record_id exists for)."""
    payload = {
        "source": "CCIL",
        "instrument_type": InstrumentType.T_BILL,
        "data_type": DataType.TRADED,
        "security_name": "182 DTB 18092026",
        "maturity_date": date(2026, 9, 18),
        "coupon_rate": None,
        "isin": None,
    }
    payload.update(overrides)
    return Bond(**payload)


class TestRecordIdWithoutIsin:
    def test_record_id_is_generated_without_isin(self):
        bond = _ccil_tbill()
        expected = record_id_for(
            "CCIL",
            InstrumentType.T_BILL,
            "182 DTB 18092026",
            date(2026, 9, 18),
            None,
        )
        assert bond.isin is None
        assert bond.record_id == expected
        assert bond.record_id.startswith("ccil|t_bill|")
        assert len(bond.record_id.split("|")[2]) == 12


class TestServiceLookupByRecordId:
    @pytest.mark.asyncio
    async def test_lookup_by_record_id(self, monkeypatch):
        bond = _ccil_tbill()
        service = BondService()

        async def _fake_refresh_all_sources():
            return [bond]

        monkeypatch.setattr(service, "refresh_all_sources", _fake_refresh_all_sources)

        assert await service.get_bond_by_record_id(bond.record_id) is bond
        assert await service.get_bond_by_record_id(MISSING_RECORD_ID) is None


class TestApiLookupByRecordId:
    def test_record_route_lookup(self, monkeypatch):
        app = FastAPI()
        app.include_router(bonds_route.router, prefix="/api/bonds")
        client = TestClient(app)

        bond = _ccil_tbill()
        service = bonds_route.get_bond_service()

        async def _fake_lookup(record_id):
            return bond if record_id == bond.record_id else None

        monkeypatch.setattr(service, "get_bond_by_record_id", _fake_lookup)

        response = client.get(f"/api/bonds/record/{bond.record_id}")
        assert response.status_code == 200
        assert response.json()["record_id"] == bond.record_id

        missing = client.get(f"/api/bonds/record/{MISSING_RECORD_ID}")
        assert missing.status_code == 404
        assert "Bond not found" in missing.json()["detail"]
