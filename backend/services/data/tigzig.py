"""TigZig bulk NAV dataset service.

Manages download, validation, and querying of the TigZig complete NAV Parquet dataset.

Memory-efficient design:
- Startup: Only checks file existence, does NOT open Parquet file
- Querying: Uses predicate pushdown and column projection
- Never loads entire dataset into RAM
"""
import os
import shutil
import tempfile
import time
from datetime import datetime, timedelta
from typing import Any, Optional

import httpx
import pyarrow.parquet as pq

from backend.utils.logging import logger


TIGZIG_BASE_URL = "https://api.tigzig.com/mf/v1"
TIGZIG_MANIFEST_URL = f"{TIGZIG_BASE_URL}/downloads/manifest"
TIGZIG_DOWNLOAD_URL = f"{TIGZIG_BASE_URL}/download?format=parquet"

DEFAULT_DATA_DIR = "/tmp/market_analysis_data"
DEFAULT_DATASET_FILENAME = "tigzig_nav.parquet"


class TigZigDatasetError(Exception):
    """Raised when TigZig dataset operations fail."""


def _get_memory_mb() -> float:
    """Get current process memory usage in MB."""
    import psutil
    process = psutil.Process()
    return process.memory_info().rss / 1024 / 1024


class TigZigDataset:
    """Manages the TigZig bulk NAV Parquet dataset.

    Memory-efficient design:
    - Does NOT keep Parquet file handles open
    - Uses memory-mapped reads only during active queries
    - Applies predicate pushdown for date/scheme filtering
    """

    def __init__(
        self,
        data_dir: str = DEFAULT_DATA_DIR,
        dataset_filename: str = DEFAULT_DATASET_FILENAME,
    ):
        self._data_dir = data_dir
        self._dataset_filename = dataset_filename
        self._dataset_path = os.path.join(data_dir, dataset_filename)
        self._temp_path = os.path.join(data_dir, f".{dataset_filename}.tmp")

        self._manifest: dict[str, Any] | None = None
        self._manifest_etag: str | None = None
        self._last_check: float = 0
        self._check_interval = 3600  # Check manifest every hour

        os.makedirs(data_dir, exist_ok=True)

    @property
    def is_available(self) -> bool:
        """Check if a valid dataset file exists.

        This only checks file existence and size - does NOT open the Parquet file.
        """
        return os.path.exists(self._dataset_path) and os.path.getsize(self._dataset_path) > 0

    @property
    def dataset_path(self) -> str:
        """Get the path to the active dataset file."""
        return self._dataset_path

    def get_stats(self) -> dict[str, Any]:
        """Get dataset statistics using lightweight metadata read.

        This reads ONLY the Parquet metadata, not any row data.
        Suitable for startup use when memory is constrained.
        """
        if not self.is_available:
            return {"available": False}

        try:
            mem_before = _get_memory_mb()
            metadata = pq.read_metadata(self._dataset_path)
            mem_after = _get_memory_mb()

            file_size = os.path.getsize(self._dataset_path)

            return {
                "available": True,
                "path": self._dataset_path,
                "size_bytes": file_size,
                "size_mb": file_size / (1024 * 1024),
                "row_groups": metadata.num_row_groups,
                "total_rows": metadata.num_rows,
                "memory_delta_mb": mem_after - mem_before,
            }
        except Exception as e:
            return {"available": False, "error": str(e)}

    async def fetch_manifest(self) -> dict[str, Any]:
        """Fetch the TigZig dataset manifest."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            headers = {}
            if self._manifest_etag:
                headers["If-None-Match"] = self._manifest_etag

            response = await client.get(TIGZIG_MANIFEST_URL, headers=headers)

            if response.status_code == 304:
                logger.info("TigZig manifest unchanged (304)")
                return self._manifest or {}

            response.raise_for_status()
            self._manifest = response.json()
            self._manifest_etag = response.headers.get("ETag")
            self._last_check = time.time()

            return self._manifest

    async def ensure_dataset(self, force_download: bool = False, manifest: dict[str, Any] | None = None) -> bool:
        """Ensure a valid dataset is available.

        Downloads the dataset if it doesn't exist or if force_download is True.
        Uses the manifest to check if the dataset has changed.

        Args:
            force_download: Force re-download even if dataset exists
            manifest: Optional pre-fetched manifest data

        Returns:
            True if a valid dataset is available
        """
        if self.is_available and not force_download:
            # Check if update is needed
            if time.time() - self._last_check < self._check_interval:
                logger.info("Using existing TigZig dataset (recently checked)")
                return True

            try:
                if manifest is None:
                    manifest = await self.fetch_manifest()
                if not self._manifest_etag or self._manifest_etag != self._get_stored_etag():
                    logger.info("TigZig dataset update detected, downloading...")
                    return await self._download_dataset(manifest)
                logger.info("TigZig dataset is up to date")
                return True
            except Exception as e:
                logger.warning(f"Manifest check failed: {e}, using existing dataset")
                return self.is_available

        if not force_download and self.is_available:
            return True

        return await self._download_dataset(manifest)

    async def _download_dataset(self, manifest: dict[str, Any] | None = None) -> bool:
        """Download the TigZig Parquet dataset.

        Downloads to a temporary file using streaming to minimize memory usage.
        Validates, then atomically renames.

        Args:
            manifest: Optional manifest data for validation

        Returns:
            True if download and validation succeeded
        """
        mem_before = _get_memory_mb()
        logger.info(f"Memory before download: {mem_before:.1f} MB")

        logger.info("Downloading TigZig NAV dataset...")

        start_time = time.time()
        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                async with client.stream("GET", TIGZIG_DOWNLOAD_URL, follow_redirects=True) as response:
                    response.raise_for_status()

                    # Stream to temp file to minimize memory usage
                    with open(self._temp_path, "wb") as f:
                        async for chunk in response.aiter_bytes(chunk_size=1024 * 1024):
                            f.write(chunk)

            download_time = time.time() - start_time
            file_size = os.path.getsize(self._temp_path)
            logger.info(
                f"Downloaded {file_size / (1024 * 1024):.1f} MB in {download_time:.1f}s"
            )

            mem_after_download = _get_memory_mb()
            logger.info(f"Memory after download: {mem_after_download:.1f} MB")

            # Validate the downloaded file (lightweight metadata check only)
            if not self._validate_dataset_light(self._temp_path):
                logger.error("Downloaded dataset validation failed")
                if os.path.exists(self._temp_path):
                    os.remove(self._temp_path)
                return self.is_available

            # Atomic rename
            shutil.move(self._temp_path, self._dataset_path)
            logger.info(f"Dataset installed at {self._dataset_path}")

            mem_after = _get_memory_mb()
            logger.info(f"Memory after install: {mem_after:.1f} MB")

            return True

        except Exception as e:
            logger.error(f"Failed to download TigZig dataset: {e}")
            if os.path.exists(self._temp_path):
                os.remove(self._temp_path)
            return self.is_available

    def _validate_dataset(self, path: str, manifest: dict[str, Any] | None = None) -> bool:
        """Validate the downloaded Parquet file.

        Args:
            path: Path to the Parquet file
            manifest: Optional manifest for row count validation

        Returns:
            True if validation passes
        """
        try:
            # Check file exists and has content
            if not os.path.exists(path) or os.path.getsize(path) == 0:
                logger.error("Dataset file is empty or missing")
                return False

            # Try to open and read metadata
            pf = pq.ParquetFile(path)
            metadata = pf.metadata

            # Check row count if manifest available
            if manifest:
                expected_rows = manifest.get("total_rows")
                if expected_rows and metadata.num_rows != expected_rows:
                    logger.warning(
                        f"Row count mismatch: expected {expected_rows}, got {metadata.num_rows}"
                    )
                    # Don't fail on minor row count differences (dataset may have been updated)

            # Check required columns exist
            schema = pf.schema_arrow
            column_names = {f.name for f in schema}
            required_columns = {"scheme_code", "date", "nav"}
            if not required_columns.issubset(column_names):
                logger.error(f"Missing required columns: {required_columns - column_names}")
                return False

            logger.info(
                f"Dataset validated: {metadata.num_rows:,} rows, {metadata.num_row_groups} row groups"
            )
            return True

        except Exception as e:
            logger.error(f"Dataset validation error: {e}")
            return False

    def _validate_dataset_light(self, path: str) -> bool:
        """Lightweight validation of the Parquet file using only metadata.

        This method does NOT read any row data, only the Parquet metadata.
        Suitable for startup validation when memory is constrained.

        Args:
            path: Path to the Parquet file

        Returns:
            True if validation passes
        """
        mem_before = _get_memory_mb()

        try:
            # Check file exists and has content
            if not os.path.exists(path) or os.path.getsize(path) == 0:
                logger.error("Dataset file is empty or missing")
                return False

            # Read ONLY metadata (no row data loaded)
            metadata = pq.read_metadata(path)

            # Check required columns exist in schema
            schema = metadata.schema.to_arrow_schema()
            column_names = set(schema.names)
            required_columns = {"scheme_code", "date", "nav"}
            if not required_columns.issubset(column_names):
                logger.error(f"Missing required columns: {required_columns - column_names}")
                return False

            mem_after = _get_memory_mb()
            logger.info(
                f"Dataset validated (light): {metadata.num_rows:,} rows, "
                f"{metadata.num_row_groups} row groups, "
                f"memory: {mem_before:.1f} -> {mem_after:.1f} MB"
            )
            return True

        except Exception as e:
            logger.error(f"Dataset validation error: {e}")
            return False

    def _get_stored_etag(self) -> str | None:
        """Get the stored ETag for the current dataset."""
        etag_file = f"{self._dataset_path}.etag"
        if os.path.exists(etag_file):
            with open(etag_file, "r") as f:
                return f.read().strip()
        return None

    def _store_etag(self, etag: str) -> None:
        """Store the ETag for the current dataset."""
        etag_file = f"{self._dataset_path}.etag"
        with open(etag_file, "w") as f:
            f.write(etag)

    def query_nav(
        self,
        scheme_codes: list[int],
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[int, list[dict[str, Any]]]:
        """Query NAV data for multiple schemes.

        Retrieves only the required columns and filters by scheme codes and date range.
        Never loads the entire dataset into memory.

        Args:
            scheme_codes: List of AMFI scheme codes
            start_date: Optional start date filter (YYYY-MM-DD)
            end_date: Optional end date filter (YYYY-MM-DD)

        Returns:
            Dictionary mapping scheme_code to list of NAV records
        """
        if not self.is_available:
            raise TigZigDatasetError("Dataset not available")

        if not scheme_codes:
            return {}

        start_time = time.time()
        mem_before = _get_memory_mb()

        # Build filters for predicate pushdown
        filters = [("scheme_code", "in", scheme_codes)]
        if start_date:
            filters.append(("date", ">=", start_date))
        if end_date:
            filters.append(("date", "<=", end_date))

        # Read only required columns with filters
        table = pq.read_table(
            self._dataset_path,
            columns=["scheme_code", "date", "nav"],
            filters=filters,
            memory_map=True,
        )

        query_time = time.time() - start_time
        mem_after = _get_memory_mb()

        # Group by scheme code - build result directly from Arrow table
        # to avoid creating large intermediate Python lists
        result: dict[int, list[dict[str, Any]]] = {code: [] for code in scheme_codes}

        # Use Arrow's native iteration instead of to_pylist() for memory efficiency
        # This avoids creating full Python lists in memory
        scheme_codes_col = table.column("scheme_code")
        dates_col = table.column("date")
        navs_col = table.column("nav")

        # Iterate over rows and build result dictionary
        for i in range(len(table)):
            code = scheme_codes_col[i].as_py()
            date = dates_col[i].as_py()
            nav = navs_col[i].as_py()
            result[code].append({
                "date": date,
                "nav": float(nav),
            })

        total_rows = len(table)
        logger.info(
            f"TigZig query: {len(scheme_codes)} schemes, {total_rows:,} rows in {query_time:.3f}s, "
            f"memory: {mem_before:.1f} -> {mem_after:.1f} MB (delta: {mem_after - mem_before:.1f} MB), "
            f"date_range={start_date or 'none'} to {end_date or 'none'}"
        )

        # Explicitly release table memory
        del table, scheme_codes_col, dates_col, navs_col

        return result

    def query_nav_chunked(
        self,
        scheme_codes: list[int],
        chunk_size: int = 100,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[int, list[dict[str, Any]]]:
        """Query NAV data for multiple schemes in memory-efficient chunks.

        Processes scheme codes in batches to limit memory usage.
        Each chunk is queried independently and results are merged.

        Args:
            scheme_codes: List of AMFI scheme codes
            chunk_size: Number of schemes to query per chunk
            start_date: Optional start date filter (YYYY-MM-DD)
            end_date: Optional end date filter (YYYY-MM-DD)

        Returns:
            Dictionary mapping scheme_code to list of NAV records
        """
        if not self.is_available:
            raise TigZigDatasetError("Dataset not available")

        if not scheme_codes:
            return {}

        start_time = time.time()
        mem_before = _get_memory_mb()
        result: dict[int, list[dict[str, Any]]] = {code: [] for code in scheme_codes}
        total_rows = 0
        num_chunks = 0

        # Process in chunks
        for i in range(0, len(scheme_codes), chunk_size):
            chunk_codes = scheme_codes[i:i + chunk_size]
            num_chunks += 1

            # Build filters for this chunk
            filters = [("scheme_code", "in", chunk_codes)]
            if start_date:
                filters.append(("date", ">=", start_date))
            if end_date:
                filters.append(("date", "<=", end_date))

            # Read only required columns with filters
            table = pq.read_table(
                self._dataset_path,
                columns=["scheme_code", "date", "nav"],
                filters=filters,
                memory_map=True,
            )

            # Convert to Python and merge into result
            # Use Arrow's native iteration for memory efficiency
            scheme_codes_col = table.column("scheme_code")
            dates_col = table.column("date")
            navs_col = table.column("nav")

            for i in range(len(table)):
                code = scheme_codes_col[i].as_py()
                date = dates_col[i].as_py()
                nav = navs_col[i].as_py()
                result[code].append({
                    "date": date,
                    "nav": float(nav),
                })

            chunk_rows = len(table)
            total_rows += chunk_rows

            # Explicitly release chunk data
            del table, scheme_codes_col, dates_col, navs_col

        query_time = time.time() - start_time
        mem_after = _get_memory_mb()
        logger.info(
            f"TigZig chunked query: {len(scheme_codes)} schemes in {num_chunks} chunks, "
            f"{total_rows:,} rows in {query_time:.3f}s, "
            f"memory: {mem_before:.1f} -> {mem_after:.1f} MB (delta: {mem_after - mem_before:.1f} MB), "
            f"date_range={start_date or 'none'} to {end_date or 'none'}"
        )

        return result

    def query_single_scheme(
        self,
        scheme_code: int,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[dict[str, Any]]:
        """Query NAV data for a single scheme.

        Args:
            scheme_code: AMFI scheme code
            start_date: Optional start date filter (YYYY-MM-DD)
            end_date: Optional end date filter (YYYY-MM-DD)

        Returns:
            List of NAV records sorted by date
        """
        result = self.query_nav([scheme_code], start_date, end_date)
        nav_data = result.get(scheme_code, [])
        nav_data.sort(key=lambda x: x["date"])
        return nav_data

    async def initialize(self) -> bool:
        """Initialize the dataset at application startup.

        Ensures a valid dataset is available.
        Uses lightweight metadata read - does NOT load row data.

        Returns:
            True if dataset is available
        """
        logger.info("Initializing TigZig dataset...")
        mem_before = _get_memory_mb()

        try:
            # Fetch manifest first
            manifest = await self.fetch_manifest()

            # Ensure dataset is available (downloads if needed)
            success = await self.ensure_dataset(manifest=manifest)

            if success and self.is_available:
                stats = self.get_stats()
                mem_after = _get_memory_mb()
                logger.info(
                    f"TigZig dataset ready: {stats.get('size_mb', 0):.1f} MB on disk, "
                    f"{stats.get('total_rows', 0):,} rows, "
                    f"memory: {mem_before:.1f} -> {mem_after:.1f} MB"
                )

            return success

        except Exception as e:
            logger.error(f"TigZig initialization failed: {e}")
            # Fall back to existing dataset if available
            return self.is_available


# Global dataset instance
_tigzig_dataset: TigZigDataset | None = None


def get_tigzig_dataset() -> TigZigDataset:
    """Get the global TigZig dataset instance."""
    global _tigzig_dataset
    if _tigzig_dataset is None:
        _tigzig_dataset = TigZigDataset()
    return _tigzig_dataset


async def initialize_tigzig() -> bool:
    """Initialize the TigZig dataset at startup."""
    dataset = get_tigzig_dataset()
    return await dataset.ensure_dataset()


TIGZIG_LATEST_URL = f"{TIGZIG_BASE_URL}/download?format=latest"
METADATA_CACHE_TTL = 86400


class TigZigMetadata:
    """Manages the TigZig latest scheme snapshot metadata."""

    def __init__(self, cache_ttl: int = METADATA_CACHE_TTL):
        self._cache_ttl = cache_ttl
        self._metadata: dict[int, dict[str, Any]] | None = None
        self._last_fetch: float = 0

    @property
    def is_cached(self) -> bool:
        if self._metadata is None:
            return False
        return (time.time() - self._last_fetch) < self._cache_ttl

    async def _fetch_snapshot(self) -> str:
        logger.info("Fetching TigZig latest snapshot...")
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.get(TIGZIG_LATEST_URL, follow_redirects=True)
            response.raise_for_status()
            return response.text

    def _parse_snapshot(self, csv_text: str) -> dict[int, dict[str, Any]]:
        import csv
        from io import StringIO

        metadata: dict[int, dict[str, Any]] = {}
        reader = csv.DictReader(StringIO(csv_text))
        for row in reader:
            try:
                code = int(row["scheme_code"])
            except (KeyError, ValueError):
                continue
            entry: dict[str, Any] = {"scheme_code": code}
            if row.get("first_date"):
                entry["first_date"] = row["first_date"]
            if row.get("aaum_cr_quarterly_avg"):
                try:
                    entry["aaum_cr_quarterly_avg"] = float(row["aaum_cr_quarterly_avg"])
                except ValueError:
                    pass
            if row.get("aaum_quarter"):
                entry["aaum_quarter"] = row["aaum_quarter"]
            if row.get("aaum_quarter_end"):
                entry["aaum_quarter_end"] = row["aaum_quarter_end"]
            if entry.get("aaum_cr_quarterly_avg") is not None or entry.get("first_date"):
                metadata[code] = entry
        return metadata

    async def get_metadata(self) -> dict[int, dict[str, Any]]:
        if self.is_cached:
            return self._metadata
        csv_text = await self._fetch_snapshot()
        self._metadata = self._parse_snapshot(csv_text)
        self._last_fetch = time.time()
        logger.info(f"TigZig metadata cached: {len(self._metadata)} schemes")
        return self._metadata

    def lookup(self, scheme_code: int) -> dict[str, Any] | None:
        if self._metadata is None:
            return None
        return self._metadata.get(scheme_code)

    def invalidate(self) -> None:
        self._metadata = None
        self._last_fetch = 0


_tigzig_metadata: TigZigMetadata | None = None


def get_tigzig_metadata() -> TigZigMetadata:
    global _tigzig_metadata
    if _tigzig_metadata is None:
        _tigzig_metadata = TigZigMetadata()
    return _tigzig_metadata
