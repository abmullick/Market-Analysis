"""TigZig bulk NAV dataset service.

Manages download, validation, and querying of the TigZig complete NAV Parquet dataset.
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


class TigZigDataset:
    """Manages the TigZig bulk NAV Parquet dataset."""

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
        self._parquet_file: pq.ParquetFile | None = None
        self._last_check: float = 0
        self._check_interval = 3600  # Check manifest every hour

        os.makedirs(data_dir, exist_ok=True)

    @property
    def is_available(self) -> bool:
        """Check if a valid dataset file exists."""
        return os.path.exists(self._dataset_path) and os.path.getsize(self._dataset_path) > 0

    @property
    def dataset_path(self) -> str:
        """Get the path to the active dataset file."""
        return self._dataset_path

    @property
    def stats(self) -> dict[str, Any]:
        """Get dataset statistics."""
        if not self.is_available:
            return {"available": False}

        try:
            if self._parquet_file is None:
                self._parquet_file = pq.ParquetFile(self._dataset_path)

            metadata = self._parquet_file.metadata
            file_size = os.path.getsize(self._dataset_path)

            return {
                "available": True,
                "path": self._dataset_path,
                "size_bytes": file_size,
                "size_mb": file_size / (1024 * 1024),
                "row_groups": metadata.num_row_groups,
                "total_rows": metadata.num_rows,
                "manifest_etag": self._manifest_etag,
                "last_check": self._last_check,
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

        Downloads to a temporary file, validates, then atomically renames.

        Args:
            manifest: Optional manifest data for validation

        Returns:
            True if download and validation succeeded
        """
        logger.info("Downloading TigZig NAV dataset...")

        start_time = time.time()
        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                response = await client.get(TIGZIG_DOWNLOAD_URL, follow_redirects=True)
                response.raise_for_status()

                # Write to temp file
                with open(self._temp_path, "wb") as f:
                    f.write(response.content)

            download_time = time.time() - start_time
            file_size = os.path.getsize(self._temp_path)
            logger.info(
                f"Downloaded {file_size / (1024 * 1024):.1f} MB in {download_time:.1f}s"
            )

            # Validate the downloaded file
            if not self._validate_dataset(self._temp_path, manifest):
                logger.error("Downloaded dataset validation failed")
                if os.path.exists(self._temp_path):
                    os.remove(self._temp_path)
                return self.is_available  # Return True if existing dataset is valid

            # Atomic rename
            shutil.move(self._temp_path, self._dataset_path)
            logger.info(f"Dataset installed at {self._dataset_path}")

            # Reset parquet file handle (will be reopened on next query)
            self._parquet_file = None

            return True

        except Exception as e:
            logger.error(f"Failed to download TigZig dataset: {e}")
            if os.path.exists(self._temp_path):
                os.remove(self._temp_path)
            return self.is_available  # Return True if existing dataset is valid

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

    def _get_parquet_file(self) -> pq.ParquetFile:
        """Get or open the Parquet file handle."""
        if self._parquet_file is None:
            self._parquet_file = pq.ParquetFile(self._dataset_path, memory_map=True)
        return self._parquet_file

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

        # Build filters
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

        # Group by scheme code
        result: dict[int, list[dict[str, Any]]] = {code: [] for code in scheme_codes}

        # Convert to Python (only the filtered data)
        scheme_codes_col = table.column("scheme_code").to_pylist()
        dates_col = table.column("date").to_pylist()
        navs_col = table.column("nav").to_pylist()

        for code, date, nav in zip(scheme_codes_col, dates_col, navs_col):
            result[code].append({
                "date": date,
                "nav": float(nav),
            })

        total_rows = len(table)
        logger.info(
            f"TigZig query: {len(scheme_codes)} schemes, {total_rows:,} rows in {query_time:.3f}s"
        )

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
            scheme_codes_col = table.column("scheme_code").to_pylist()
            dates_col = table.column("date").to_pylist()
            navs_col = table.column("nav").to_pylist()

            for code, date, nav in zip(scheme_codes_col, dates_col, navs_col):
                result[code].append({
                    "date": date,
                    "nav": float(nav),
                })

            chunk_rows = len(table)
            total_rows += chunk_rows

            # Explicitly release chunk data
            del table, scheme_codes_col, dates_col, navs_col

        query_time = time.time() - start_time
        logger.info(
            f"TigZig chunked query: {len(scheme_codes)} schemes in {num_chunks} chunks, "
            f"{total_rows:,} rows in {query_time:.3f}s"
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

        Returns:
            True if dataset is available
        """
        logger.info("Initializing TigZig dataset...")

        try:
            # Fetch manifest first
            manifest = await self.fetch_manifest()

            # Ensure dataset is available
            success = await self.ensure_dataset(manifest=manifest)

            if success and self.is_available:
                stats = self.stats
                logger.info(
                    f"TigZig dataset ready: {stats.get('size_mb', 0):.1f} MB, "
                    f"{stats.get('total_rows', 0):,} rows"
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
