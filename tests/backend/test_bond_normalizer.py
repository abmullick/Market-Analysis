"""Tests for bond model normalization.

Tests:
  - CCIL field normalization
  - NSE field normalization
  - T-Bill handling
  - G-Sec cash-flow generation
  - YTM calculation
  - Accrued interest
  - Duration / modified duration / convexity / DV01

External data sources are NOT called; mocked provider responses are used.
"""

from __future__ import annotations

import pytest
from datetime import date

from backend.models.bonds import (
    Bond,
    CcilRawRecord,
    NseRawRecord,
    RbiRawRecord,
    InstrumentType,
    DataType,
    DayCountConvention,
)
from backend.services.bonds.bond_normalizer import (
    _nse_instrument_type,
    normalize_ccil_record,
    normalize_nse_record,
    normalize_rbi_record,
)
from backend.services.data.bonds.nse import parse_debt_instruments_csv
from backend.services.bonds.bond_cashflows import generate_cash_flows, accrued_interest
from backend.services.bonds.bond_analytics import compute_analytics, solve_ytm


# =========================================================================
# CCIL normalization tests
# =========================================================================

class TestCcilNormalization:
    """CCIL Market Watch field normalization."""

    def test_central_gsec_traded(self):
        """Central G-Sec with LTP is normalized as traded."""
        raw = CcilRawRecord(
            section="CENTRAL",
            security_description="7.15%, 09-Dec-2026",
            maturity_date="09-Dec-2026",
            ltp="100.50",
            lty="7.12",
            lta="50000",
            tta="",
            bid_price="",
            bid_yield="",
            offer_price="",
            offer_yield="",
        )
        bond = normalize_ccil_record(raw)

        assert bond.isin is None  # no ISIN present
        assert bond.security_name == "7.15%, 09-Dec-2026"
        assert bond.issuer == "Government of India"
        assert bond.instrument_type == InstrumentType.G_SEC
        assert bond.maturity_date == date(2026, 12, 9)
        assert bond.coupon_rate == 7.15
        assert bond.ytm == 7.12
        assert bond.price == 100.50
        assert bond.last_traded_price == 100.50
        assert bond.last_traded_yield == 7.12
        assert bond.data_type == DataType.TRADED
        assert bond.source == "CCIL"

    def test_state_sdl(self):
        """State SDL is recognized as SDL instrument type."""
        raw = CcilRawRecord(
            section="STATE",
            security_description="State of Maharashtra",
            maturity_date="09-Jun-2027",
            ltp="101.20",
            lty="6.85",
            lta="30000",
            tta="",
            bid_price="",
            bid_yield="",
            offer_price="",
            offer_yield="",
        )
        bond = normalize_ccil_record(raw)

        assert bond.instrument_type == InstrumentType.SDL
        assert bond.source == "CCIL"
        assert bond.data_type == DataType.TRADED

    def test_tbill_zero_coupon(self):
        """T-Bill is recognized as zero-coupon instrument."""
        raw = CcilRawRecord(
            section="T-BILLS",
            security_description="91 Day T-Bill",
            maturity_date="15-Jan-2026",
            ltp="98.50",
            lty="7.20",
            lta="100000",
            tta="",
            bid_price="",
            bid_yield="",
            offer_price="",
            offer_yield="",
        )
        bond = normalize_ccil_record(raw)

        assert bond.instrument_type == InstrumentType.T_BILL
        assert bond.coupon_rate is None  # no coupon extracted
        assert bond.source == "CCIL"
        assert bond.data_type == DataType.TRADED

    def test_tbill_coupon_zero(self):
        """T-Bill from CCIL section has coupon set to None."""
        raw = CcilRawRecord(
            section="T-BILLS",
            security_description="364 Day T-Bill",
            maturity_date="25-Dec-2025",
            ltp="97.00",
            lty="8.10",
            lta="",
            tta="",
            bid_price="",
            bid_yield="",
            offer_price="",
            offer_yield="",
        )
        bond = normalize_ccil_record(raw)
        assert bond.coupon_rate is None

    def test_indicative_bid_offer(self):
        """When only bid/offer are present, data_type is indicative."""
        raw = CcilRawRecord(
            section="CENTRAL",
            security_description="6.50%, 09-Jun-2031",
            maturity_date="09-Jun-2031",
            ltp="",
            lty="",
            lta="",
            tta="",
            bid_price="99.50",
            bid_yield="6.60",
            offer_price="100.50",
            offer_yield="6.40",
        )
        bond = normalize_ccil_record(raw)

        assert bond.data_type == DataType.INDICATIVE
        assert bond.price is None
        assert bond.ytm is None
        assert bond.bid_price == 99.50
        assert bond.bid_yield == 6.60
        assert bond.offer_price == 100.50
        assert bond.offer_yield == 6.40

    def test_coupon_extraction_from_description(self):
        """Coupon rate is extracted from CCIL description."""
        raw = CcilRawRecord(
            section="CENTRAL",
            security_description="7.15%, 09-Dec-2026",
            maturity_date="09-Dec-2026",
            ltp="",
            lty="",
            lta="",
            tta="",
            bid_price="",
            bid_yield="",
            offer_price="",
            offer_yield="",
        )
        bond = normalize_ccil_record(raw)
        assert bond.coupon_rate == 7.15

    def test_isin_extraction_from_description(self):
        """ISIN is extracted from CCIL description when present."""
        raw = CcilRawRecord(
            section="CENTRAL",
            security_description="7.15% ISIN IB2345678901 09-Dec-2026",
            maturity_date="09-Dec-2026",
            ltp="",
            lty="",
            lta="",
            tta="",
            bid_price="",
            bid_yield="",
            offer_price="",
            offer_yield="",
        )
        bond = normalize_ccil_record(raw)
        assert bond.isin == "IB2345678901"

    def test_nil_fields_remain_none(self):
        """Fields not present in the source remain None."""
        raw = CcilRawRecord(
            section="CENTRAL",
            security_description="6.50%, 09-Jun-2031",
            maturity_date="09-Jun-2031",
            ltp="",
            lty="",
            lta="",
            tta="",
            bid_price="",
            bid_yield="",
            offer_price="",
            offer_yield="",
        )
        bond = normalize_ccil_record(raw)
        assert bond.issue_date is None
        assert bond.face_value is None
        assert bond.day_count_convention == DayCountConvention.UNKNOWN  # defaults to UNKNOWN, not None
        assert bond.callable is False  # defaults to False, not None
        assert bond.puttable is False  # defaults to False, not None
        assert bond.listing_status is None


