"""Focused tests for government-bond source aggregation in
``BondService.refresh_all_sources``.

Regression guard: the NSE security master must contribute standalone Bond
records. Previously NSE rows were only used to enrich CCIL observations, so
the API returned an empty list whenever CCIL published no records.

No network access: the provider clients are stubbed with in-memory rows.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from backend.models.bonds import CcilRawRecord, InstrumentType, NseRawRecord
from backend.services.bonds import bond_service as bond_service_module
from backend.services.bonds.bond_service import BondService

GSEC_ISIN = "IN0020300012"
GSEC_DESC = "7.15% GS 2030"
GSEC_MATURITY = "15-Jan-2030"


def _nse_record(
    description: str = GSEC_DESC,
    isin: str = GSEC_ISIN,
    maturity: str = GSEC_MATURITY,
    **overrides,
) -> NseRawRecord:
    payload = dict(
        report_type="debt-master",
        security_description=description,
        isin=isin,
        maturity_date=maturity,
        coupon_rate="7.15",
        coupon_frequency="Half-Yearly",
        face_value="100",
        issuer="Government of India",
        instrument_type="G-Sec",
        listing_status="Listed",
    )
    payload.update(overrides)
    return NseRawRecord(**payload)


def _ccil_record(**overrides) -> CcilRawRecord:
    payload = dict(
        section="central",
        security_description=GSEC_DESC,
        maturity_date=GSEC_MATURITY,
        ltp="100.50",
        lty="7.10",
    )
    payload.update(overrides)
    return CcilRawRecord(**payload)


def _stub_service(
    monkeypatch,
    *,
    ccil: list | None = None,
    nse: list | None = None,
    rbi: list | None = None,
) -> BondService:
    """Return a BondService whose three providers are in-memory stubs."""
    service = BondService()
    service._cache.invalidate()

    def _client(records):
        async def fetch_all():
            return list(records or [])

        return SimpleNamespace(fetch_all=fetch_all)

    monkeypatch.setattr(service, "_get_ccil", lambda: _client(ccil))
    monkeypatch.setattr(service, "_get_nse", lambda: _client(nse))
    monkeypatch.setattr(service, "_get_rbi", lambda: _client(rbi))
    return service


class TestNseOnlyAggregation:
    def test_nse_records_survive_when_ccil_is_empty(self, monkeypatch):
        """CCIL=0, NSE>0 must still produce populated, ISIN-bearing bonds."""
        service = _stub_service(
            monkeypatch,
            ccil=[],
            nse=[
                _nse_record(),
                _nse_record(
                    description="7.26% GS 2033",
                    isin="IN0020300092",
                    maturity="22-Aug-2033",
                    coupon_rate="7.26",
                ),
            ],
        )

        bonds = asyncio.run(service.refresh_all_sources())

        assert len(bonds) == 2
        assert {b.isin for b in bonds} == {GSEC_ISIN, "IN0020300092"}
        assert all(b.source == "NSE" for b in bonds)
        assert all(b.instrument_type == InstrumentType.G_SEC for b in bonds)

        first = next(b for b in bonds if b.isin == GSEC_ISIN)
        assert first.security_name == GSEC_DESC
        assert first.coupon_rate == 7.15
        assert first.coupon_frequency == 2
        assert first.face_value == 100.0
        assert first.listing_status == "Listed"

        # Source status must still report the NSE retrieval accurately.
        assert service.source_statuses["NSE"].status == "success"
        assert service.source_statuses["NSE"].record_count == 2
        assert service.source_statuses["CCIL"].record_count == 0

    def test_malformed_nse_row_does_not_abort_the_batch(self, monkeypatch):
        """One bad row must not discard the remaining NSE records."""
        good = _nse_record()
        bad = _nse_record(description="BROKEN ROW", isin="IN0020300099")

        service = _stub_service(monkeypatch, ccil=[], nse=[bad, good])
        real_normalize = bond_service_module.normalize_nse_record

        def flaky_normalize(raw):
            if raw.security_description == "BROKEN ROW":
                raise ValueError("malformed source row")
            return real_normalize(raw)

        monkeypatch.setattr(
            bond_service_module, "normalize_nse_record", flaky_normalize
        )

        bonds = asyncio.run(service.refresh_all_sources())

        assert [b.security_name for b in bonds] == [GSEC_DESC]


class TestCcilNseDeduplication:
    def test_same_isin_prefers_the_enriched_ccil_record(self, monkeypatch):
        """CCIL + matching NSE yields one record: the richer CCIL one."""
        service = _stub_service(
            monkeypatch, ccil=[_ccil_record()], nse=[_nse_record()]
        )

        bonds = asyncio.run(service.refresh_all_sources())

        assert len(bonds) == 1
        bond = bonds[0]
        assert bond.isin == GSEC_ISIN          # ISIN supplied by NSE enrichment
        assert bond.source == "CCIL"           # CCIL observation preserved
        assert bond.trade_date is None
        assert bond.price == 100.50            # CCIL market data not replaced
        assert bond.issue_date is None         # NSE has no issue date here
        assert bond.coupon_frequency == 2      # NSE reference field merged
        # record_id stays the documented source-scoped fallback identifier
        # (never an ISIN); dedup collapsed the pair on the shared ISIN.
        assert bond.record_id.startswith("ccil|")