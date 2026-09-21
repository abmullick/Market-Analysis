"""Persistent Bond Central credit-ratings index (SQLite).

The CDSL corporate-bond universe stays the primary bond universe. Bond Central
is used ONLY as a supplementary credit-rating source: this module stores the
rating information its public securities API publishes, keyed by normalized
ISIN, so bond list / detail requests never call Bond Central and never issue
one request per ISIN.

Retained per ISIN (rating information only — no Bond Central security details):

    credit_rating, credit_rating_agency_name, date_of_credit_rating,
    ratings_watch, ratings_outlook
    (+ security_status, display-only, matching the existing
       ``BondCentralRating`` contract)

Every ISIN the source lists is indexed with a coverage status, so "the source
publishes no rating for this security" stays distinct from "this security is
not in the index at all":

    rated    — at least one usable CRA rating value
    unrated  — listed by the source with no rating value and no rating metadata
    unknown  — listed with rating metadata (agency/date/...) but no rating value

Storage uses only the standard library (``sqlite3``) and lives beside the
project's other persistent caches (``data/cache``). Refreshing is handled by
:mod:`backend.services.bonds.bond_central_ratings_sync`.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Iterable, Optional

from backend.models.bonds import BondCentralRating
from backend.utils.logging import logger

#: Coverage status values stored per ISIN.
RATING_STATUS_RATED = "rated"
RATING_STATUS_UNRATED = "unrated"
RATING_STATUS_UNKNOWN = "unknown"

#: Metadata keys persisted in the ``meta`` table (surfaced by the status API).
META_LAST_SUCCESS = "last_success_ts"
META_LAST_ATTEMPT = "last_attempt_ts"
META_STATUS = "status"
META_ERROR = "error"
META_RECORDS_PROCESSED = "records_processed"
META_RATINGS_STORED = "ratings_stored"
META_SECURITIES_INDEXED = "securities_indexed"
META_CDSL_ISINS_TOTAL = "cdsl_isins_total"
META_CDSL_ISINS_MATCHED = "cdsl_isins_matched"
META_PAGES_FETCHED = "pages_fetched"
META_PAGES_FAILED = "pages_failed"
META_TOTAL_PAGES = "total_pages"
META_DURATION_SECONDS = "duration_seconds"

META_KEYS: tuple[str, ...] = (
    META_LAST_SUCCESS,
    META_LAST_ATTEMPT,
    META_STATUS,
    META_ERROR,
    META_RECORDS_PROCESSED,
    META_RATINGS_STORED,
    META_SECURITIES_INDEXED,
    META_CDSL_ISINS_TOTAL,
    META_CDSL_ISINS_MATCHED,
    META_PAGES_FETCHED,
    META_PAGES_FAILED,
    META_TOTAL_PAGES,
    META_DURATION_SECONDS,
)

_RATINGS_COLUMNS: tuple[str, ...] = (
    "isin",
    "credit_rating",
    "credit_rating_agency_name",
    "date_of_credit_rating",
    "ratings_watch",
    "ratings_outlook",
    "security_status",
)

_RATINGS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS {table} (
    isin TEXT NOT NULL,
    credit_rating TEXT NOT NULL DEFAULT '',
    credit_rating_agency_name TEXT NOT NULL DEFAULT '',
    date_of_credit_rating TEXT NOT NULL DEFAULT '',
    ratings_watch TEXT NOT NULL DEFAULT '',
    ratings_outlook TEXT NOT NULL DEFAULT '',
    security_status TEXT NOT NULL DEFAULT '',
    UNIQUE (isin, credit_rating, credit_rating_agency_name,
            date_of_credit_rating, ratings_watch, ratings_outlook,
            security_status)
)
"""

_SECURITIES_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS {table} (
    isin TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    fetched_at REAL NOT NULL
)
"""

_META_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
)
"""


def normalize_isin(isin: Any) -> str:
    """Normalize an ISIN for indexing / joining (trim + upper-case)."""
    return str(isin or "").strip().upper()


