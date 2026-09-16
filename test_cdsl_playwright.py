from __future__ import annotations

from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


URL = "https://www.cdslindia.com/corporatebond/CorporateBondReports.aspx"


def main() -> None:
    with sync_playwright() as p:
        print("Launching Chromium...")

        browser = p.chromium.launch(
            headless=True,
        )

        page = browser.new_page()

        print("Opening CDSL report page...")

        response = page.goto(
            URL,
            wait_until="domcontentloaded",
            timeout=60_000,
        )

        print("Initial response status:", response.status if response else None)
        print("Initial page URL      :", page.url)

        # ---------------------------------------------------------
        # Initial page diagnostics
        # ---------------------------------------------------------
        viewstate = page.locator(
            'input[name="__VIEWSTATE"]'
        ).input_value()

        rows_before = page.locator(
            "table.tblSecDetails tr"
        ).count()

        trade_date = page.locator(
            "#idtradedate"
        ).input_value()

        hidden_trade_date = page.locator(
            "#idhdndate"
        ).input_value()

        market_type = page.locator(
            "#markettype_select"
        ).input_value()

        filter_type = page.locator(
            "#filter_select"
        ).input_value()

        print("Initial ViewState     :", len(viewstate))
        print("Initial table rows    :", rows_before)
        print("Trade date            :", trade_date)
        print("Hidden trade date     :", hidden_trade_date)
        print("Market type           :", market_type)
        print("Filter                :", filter_type)

        # ---------------------------------------------------------
        # The page already defaults to:
        #
        #   Market type = B
        #   Filter      = A
        #
        # Keep those values.  In particular, search_text is hidden
        # when filter A ("For all") is selected, so DO NOT call
        # fill() on it.
        # ---------------------------------------------------------
        page.locator("#markettype_select").select_option("B")
        page.locator("#filter_select").select_option("A")

        print()
        print("Submitting CDSL Search...")

        # ---------------------------------------------------------
        # Click the actual HTML submit button.
        # Chromium will execute the page JavaScript and perform the
        # real ASP.NET form submission.
        # ---------------------------------------------------------
        try:
            with page.expect_navigation(
                wait_until="domcontentloaded",
                timeout=60_000,
            ):
                page.locator("#btnsearch").click()

        except PlaywrightTimeoutError:
            print(
                "Navigation event timed out; "
                "continuing to inspect the page..."
            )

        # Allow the resulting document to settle.
        page.wait_for_timeout(2_000)

        print()
        print("After Search")
        print("=" * 72)

        print("Current URL:", page.url)

        # ---------------------------------------------------------
        # Result diagnostics
        # ---------------------------------------------------------
        result_viewstate = page.locator(
            'input[name="__VIEWSTATE"]'
        ).input_value()

        table = page.locator(
            "table.tblSecDetails"
        )

        table_exists = table.count() > 0
        rows_after = table.locator("tr").count() if table_exists else 0
        isin_links = table.locator("a").count() if table_exists else 0

        print("Result ViewState      :", len(result_viewstate))
        print("Secondary table       :", table_exists)
        print("Secondary rows        :", rows_after)
        print("ISIN links            :", isin_links)

        body_text = page.locator("body").inner_text()

        print()
        print("Response checks:")
        print(
            "No secondary-market data:",
            "No Data Is Available For Secondary Market"
            in body_text,
        )
        print(
            "No primary-market data:",
            "No Data Is Available For Primary Market"
            in body_text,
        )

        # ---------------------------------------------------------
        # Save response HTML
        # ---------------------------------------------------------
        output = Path(
            "cdsl_playwright_response.html"
        )

        output.write_text(
            page.content(),
            encoding="utf-8",
        )

        print()
        print("Saved response:", output)

        # ---------------------------------------------------------
        # Print first few rows if data exists
        # ---------------------------------------------------------
        if table_exists and rows_after > 1:
            print()
            print("First 3 secondary-market rows:")

            rows = table.locator("tr")

            for i in range(min(4, rows.count())):
                text = rows.nth(i).inner_text(
                    separator=" | "
                ).strip()

                print(
                    f"ROW {i}: {text}"
                )

        browser.close()


if __name__ == "__main__":
    main()
