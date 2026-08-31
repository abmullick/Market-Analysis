"""Tests for TigZig dataset service and integration."""
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.data.tigzig import (
    TigZigDataset,
    TigZigDatasetError,
    get_tigzig_dataset,
)
from backend.services.mutual_funds.fetcher import MutualFundFetcher

# Configure pytest-asyncio to use auto mode
pytestmark = pytest.mark.asyncio


class TestTigZigDataset:
    """Test TigZigDataset class."""

    def test_init_creates_directory(self):
        """Dataset directory should be created on init."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dataset = TigZigDataset(data_dir=tmpdir)
            assert os.path.exists(tmpdir)
            assert dataset._dataset_path == os.path.join(tmpdir, "tigzig_nav.parquet")

    def test_is_available_false_when_no_file(self):
        """is_available should return False when no file exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dataset = TigZigDataset(data_dir=tmpdir)
            assert dataset.is_available is False

    def test_stats_unavailable(self):
        """stats should report unavailable when no file exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dataset = TigZigDataset(data_dir=tmpdir)
            stats = dataset.stats
            assert stats["available"] is False

    async def test_ensure_dataset_downloads_when_missing(self):
        """ensure_dataset should download when file doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dataset = TigZigDataset(data_dir=tmpdir)

            # Mock the download
            with patch.object(dataset, '_download_dataset', new_callable=AsyncMock) as mock_download:
                mock_download.return_value = True
                result = await dataset.ensure_dataset()
                assert result is True
                mock_download.assert_called_once()

    async def test_ensure_dataset_uses_existing(self):
        """ensure_dataset should use existing file if available."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dataset = TigZigDataset(data_dir=tmpdir)

            # Create a dummy file
            with open(dataset._dataset_path, "wb") as f:
                f.write(b"dummy")

            # Mock manifest fetch to avoid network call
            with patch.object(dataset, 'fetch_manifest', new_callable=AsyncMock) as mock_manifest:
                mock_manifest.return_value = {"total_rows": 100}
                result = await dataset.ensure_dataset()
                assert result is True

    def test_validate_dataset_empty_file(self):
        """Validation should fail for empty file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dataset = TigZigDataset(data_dir=tmpdir)

            # Create empty file
            empty_path = os.path.join(tmpdir, "empty.parquet")
            with open(empty_path, "wb") as f:
                pass

            assert dataset._validate_dataset(empty_path) is False

    def test_validate_dataset_missing_columns(self):
        """Validation should fail if required columns missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dataset = TigZigDataset(data_dir=tmpdir)

            # Create parquet with wrong columns
            try:
                import pyarrow as pa
                import pyarrow.parquet as pq

                table = pa.table({"wrong_column": [1, 2, 3]})
                bad_path = os.path.join(tmpdir, "bad.parquet")
                pq.write_table(table, bad_path)

                assert dataset._validate_dataset(bad_path) is False
            except ImportError:
                pytest.skip("pyarrow not available")


class TestTigZigDatasetQueries:
    """Test TigZig dataset query methods."""

    def test_query_nav_empty_codes_returns_empty(self):
        """query_nav should return empty dict for empty codes when dataset exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dataset = TigZigDataset(data_dir=tmpdir)

            # Create a minimal valid parquet file
            try:
                import pyarrow as pa
                import pyarrow.parquet as pq

                table = pa.table(
                    {
                        "scheme_code": pa.array([], type=pa.int32()),
                        "date": pa.array([], type=pa.string()),
                        "nav": pa.array([], type=pa.decimal128(18, 4)),
                    }
                )
                pq.write_table(table, dataset._dataset_path)
            except ImportError:
                pytest.skip("pyarrow not available")

            result = dataset.query_nav([])
            assert result == {}

    def test_query_nav_dataset_unavailable(self):
        """query_nav should raise error when dataset unavailable."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dataset = TigZigDataset(data_dir=tmpdir)
            with pytest.raises(TigZigDatasetError):
                dataset.query_nav([12345])


class TestTigZigIntegration:
    """Test TigZig integration with fetcher."""

    async def test_fetcher_uses_tigzig_when_available(self):
        """Fetcher should use TigZig when dataset is available."""
        from backend.config.settings import Settings

        settings = Settings()
        fetcher = MutualFundFetcher(settings=settings)

        # Mock TigZig dataset
        mock_dataset = MagicMock()
        mock_dataset.is_available = True
        mock_dataset.query_single_scheme.return_value = [
            {"date": "2024-01-01", "nav": 100.0},
            {"date": "2024-01-02", "nav": 101.0},
        ]

        with patch("backend.services.mutual_funds.fetcher.get_tigzig_dataset", return_value=mock_dataset):
            result = await fetcher.get_nav_history_tigzig("12345", lookback_years=1)
            assert len(result) == 2
            assert result[0].date == "2024-01-01"
            assert result[0].nav == 100.0

    async def test_fetcher_fallback_to_mfapi(self):
        """Fetcher should fallback to MFAPI when TigZig unavailable."""
        from backend.config.settings import Settings

        settings = Settings()
        fetcher = MutualFundFetcher(settings=settings)

        # Mock TigZig dataset as unavailable
        mock_dataset = MagicMock()
        mock_dataset.is_available = False

        with patch("backend.services.mutual_funds.fetcher.get_tigzig_dataset", return_value=mock_dataset):
            with patch.object(fetcher, "_get_nav_history_mfapi", new_callable=AsyncMock) as mock_mfapi:
                mock_mfapi.return_value = [{"date": "2024-01-01", "nav": 100.0}]
                result = await fetcher.get_nav_history("12345", lookback_years=1)
                mock_mfapi.assert_called_once()


class TestGetTigzigDataset:
    """Test get_tigzig_dataset singleton."""

    def test_returns_singleton(self):
        """get_tigzig_dataset should return same instance."""
        # Reset global
        import backend.services.data.tigzig as tigzig_module
        tigzig_module._tigzig_dataset = None

        dataset1 = get_tigzig_dataset()
        dataset2 = get_tigzig_dataset()
        assert dataset1 is dataset2


class TestFundGroupingIntegration:
    """Test fund grouping with TigZig data."""

    def test_grouping_preserves_all_schemes(self):
        """All schemes should be grouped without loss."""
        from backend.services.mutual_funds.fund_grouper import FundGrouper

        grouper = FundGrouper()

        # Add schemes with variants
        schemes = [
            {"scheme_code": "1", "scheme_name": "ABC Fund - Growth", "amc": "AMC A"},
            {"scheme_code": "2", "scheme_name": "ABC Fund - IDCW", "amc": "AMC A"},
            {"scheme_code": "3", "scheme_name": "XYZ Fund", "amc": "AMC B"},
        ]

        for s in schemes:
            grouper.add_scheme(s)

        groups = grouper.get_groups()
        assert len(groups) == 2  # ABC Fund and XYZ Fund

        # Check ABC Fund group
        abc_group = [g for k, g in groups.items() if "ABC Fund" in k][0]
        assert len(abc_group) == 2

    def test_ranking_candidates_one_per_fund(self):
        """Should produce one candidate per underlying fund."""
        from backend.services.mutual_funds.fund_grouper import FundGrouper

        grouper = FundGrouper()

        schemes = [
            {"scheme_code": "1", "scheme_name": "ABC Fund - Growth", "amc": "AMC A"},
            {"scheme_code": "2", "scheme_name": "ABC Fund - IDCW", "amc": "AMC A"},
            {"scheme_code": "3", "scheme_name": "XYZ Fund", "amc": "AMC B"},
        ]

        for s in schemes:
            grouper.add_scheme(s)

        candidates = grouper.get_ranking_candidates()
        assert len(candidates) == 2

    def test_excluded_variants_traceable(self):
        """Excluded variants should be traceable to parent fund."""
        from backend.services.mutual_funds.fund_grouper import FundGrouper

        grouper = FundGrouper()

        schemes = [
            {"scheme_code": "1", "scheme_name": "ABC Fund - Growth", "amc": "AMC A"},
            {"scheme_code": "2", "scheme_name": "ABC Fund - IDCW", "amc": "AMC A"},
        ]

        for s in schemes:
            grouper.add_scheme(s)

        excluded = grouper.get_excluded_variants()
        assert len(excluded) == 1
        assert excluded[0]["_selected_candidate"] == "1"  # Growth preferred


class TestChunkedQueryCorrectness:
    """Regression tests proving chunked queries produce identical results."""

    def test_chunked_query_matches_full_query(self):
        """query_nav_chunked should return same results as query_nav."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dataset = TigZigDataset(data_dir=tmpdir)

            try:
                import pyarrow as pa
                import pyarrow.parquet as pq
            except ImportError:
                pytest.skip("pyarrow not available")

            # Create test data with multiple scheme codes and dates
            scheme_codes = [100001, 100002, 100003, 100004, 100005]
            dates = ["2020-01-01", "2020-01-02", "2020-01-03"]
            rows = []
            for code in scheme_codes:
                for date in dates:
                    rows.append({
                        "scheme_code": code,
                        "date": date,
                        "nav": 100.0 + code % 10 + dates.index(date),
                    })

            table = pa.table({
                "scheme_code": pa.array([r["scheme_code"] for r in rows], type=pa.int32()),
                "date": pa.array([r["date"] for r in rows], type=pa.string()),
                "nav": pa.array([r["nav"] for r in rows], type=pa.float64()),
            })
            pq.write_table(table, dataset._dataset_path)

            # Query all at once
            full_result = dataset.query_nav(scheme_codes)

            # Query in chunks of 2
            chunked_result = dataset.query_nav_chunked(scheme_codes, chunk_size=2)

            # Results should be identical
            assert set(full_result.keys()) == set(chunked_result.keys())
            for code in scheme_codes:
                assert len(full_result[code]) == len(chunked_result[code])
                for full_row, chunked_row in zip(
                    sorted(full_result[code], key=lambda x: x["date"]),
                    sorted(chunked_result[code], key=lambda x: x["date"])
                ):
                    assert full_row["date"] == chunked_row["date"]
                    assert full_row["nav"] == chunked_row["nav"]

    def test_chunked_query_with_various_chunk_sizes(self):
        """Chunk size should not affect results."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dataset = TigZigDataset(data_dir=tmpdir)

            try:
                import pyarrow as pa
                import pyarrow.parquet as pq
            except ImportError:
                pytest.skip("pyarrow not available")

            # Create test data
            scheme_codes = list(range(200001, 200021))  # 20 codes
            dates = ["2021-06-01", "2021-06-02", "2021-06-03", "2021-06-04", "2021-06-05"]
            rows = []
            for code in scheme_codes:
                for date in dates:
                    rows.append({
                        "scheme_code": code,
                        "date": date,
                        "nav": 50.0 + (code % 100) * 0.1 + dates.index(date) * 0.5,
                    })

            table = pa.table({
                "scheme_code": pa.array([r["scheme_code"] for r in rows], type=pa.int32()),
                "date": pa.array([r["date"] for r in rows], type=pa.string()),
                "nav": pa.array([r["nav"] for r in rows], type=pa.float64()),
            })
            pq.write_table(table, dataset._dataset_path)

            # Query all at once (baseline)
            full_result = dataset.query_nav(scheme_codes)

            # Test various chunk sizes
            for chunk_size in [1, 3, 5, 10, 7, 15]:
                chunked_result = dataset.query_nav_chunked(scheme_codes, chunk_size=chunk_size)

                # Verify same scheme codes returned
                assert set(full_result.keys()) == set(chunked_result.keys()), \
                    f"Chunk size {chunk_size}: scheme codes mismatch"

                # Verify same data for each scheme
                for code in scheme_codes:
                    full_sorted = sorted(full_result[code], key=lambda x: (x["date"], x["nav"]))
                    chunked_sorted = sorted(chunked_result[code], key=lambda x: (x["date"], x["nav"]))
                    assert len(full_sorted) == len(chunked_sorted), \
                        f"Chunk size {chunk_size}: row count mismatch for code {code}"
                    for full_row, chunked_row in zip(full_sorted, chunked_sorted):
                        assert full_row["date"] == chunked_row["date"], \
                            f"Chunk size {chunk_size}: date mismatch for code {code}"
                        assert abs(full_row["nav"] - chunked_row["nav"]) < 1e-10, \
                            f"Chunk size {chunk_size}: nav mismatch for code {code}"

    def test_chunked_query_empty_codes(self):
        """Chunked query with empty codes should return empty dict."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dataset = TigZigDataset(data_dir=tmpdir)

            try:
                import pyarrow as pa
                import pyarrow.parquet as pq
            except ImportError:
                pytest.skip("pyarrow not available")

            # Create minimal dataset
            table = pa.table({
                "scheme_code": pa.array([], type=pa.int32()),
                "date": pa.array([], type=pa.string()),
                "nav": pa.array([], type=pa.float64()),
            })
            pq.write_table(table, dataset._dataset_path)

            result = dataset.query_nav_chunked([], chunk_size=10)
            assert result == {}

    def test_chunked_query_single_code(self):
        """Chunked query with single code should work correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dataset = TigZigDataset(data_dir=tmpdir)

            try:
                import pyarrow as pa
                import pyarrow.parquet as pq
            except ImportError:
                pytest.skip("pyarrow not available")

            # Create test data with single code
            table = pa.table({
                "scheme_code": pa.array([999999, 999999, 999999], type=pa.int32()),
                "date": pa.array(["2023-01-01", "2023-01-02", "2023-01-03"], type=pa.string()),
                "nav": pa.array([100.0, 101.0, 102.0], type=pa.float64()),
            })
            pq.write_table(table, dataset._dataset_path)

            # Query with chunk_size=1 (edge case)
            result = dataset.query_nav_chunked([999999], chunk_size=1)
            assert 999999 in result
            assert len(result[999999]) == 3