class BondCentralRatingsIndex:
    """SQLite-backed ISIN -> Bond Central rating index with an in-memory cache.

    Reads are served from an in-memory snapshot (loaded once, reloaded after a
    successful refresh), so joining the index against the CDSL corporate
    universe costs no I/O and makes no network calls.
    """

    def __init__(self, db_path: str, ttl_seconds: int = 86400) -> None:
        self.db_path = db_path
        self.ttl_seconds = int(ttl_seconds)
        self._lock = threading.RLock()
        self._snapshot_loaded = False
        self._ratings: dict[str, list[BondCentralRating]] = {}
        self._statuses: dict[str, str] = {}
        self._meta: dict[str, Any] = {}
        self._last_match: dict[str, Any] = {}
        self._ensure_schema()

    # ------------------------------------------------------------------
    # Storage plumbing
    # ------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        """Open a connection; writes use explicit transactions."""
        path = Path(self.db_path)
        if path.parent and not path.parent.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path, timeout=30.0, isolation_level=None)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        conn = self._connect()
        try:
            conn.execute("BEGIN")
            conn.execute(_RATINGS_TABLE_SQL.format(table="ratings"))
            conn.execute(_SECURITIES_TABLE_SQL.format(table="securities"))
            conn.execute(_META_TABLE_SQL)
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Snapshot (in-memory read path)
    # ------------------------------------------------------------------

    def load(self, force: bool = False) -> None:
        """(Re)load the in-memory snapshot from SQLite."""
        with self._lock:
            if self._snapshot_loaded and not force:
                return
            ratings: dict[str, list[BondCentralRating]] = {}
            statuses: dict[str, str] = {}
            meta: dict[str, Any] = {}
            conn = self._connect()
            try:
                for row in conn.execute(
                    "SELECT isin, credit_rating, credit_rating_agency_name, "
                    "date_of_credit_rating, ratings_watch, ratings_outlook, "
                    "security_status FROM ratings"
                ):
                    isin = normalize_isin(row["isin"])
                    if not isin:
                        continue
                    ratings.setdefault(isin, []).append(
                        BondCentralRating(
                            credit_rating=row["credit_rating"] or None,
                            credit_rating_agency_name=(
                                row["credit_rating_agency_name"] or None
                            ),
                            date_of_credit_rating=(
                                row["date_of_credit_rating"] or None
                            ),
                            ratings_watch=row["ratings_watch"] or None,
                            ratings_outlook=row["ratings_outlook"] or None,
                            security_status=row["security_status"] or None,
                        )
                    )
                for row in conn.execute("SELECT isin, status FROM securities"):
                    statuses[normalize_isin(row["isin"])] = row["status"]
                for row in conn.execute("SELECT key, value FROM meta"):
                    meta[row["key"]] = self._decode(row["value"])
            finally:
                conn.close()
            self._ratings = ratings
            self._statuses = statuses
            self._meta = meta
            self._snapshot_loaded = True

    @staticmethod
    def _decode(value: str) -> Any:
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return value

    @staticmethod
    def _encode(value: Any) -> str:
        return json.dumps(value)

    # ------------------------------------------------------------------
    # Read API (used by the Bond service join)
    # ------------------------------------------------------------------

    def ratings_for(self, isin: str) -> list[BondCentralRating]:
        """Return every retained rating observation for *isin* (may be empty)."""
        self.load()
        with self._lock:
            return list(self._ratings.get(normalize_isin(isin), ()))

    def status_for(self, isin: str) -> Optional[str]:
        """Return the coverage status for *isin* (``None`` when not indexed)."""
        self.load()
        with self._lock:
            return self._statuses.get(normalize_isin(isin))

    def is_indexed(self, isin: str) -> bool:
        """True when the source lists *isin* (rated, unrated or unknown)."""
        return self.status_for(isin) is not None

    def is_known_unrated(self, isin: str) -> bool:
        """True when the source explicitly lists *isin* without any rating."""
        return self.status_for(isin) == RATING_STATUS_UNRATED

    def indexed_isins(self) -> set[str]:
        self.load()
        with self._lock:
            return set(self._statuses)

    def index_size(self) -> int:
        self.load()
        with self._lock:
            return len(self._statuses)

    def ratings_count(self) -> int:
        self.load()
        with self._lock:
            return sum(len(rows) for rows in self._ratings.values())

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------

    def metadata(self) -> dict[str, Any]:
        """Return cache/refresh metadata (last refresh, counters, status)."""
        self.load()
        with self._lock:
            meta = dict(self._meta)
            indexed = len(self._statuses)
            ratings_stored = sum(len(rows) for rows in self._ratings.values())
        meta["running"] = meta.get(META_STATUS) == "running"
        meta["db_path"] = self.db_path
        meta["ttl_seconds"] = self.ttl_seconds
        meta["indexed_isins"] = indexed
        meta["ratings_stored"] = ratings_stored
        last_success = meta.get(META_LAST_SUCCESS)
        if isinstance(last_success, (int, float)) and last_success:
            age = time.time() - float(last_success)
            meta["last_success_age_seconds"] = round(age, 1)
            meta["stale"] = age > self.ttl_seconds
        else:
            meta["last_success_age_seconds"] = None
            meta["stale"] = True
        for key in META_KEYS:
            meta.setdefault(key, None)
        meta.update(self._last_match)
        return meta

    def update_metadata(self, **values: Any) -> None:
        """Persist metadata values (``None`` deletes the key)."""
        if not values:
            return
        conn = self._connect()
        try:
            conn.execute("BEGIN")
            for key, value in values.items():
                if value is None:
                    conn.execute("DELETE FROM meta WHERE key = ?", (key,))
                else:
                    conn.execute(
                        "INSERT INTO meta (key, value) VALUES (?, ?) "
                        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                        (key, self._encode(value)),
                    )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()
        with self._lock:
            for key, value in values.items():
                if value is None:
                    self._meta.pop(key, None)
                else:
                    self._meta[key] = value

    def record_match_stats(
        self,
        cdsl_isins_total: int,
        cdsl_isins_matched: int,
    ) -> None:
        """Record how many CDSL corporate ISINs the index matched.

        Called by the join while building a corporate list; persisted so the
        status endpoint can report it after a restart. Writes only when the
        values change, so list requests stay write-free in the common case.
        """
        stats = {
            META_CDSL_ISINS_TOTAL: int(cdsl_isins_total),
            META_CDSL_ISINS_MATCHED: int(cdsl_isins_matched),
        }
        if self._last_match == stats:
            return
        self._last_match = stats
        try:
            self.update_metadata(**stats)
        except Exception as exc:  # metadata is diagnostic only
            logger.debug("Bond Central ratings metadata update failed: %s", exc)

    # ------------------------------------------------------------------
    # Write API (used by the refresh/sync service)
    # ------------------------------------------------------------------

    def replace_snapshot(
        self,
        ratings_by_isin: dict[str, Iterable[BondCentralRating]],
        statuses_by_isin: dict[str, str],
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        """Atomically replace the index with a freshly swept snapshot.

        Rows are written to side tables and swapped in inside one transaction,
        so an interrupted refresh can never leave a half-built index behind
        (callers simply do not call this after a failed sweep).
        """
        now = time.time()
        rating_rows: list[tuple] = []
        for isin, rows in ratings_by_isin.items():
            key = normalize_isin(isin)
            if not key:
                continue
            for row in rows:
                rating_rows.append(
                    (
                        key,
                        row.credit_rating or "",
                        row.credit_rating_agency_name or "",
                        row.date_of_credit_rating or "",
                        row.ratings_watch or "",
                        row.ratings_outlook or "",
                        row.security_status or "",
                    )
                )
        security_rows = [
            (normalize_isin(isin), status, now)
            for isin, status in statuses_by_isin.items()
            if normalize_isin(isin)
        ]

        with self._lock:
            conn = self._connect()
            try:
                conn.execute("BEGIN")
                conn.execute("DROP TABLE IF EXISTS ratings_new")
                conn.execute("DROP TABLE IF EXISTS securities_new")
                conn.execute(_RATINGS_TABLE_SQL.format(table="ratings_new"))
                conn.execute(_SECURITIES_TABLE_SQL.format(table="securities_new"))
                conn.executemany(
                    "INSERT OR IGNORE INTO ratings_new "
                    f"({', '.join(_RATINGS_COLUMNS)}) "
                    f"VALUES ({', '.join('?' * len(_RATINGS_COLUMNS))})",
                    rating_rows,
                )
                conn.executemany(
                    "INSERT OR REPLACE INTO securities_new "
                    "(isin, status, fetched_at) VALUES (?, ?, ?)",
                    security_rows,
                )
                conn.execute("DROP TABLE IF EXISTS ratings")
                conn.execute("DROP TABLE IF EXISTS securities")
                conn.execute("ALTER TABLE ratings_new RENAME TO ratings")
                conn.execute("ALTER TABLE securities_new RENAME TO securities")
                for key, value in (metadata or {}).items():
                    if value is None:
                        conn.execute("DELETE FROM meta WHERE key = ?", (key,))
                    else:
                        conn.execute(
                            "INSERT INTO meta (key, value) VALUES (?, ?) "
                            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                            (key, self._encode(value)),
                        )
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise
            finally:
                conn.close()
            self._snapshot_loaded = False

        self.load(force=True)
        logger.info(
            "Bond Central ratings index replaced: %d ISINs indexed, %d rating rows",
            len(statuses_by_isin),
            len(rating_rows),
        )


#: Shared index instance (one SQLite file per process).
_index: Optional[BondCentralRatingsIndex] = None
_index_lock = threading.Lock()


def get_ratings_index(settings: Any = None) -> BondCentralRatingsIndex:
    """Return the process-wide Bond Central ratings index."""
    global _index
    with _index_lock:
        if _index is None:
            if settings is None:
                from backend.config.settings import Settings

                settings = Settings()
            _index = BondCentralRatingsIndex(
                db_path=getattr(
                    settings,
                    "bond_central_ratings_db",
                    "data/cache/bond_central_ratings.sqlite3",
                ),
                ttl_seconds=int(
                    getattr(settings, "bond_central_ratings_ttl_seconds", 86400)
                ),
            )
        return _index

