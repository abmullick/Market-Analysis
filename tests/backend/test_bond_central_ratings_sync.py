"""Focused tests for Bond Central ratings page retries and split recovery.

Regression context: pages 19, 42, 200, 209, 239 and 253 persistently
returned HTTP 500 server-side (poison records inside the 100-record
window). The sweep retries each failed page (up to 3 retries), then
splits a still-failing size=100 window into 2x size=50 (a failing half
into 2x size=25), keeps sweeping later pages, logs page number + HTTP
status + body excerpt, and never replaces the stored snapshot with
incomplete data.
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
    META_PAGES_FAILED,
    META_RECORDS_PROCESSED,
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

    def metadata(self) -> dict:
        return dict(self.meta)

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
    """Persistent HTTP 500 incl. split recovery: 4 + 8 + 16 calls."""
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
    # 1+3 at size=100, 2 halves x 4 at size=50, 4 quarters x 4 at size=25,
    # 2 quarters x 25 size=1 single-record probes.
    assert len(calls) == 4 + 8 + 16 + 50
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


def test_failed_quarter_skipped_with_diagnostic(monkeypatch, caplog):
    """One size=25 quarter fails: 75 rows kept, diagnostic recorded."""
    def _window_rows(page: int, size: int):
        base = (page - 1) * size
        return [_row(f"IN{base + i:010d}") for i in range(size)]

    class Client:
        async def fetch_securities_page(self, page, size):
            if size == 100:
                raise _http500(page)
            if size == 50 and page == 38:
                raise _http500(page, body="half poisoned")
            if size == 25 and page == 76:
                raise _http500(page, body="quarter poisoned")
            return _window_rows(page, size), {"total_pages": 256}

    async def fake_sleep(delay: float) -> None:
        pass

    monkeypatch.setattr(sync_module.asyncio, "sleep", fake_sleep)
    sync = _make_sync(Client())

    with caplog.at_level("WARNING"):
        rows, info = asyncio.run(sync._fetch_page_with_retry(19))

    assert len(rows) == 75
    assert "_recovery_warnings" in info
    detail = str(info["_recovery_warnings"])
    assert "page 19" in detail and "page 76" in detail
    assert "size=25" in detail and "offset=1875" in detail
    assert "500" in detail and "quarter poisoned" in detail
    warnings = [r.getMessage() for r in caplog.records if r.levelname == "WARNING"]
    assert any("page 76" in m and "quarter poisoned" in m for m in warnings)


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
    assert 100 in sizes and 50 in sizes and 25 in sizes
    assert meta[META_STATUS] == "partial"
    assert meta[META_PAGES_FAILED] == 1
    assert "page 2" in str(meta.get("error"))
    assert "500" in str(meta.get("error"))
    assert sync.index.snapshots_replaced == 0
    warnings = [r.getMessage() for r in caplog.records if r.levelname == "WARNING"]
    assert any(
        "page 2" in m and "500" in m for m in warnings
    )


def test_refresh_commits_when_sweep_completed_with_known_missing(monkeypatch):
    """Completed sweep with some missed non-CDSL records: snapshot committed, status partial."""
    sleeps: list = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr(sync_module.asyncio, "sleep", fake_sleep)

    class Client:
        async def fetch_securities_page(self, page, size):
            if page == 2:
                raise NotImplementedError
            return [], {"total_pages": 256, "has_next": False}

    client = Client()
    sync = _make_sync(client)
    meta = asyncio.run(sync.refresh(reason="test"))
    assert meta[META_STATUS] == "partial"
    assert sync.index.snapshots_replaced == 1
    assert meta[META_PAGES_FAILED] == 0


def test_refresh_commits_snapshot_when_sweep_completed_with_known_missing(monkeypatch):
    """Completed sweep with missed non-CDSL records: snapshot committed, status partial."""
    sleeps: list = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr(sync_module.asyncio, "sleep", fake_sleep)

    class Client:
        async def fetch_securities_page(self, page, size):
            if size == 100 and page == 2:
                raise _http500(page, body="block of 100")
            if size == 50 or size == 25:
                raise _http500(page, body="all subwindows failed")
            if size == 1:
                off = (page - 1) * 1
                if off in (1879, 1880, 1885):
                    raise _http500(page, body=f"poison offset {off}")
                return [_row(f"IN{off:010d}")], {"total_pages": 256}
            return [_row(f"IN{(page-1)*size + i:010d}") for i in range(size)], {"total_pages": 256}

    client = Client()
    sync = _make_sync(client)
    meta = asyncio.run(sync.refresh(reason="test"))
    assert meta[META_STATUS] == "partial"
    assert sync.index.snapshots_replaced == 1
    assert meta[META_PAGES_FAILED] == 0

