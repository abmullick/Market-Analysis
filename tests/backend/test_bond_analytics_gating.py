"""Analytics gating tests: metrics only from source-validated inputs.

Phase 1/2 regression coverage for the Bond analytics engine:
  - valid, complete inputs -> full metric set;
  - missing inputs -> metric is None + explanatory reason (never fabricated);
  - invalid inputs -> gated with reasons (no nonsense YTM / negative-price);
  - zero-coupon (T-Bill) path preserved;
  - government semi-annual convention applied transparently;
  - source-provided (CDSL) schedules preferred and labelled;
  - corporate rich-detail term merging (frequency/day-count/dates);
  - corporate analytics service path + caching.
"""
from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from backend.models.bonds import (
    Bond,
    CdslCashFlowEvent,
    DataType,
    DayCountConvention,
    InstrumentType,
)
from backend.services.bonds.bond_analytics import compute_analytics
from backend.services.bonds.bond_cashflows import build_cash_flow_schedule
from backend.services.bonds.bond_normalizer import _parse_coupon_frequency
from backend.services.bonds.bond_service import _merge_rich_detail_into_bond


SETTLEMENT = date(2026, 9, 18)


def _satin_bond(**overrides) -> Bond:
    """INE03K307066 with the CDSL-published terms (verified live 2026-09-18)."""
    fields = dict(
        isin="INE03K307066",
        security_name="SATIN FINSERV LIMITED 10.95 NCD 10MR27 FVRS1LAC",
        issuer="SATIN FINSERV LIMITED",
        instrument_type=InstrumentType.CORPORATE,
        maturity_date=date(2027, 3, 10),
        redemption_date=date(2027, 3, 10),
        interest_start_date=date(2025, 10, 10),
        coupon_rate=10.95,
        coupon_frequency=12,
        face_value=100000.0,
        day_count_convention=DayCountConvention.ACT_360,
        source="CDSL",
        data_type=DataType.TRADED,
        exchange="NSE",
        price=101.06,
        ytm=9.0,
        trade_date=SETTLEMENT,
    )
    fields.update(overrides)
    return Bond(**fields)


class TestValidCompleteInputs:
    def test_settlement_date_drives_accrual_and_remaining_flows(self):
        """The settlement date drives accrued-interest days and the set of
        remaining (future) cash flows used for YTM/duration/convexity/DV01.

        For a monthly-paying bond settled on 2026-09-18 with coupons on the
        10th of each month, the previous coupon is 2026-09-10 (8 days accrued)
        and exactly 6 payments remain after settlement (10-Oct-2026 through
        10-Mar-2027, the last combining coupon + redemption).
        """
        a = compute_analytics(_satin_bond(), settlement_date=SETTLEMENT)

        assert a.settlement_date == SETTLEMENT
        assert a.accrued_interest_days == 8
        assert a.accrued_interest is not None

        cfs = a.cash_flows
        assert cfs is not None
        # Full schedule spans the whole interest window.
        assert len(cfs) >= 18

        future = [c for c in cfs if c["date"] > SETTLEMENT]
        assert len(future) == 6
        assert future[0]["date"] == date(2026, 10, 10)
        assert future[-1]["date"] == date(2027, 3, 10)
        assert future[-1]["total"] == 100.0 + future[-1]["coupon"]

    def test_past_coupons_remain_in_schedule_but_not_in_pricing(self):
        """Cash-flow schedules report the full payment calendar (including
        already-paid coupons), but YTM, duration, convexity and DV01 only use
        flows with date > settlement_date.

        Verify by constructing the same bond on two settlement dates: when the
        settlement date moves forward by one coupon period, the number of
        future flows used for pricing drops by one.
        """
        base = Bond(
            isin="INE-PAST-FUTURE",
            security_name="Past/Future Test Bond",
            issuer="Issuer",
            instrument_type=InstrumentType.GOVERNMENT,
            coupon_rate=8.0,
            coupon_frequency=2,
            day_count_convention=DayCountConvention.THIRTY_360,
            face_value=100.0,
            redemption_date=date(2027, 4, 10),
            price=100.0,
            ltp=100.0,
            ytm=8.0,
        )

        r1 = compute_analytics(base, settlement_date=date(2025, 9, 1))
        future1 = [c for c in (r1.cash_flows or []) if c["date"] > date(2025, 9, 1)]

        r2 = compute_analytics(base, settlement_date=date(2025, 10, 10))
        future2 = [c for c in (r2.cash_flows or []) if c["date"] > date(2025, 10, 10)]

        assert len(future2) == len(future1) - 1

        past_present = any(
            c["date"] == date(2025, 10, 10) for c in (r2.cash_flows or [])
        )
        assert past_present

    def test_satin_full_metric_set(self):
        a = compute_analytics(_satin_bond(), settlement_date=SETTLEMENT)

        assert a.current_yield == pytest.approx(
            10.95 * 100.0 / (101.06 - a.accrued_interest), abs=1e-6
        )
        # Plausible solved YTM near the source-reported WAY of 9.00% — and
        # critically NOT the old degenerate single-flow artifact.
        assert a.calculated_ytm is not None
        assert 0.0 < a.calculated_ytm < 30.0
        assert abs(a.calculated_ytm - 9.0) < 3.0
        # Market YTM preserved separately.
        assert a.market_ytm == 9.0
        assert a.cash_flow_source == "calculated"
        # Monthly schedule 10-Oct-2025 .. 10-Mar-2027 = 18 payments.
        assert len(a.cash_flows) == 18
        assert a.cash_flows[0]["date"] == date(2025, 10, 10)
        assert a.cash_flows[-1]["date"] == date(2027, 3, 10)
        assert a.cash_flows[-1]["principal"] == 100.0
        assert a.cash_flows[-1]["coupon"] == pytest.approx(10.95 / 12, abs=1e-9)
        assert a.macaulay_duration is not None
        assert a.modified_duration is not None
        assert a.modified_duration < a.macaulay_duration
        assert a.convexity is not None
        assert a.dv01 is not None
        assert a.dv01 < 1.0  # per 100 par
        assert not a.unavailable_metrics
        # Face value disclosed in notes (per-100-par basis).
        assert any("per 100 par" in n for n in a.notes)

    def test_accrued_interest_present_with_schedule(self):
        a = compute_analytics(_satin_bond(), settlement_date=SETTLEMENT)
        # 18-Sep is 8 days after the 10-Sep monthly coupon.
        assert a.accrued_interest is not None
        assert a.accrued_interest >= 0
        assert a.accrued_interest_days == 8


