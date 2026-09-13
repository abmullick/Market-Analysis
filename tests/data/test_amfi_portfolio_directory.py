"""Focused tests for the AMFI disclosure-directory layer (mocked HTML)."""
import pytest

from backend.services.data.amfi_portfolio_directory import (
    AmfiDirectoryError,
    AmfiPortfolioDirectory,
    build_directory,
    extract_members_from_html,
    resolve_disclosure_url,
)


def _member(mf_id, mf_name, amc_name, monthly, fortnightly="", half="",
            esc='\\"'):
    # Mimic the RSC string payload exactly as served in the real AMFI page:
    # a single backslash before each inner quote (\"), with plain : , { }
    # delimiters.
    q = esc
    return (
        f"{q}mf_id{q}:{q}{mf_id}{q},{q}mf_name{q}:{q}{mf_name}{q},"
        f"{q}amc_name{q}:{q}{amc_name}{q},"
        f"{q}amc_fortnightly_portfolio_disclosure{q}:{q}{fortnightly}{q},"
        f"{q}amc_monthly_portfolio_disclosure{q}:{q}{monthly}{q},"
        f"{q}amc_halfYearly_portfolio_disclosure{q}:{q}{half}{q}"
    )


MOCK_HTML = (
    "<html><body><script>self.__next_f.push([1,"
    "\"members\":[{"
    + _member("3", "Aditya Birla Sun Life Mutual Fund",
              "Aditya Birla Sun Life AMC Limited",
              "https://mutualfund.adityabirlacapital.com/forms-and-downloads/portfolio",
              "https://mutualfund.adityabirlacapital.com/forms-and-downloads/portfolio",
              "https://mutualfund.adityabirlacapital.com/forms-and-downloads/portfolio")
    + "},{"
    + _member("46", "Bank of India Mutual Fund",
              "Bank of India Investment Managers Private Limited",
              "https://www.boimf.in/investor-corner#t2",
              "https://www.boimf.in/regulatory-reports",
              "https://www.boimf.in/regulatory-reports/financials")
    + "}]}]);</script></body></html>"
)


class TestExtractMembers:
    def test_two_members_extracted(self):
        members = extract_members_from_html(MOCK_HTML)
        assert len(members) == 2
        assert members[0]["mf_id"] == "3"
        assert members[0]["mf_name"] == "Aditya Birla Sun Life Mutual Fund"
        assert members[1]["mf_id"] == "46"

    def test_monthly_preferred(self):
        directory = build_directory(extract_members_from_html(MOCK_HTML))
        assert resolve_disclosure_url(directory, "3") == (
            "https://mutualfund.adityabirlacapital.com/"
            "forms-and-downloads/portfolio")
        assert resolve_disclosure_url(directory, 46) == (
            "https://www.boimf.in/investor-corner#t2")

    def test_monthly_empty_falls_back(self):
        members = extract_members_from_html(MOCK_HTML)
        members[1]["amc_monthly_portfolio_disclosure"] = ""
        directory = build_directory(members)
        assert resolve_disclosure_url(directory, "46") == (
            "https://www.boimf.in/regulatory-reports")

    def test_unknown_mf_id_raises(self):
        directory = build_directory(extract_members_from_html(MOCK_HTML))
        with pytest.raises(AmfiDirectoryError):
            resolve_disclosure_url(directory, "999")

    def test_no_members_raises(self):
        with pytest.raises(AmfiDirectoryError):
            extract_members_from_html("<html><body>no payload</body></html>")


class FakeResponse:
    def __init__(self, text):
        self.text = text

    def raise_for_status(self):
        return None


class FakeClient:
    def __init__(self, text):
        self.text = text
        self.calls = 0

    async def get(self, url, headers=None, timeout=None):
        self.calls += 1
        assert "portfolio-disclosure" in url
        return FakeResponse(self.text)


@pytest.mark.asyncio
async def test_service_uses_page_members():
    svc = AmfiPortfolioDirectory()
    fake = FakeClient(MOCK_HTML)
    assert await svc.get_disclosure_url("3", client=fake) == (
        "https://mutualfund.adityabirlacapital.com/"
        "forms-and-downloads/portfolio")
    assert fake.calls == 1
    # Second lookup served from the in-process cache (no extra fetch).
    assert await svc.get_disclosure_url(46, client=fake) == (
        "https://www.boimf.in/investor-corner#t2")
    assert fake.calls == 1