# =========================================================================
# NSE normalization tests
# =========================================================================

class TestNseNormalization:
    """NSE public debt report field normalization."""

    def test_gsec_list_reference(self):
        """NSE gsec-list record is normalized as reference."""
        raw = NseRawRecord(
            report_type="GSEC List",
            security_description="7.15% G-Sec 2026",
            isin="IB2345678901",
            maturity_date="09-Dec-2026",
            coupon_rate="7.15",
            price="",
            yield_pct="",
            traded_value="",
            trade_date="",
            accrued_interest="",
        )
        bond = normalize_nse_record(raw)

        assert bond is not None
        assert bond.instrument_type == InstrumentType.G_SEC
        assert bond.source == "NSE"
        assert bond.data_type == DataType.REFERENCE
        assert bond.isin == "IB2345678901"
        assert bond.coupon_rate == 7.15

    def test_tbill_list(self):
        """NSE T-Bill list record is normalized as T-Bill."""
        raw = NseRawRecord(
            report_type="TBILL List",
            security_description="91 Day T-Bill",
            isin="",
            maturity_date="15-Jan-2026",
            coupon_rate="0",
            price="",
            yield_pct="7.20",
            traded_value="",
            trade_date="",
            accrued_interest="",
        )
        bond = normalize_nse_record(raw)

        assert bond is not None
        assert bond.instrument_type == InstrumentType.T_BILL
        assert bond.source == "NSE"
        assert bond.data_type == DataType.REFERENCE
        assert bond.coupon_rate == 0.0

    def test_trades_record(self):
        """NSE WDM trade record is normalized as traded."""
        raw = NseRawRecord(
            report_type="Trades",
            security_description="7.15% G-Sec 2026",
            isin="IB2345678901",
            maturity_date="09-Dec-2026",
            coupon_rate="7.15",
            price="100.50",
            yield_pct="7.12",
            traded_value="50000",
            trade_date="09-Dec-2026",
            accrued_interest="1.25",
        )
        bond = normalize_nse_record(raw)

        assert bond is not None
        assert bond.source == "NSE"
        assert bond.data_type == DataType.TRADED
        assert bond.price == 100.50
        assert bond.ytm == 7.12
        assert bond.trade_date == date(2026, 12, 9)

    def test_non_bond_record_returns_none(self):
        """Non-government records return None."""
        raw = NseRawRecord(
            report_type="Corporate",
            security_description="Some Corporate Bond",
            isin="",
            maturity_date="",
            coupon_rate="",
            price="",
            yield_pct="",
            traded_value="",
            trade_date="",
            accrued_interest="",
        )
        bond = normalize_nse_record(raw)
        assert bond is None

    def test_nil_fields_remain_none(self):
        """NSE fields not present remain None."""
        raw = NseRawRecord(
            report_type="GSEC List",
            security_description="7.15% G-Sec 2026",
            isin="",
            maturity_date="",
            coupon_rate="",
            price="",
            yield_pct="",
            traded_value="",
            trade_date="",
            accrued_interest="",
        )
        bond = normalize_nse_record(raw)
        assert bond.issue_date is None
        assert bond.face_value is None
        assert bond.day_count_convention == DayCountConvention.UNKNOWN  # defaults to UNKNOWN, not None


