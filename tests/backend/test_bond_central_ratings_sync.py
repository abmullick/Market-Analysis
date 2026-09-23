"""Focused tests for Bond Central ratings page retries and split recovery.

Regression context: pages 19, 42, 200, 209, 239 and 253 persistently
returned HTTP 500 server-side (poison records inside the 100-record
window). The sweep retries each failed page (up to 3 retries), then
splits a still-failing size=100 window into 2x size=50 (a failing half
into 2x size=25, a still-failing quarter narrowed to size=1), keeps
sweeping later pages, and logs page number + HTTP status + body excerpt
for every record that stays unretrievable.

Snapshot contract: the stored snapshot is replaced only when the sweep
completes — status ``ok`` when every record was retrieved, ``partial``
when known records stayed unretrievable. An interrupted or fully failed
sweep never replaces the snapshot.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from backend.models.bonds import BondCentralRawRating
from backend.services.bonds import bond_central_ratings_sync as sync_module
from backend.services.bonds.bond_central_ratings_index import (
    META_CDSL_ISINS_MATCHED,
    META_CDSL_ISINS_TOTAL,
    META_DURATION_SECONDS,
    META_LAST_SUCCESS,
    META_PAGES_FAILED,
    META_RATINGS_STORED,
    META_RECORDS_PROCESSED,
    META_SECURITIES_INDEXED,
    META_STATUS,
)
from backend.services.bonds.bond_central_ratings_sync import BondCentralRatingsSync
from backend.services.data.bonds.bond_central import BondCentralFetchError


def _row(isin: str = "IN0000000001") -> BondCentralRawRating:
    return BondCentralRawRating(
        isin=isin, credit_rating="AAA", credit_rating_agency_name="CARE"
    )


def _http500(page: int, body: str = "Internal Server Error"):
    return BondCentralFetchError(
        f"HTTP 500 for page {page}", status_code=500, body_excerpt=body
    )


class _FakeIndex:
    def __init__(self) -> None:
        self.meta: dict = {"stale": True, "status": "ok"}
        self.snapshots_replaced = 0
        self.match_stats_calls: list = []

    def metadata(self) -> dict:
        meta = dict(self.meta)
        # The real index computes indexed_isins from the committed snapshot;
        # mirror that so tests can assert the snapshot-derived value.
        meta["indexed_isins"] = len(getattr(self, "_isin_statuses", {}))
        return meta

    def update_metadata(self, **values) -> None:
        for key, value in values.items():
            if value is None:
                self.meta.pop(key, None)
            else:
                self.meta[key] = value

    def replace_snapshot(self, ratings_by_isin, statuses, metadata=None) -> None:
        self.snapshots_replaced += 1
        self._isin_statuses = dict(statuses)
        for key, value in dict(metadata or {}).items():
            if value is None:
                self.meta.pop(key, None)
            else:
                self.meta[key] = value

    def record_match_stats(self, total, matched) -> None:
        # Mirrors the real index (persists into meta) and records every
        # call so tests can prove the refresh never writes 0/0 when the
        # CDSL universe is unavailable.
        self.match_stats_calls.append((total, matched))
        self.meta[META_CDSL_ISINS_TOTAL] = total
        self.meta[META_CDSL_ISINS_MATCHED] = matched


class _FauxCdslIndex(_FakeIndex):
    def __init__(self, cdsl_isins):
        super().__init__()
        self.cdsl_isins = set(cdsl_isins)
        self._isin_statuses: dict[str, str] = {}

    def current_isin_status(self, isin):
        return self._isin_statuses.get(isin)

def _make_sync(client) -> BondCentralRatingsSync:
    settings = SimpleNamespace(
        bond_central_ratings_ttl_seconds=86400,
        bond_central_ratings_page_delay_seconds=0.0,
        bond_central_ratings_max_retries=3,
        bond_central_ratings_auto_refresh=False,
    )
    return BondCentralRatingsSync(
        settings=settings, index=_FakeIndex(), client=client
    )


def _make_sync_with_cdsl(client, cdsl_isins):
    settings = SimpleNamespace(
        bond_central_ratings_ttl_seconds=86400,
        bond_central_ratings_page_delay_seconds=0.0,
        bond_central_ratings_max_retries=3,
        bond_central_ratings_auto_refresh=False,
    )
    return BondCentralRatingsSync(
        settings=settings, index=_FauxCdslIndex(cdsl_isins), client=client
    )


def test_transient_http500_recovers_with_2s_5s_backoff(monkeypatch):
    """Two HTTP 500s then success: 3 client calls, sleeps [2, 5]."""
    calls = {"n": 0}
    sleeps: list = []

    class Client:
        async def fetch_securities_page(self, page, size):
            calls["n"] += 1
            if calls["n"] <= 2:
                raise _http500(page)
            return [_row()], {"total_pages": 1, "has_next": False}

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr(sync_module.asyncio, "sleep", fake_sleep)
    sync = _make_sync(Client())

    rows, _ = asyncio.run(sync._fetch_page_with_retry(19))

    assert len(rows) == 1
    assert calls["n"] == 3
    assert sleeps == [2.0, 5.0]


def test_persistent_http500_retried_three_times(monkeypatch):
    """Persistent HTTP 500 incl. full split recovery down to size=1."""
    calls: list = []
    sleeps: list = []

    class Client:
        async def fetch_securities_page(self, page, size):
            calls.append((page, size))
            raise _http500(page, body="boom")

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr(sync_module.asyncio, "sleep", fake_sleep)
    sync = _make_sync(Client())

    with pytest.raises(BondCentralFetchError) as excinfo:
        asyncio.run(sync._fetch_page_with_retry(42))

    assert "unrecoverable after split" in str(excinfo.value)
    # 4 at size=100 (initial + 3 retries), 2 halves x 4 at size=50,
    # 4 quarters x 4 at size=25, then each of the 4 failing quarters is
    # narrowed to 25 size=1 single-record probes (every record tried once).
    assert len(calls) == 4 + 8 + 16 + 100
    assert [c for c in calls if c[1] == 100] == [(42, 100)] * 4
    assert sleeps == [2.0, 5.0, 10.0] * 7


def test_normal_100_page_unchanged(monkeypatch):
    """Healthy size=100 page: single client call, no splitting."""
    calls: list = []

    class Client:
        async def fetch_securities_page(self, page, size):
            calls.append((page, size))
            return [_row()], {"total_pages": 1, "has_next": False}

    async def fake_sleep(delay: float) -> None:
        raise AssertionError("no retries expected")

    monkeypatch.setattr(sync_module.asyncio, "sleep", fake_sleep)
    sync = _make_sync(Client())

    rows, info = asyncio.run(sync._fetch_page_with_retry(19))

    assert len(rows) == 1
    assert calls == [(19, 100)]
    assert info["total_pages"] == 1


def test_split_halves_recover_full_window(monkeypatch):
    """size=100 500s, both size=50 halves succeed: 100 rows in order."""
    calls: list = []

    def _window_rows(page: int, size: int):
        base = (page - 1) * size
        return [_row(f"IN{base + i:010d}") for i in range(size)]

    class Client:
        async def fetch_securities_page(self, page, size):
            calls.append((page, size))
            if size == 100:
                raise _http500(page)
            assert size == 50
            return _window_rows(page, size), {"total_pages": 256}

    async def fake_sleep(delay: float) -> None:
        pass

    monkeypatch.setattr(sync_module.asyncio, "sleep", fake_sleep)
    sync = _make_sync(Client())

    rows, info = asyncio.run(sync._fetch_page_with_retry(19))

    assert len([c for c in calls if c[1] == 100]) == 4
    assert (37, 50) in calls and (38, 50) in calls
    assert len(rows) == 100
    assert rows[0].isin == "IN0000001800"
    assert rows[49].isin == "IN0000001849"
    assert rows[50].isin == "IN0000001850"
    assert rows[99].isin == "IN0000001899"
    assert info["total_pages"] == 256


def test_split_quarters_recover_failed_half(monkeypatch):
    """size=100 500s, one size=50 half 500s, quarters succeed: 100 rows."""
    calls: list = []

    def _window_rows(page: int, size: int):
        base = (page - 1) * size
        return [_row(f"IN{base + i:010d}") for i in range(size)]

    class Client:
        async def fetch_securities_page(self, page, size):
            calls.append((page, size))
            if size == 100:
                raise _http500(page)
            if size == 50 and page == 38:
                raise _http500(page, body="half poisoned")
            assert size in (50, 25)
            return _window_rows(page, size), {"total_pages": 256}

    async def fake_sleep(delay: float) -> None:
        pass

    monkeypatch.setattr(sync_module.asyncio, "sleep", fake_sleep)
    sync = _make_sync(Client())

    rows, _ = asyncio.run(sync._fetch_page_with_retry(19))

    assert len(rows) == 100
    assert rows[0].isin == "IN0000001800"
    assert rows[-1].isin == "IN0000001899"
    quarter_pages = {page for page, size in calls if size == 25}
    assert quarter_pages == {75, 76}


def test_failed_quarter_narrowed_to_size1_with_diagnostics(monkeypatch, caplog):
    """Failing size=25 quarter narrows to size=1: only poison records lost."""
    POISON = {1879, 1880, 1885}

    class Client:
        async def fetch_securities_page(self, page, size):
            if size == 100:
                raise _http500(page)
            if size == 50 and page == 38:
                raise _http500(page, body="half poisoned")
            if size == 25 and page == 76:
                raise _http500(page, body="quarter poisoned")
            base = (page - 1) * size
            offsets = [base + i for i in range(size)]
            hit = next((off for off in offsets if off in POISON), None)
            if hit is not None:
                raise _http500(page, body=f"poison offset {hit}")
            return (
                [_row(f"IN{off:010d}") for off in offsets],
                {"total_pages": 256},
            )

    async def fake_sleep(delay: float) -> None:
        pass

    monkeypatch.setattr(sync_module.asyncio, "sleep", fake_sleep)
    sync = _make_sync(Client())

    with caplog.at_level("WARNING"):
        rows, info = asyncio.run(sync._fetch_page_with_retry(19))

    # 50 (half 37) + 25 (quarter 75) + 22 of 25 size=1 probes (quarter 76
    # lost only offsets 1879/1880/1885).
    assert len(rows) == 97
    assert "_recovery_warnings" in info
    detail = str(info["_recovery_warnings"])
    assert "page 19" in detail and "size=1" in detail
    assert "offset=1879" in detail and "offset=1880" in detail
    assert "offset=1885" in detail
    assert "500" in detail and "poison offset" in detail
    warnings = [r.getMessage() for r in caplog.records if r.levelname == "WARNING"]
    assert any("offset=1879" in m and "500" in m for m in warnings)


def test_refresh_processes_recovered_records(monkeypatch):
    """Fully recovered window flows into a complete snapshot (300 rows)."""

    def _window_rows(page: int, size: int):
        base = (page - 1) * size
        return [_row(f"IN{base + i:010d}") for i in range(size)]

    class Client:
        async def fetch_securities_page(self, page, size):
            if size == 100 and page == 2:
                raise _http500(page)
            if size == 100:
                info = (
                    {"total_pages": 3}
                    if page < 3
                    else {"total_pages": 3, "has_next": False}
                )
                return _window_rows(page, size), info
            assert size in (50, 25)
            return _window_rows(page, size), {"total_pages": 3}

    async def fake_sleep(delay: float) -> None:
        pass

    monkeypatch.setattr(sync_module.asyncio, "sleep", fake_sleep)
    sync = _make_sync(Client())
    meta = asyncio.run(sync.refresh(reason="test"))

    # Fully recovered window: no errors, complete snapshot, all rows counted.
    assert meta[META_STATUS] == "ok"
    assert meta[META_PAGES_FAILED] == 0
    assert meta[META_RECORDS_PROCESSED] == 300
    assert sync.index.snapshots_replaced == 1


def test_refresh_continues_and_keeps_snapshot(monkeypatch, caplog):
    """Page 2 fails at every size: all splits fail, snapshot kept."""
    sleeps: list = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr(sync_module.asyncio, "sleep", fake_sleep)

    class Client:
        def __init__(self) -> None:
            self.calls: list = []

        async def fetch_securities_page(self, page, size):
            self.calls.append((page, size))
            if size == 100 and page == 2:
                raise _http500(page, body="<html>server exploded</html>")
            if size == 50 and page in (3, 4):
                raise _http500(page, body="half poisoned")
            if size == 25 and page in (5, 6, 7, 8):
                raise _http500(page, body="quarter poisoned")
            if size == 1:
                off = page - 1
                if 100 <= off <= 199:  # every single record of page 2's window
                    raise _http500(
                        page, body="<html>single record poisoned</html>"
                    )
            info = (
                {"total_pages": 3}
                if page < 3
                else {"total_pages": 3, "has_next": False}
            )
            return [_row(f"IN000000000{page}")], info

    client = Client()
    sync = _make_sync(client)

    with caplog.at_level("WARNING"):
        meta = asyncio.run(sync.refresh(reason="test"))

    sizes = sorted({size for _, size in client.calls})
    assert 100 in sizes and 50 in sizes and 25 in sizes and 1 in sizes
    assert meta[META_STATUS] == "partial"
    assert meta[META_PAGES_FAILED] == 1
    assert "page 2" in str(meta.get("error"))
    assert "500" in str(meta.get("error"))
    assert sync.index.snapshots_replaced == 0
    warnings = [r.getMessage() for r in caplog.records if r.levelname == "WARNING"]
    assert any(
        "page 2" in m and "500" in m for m in warnings
    )


def test_refresh_interrupted_sweep_does_not_replace_snapshot(monkeypatch):
    """Unexpected failure mid-sweep: no snapshot replacement, error recorded."""
    sleeps: list = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr(sync_module.asyncio, "sleep", fake_sleep)

    class Client:
        async def fetch_securities_page(self, page, size):
            if page == 2:
                raise NotImplementedError("unexpected payload shape")
            # Page 1 succeeds, so a finally-commit would replace the snapshot.
            return [_row(f"IN{page:010d}")], {"total_pages": 3}

    sync = _make_sync(Client())

    with pytest.raises(NotImplementedError):
        asyncio.run(sync.refresh(reason="test"))

    # An interrupted sweep must never replace the snapshot...
    assert sync.index.snapshots_replaced == 0
    meta = sync.index.metadata()
    assert meta[META_STATUS] == "error"
    assert "interrupted" in str(meta.get("error"))
    assert "NotImplementedError" in str(meta.get("error"))
    assert meta.get(META_LAST_SUCCESS) is None


def test_refresh_commits_snapshot_when_sweep_completed_with_known_missing(monkeypatch):
    """Completed sweep missing non-CDSL records: snapshot committed, partial."""
    sleeps: list = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr(sync_module.asyncio, "sleep", fake_sleep)

    POISON = {1879, 1880, 1885}

    class Client:
        async def fetch_securities_page(self, page, size):
            if size == 100 and page == 19:
                raise _http500(page, body="block of 100")
            if size in (50, 25):
                raise _http500(page, body="all subwindows failed")
            base = (page - 1) * size
            offsets = [base + i for i in range(size)]
            hit = next((off for off in offsets if off in POISON), None)
            if hit is not None:
                raise _http500(page, body=f"poison offset {hit}")
            return (
                [_row(f"IN{off:010d}") for off in offsets],
                {"total_pages": 256},
            )

    sync = _make_sync(Client())
    meta = asyncio.run(sync.refresh(reason="test"))

    # Completed sweep (pages_failed == 0) with 3 known missing records
    # (none of them a CDSL ISIN): the snapshot IS replaced, status partial.
    assert meta[META_STATUS] == "partial"
    assert sync.index.snapshots_replaced == 1
    assert meta[META_PAGES_FAILED] == 0
    assert meta[META_RECORDS_PROCESSED] == 25597  # 25600 - 3 missing
    assert meta[META_SECURITIES_INDEXED] == 25597
    assert meta[META_RATINGS_STORED] == 25597
    assert meta["indexed_isins"] == 25597
    assert meta.get(META_LAST_SUCCESS)
    assert "offset=1879" in str(meta.get("error"))


def test_refresh_ok_when_every_record_retrieved(monkeypatch):
    """Fully successful sweep: status ok, snapshot committed, last_success set."""
    sleeps: list = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr(sync_module.asyncio, "sleep", fake_sleep)

    class Client:
        async def fetch_securities_page(self, page, size):
            base = (page - 1) * size
            rows = [_row(f"IN{base + i:010d}") for i in range(size)]
            info = {"total_pages": 3}
            if page >= 3:
                info["has_next"] = False
            return rows, info

    sync = _make_sync(Client())
    meta = asyncio.run(sync.refresh(reason="test"))

    assert meta[META_STATUS] == "ok"
    assert meta.get("error") is None
    assert meta[META_PAGES_FAILED] == 0
    assert meta[META_RECORDS_PROCESSED] == 300
    assert meta[META_SECURITIES_INDEXED] == 300
    assert meta[META_RATINGS_STORED] == 300
    assert meta["indexed_isins"] == 300
    assert meta.get(META_LAST_SUCCESS)
    assert sync.index.snapshots_replaced == 1


def test_refresh_partial_when_unretrievable_cdsl_isin(monkeypatch):
    """Missing CDSL ISIN on a completed sweep: partial, committed, unmatched."""
    CDSL_POISON = "INE859C07220"  # offset 1879 (inside page 19's window)
    CDSL_HEALTHY = "INE001A01036"  # offset 100 (fetched with page 2)

    async def fake_sleep(delay: float) -> None:
        pass

    monkeypatch.setattr(sync_module.asyncio, "sleep", fake_sleep)

    def _isin_at(off: int) -> str:
        if off == 1879:
            return CDSL_POISON
        if off == 100:
            return CDSL_HEALTHY
        return f"IN{off:010d}"

    class Client:
        async def fetch_securities_page(self, page, size):
            if size == 100 and page == 19:
                raise _http500(page, body="block of 100")
            if size in (50, 25):
                raise _http500(page, body="all subwindows failed")
            base = (page - 1) * size
            offsets = [base + i for i in range(size)]
            if 1879 in offsets:
                raise _http500(page, body="poison offset 1879")
            return (
                [_row(_isin_at(off)) for off in offsets],
                {"total_pages": 256},
            )

    sync = _make_sync_with_cdsl(Client(), {CDSL_POISON, CDSL_HEALTHY})
    meta = asyncio.run(sync.refresh(reason="test"))

    assert meta[META_STATUS] == "partial"
    assert sync.index.snapshots_replaced == 1
    assert meta[META_PAGES_FAILED] == 0
    assert meta[META_RECORDS_PROCESSED] == 25599  # 25600 - 1 missing
    # Match stats are computed against the resulting index: the healthy
    # CDSL ISIN matches, the unretrievable one cannot.
    assert meta[META_CDSL_ISINS_TOTAL] == 2
    assert meta[META_CDSL_ISINS_MATCHED] == 1
    assert sync.index.current_isin_status(CDSL_POISON) is None
    assert sync.index.current_isin_status(CDSL_HEALTHY) is not None
    assert "offset=1879" in str(meta.get("error"))
    assert meta.get(META_LAST_SUCCESS)


def test_refresh_keeps_existing_cdsl_match_stats_when_universe_unavailable():
    """No cdsl_isins on the index: refresh must not overwrite 934/284.

    Production BondCentralRatingsIndex exposes no cdsl_isins attribute, so
    the refresh cannot compute CDSL match stats. Previously it persisted
    (0, 0), clobbering the valid values written by the bond-service join.
    The stats must instead survive the refresh untouched.
    """

    class Client:
        async def fetch_securities_page(self, page, size):
            base = (page - 1) * size
            rows = [_row(f"IN{base + i:010d}") for i in range(size)]
            return rows, {"total_pages": 1, "has_next": False}

    # _make_sync uses _FakeIndex: no cdsl_isins attribute, same as prod.
    sync = _make_sync(Client())
    sync.index.meta[META_CDSL_ISINS_TOTAL] = 934
    sync.index.meta[META_CDSL_ISINS_MATCHED] = 284

    meta = asyncio.run(sync.refresh(reason="test"))

    # The snapshot committed, but the existing CDSL match statistics
    # survived and record_match_stats was never called with (0, 0).
    assert sync.index.snapshots_replaced == 1
    assert meta[META_STATUS] == "ok"
    assert meta[META_CDSL_ISINS_TOTAL] == 934
    assert meta[META_CDSL_ISINS_MATCHED] == 284
    assert sync.index.match_stats_calls == []


def test_refresh_persists_cdsl_match_stats_when_universe_available():
    """With a CDSL universe available, freshly computed stats persist."""

    class Client:
        async def fetch_securities_page(self, page, size):
            base = (page - 1) * size
            rows = [_row(f"IN{base + i:010d}") for i in range(size)]
            return rows, {"total_pages": 1, "has_next": False}

    # One universe ISIN is in the swept index (IN0000000000), one is not.
    cdsl_isins = {"IN0000000000", "INE999A01234"}
    sync = _make_sync_with_cdsl(Client(), cdsl_isins)
    sync.index.meta[META_CDSL_ISINS_TOTAL] = 934
    sync.index.meta[META_CDSL_ISINS_MATCHED] = 284

    meta = asyncio.run(sync.refresh(reason="test"))

    # Previously persisted values are replaced with the computed ones.
    assert meta[META_CDSL_ISINS_TOTAL] == 2
    assert meta[META_CDSL_ISINS_MATCHED] == 1
    assert sync.index.match_stats_calls == [(2, 1)]

