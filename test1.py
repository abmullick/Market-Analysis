from __future__ import annotations

from pathlib import Path

import requests
from bs4 import BeautifulSoup


URL = "https://www.cdslindia.com/corporatebond/CorporateBondReports.aspx"

HEADERS_GET = {
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,image/apng,*/*;q=0.8,"
        "application/signed-exchange;v=b3;q=0.7"
    ),
    "Accept-Language": "en-US,en;q=0.9,bn;q=0.8",
    "Cache-Control": "max-age=0",
    "Priority": "u=0, i",
    "Sec-CH-UA": '"Google Chrome";v="153", "Not_A Brand";v="8", "Chromium";v="153"',
    "Sec-CH-UA-Mobile": "?0",
    "Sec-CH-UA-Platform": '"Windows"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/153.0.0.0 Safari/537.36"
    ),
}

HEADERS_POST = {
    "Accept": HEADERS_GET["Accept"],
    "Accept-Language": HEADERS_GET["Accept-Language"],
    "Cache-Control": "max-age=0",
    "Content-Type": "application/x-www-form-urlencoded",
    "Origin": "https://www.cdslindia.com",
    "Priority": "u=0, i",
    "Referer": URL,
    "Sec-CH-UA": HEADERS_GET["Sec-CH-UA"],
    "Sec-CH-UA-Mobile": "?0",
    "Sec-CH-UA-Platform": '"Windows"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
    "User-Agent": HEADERS_GET["User-Agent"],
}


def hidden_fields(soup: BeautifulSoup) -> dict[str, str]:
    fields: dict[str, str] = {}

    for element in soup.select('input[type="hidden"]'):
        name = element.get("name")
        if name:
            fields[name] = element.get("value", "")

    return fields


def inspect(label: str, response: requests.Response) -> None:
    html = response.text
    soup = BeautifulSoup(html, "html.parser")

    viewstate = soup.select_one('input[name="__VIEWSTATE"]')
    validation = soup.select_one('input[name="__EVENTVALIDATION"]')
    generator = soup.select_one('input[name="__VIEWSTATEGENERATOR"]')

    table = soup.select_one("table.tblSecDetails")

    rows = len(table.select("tr")) if table else 0
    links = len(table.select("a")) if table else 0

    print()
    print("=" * 72)
    print(label)
    print("=" * 72)
    print("STATUS          :", response.status_code)
    print("FINAL URL       :", response.url)
    print("HTML BYTES      :", len(response.content))
    print("VIEWSTATE LEN   :", len(viewstate.get("value", "")) if viewstate else 0)
    print("GENERATOR LEN   :", len(generator.get("value", "")) if generator else 0)
    print("VALIDATION LEN  :", len(validation.get("value", "")) if validation else 0)
    print("SEC TABLE       :", bool(table))
    print("TABLE ROWS      :", rows)
    print("ISIN LINKS      :", links)

    if table:
        first_row = table.select_one("tr")
        if first_row:
            print("FIRST ROW TEXT  :", first_row.get_text(" | ", strip=True)[:500])

    Path("cdsl_search_response.html").write_text(
        html,
        encoding="utf-8",
    )

    print("SAVED           : cdsl_search_response.html")


def main() -> None:
    session = requests.Session()

    # ------------------------------------------------------------
    # 1. Fresh page GET
    # ------------------------------------------------------------
    print("1. GET fresh CDSL report page")

    response_get = session.get(
        URL,
        headers=HEADERS_GET,
        timeout=30,
        allow_redirects=True,
    )

    inspect("INITIAL GET", response_get)

    get_soup = BeautifulSoup(response_get.text, "html.parser")
    form = get_soup.select_one("form")

    if not form:
        raise RuntimeError("No HTML form found on CDSL report page.")

    state = hidden_fields(get_soup)

    print()
    print("HIDDEN FIELDS:")
    for key, value in state.items():
        if key.startswith("__"):
            print(f"  {key}: {len(value)} chars")

    # ------------------------------------------------------------
    # 2. Exact browser search parameters from the captured POST
    # ------------------------------------------------------------
    form_data = dict(state)

    form_data.update(
        {
            "customRadioInline1": "customRadioInline1",
            "idtradedate": "September 17, 2026",
            "idhdndate": "",
            "markettype_select": "B",
            "filter_select": "A",
            "search_text": "",
            "btnsearch": "Search",
            "otcidtradedate": "September 17, 2026",
            "otcidhdndate": "",
            "otc_filter_select": "A",
            "searchotc_text": "",
            "txtMaturityDate": "September 17, 2026",
        }
    )

    print()
    print("2. POST exact browser search parameters")
    print("   Trade date       : September 17, 2026")
    print("   idhdndate        : <empty>")
    print("   market type      : B")
    print("   filter           : A")
    print("   search_text      : <empty>")
    print("   btnsearch        : Search")

    response_post = session.post(
        URL,
        headers=HEADERS_POST,
        data=form_data,
        timeout=60,
        allow_redirects=True,
    )

    inspect("SEARCH POST", response_post)

    # ------------------------------------------------------------
    # 3. Response text diagnostics
    # ------------------------------------------------------------
    soup = BeautifulSoup(response_post.text, "html.parser")

    report_text = soup.get_text(" ", strip=True)

    print()
    print("3. RESPONSE CHECKS")
    print(
        "   'No Data Is Available For Secondary Market' :",
        "No Data Is Available For Secondary Market" in report_text,
    )
    print(
        "   'No Data Is Available For Primary Market'   :",
        "No Data Is Available For Primary Market" in report_text,
    )
    print(
        "   'Secondary Market Trade Data'              :",
        "Secondary Market Trade Data" in report_text,
    )
    print(
        "   'Primary Issuance Trade Data'              :",
        "Primary Issuance Trade Data" in report_text,
    )


if __name__ == "__main__":
    main()
