"""Offline tests for source-scoped bond record identity.

No network access: every case is derived from in-memory fixtures.
"""

from __future__ import annotations

import re
from datetime import date, datetime

import pytest

from backend.services.bonds.bond_identity import (
    SOURCE_CCIL,
    SOURCE_NSE,
    ensure_record_id,
    ensure_record_ids,
    is_valid_record_id,
    normalize_identity_text,
    parse_record_id,
    record_id_for,
    record_id_for_bond,
    record_id_source,
)

RECORD_ID_PATTERN = re.compile(r"^[a-z0-9_]+\|[a-z0-9_]+\|[0-9a-f]{12}$")


def _ccil_bond(**overrides):
    bond = {
        "source": "CCIL",
        "data_type": "TRADED",
        "security_name": "06.94 GS 2036",
        "maturity_date": "2036-05-11",
        "coupon_rate": 6.94,
        "isin": None,
    }
    bond.update(overrides)
    return bond


class TestRecordIdFormat:
    def test_matches_documented_format(self):
        record_id = record_id_for("CCIL", "TRADED", "06.94 GS 2036", "2036-05-11", 6.94)
        assert RECORD_ID_PATTERN.match(record_id)
        assert is_valid_record_id(record_id)

    def test_source_and_type_are_lowercase_prefixes(self):
        record_id = record_id_for("CCIL", "TRADED", "X", "2036-05-11", 6.94)
        assert record_id.startswith("ccil|traded|")
        assert record_id_source(record_id) == "ccil"

    def test_rejects_malformed_identifiers(self):
        for value in (None, "", "ccil", "ccil|traded", "ccil|traded|zzzzzzzzzzzz", "INE040A08831"):
            assert not is_valid_record_id(value)
            assert parse_record_id(value) is None

    def test_parse_returns_components(self):
        record_id = record_id_for("NSE", "REFERENCE", "CG2036", "2036-06-07", 8.33)
        parsed = parse_record_id(record_id)
        assert parsed is not None
        assert parsed["source"] == "nse"
        assert parsed["data_type"] == "reference"
        assert len(parsed["digest"]) == 12


class TestDeterminism:
    def test_same_inputs_produce_same_id(self):
        first = record_id_for("CCIL", "TRADED", "06.94 GS 2036", "2036-05-11", 6.94)
        second = record_id_for("CCIL", "TRADED", "06.94 GS 2036", "2036-05-11", 6.94)
        assert first == second

    def test_casing_and_whitespace_are_normalized(self):
        canonical = record_id_for("CCIL", "TRADED", "06.94 GS 2036", "2036-05-11", 6.94)
        variant = record_id_for("ccil ", " traded", "  06.94   gs 2036 ", "2036-05-11", "6.94")
        assert canonical == variant

    def test_equivalent_date_and_float_forms_agree(self):
        from_string = record_id_for("CCIL", "TRADED", "X", "2036-05-11", 6.9)
        from_date = record_id_for("CCIL", "TRADED", "X", date(2036, 5, 11), 6.90)
        from_datetime = record_id_for("CCIL", "TRADED", "X", datetime(2036, 5, 11, 9, 30), 6.9000)
        assert from_string == from_date == from_datetime

    def test_enum_like_data_type_is_supported(self):
        class _DataType:
            value = "TRADED"

        assert record_id_for("CCIL", _DataType(), "X", "2036-05-11", 6.94) == record_id_for(
            "CCIL", "TRADED", "X", "2036-05-11", 6.94
        )


class TestSourceScoping:
    def test_sources_do_not_collide(self):
        ccil = record_id_for(SOURCE_CCIL, "TRADED", "7.15% G-Sec 2026", "2026-01-01", 7.15)
        nse = record_id_for(SOURCE_NSE, "TRADED", "7.15% G-Sec 2026", "2026-01-01", 7.15)
        assert ccil != nse
        assert ccil.startswith("ccil|")
        assert nse.startswith("nse|")

    def test_data_types_do_not_collide(self):
        traded = record_id_for("NSE", "TRADED", "CG2036", "2036-06-07", 8.33)
        reference = record_id_for("NSE", "REFERENCE", "CG2036", "2036-06-07", 8.33)
        assert traded != reference