class TestMissingInputs:
    def test_missing_frequency_blocks_schedule_and_ytm(self):
        bond = _satin_bond(coupon_frequency=None)
        a = compute_analytics(bond, settlement_date=SETTLEMENT)

        assert a.cash_flows is None
        assert a.cash_flow_source is None
        assert a.unavailable_metrics["cash_flows"] == (
            "Coupon frequency not published "
            "(cannot assume annual or semi-annual)."
        )
        # YTM needs the schedule — unavailable with the same root cause.
        assert a.calculated_ytm is None
        assert a.unavailable_metrics["calculated_ytm"] == (
            a.unavailable_metrics["cash_flows"]
        )
        for metric in ("macaulay_duration", "modified_duration", "convexity", "dv01"):
            assert a.unavailable_metrics[metric] == (
                a.unavailable_metrics["cash_flows"]
            )
        # Current yield only needs coupon + price — still computed (traded
        # price used because accrued interest is unavailable without a
        # schedule).
        assert a.current_yield == pytest.approx(10.95 * 100.0 / 101.06, abs=1e-6)

    def test_missing_coupon_blocks_schedule_and_current_yield(self):
        bond = _satin_bond(coupon_rate=None)
        a = compute_analytics(bond, settlement_date=SETTLEMENT)

        assert a.cash_flows is None
        assert a.current_yield is None
        assert "coupon rate" in a.unavailable_metrics["current_yield"].lower()

    def test_missing_price_blocks_all_price_metrics(self):
        bond = _satin_bond(price=None)
        a = compute_analytics(bond, settlement_date=SETTLEMENT)

        assert a.current_yield is None
        assert a.calculated_ytm is None
        for metric in ("current_yield", "calculated_ytm", "macaulay_duration"):
            assert "price" in a.unavailable_metrics[metric].lower()

    def test_missing_anchor_blocks_corporate_schedule(self):
        bond = _satin_bond(interest_start_date=None)
        a = compute_analytics(bond, settlement_date=SETTLEMENT)

        assert a.cash_flows is None
        assert "anchor" in a.unavailable_metrics["cash_flows"].lower()

    def test_market_ytm_still_passed_through_when_calculation_gated(self):
        a = compute_analytics(
            _satin_bond(coupon_frequency=None), settlement_date=SETTLEMENT
        )
        assert a.market_ytm == 9.0