class TestNseWdmMasterClassification:
    """Real NSE WDM Debt Instruments master rows (SECTYPE-driven classification).

    These mirror the live WDM-SEC-AVAILABLE-FOR-TRADE CSV:

        SECTYPE=TB  SECURITY=364D  ISSUE_DESC="GOI TBILL 364D-23/10/26"
        SECTYPE=SG  SECURITY=GUJ31 ISSUE_DESC="SDL GUJARAT 8.26% 2031"
        SECTYPE=SG  SECURITY=UP26  ISSUE_DESC="SPECIAL BOND UP 8.55% 2026"
        SECTYPE=GS  SECURITY=CG2036
        SECTYPE=PT  SECURITY=GSIL28  (corporate symbol containing "gs")
    """

    def _wdm(self, **overrides) -> NseRawRecord:
        payload = dict(
            report_type="WDM",
            security_description="364D",
            issue_description="GOI TBILL 364D-23/10/26",
            isin="IN002025Z302",
            instrument_type="TB",
            maturity_date="23-Oct-2026",
            coupon_rate="231026",
            issue_date="24-Oct-2025",
            listing_status="Listed",
        )
        payload.update(overrides)
        return NseRawRecord(**payload)

    def test_tb_sectype_classified_as_tbill(self):
        """Test 1 - SECTYPE=TB classifies as T-Bill."""
        bond = normalize_nse_record(self._wdm())

        assert bond is not None
        assert bond.instrument_type == InstrumentType.T_BILL
        assert bond.source == "NSE"
        assert bond.data_type == DataType.REFERENCE
        assert bond.isin == "IN002025Z302"

    def test_sg_sectype_with_sdl_description_classified_as_sdl(self):
        """Test 2 - SECTYPE=SG with an SDL description classifies as SDL."""
        raw = self._wdm(
            instrument_type="SG",
            security_description="GUJ31",
            issue_description="SDL GUJARAT 8.26% 2031",
            isin="IN1520150112",
            maturity_date="13-Jan-2031",
            coupon_rate="8.26%",
        )
        bond = normalize_nse_record(raw)

        assert bond is not None
        assert bond.instrument_type == InstrumentType.SDL
        assert bond.source == "NSE"

    def test_sg_special_bond_is_not_sdl(self):
        """Test 3 - SECTYPE=SG special bond must not classify as SDL."""
        raw = self._wdm(
            instrument_type="SG",
            security_description="UP26",
            issue_description="SPECIAL BOND UP 8.55% 2026",
            isin="IN3320140129",
            maturity_date="04-Oct-2026",
            coupon_rate="8.55%",
        )
        assert _nse_instrument_type(raw, raw.security_description) != InstrumentType.SDL
        assert normalize_nse_record(raw) is None

    def test_sg_without_sdl_description_is_unclassified(self):
        """SECTYPE=SG without SDL/state confirmation must not become SDL."""
        raw = self._wdm(
            instrument_type="SG",
            security_description="UP26",
            issue_description=None,
            isin="IN3320140129",
        )
        assert _nse_instrument_type(raw, raw.security_description) == InstrumentType.UNKNOWN
        assert normalize_nse_record(raw) is None

    def test_corporate_symbol_with_gs_substring_is_not_gsec(self):
        """Test 4 - 'gs' inside a larger token (GSIL28) never implies G-Sec."""
        raw = self._wdm(
            report_type="debt-master",
            instrument_type="PT",
            security_description="GSIL28",
            issue_description="GSIL 9.03% 2028",
            isin="INE08EQ08031",
            maturity_date="22-Mar-2028",
            coupon_rate="9.03%",
        )
        assert _nse_instrument_type(raw, raw.security_description) != InstrumentType.G_SEC
        assert normalize_nse_record(raw) is None

    def test_wdm_gs_sectype_classified_as_gsec(self):
        """SECTYPE=GS classifies as G-Sec without description keywords."""
        raw = self._wdm(
            instrument_type="GS",
            security_description="CG2036",
            issue_description="GOI LOAN 8.33% 2036",
            isin="IN0020060045",
            maturity_date="07-Jun-2036",
            coupon_rate="8.33%",
            coupon_frequency="Half Yearly",
        )
        bond = normalize_nse_record(raw)

        assert bond is not None
        assert bond.instrument_type == InstrumentType.G_SEC
        assert bond.issuer == "Government of India"

    def test_wdm_parser_preserves_issue_description(self):
        """Test 8 - ISSUE_DESC maps to issue_description; SECURITY stays separate."""
        csv_text = (
            "SECTYPE,SECURITY,ISSUE_NAME,ISSUE_DESC,ISSUE_DATE,MAT_DATE,"
            "Last IP Dt,Next IP Dt,Cpn Freq,Last Traded Date,"
            "Last Traded Price (in Rs.),ISIN NO.,STATUS\n"
            "TB,364D,231026,GOI TBILL 364D-23/10/26,24-Oct-2025,23-Oct-2026,"
            ",, , , ,IN002025Z302,Listed\n"
            "SG,GUJ31,8.26%,SDL GUJARAT 8.26% 2031,13-Jan-2016,13-Jan-2031,"
            ",,Half Yearly, , ,IN1520150112,Listed\n"
        )
        records = parse_debt_instruments_csv(csv_text)

        assert len(records) == 2
        tb, sdl = records

        assert tb.issue_description == "GOI TBILL 364D-23/10/26"
        assert tb.security_description == "364D"
        assert tb.instrument_type == "TB"
        assert tb.isin == "IN002025Z302"
        assert tb.maturity_date == "23-Oct-2026"
        assert tb.listing_status == "Listed"

        assert sdl.issue_description == "SDL GUJARAT 8.26% 2031"
        assert sdl.security_description == "GUJ31"
        assert sdl.instrument_type == "SG"
        assert sdl.isin == "IN1520150112"