class TestMissingFieldPreservation:
    def test_none_components_are_not_fabricated(self):
        record_id = record_id_for("CCIL", "TRADED", None, None, None)
        assert RECORD_ID_PATTERN.match(record_id)

    def test_missing_and_non_missing_inputs_differ(self):
        with_maturity = record_id_for("CCIL", "TRADED", "X", "2036-05-11", None)
        without_maturity = record_id_for("CCIL", "TRADED", "X", None, None)
        assert with_maturity != without_maturity

    def test_unknown_source_is_labelled_not_invented(self):
        record_id = record_id_for(None, None, "X", None, None)
        assert record_id.startswith("unknown|unknown|")


class TestCollisionLimitation:
    """Documents the accepted, same-source collision limitation."""

    def test_same_fields_from_same_source_collide(self):
        first = record_id_for("CCIL", "TRADED", "08.07 KL SGS 2044", "2044-09-16", 8.07)
        second = record_id_for("CCIL", "TRADED", "08.07 KL SGS 2044", "2044-09-16", 8.07)
        assert first == second  # collision is expected and documented

    def test_collision_is_resolved_by_maturity_or_coupon(self):
        base = record_id_for("CCIL", "TRADED", "08.07 KL SGS 2044", "2044-09-16", 8.07)
        other_coupon = record_id_for("CCIL", "TRADED", "08.07 KL SGS 2044", "2044-09-16", 8.08)
        other_maturity = record_id_for("CCIL", "TRADED", "08.07 KL SGS 2044", "2045-09-16", 8.07)
        assert base != other_coupon
        assert base != other_maturity

    def test_distinct_descriptions_do_not_collide(self):
        first = record_id_for("CCIL", "TRADED", "06.94 GS 2036", "2036-05-11", 6.94)
        second = record_id_for("CCIL", "TRADED", "07.26 GS 2029", "2029-02-06", 7.26)
        assert first != second


class TestBondHelpers:
    def test_record_id_for_bond_accepts_dict(self):
        bond = _ccil_bond()
        assert record_id_for_bond(bond) == record_id_for(
            "CCIL", "TRADED", "06.94 GS 2036", "2036-05-11", 6.94
        )

    def test_record_id_for_bond_accepts_object(self):
        class _Bond:
            source = "CCIL"
            data_type = "TRADED"
            security_name = "06.94 GS 2036"
            maturity_date = date(2036, 5, 11)
            coupon_rate = 6.94

        assert is_valid_record_id(record_id_for_bond(_Bond()))

    def test_security_description_is_used_when_name_absent(self):
        without_name = _ccil_bond(security_name=None, security_description="06.94 GS 2036")
        assert record_id_for_bond(without_name) == record_id_for(
            "CCIL", "TRADED", "06.94 GS 2036", "2036-05-11", 6.94
        )

    def test_ensure_record_id_preserves_existing_value(self):
        bond = _ccil_bond(record_id="ccil|traded|0123456789ab")
        assert ensure_record_id(bond) is bond
        assert bond["record_id"] == "ccil|traded|0123456789ab"

    def test_ensure_record_id_stamps_missing_value(self):
        stamped = ensure_record_id(_ccil_bond())
        assert is_valid_record_id(stamped["record_id"])

    def test_ensure_record_ids_preserves_order_and_none_fields(self):
        bonds = ensure_record_ids([_ccil_bond(), _ccil_bond(security_name="07.26 GS 2029")])
        assert len(bonds) == 2
        assert bonds[0]["record_id"] != bonds[1]["record_id"]
        assert bonds[0]["isin"] is None


class TestTextNormalization:
    def test_whitespace_and_case_collapse(self):
        assert normalize_identity_text("  06.94 \u00a0gs   2036 ") == "06.94 GS 2036"

    def test_none_becomes_empty_string(self):
        assert normalize_identity_text(None) == ""
