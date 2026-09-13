"""Centralized AMFI AMC disclosure-directory discovery layer.

The AMFI Portfolio Disclosure page
(https://www.amfiindia.com/online-center/portfolio-disclosure) is a
server-rendered Next.js page whose RSC payload embeds a ``members`` array
with AMC metadata, including ``mf_id``, ``mf_name``, ``amc_name`` and the
per-frequency disclosure URLs::

    amc_fortnightly_portfolio_disclosure
    amc_monthly_portfolio_disclosure
    amc_halfYearly_portfolio_disclosure

This module fetches that page, extracts the ``members`` data robustly
from the Next.js/RSC response (no hardcoded AMC URLs), and resolves the
disclosure URL (preferably monthly) for a given ``mf_id``.

It is discovery-only: it is NOT wired into ``/stock-overlap`` yet and
changes no existing behavior.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

import httpx

from backend.config.settings import Settings
from backend.utils.logging import logger

AMFI_PORTFOLIO_DISCLOSURE_URL = (
    "https://www.amfiindia.com/online-center/portfolio-disclosure"
)

#: Preferred lookup order: monthly first, then fortnightly/half-yearly.
DISCLOSURE_URL_FIELDS = (
    "amc_monthly_portfolio_disclosure",
    "amc_fortnightly_portfolio_disclosure",
    "amc_halfYearly_portfolio_disclosure",
)

_MEMBER_RE = re.compile(
    r'\\+"mf_id\\+":\\+"(?P<mf_id>[^"\\]+)\\+".*?'
    r'\\+"mf_name\\+":\\+"(?P<mf_name>(?:[^"\\]|\\+.)*?)\\+".*?'
    r'\\+"amc_name\\+":\\+"(?P<amc_name>(?:[^"\\]|\\+.)*?)\\+".*?'
    r'\\+"amc_fortnightly_portfolio_disclosure\\+":\\+"'
    r'(?P<fortnightly>(?:[^"\\]|\\+.)*?)\\+".*?'
    r'\\+"amc_monthly_portfolio_disclosure\\+":\\+"'
    r'(?P<monthly>(?:[^"\\]|\\+.)*?)\\+".*?'
    r'\\+"amc_halfYearly_portfolio_disclosure\\+":\\+"'
    r'(?P<halfyearly>(?:[^"\\]|\\+.)*?)\\"',
    re.DOTALL,
)

_ESCAPE_RE = re.compile(r"\\+(.)", re.DOTALL)


def _unescape_rsc_string(value: str) -> str:
    """Reduce RSC backslash-escape runs (``\\\\\"`` -> ``\"``, etc.)."""
    previous = None
    current = value
    while previous != current:
        previous = current
        current = _ESCAPE_RE.sub(r"\1", current)
    try:
        return json.loads(f'"{current}"')
    except (ValueError, TypeError):
        return current


@dataclass
class AmcDisclosureEntry:
    """One AMC's disclosure metadata from the AMFI directory page."""

    mf_id: str
    mf_name: str = ""
    amc_name: str = ""
    fortnightly_url: str = ""
    monthly_url: str = ""
    half_yearly_url: str = ""
    raw: dict[str, Any] | None = None

    def preferred_url(self) -> str:
        """Monthly URL first, then fortnightly, then half-yearly."""
        for url in (self.monthly_url, self.fortnightly_url,
                    self.half_yearly_url):
            if url:
                return url
        return ""


class AmfiDirectoryError(Exception):
    """AMFI disclosure-directory fetch/parse failure."""


def extract_members_from_html(html: str) -> list[dict[str, Any]]:
    """Extract the ``members`` array from the RSC page HTML.

    The payload is double-escaped inside ``self.__next_f.push(...)``
    string literals, so plain ``json.loads`` of the page is not possible.
    Members are matched field-by-field with tolerance for extra fields
    between the known keys; each captured value is unescaped. Raises
    :class:`AmfiDirectoryError` when no member can be extracted.
    """
    members: list[dict[str, Any]] = []
    for match in _MEMBER_RE.finditer(html or ""):
        members.append({
            "mf_id": _unescape_rsc_string(match.group("mf_id")),
            "mf_name": _unescape_rsc_string(match.group("mf_name")),
            "amc_name": _unescape_rsc_string(match.group("amc_name")),
            "amc_fortnightly_portfolio_disclosure": _unescape_rsc_string(
                match.group("fortnightly")),
            "amc_monthly_portfolio_disclosure": _unescape_rsc_string(
                match.group("monthly")),
            "amc_halfYearly_portfolio_disclosure": _unescape_rsc_string(
                match.group("halfyearly")),
        })
    if not members:
        raise AmfiDirectoryError(
            "No AMC members found in AMFI portfolio-disclosure page")
    return members


def build_directory(
    members: Sequence[Mapping[str, Any]],
) -> dict[str, AmcDisclosureEntry]:
    """Index extracted members by ``mf_id`` (first entry wins)."""
    directory: dict[str, AmcDisclosureEntry] = {}
    for member in members:
        mf_id = str(member.get("mf_id") or "").strip()
        if not mf_id or mf_id in directory:
            continue
        directory[mf_id] = AmcDisclosureEntry(
            mf_id=mf_id,
            mf_name=str(member.get("mf_name") or ""),
            amc_name=str(member.get("amc_name") or ""),
            fortnightly_url=str(
                member.get("amc_fortnightly_portfolio_disclosure") or ""),
            monthly_url=str(
                member.get("amc_monthly_portfolio_disclosure") or ""),
            half_yearly_url=str(
                member.get("amc_halfYearly_portfolio_disclosure") or ""),
            raw=dict(member),
        )
    return directory


def resolve_disclosure_url(
    directory: Mapping[str, AmcDisclosureEntry],
    mf_id: str | int,
) -> str:
    """Return the preferred (monthly-first) disclosure URL for ``mf_id``."""
    entry = directory.get(str(mf_id).strip())
    if entry is None:
        raise AmfiDirectoryError(f"Unknown mf_id: {mf_id!r}")
    url = entry.preferred_url()
    if not url:
        raise AmfiDirectoryError(f"No disclosure URL for mf_id: {mf_id!r}")
    return url


class AmfiPortfolioDirectory:
    """Fetch + query the AMFI AMC disclosure directory (discovery only)."""

    def __init__(
        self,
        page_url: str = AMFI_PORTFOLIO_DISCLOSURE_URL,
        timeout: float = 30.0,
        settings: Settings | None = None,
    ) -> None:
        self.page_url = page_url
        self.timeout = timeout
        self.settings = settings
        self._cache: dict[str, AmcDisclosureEntry] = {}

    async def fetch_members(
        self, client: httpx.AsyncClient | None = None,
    ) -> list[dict[str, Any]]:
        """GET the directory page and extract members (not cached)."""
        logger.info("Fetching AMFI portfolio-disclosure directory")
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            if client is not None:
                response = await client.get(
                    self.page_url, headers=headers, timeout=self.timeout)
            else:
                async with httpx.AsyncClient(
                        follow_redirects=True) as http_client:
                    response = await http_client.get(
                        self.page_url, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            html = response.text
        except Exception as exc:
            raise AmfiDirectoryError(
                f"AMFI directory page fetch failed: {exc}") from exc
        return extract_members_from_html(html)

    async def get_directory(
        self, client: httpx.AsyncClient | None = None,
        refresh: bool = False,
    ) -> dict[str, AmcDisclosureEntry]:
        """Return the mf_id-indexed directory (cached in-process)."""
        if self._cache and not refresh:
            return self._cache
        self._cache = build_directory(await self.fetch_members(client))
        return self._cache

    async def get_disclosure_url(
        self, mf_id: str | int, client: httpx.AsyncClient | None = None,
    ) -> str:
        """Preferred disclosure URL for ``mf_id`` (monthly first)."""
        return resolve_disclosure_url(await self.get_directory(client),
                                      mf_id)

    def lookup_cached(self, mf_id: str | int) -> AmcDisclosureEntry | None:
        """Non-network lookup against the in-process cache, if loaded."""
        return self._cache.get(str(mf_id).strip())