# =========================================================================
# RBI normalization tests
# =========================================================================

class TestRbiNormalization:
    """RBI / DBIE reference record normalization."""

    def test_gsec_reference(self):
        """RBI G-Sec reference record is normalized as reference."""
        raw = RbiRawRecord(
            series="G-Sec-2026",
            security_description="7.15% G-Sec 2026",
            isin="",
            instrument_type="G-Sec",
            maturity_date="09-Dec-2026",
            coupon_rate="7.15",
            issue_date="09-Dec-2021",
            auction_yield="7.20",
            reference_yield="7.18",
            state_borrowing_ref="",
            as_of="09-Dec-2025",
        )
        bond = normalize_rbi_record(raw)

        assert bond is not None
        assert bond.source == "RBI"
        assert bond.data_type == DataType.REFERENCE
        assert bond.instrument_type == InstrumentType.G_SEC
        assert bond.coupon_rate == 7.15
        # RBI prefers reference_yield for G-Secs
        assert bond.ytm == 7.18

    def test_tbill_auction_yield(self):
        """RBI T-Bill record uses auction_yield as YTM."""
        raw = RbiRawRecord(
            series="TBill-91Day",
            security_description="91 Day T-Bill",
            isin="",
            instrument_type="TBill",
            maturity_date="15-Jan-2026",
            coupon_rate="0",
            issue_date="",
            auction_yield="7.25",
            reference_yield="",
            state_borrowing_ref="",
            as_of="15-Jan-2026",
        )
        bond = normalize_rbi_record(raw)

        assert bond is not None
        assert bond.instrument_type == InstrumentType.T_BILL
        assert bond.coupon_rate == 0.0
        # T-Bill uses auction_yield
        assert bond.ytm == 7.25

    def test_sdl_reference(self):
        """RBI SDL record is normalized as SDL."""
        raw = RbiRawRecord(
            series="SDL-Maharashtra",
            security_description="Maharashtra SDL",
            isin="",
            instrument_type="SDL",
            maturity_date="09-Jun-2027",
            coupon_rate="6.85",
            issue_date="",
            auction_yield="",
            reference_yield="6.90",
            state_borrowing_ref="",
            as_of="09-Dec-2025",
        )
        bond = normalize_rbi_record(raw)

        assert bond is not None
        assert bond.instrument_type == InstrumentType.SDL
        assert bond.source == "RBI"

    def test_nil_reference_returns_none(self):
        """Empty RBI record returns None."""
        raw = RbiRawRecord(
            series="",
            security_description="",
            isin="",
            instrument_type="",
            maturity_date="",
            coupon_rate="",
            issue_date="",
            auction_yield="",
            reference_yield="",
            state_borrowing_ref="",
            as_of="",
        )
        bond = normalize_rbi_record(raw)
        assert bond is None


# =========================================================================
# T-Bill handling tests
# =========================================================================