class TestInvalidInputs:
    def test_negative_price_gated(self):
        a = compute_analytics(_satin_bond(price=-5.0), settlement_date=SETTLEMENT)
        assert a.calculated_ytm is None
        assert "price" in a.unavailable_metrics["calculated_ytm"].lower()

    def test_unsupported_frequency_refused_not_defaulted(self):
        flows, source, reason = build_cash_flow_schedule(
            coupon_rate=10.95,
            coupon_frequency=7,
            anchor_date=date(2025, 10, 10),
            final_date=date(2027, 3, 10),
        )
        assert flows is None
        assert source is None
        assert "supported" in reason.lower()

    def test_matured_bond_has_no_future_ytm(self):
        a = compute_analytics(
            _satin_bond(), settlement_date=date(2027, 6, 1)
        )
        assert a.calculated_ytm is None
        assert a.unavailable_metrics["calculated_ytm"]


class TestZeroCoupon:
    def test_tbill_path_preserved(self):
        bond = Bond(
            isin="IN1234567890",
            security_name="91 Day T-Bill",
            instrument_type=InstrumentType.T_BILL,
            maturity_date=date(2026, 12, 15),
            coupon_rate=0.0,
            dirty_price=97.5,
            ytm=6.5,
            source="CCIL",
            data_type=DataType.TRADED,
            face_value=100.0,
        )
        a = compute_analytics(bond, settlement_date=date(2026, 9, 18))

        assert len(a.cash_flows) == 1
        assert a.cash_flows[0]["coupon"] == 0.0
        assert a.cash_flow_source == "calculated"
        assert a.current_yield is None
        assert "zero-coupon" in a.unavailable_metrics["current_yield"].lower()
        assert "zero-coupon" in a.unavailable_metrics["accrued_interest"].lower()
        assert a.macaulay_duration is not None
        assert a.macaulay_duration == pytest.approx(
            (date(2026, 12, 15) - date(2026, 9, 18)).days / 365.0, abs=0.01
        )


class TestGovernmentConventions:
    def test_gsec_semi_annual_convention_disclosed(self):
        bond = Bond(
            isin="IN0020260015",
            security_name="7.15% GS 2026",
            instrument_type=InstrumentType.G_SEC,
            maturity_date=date(2027, 12, 9),
            coupon_rate=7.15,
            dirty_price=100.0,
            ytm=7.15,
            source="CCIL",
            data_type=DataType.TRADED,
            face_value=100.0,
        )
        a = compute_analytics(bond, settlement_date=date(2025, 8, 1))

        assert a.cash_flows is not None
        assert len(a.cash_flows) > 1
        assert a.cash_flow_source == "calculated"
        assert a.calculated_ytm is not None
        assert a.macaulay_duration is not None
        assert a.dv01 is not None
        assert any("semi-annual" in n for n in a.notes)
        assert any("maturity date" in n for n in a.notes)
        assert not a.unavailable_metrics

    def test_gsec_published_frequency_respected(self):
        bond = Bond(
            isin="IN0020260015",
            security_name="7.15% GS 2026",
            instrument_type=InstrumentType.G_SEC,
            maturity_date=date(2027, 12, 9),
            coupon_rate=7.15,
            coupon_frequency=2,
            dirty_price=100.0,
            ytm=7.15,
            source="CCIL",
            data_type=DataType.TRADED,
        )
        a = compute_analytics(bond, settlement_date=date(2025, 8, 1))
        assert not any("semi-annual applied" in n for n in a.notes)


class TestSourceProvidedSchedule:
    def test_cdsl_schedule_preferred_and_labelled(self):
        bond = _satin_bond(
            cash_flow_schedule=[
                CdslCashFlowEvent(
                    event_type="Interest Payment",
                    due_date="10-Oct-2026",
                    amount_payable="912.50",
                ),
                CdslCashFlowEvent(
                    event_type="Principal Redemption",
                    due_date="10-Mar-2027",
                    amount_payable="100000",
                ),
            ]
        )
        a = compute_analytics(bond, settlement_date=SETTLEMENT)

        assert a.cash_flow_source == "source"
        assert all(row["source"] == "cdsl" for row in a.cash_flows)
        # Amounts normalized to per-100 par (face value 100000 -> scale 1000).
        assert a.cash_flows[0]["coupon"] == pytest.approx(0.9125, abs=1e-9)
        assert a.cash_flows[1]["principal"] == pytest.approx(100.0, abs=1e-9)
        assert any("source-published" in n.lower() for n in a.notes)
        assert a.calculated_ytm is not None


