# Bond Analysis — Current Implementation

## Scope

Bond Analysis is an active product module for researching **government and corporate bonds**. The page is designed around source-backed bond terms, market observations, calculated yield/risk analytics, cash flows, and data-source status.

## Bond Universes

The selector keeps the two universes separate and lazy-loaded:

- **Government Bonds** — G-Secs, Treasury Bills (T-Bills), and State Development Loans (SDLs).
- **Corporate Bonds** — corporate securities sourced through the application's CDSL / Bond Central integrations and normalized into the common bond model.

Only the active universe is requested. The browser does not fabricate identifiers. A bond is identified by its published **ISIN** when available, otherwise by the backend-provided source-scoped `record_id`.

## Discovery, Search & Filters

The Bond Analysis selector supports:

- Search by security name, ISIN, or issuer.
- Government instrument-type filtering: G-Sec, SDL, T-Bill.
- Source filtering where applicable: CCIL, NSE, RBI.
- Sorting by Maturity Date, Market YTM, Clean Price, Coupon Rate, Security Name, or Instrument Type.
- Ascending/descending sort direction.
- Advanced Coupon Rate range filtering.
- Government/corporate maturity-date range filtering.
- Corporate Weighted Average Yield range filtering.
- Corporate Trade Date and Issuer filters.
- Corporate Credit Rating multi-select filtering.

Range and credit-rating filters are applied to the already retrieved active-universe results and do not require unnecessary requests for the inactive universe.

## Selection & Detail Workflow

Every bond with a usable published identity is selectable. Selecting a bond loads the corresponding detail view without inventing an identifier.

For government bonds, the detail workflow can use:

- `GET /api/bonds/{isin}`
- `GET /api/bonds/{isin}/market`
- `GET /api/bonds/{isin}/analytics`

For corporate bonds, the detail workflow uses the corporate detail and analytics endpoints. Records that have only a backend `record_id` use the record endpoint; ISIN-only analytics are not fabricated for those records.

## Bond Summary

The summary can expose identity, instrument type, issuer, maturity, coupon terms, face value, listing information, and headline market observations such as price and yield.

Government and corporate records use the same normalized bond model while retaining source-specific fields where supplied.

## Market Data

Market observations can contain:

- Clean Price and Dirty Price.
- Source-reported Yield to Maturity (Market YTM).
- Bid Price / Bid Yield.
- Offer Price / Offer Yield.
- Last Traded Price / Last Traded Yield.
- Traded Value, Traded Quantity, and Trade Count.
- Volume-weighted average price and yield for sources that publish them.
- Observation/trade date and time.
- Source, data type, as-of date, and freshness information.

The UI keeps source-reported Market YTM separate from the independently calculated YTM.

## Yield & Valuation Analytics

The analytics engine can provide:

- **Current Yield** — annual coupon relative to clean price.
- **Calculated YTM** — independently calculated yield to maturity based on the bond's terms and market price.
- **Market YTM** — source-reported yield retained separately for comparison/validation.
- **Accrued Interest** and accrued-interest days.
- Settlement date and relevant day-count convention.
- Coupon frequency and cash-flow assumptions.

A source-reported yield is never silently substituted for the calculated YTM, and vice versa.

## Duration, Convexity & DV01

The risk/sensitivity analytics include, where the required inputs are available:

- **Macaulay Duration** — weighted-average time to receive the bond's cash flows, in years.
- **Modified Duration** — approximate percentage price change for a 1% change in yield.
- **Convexity** — second-order sensitivity describing how duration changes as yield changes.
- **DV01** — approximate price/value change for a 0.01% (one basis point) yield move, per 100 of face value.

Unavailable analytics remain unavailable when the required data or calculation conditions are not satisfied.

## Cash Flows & Contract Terms

The detail view can expose the coupon schedule and redemption cash flows. Corporate detail can additionally contain:

- Coupon basis/type and interest period.
- Call and put options and dates.
- Redemption type, date, and premium information.
- Perpetual status.
- Secured/unsecured status and seniority where supplied.
- Credit rating, agency, rating status, outlook, and rating-action date.
- Issue size, outstanding amount, issue price, and issuance mode where supplied.
- Exchange/listing status.

## Corporate Credit Ratings

Corporate bonds support source-published credit-rating observations. Multiple rating agencies/actions are preserved rather than silently collapsing the history into a single invented value. The selector can filter by normalized rating categories, including an explicit Unknown state for missing ratings and a separate Unrated state where the source says so.

## Data Sources & Freshness

The bond layer normalizes multiple source feeds behind the bond service/model layer. The UI exposes source identity and source-health information rather than presenting an unsuccessful provider retrieval as a successful empty universe.

Market observations can be classified as traded, indicative, MTM, reference, auction, historical, or unknown depending on the source payload.

## Methodology & Conventions

Bond calculations are performed in the backend analytics service rather than duplicated in browser JavaScript. Day-count convention, coupon frequency, settlement date, maturity, price type, and accrued interest are treated as explicit inputs to the analytics engine where available.

Prices may be clean or dirty; the application keeps the two concepts separate when both are supplied. Yields are represented as percentages.

## Missing Data

The application does not invent a price, yield, rating, cash-flow event, duration, or other bond metric when the source does not provide enough information. Unsupported or unavailable analytics are shown as unavailable rather than being silently replaced with another metric.

## Architecture

```text
Bond Analysis UI
      ↓
FastAPI Bond Routes
      ↓
Bond Services / Analytics
      ↓
Normalized Bond Models
      ↓
CCIL / NSE / RBI / CDSL / Bond Central source integrations
```

Government and corporate universes are loaded independently, and the frontend only requests the active universe.

## Help & Methodology

The application's Help & Methodology page includes a dedicated Bond Analysis section covering the bond universes, selection workflow, filters, market price/yield terminology, calculated versus market YTM, duration, convexity, DV01, accrued interest, cash flows, corporate ratings, data freshness, and missing-data conventions.