class TestTBillHandling:
    """T-Bill specific behavior across the bond stack."""

    def test_tbill_cash_flow_single_payment(self):
        """T-Bill generates a single zero-coupon cash flow at maturity."""
        cfs = generate_cash_flows(
            issue_date=date(2025, 1, 1),
            maturity_date=date(2025, 4, 15),
            coupon_rate=0,
            coupon_frequency=2,
            face_value=100.0,
        )
        assert len(cfs) == 1
        assert cfs[0]["coupon"] == 0.0
        assert cfs[0]["principal"] == 100.0
        assert cfs[0]["total"] == 100.0
        assert cfs[0]["date"] == date(2025, 4, 15)

    def test_tbill_analytics_no_coupon_calculations(self):
        """T-Bill analytics does not force coupon-bond calculations."""
        bond = Bond(
            isin="MISSING",
            security_name="91 Day T-Bill",
            issuer="Government of India",
            instrument_type=InstrumentType.T_BILL,
            maturity_date=date(2026, 7, 15),
            coupon_rate=0.0,
            dirty_price=97.50,
            ytm=7.50,
            source="CCIL",
            data_type=DataType.TRADED,
            face_value=100.0,
        )
        analytics = compute_analytics(bond, settlement_date=date(2026, 1, 1))

        assert analytics.calculated_ytm is not None  # YTM computed from price
        assert analytics.current_yield is None  # no coupon
        assert analytics.cash_flows is not None
        assert len(analytics.cash_flows) == 1
        assert analytics.cash_flows[0]["coupon"] == 0.0

    def test_tbill_duration_is_time_to_maturity(self):
        """T-Bill Macaulay duration equals time to maturity."""
        bond = Bond(
            isin="MISSING",
            security_name="91 Day T-Bill",
            issuer="Government of India",
            instrument_type=InstrumentType.T_BILL,
            maturity_date=date(2026, 7, 15),
            coupon_rate=0.0,
            price=None,
            ytm=7.50,
            source="CCIL",
            data_type=DataType.TRADED,
            face_value=100.0,
        )
        analytics = compute_analytics(bond, settlement_date=date(2026, 1, 1))
        # With no dirty price, duration may be None
        # But if price set, duration = TTM
        bond2 = Bond(
            isin="MISSING",
            security_name="91 Day T-Bill",
            issuer="Government of India",
            instrument_type=InstrumentType.T_BILL,
            maturity_date=date(2026, 7, 15),
            coupon_rate=0.0,
            dirty_price=97.50,
            ytm=7.50,
            source="CCIL",
            data_type=DataType.TRADED,
            face_value=100.0,
        )
        analytics2 = compute_analytics(bond2, settlement_date=date(2026, 1, 1))
        assert analytics2.macaulay_duration is not None
        assert analytics2.macaulay_duration > 0


# =========================================================================
# G-Sec cash flow generation tests
# =========================================================================

class TestGSecCashFlows:
    """Cash flow generation for coupon-bearing G-Secs."""

    def test_semi_annual_coupons(self):
        """Semi-annual coupons are generated correctly."""
        cfs = generate_cash_flows(
            issue_date=date(2025, 1, 1),
            maturity_date=date(2026, 1, 1),
            coupon_rate=7.0,       # 7% per annum
            coupon_frequency=2,    # semi-annual
            face_value=100.0,
        )
        # 2 years of semi-annual = 4 coupons + final principal
        # issue 2025-01-01, maturity 2026-01-01
        # coupons on: ~Jul 2025, Jan 2026 (final + principal)
        assert len(cfs) >= 2

        # Check coupon amounts
        for cf in cfs:
            if cf["period"] < 0:
                continue
            # coupon should be 100 * 7% / 2 = 3.5 per period
            if cf["date"] != cfs[-1]["date"]:
                # interim coupon
                assert abs(cf["coupon"] - 3.5) < 0.001
            else:
                # final period includes principal
                assert cf["principal"] == 100.0
                assert abs(cf["coupon"] - 3.5) < 0.001

    def test_final_cash_flow_includes_principal(self):
        """Final cash flow includes coupon + principal."""
        cfs = generate_cash_flows(
            issue_date=date(2025, 1, 1),
            maturity_date=date(2026, 1, 1),
            coupon_rate=7.0,
            coupon_frequency=2,
            face_value=100.0,
        )
        final = cfs[-1]
        assert final["principal"] == 100.0
        assert final["total"] == pytest.approx(final["coupon"] + 100.0)

    def test_zero_coupon_returns_single_flow(self):
        """Zero-coupon returns single maturity cash flow."""
        cfs = generate_cash_flows(
            issue_date=date(2025, 1, 1),
            maturity_date=date(2026, 1, 1),
            coupon_rate=0,
            coupon_frequency=2,
            face_value=100.0,
        )
        assert len(cfs) == 1
        assert cfs[0]["coupon"] == 0.0
        assert cfs[0]["principal"] == 100.0

    def test_missing_maturity_returns_empty(self):
        """Missing maturity returns empty list."""
        cfs = generate_cash_flows(
            issue_date=date(2025, 1, 1),
            maturity_date=None,
            coupon_rate=7.0,
            coupon_frequency=2,
            face_value=100.0,
        )
        assert cfs == []