class TestFrequencyParser:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("twelve times a year", 12),
            ("Once a Year", 1),
            ("Half-Yearly", 2),
            ("Quarterly", 4),
            ("Monthly", 12),
            ("2", 2),
            (None, None),
            ("unknown label", None),
        ],
    )
    def test_parse(self, raw, expected):
        assert _parse_coupon_frequency(raw) == expected


class TestRichDetailMerge:
    def _rich(self, **overrides):
        fields = dict(
            issuer_name="SATIN FINSERV LIMITED",
            security_description=None,
            issuer_address=None,
            cin=None,
            lei=None,
            type_of_issuer=None,
            nature_of_issuer=None,
            business_sector=None,
            instrument_type=None,
            face_value="100000",
            frequency_of_interest_payment="twelve times a year",
            day_count_convention="Actual/360",
            interest_payment_start_date="10-Oct-2025",
            interest_payment_end_date=None,
            redemption_date="10-Mar-2027",
            redemption_type="Bullet",
            coupon_basis="Fixed",
            coupon_type="Simple",
            security_type="Secured",
            coupon_rate_label="10.95%",
            cash_flow_schedule=[],
        )
        fields.update(overrides)
        return SimpleNamespace(**fields)

    def test_terms_mapped(self):
        bond = _satin_bond(
            coupon_frequency=None,
            face_value=None,
            day_count_convention=DayCountConvention.UNKNOWN,
            interest_start_date=None,
            redemption_date=None,
            coupon_rate=None,
        )
        merged = _merge_rich_detail_into_bond(bond, self._rich())

        assert merged.face_value == 100000.0
        assert merged.coupon_frequency == 12
        assert merged.day_count_convention == DayCountConvention.ACT_360
        assert merged.interest_start_date == date(2025, 10, 10)
        assert merged.redemption_date == date(2027, 3, 10)
        assert merged.coupon_rate == 10.95  # from the published label
        assert merged.redemption_type == "Bullet"
        assert merged.coupon_basis == "Fixed"

    def test_existing_values_not_overwritten(self):
        bond = _satin_bond()  # coupon 10.95 already present from trade row
        merged = _merge_rich_detail_into_bond(bond, self._rich())
        assert merged.coupon_rate == 10.95

    def test_merged_bond_computes_full_analytics(self):
        bond = _satin_bond(
            coupon_frequency=None,
            face_value=None,
            day_count_convention=DayCountConvention.UNKNOWN,
            interest_start_date=None,
            redemption_date=None,
        )
        merged = _merge_rich_detail_into_bond(bond, self._rich())
        a = compute_analytics(merged, settlement_date=SETTLEMENT)

        assert a.calculated_ytm is not None
        assert len(a.cash_flows) == 18
        assert not a.unavailable_metrics


class TestCorporateAnalyticsService:
    def test_service_path_and_cache(self, monkeypatch):
        import asyncio

        from backend.config.settings import Settings
        from backend.services.bonds.bond_service import BondService

        service = BondService()
        service._cache.invalidate()
        calls = {"n": 0}

        async def fake_get_bond(isin, trade_date=None):
            calls["n"] += 1
            return _satin_bond()

        monkeypatch.setattr(
            service, "get_corporate_bond_by_isin", fake_get_bond
        )

        first = asyncio.run(service.get_corporate_analytics("INE03K307066"))
        assert first.calculated_ytm is not None
        assert first.market_ytm == 9.0

        second = asyncio.run(service.get_corporate_analytics("INE03K307066"))
        assert second is first  # served from the analytics cache
        assert calls["n"] == 1  # bond fetched once

    def test_service_unknown_isin_returns_none(self, monkeypatch):
        import asyncio

        from backend.config.settings import Settings
        from backend.services.bonds.bond_service import BondService

        service = BondService()
        service._cache.invalidate()

        async def fake_get_bond(isin, trade_date=None):
            return None

        monkeypatch.setattr(
            service, "get_corporate_bond_by_isin", fake_get_bond
        )
        result = asyncio.run(service.get_corporate_analytics("UNKNOWN000000"))
        assert result is None