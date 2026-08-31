"""Tests for TigZig metadata snapshot service."""

import pytest
from backend.services.data.tigzig import TigZigMetadata


class TestTigZigMetadata:
    """Test the TigZig metadata snapshot parsing and caching."""

    def test_parse_snapshot_extracts_required_fields(self):
        """Parser should extract scheme_code, first_date, aaum_cr_quarterly_avg, aaum_quarter, aaum_quarter_end."""
        csv_text = (
            "scheme_code,isin,scheme_name,aaum_cr_quarterly_avg,aaum_quarter,aaum_quarter_end,first_date,nav\n"
            "100027,INF123,Fund A,1500.5,2024-Q1,2024-03-31,2006-04-03,45.67\n"
            "100028,INF456,Fund B,2500.0,2024-Q2,2024-06-30,2007-05-15,123.45\n"
        )
        service = TigZigMetadata()
        result = service._parse_snapshot(csv_text)

        assert 100027 in result
        assert 100028 in result
        assert result[100027]["first_date"] == "2006-04-03"
        assert result[100027]["aaum_cr_quarterly_avg"] == 1500.5
        assert result[100027]["aaum_quarter"] == "2024-Q1"
        assert result[100027]["aaum_quarter_end"] == "2024-03-31"
        assert result[100028]["first_date"] == "2007-05-15"
        assert result[100028]["aaum_cr_quarterly_avg"] == 2500.0

    def test_parse_snapshot_skips_rows_with_missing_scheme_code(self):
        """Rows with invalid scheme_code should be skipped."""
        csv_text = (
            "scheme_code,isin,scheme_name,first_date\n"
            ",INF123,Fund A,2006-04-03\n"
            "abc,INF456,Fund B,2007-05-15\n"
            "100029,INF789,Fund C,2008-06-20\n"
        )
        service = TigZigMetadata()
        result = service._parse_snapshot(csv_text)

        assert len(result) == 1
        assert 100029 in result

    def test_parse_snapshot_skips_rows_without_metadata(self):
        """Rows without AUM or first_date should be skipped."""
        csv_text = (
            "scheme_code,isin,scheme_name,aaum_cr_quarterly_avg,first_date,nav\n"
            "100027,INF123,Fund A,,,45.67\n"
            "100028,INF456,Fund B,1500.5,,123.45\n"
            "100029,INF789,Fund C,,2008-06-20,67.89\n"
        )
        service = TigZigMetadata()
        result = service._parse_snapshot(csv_text)

        assert 100027 not in result
        assert 100028 in result
        assert 100029 in result

    def test_lookup_returns_metadata_by_scheme_code(self):
        """Lookup should return metadata for a given scheme_code."""
        csv_text = (
            "scheme_code,isin,scheme_name,aaum_cr_quarterly_avg,first_date,nav\n"
            "100027,INF123,Fund A,1500.5,2006-04-03,45.67\n"
        )
        service = TigZigMetadata()
        service._metadata = service._parse_snapshot(csv_text)

        result = service.lookup(100027)
        assert result is not None
        assert result["aaum_cr_quarterly_avg"] == 1500.5
        assert result["first_date"] == "2006-04-03"

    def test_lookup_returns_none_for_missing_scheme(self):
        """Lookup should return None for scheme not in metadata."""
        csv_text = (
            "scheme_code,isin,scheme_name,aaum_cr_quarterly_avg,first_date,nav\n"
            "100027,INF123,Fund A,1500.5,2006-04-03,45.67\n"
        )
        service = TigZigMetadata()
        service._metadata = service._parse_snapshot(csv_text)

        assert service.lookup(999999) is None

    def test_cache_ttl_prevents_refetch(self):
        """Metadata should be cached and not refetched within TTL."""
        service = TigZigMetadata(cache_ttl=3600)
        service._metadata = {100027: {"scheme_code": 100027}}
        service._last_fetch = __import__("time").time()

        assert service.is_cached is True

    def test_cache_expires_after_ttl(self):
        """Cache should expire after TTL."""
        service = TigZigMetadata(cache_ttl=1)
        service._metadata = {100027: {"scheme_code": 100027}}
        service._last_fetch = __import__("time").time() - 2

        assert service.is_cached is False

    def test_invalidate_clears_cache(self):
        """Invalidate should clear the cache."""
        service = TigZigMetadata()
        service._metadata = {100027: {"scheme_code": 100027}}
        service._last_fetch = __import__("time").time()

        service.invalidate()

        assert service._metadata is None
        assert service._last_fetch == 0