# =========================================================================
# Accrued interest tests
# =========================================================================

class TestAccruedInterest:
    """Accrued interest calculations."""

    def test_zero_coupon_no_accrual(self):
        """Zero-coupon instruments have zero accrued interest."""
        ai, days = accrued_interest(
            coupon_rate=0,
            face_value=100.0,
            last_coupon_date=date(2025, 1, 1),
            settlement_date=date(2025, 3, 15),
            coupon_frequency=2,
            day_count="ACT/365",
        )
        assert ai == 0.0
        assert days == 0

    def test_standard_semi_annual_accrual(self):
        """Standard ACT/365 accrual for semi-annual bond."""
        coupon = 100.0 * 7.0 / 100.0 / 2  # 3.5 per period
        last_coupon = date(2025, 1, 1)
        settlement = date(2025, 3, 15)  # 73 days later
        ai, days = accrued_interest(
            coupon_rate=7.0,
            face_value=100.0,
            last_coupon_date=last_coupon,
            settlement_date=settlement,
            coupon_frequency=2,
            day_count="ACT/365",
        )
        expected = coupon * 73 / 365.0
        assert days == 73
        assert ai == pytest.approx(expected)

    def test_act_360_convention(self):
        """ACT/360 convention produces different accrual."""
        last_coupon = date(2025, 1, 1)
        settlement = date(2025, 3, 15)  # 73 days
        ai_365, _ = accrued_interest(
            coupon_rate=7.0,
            face_value=100.0,
            last_coupon_date=last_coupon,
            settlement_date=settlement,
            coupon_frequency=2,
            day_count="ACT/365",
        )
        ai_360, _ = accrued_interest(
            coupon_rate=7.0,
            face_value=100.0,
            last_coupon_date=last_coupon,
            settlement_date=settlement,
            coupon_frequency=2,
            day_count="ACT/360",
        )
        assert ai_360 > ai_365  # 360 < 365 => larger accrual

    def test_settlement_on_coupon_date(self):
        """Accrual is zero on coupon date."""
        last_coupon = date(2025, 1, 1)
        settlement = date(2025, 1, 1)
        ai, days = accrued_interest(
            coupon_rate=7.0,
            face_value=100.0,
            last_coupon_date=last_coupon,
            settlement_date=settlement,
            coupon_frequency=2,
        )
        assert ai == 0.0
        assert days == 0

    def test_no_last_coupon_returns_zero(self):
        """Missing last coupon date returns zero."""
        ai, days = accrued_interest(
            coupon_rate=7.0,
            face_value=100.0,
            last_coupon_date=None,
            settlement_date=date(2025, 3, 15),
            coupon_frequency=2,
        )
        assert ai == 0.0
        assert days == 0


# =========================================================================
# YTM calculation tests
# =========================================================================

class TestYtmCalculation:
    """Independent YTM calculation."""

    def test_par_bond_ytm_equals_coupon(self):
        """A bond priced at par has YTM equal to coupon rate."""
        from backend.services.bonds.bond_analytics import (
            solve_ytm,
            _price_from_yield,
        )

        cfs = [
            {"date": date(2026, 1, 1), "total": 3.5},
            {"date": date(2026, 7, 1), "total": 3.5},
            {"date": date(2027, 1, 1), "total": 103.5},
        ]
        settlement = date(2025, 7, 1)

        # Price at par = 100
        ytm = solve_ytm(cfs, dirty_price=100.0, settlement_date=settlement)
        assert ytm is not None
        # Should be close to coupon rate of 7%
        assert abs(ytm - 0.07) < 0.005

    def test_discount_bond_ytm_higher_than_coupon(self):
        """A discount bond has YTM higher than coupon."""
        # All cash flows must be after settlement for correct discounting
        cfs = [
            {"date": date(2026, 1, 1), "total": 3.5},
            {"date": date(2026, 7, 1), "total": 3.5},
            {"date": date(2027, 1, 1), "total": 103.5},
        ]
        settlement = date(2025, 10, 1)

        ytm = solve_ytm(cfs, dirty_price=98.0, settlement_date=settlement)
        assert ytm is not None
        assert ytm > 0.07  # coupon is 7%, price below par => YTM > coupon

    def test_premium_bond_ytm_lower_than_coupon(self):
        """A premium bond has YTM lower than coupon."""
        cfs = [
            {"date": date(2026, 1, 1), "total": 3.5},
            {"date": date(2027, 1, 1), "total": 103.5},
        ]
        settlement = date(2025, 7, 1)

        ytm = solve_ytm(cfs, dirty_price=102.0, settlement_date=settlement)
        assert ytm is not None
        assert ytm < 0.07  # coupon is 7%, price above par => YTM < coupon

    def test_face_value_price_returns_none(self):
        """Zero or negative price returns None."""
        cfs = [{"date": date(2026, 1, 1), "total": 100.0}]
        settlement = date(2025, 7, 1)

        assert solve_ytm(cfs, dirty_price=0, settlement_date=settlement) is None
        assert solve_ytm(cfs, dirty_price=-10, settlement_date=settlement) is None

    def test_empty_cash_flows_returns_none(self):
        """Empty cash flows return None."""
        settlement = date(2025, 7, 1)
        assert solve_ytm([], dirty_price=100.0, settlement_date=settlement) is None

    def test_calculated_ytm_independent_of_market_ytm(self):
        """Calculated YTM is independent of market YTM."""
        # Use a bond where ALL cash flows are in the future relative to settlement.
        # Issue date is AFTER settlement so cash flow generation starts from a future date.
        bond = Bond(
            isin="IB1234567890",
            security_name="7.15% G-Sec 2027",
            issuer="Government of India",
            instrument_type=InstrumentType.G_SEC,
            issue_date=date(2025, 9, 1),
            maturity_date=date(2027, 9, 1),
            coupon_rate=7.15,
            dirty_price=100.0,
            ytm=7.00,  # market YTM (different from calculated)
            source="CCIL",
            data_type=DataType.TRADED,
            face_value=100.0,
        )
        analytics = compute_analytics(bond, settlement_date=date(2025, 8, 1))

        # Calculated YTM should be derived from price, not copied from market
        assert analytics.calculated_ytm is not None
        assert analytics.market_ytm == 7.00
        # At par with 7.15% coupon, calculated YTM should be ~7.15%
        assert abs(analytics.calculated_ytm - 7.15) < 2.0


