from __future__ import annotations

import re
from pathlib import Path

import requests
from bs4 import BeautifulSoup


URL = "https://www.cdslindia.com/corporatebond/CorporateBondReports.aspx"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/153.0.0.0 Safari/537.36"
)

HEADERS = {
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
    "User-Agent": USER_AGENT,
}


# Cookies copied from the browser GET cURL you just captured.
# Diagnostic only — do not hard-code these into the application.
BROWSER_COOKIES = {
    "ADRUM_BTa": (
        "R:0|g:e24f0ad2-0d17-4858-9294-f5ec8edb04a6|"
        "n:customer1_112866c9-5b5a-4c8d-a36f-7bad42466a35"
    ),
    "SameSite": "None",
    "ADRUM_BT1": "R:0|i:93156|e:665",
}


def inspect_response(label: str, response: requests.Response) -> None:
    html = response.text
    soup = BeautifulSoup(html, "html.parser")

    viewstate = soup.find("input", {"name": "__VIEWSTATE"})
    viewstate_len = len(viewstate.get("value", "")) if viewstate else 0

    table = soup.select_one("table.tblSecDetails")
    rows = len(table.find_all("tr")) if table else 0

    isin_links = len(table.select("a")) if table else 0

    print()
    print("=" * 70)
    print(label)
    print("=" * 70)
    print("STATUS          :", response.status_code)
    print("FINAL URL       :", response.url)
    print("HTML BYTES      :", len(response.content))
    print("CONTENT-TYPE    :", response.headers.get("Content-Type"))
    print("VIEWSTATE LEN   :", viewstate_len)
    print("SEC TABLE       :", bool(table))
    print("TABLE ROWS      :", rows)
    print("ISIN LINKS      :", isin_links)

    output = Path(
        "cdsl_get_"
        + re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")
        + ".html"
    )
    output.write_text(html, encoding="utf-8")
    print("SAVED           :", output)


def main() -> None:
    print("CDSL GET diagnostic")
    print("URL:", URL)

    # ------------------------------------------------------------
    # TEST A: exact browser-style GET, no pre-existing cookies
    # ------------------------------------------------------------
    session_a = requests.Session()
    response_a = session_a.get(
        URL,
        headers=HEADERS,
        timeout=30,
        allow_redirects=True,
    )

    inspect_response(
        "A - browser-style GET WITHOUT browser cookies",
        response_a,
    )

    print("\nSESSION A COOKIES:", dict(session_a.cookies))

    # ------------------------------------------------------------
    # TEST B: same GET, but with the cookies from Chrome cURL
    # ------------------------------------------------------------
    session_b = requests.Session()
    session_b.cookies.update(BROWSER_COOKIES)

    response_b = session_b.get(
        URL,
        headers=HEADERS,
        timeout=30,
        allow_redirects=True,
    )

    inspect_response(
        "B - browser-style GET WITH captured browser cookies",
        response_b,
    )

    print("\nSESSION B COOKIES:", dict(session_b.cookies))


if __name__ == "__main__":
    main()