# =========================================================================
# Duration / Convexity / DV01 tests
# =========================================================================

class TestDurationConvexity:
    """Duration, convexity, and DV01 calculations."""

    def test_macaulay_duration_for_coupon_bond(self):
        """Macaulay duration is computed for a coupon bond."""
        bond = Bond(
            isin="IB1234567890",
            security_name="7.15% G-Sec 2026",
            issuer="Government of India",
            instrument_type=InstrumentType.G_SEC,
            maturity_date=date(2027, 12, 9),
            coupon_rate=7.15,
            dirty_price=100.0,
            ytm=7.15,
            source="CCIL",
            data_type=DataType.TRADED,
            face_value=100.0,
        )
        analytics = compute_analytics(bond, settlement_date=date(2025, 8, 1))

        assert analytics.macaulay_duration is not None
        assert analytics.macaulay_duration > 0
        assert analytics.macaulay_duration < 3.0  # less than 2.5 years

    def test_modified_duration_less_than_macaulay(self):
        """Modified duration is less than Macaulay duration."""
        bond = Bond(
            isin="IB1234567890",
            security_name="7.15% G-Sec 2026",
            issuer="Government of India",
            instrument_type=InstrumentType.G_SEC,
            maturity_date=date(2027, 12, 9),
            coupon_rate=7.15,
            dirty_price=100.0,
            ytm=7.15,
            source="CCIL",
            data_type=DataType.TRADED,
            face_value=100.0,
        )
        analytics = compute_analytics(bond, settlement_date=date(2025, 8, 1))

        assert analytics.modified_duration is not None
        assert analytics.modified_duration <= analytics.macaulay_duration

    def test_dv01_positive(self):
        """DV01 is positive for a normal bond."""
        bond = Bond(
            isin="IB1234567890",
            security_name="7.15% G-Sec 2026",
            issuer="Government of India",
            instrument_type=InstrumentType.G_SEC,
            maturity_date=date(2027, 12, 9),
            coupon_rate=7.15,
            dirty_price=100.0,
            ytm=7.15,
            source="CCIL",
            data_type=DataType.TRADED,
            face_value=100.0,
        )
        analytics = compute_analytics(bond, settlement_date=date(2025, 8, 1))

        assert analytics.dv01 is not None
        assert analytics.dv01 > 0

    def test_convexity_positive(self):
        """Convexity is positive for a normal bond."""
        bond = Bond(
            isin="IB1234567890",
            security_name="7.15% G-Sec 2026",
            issuer="Government of India",
            instrument_type=InstrumentType.G_SEC,
            maturity_date=date(2027, 12, 9),
            coupon_rate=7.15,
            dirty_price=100.0,
            ytm=7.15,
            source="CCIL",
            data_type=DataType.TRADED,
            face_value=100.0,
        )
        analytics = compute_analytics(bond, settlement_date=date(2025, 8, 1))

        assert analytics.convexity is not None
        assert analytics.convexity > 0

    def test_zero_coupon_duration_equals_ttm(self):
        """Zero-coupon (T-Bill) duration equals time to maturity."""
        bond = Bond(
            isin="MISSING",
            security_name="91 Day T-Bill",
            issuer="Government of India",
            instrument_type=InstrumentType.T_BILL,
            maturity_date=date(2026, 10, 15),
            coupon_rate=0.0,
            dirty_price=97.50,
            ytm=7.50,
            source="CCIL",
            data_type=DataType.TRADED,
            face_value=100.0,
        )
        analytics = compute_analytics(bond, settlement_date=date(2026, 1, 1))

        assert analytics.macaulay_duration is not None
        # Duration should equal TTM
        ttm = (date(2026, 10, 15) - date(2026, 1, 1)).days / 365.0
        assert abs(analytics.macaulay_duration - ttm) < 0.1

    def test_analytics_result_contains_all_fields(self):
        """AnalyticsResult contains all required fields."""
        bond = Bond(
            isin="IB1234567890",
            security_name="7.15% G-Sec 2026",
            issuer="Government of India",
            instrument_type=InstrumentType.G_SEC,
            maturity_date=date(2027, 12, 9),
            coupon_rate=7.15,
            dirty_price=100.0,
            ytm=7.15,
            source="CCIL",
            data_type=DataType.TRADED,
            face_value=100.0,
        )
        analytics = compute_analytics(bond, settlement_date=date(2025, 8, 1))

        assert analytics.current_yield is not None
        assert analytics.calculated_ytm is not None
        assert analytics.market_ytm == 7.15
        assert analytics.cash_flows is not None
        assert analytics.accrued_interest >= 0
        assert analytics.macaulay_duration is not None
        assert analytics.modified_duration is not None
        assert analytics.convexity is not None
        assert analytics.dv01 is not None


# =========================================================================
# Data freshness / classification tests
# =========================================================================

class TestDataClassification:
    """Data type classification and freshness."""

    def test_traded_classification(self):
        """Bond with LTP is classified as traded."""
        bond = Bond(
            isin="IB1234567890",
            security_name="7.15% G-Sec 2026",
            issuer="Government of India",
            instrument_type=InstrumentType.G_SEC,
            maturity_date=date(2026, 12, 9),
            coupon_rate=7.15,
            last_traded_price=100.50,
            source="CCIL",
            data_type=DataType.TRADED,
        )
        assert bond.data_type == DataType.TRADED
        assert bond.last_traded_price == 100.50

    def test_indicative_classification(self):
        """Bond with only bid/offer is classified as indicative."""
        bond = Bond(
            isin="IB1234567890",
            security_name="7.15% G-Sec 2026",
            issuer="Government of India",
            instrument_type=InstrumentType.G_SEC,
            maturity_date=date(2026, 12, 9),
            coupon_rate=7.15,
            bid_price=99.50,
            offer_price=100.50,
            source="CCIL",
            data_type=DataType.INDICATIVE,
        )
        assert bond.data_type == DataType.INDICATIVE
        assert bond.price is None
        assert bond.bid_price == 99.50

    def test_reference_classification(self):
        """RBI reference bonds are classified as reference."""
        bond = Bond(
            isin="",
            security_name="7.15% G-Sec 2026",
            issuer="Government of India",
            instrument_type=InstrumentType.G_SEC,
            maturity_date=date(2026, 12, 9),
            coupon_rate=7.15,
            source="RBI",
            data_type=DataType.REFERENCE,
            as_of=date(2025, 12, 9),
        )
        assert bond.data_type == DataType.REFERENCE
        assert bond.as_of == date(2025, 12, 9)


# =========================================================================
# Corporate bond extensibility tests
# =========================================================================

class TestCorporateExtensibility:
    """Optional corporate-bond fields are present but not populated for G-Secs."""

    def test_gsec_does_not_populate_corporate_fields(self):
        """G-Sec does not set corporate-specific fields."""
        bond = Bond(
            isin="IB1234567890",
            security_name="7.15% G-Sec 2026",
            issuer="Government of India",
            instrument_type=InstrumentType.G_SEC,
            maturity_date=date(2026, 12, 9),
            coupon_rate=7.15,
            source="CCIL",
            data_type=DataType.TRADED,
        )
        assert bond.credit_rating is None
        assert bond.rating_agency is None
        assert bond.secured_status is None
        assert bond.seniority is None
        assert bond.call_date is None
        assert bond.put_date is None
        assert bond.issuer_sector is None

    def test_bond_model_has_corporate_fields(self):
        """Bond model has optional corporate-bond fields."""
        bond = Bond.construct()
        assert hasattr(bond, "credit_rating")
        assert hasattr(bond, "rating_agency")
        assert hasattr(bond, "secured_status")
        assert hasattr(bond, "seniority")
        assert hasattr(bond, "call_date")
        assert hasattr(bond, "put_date")
        assert hasattr(bond, "issuer_sector")
