# Bond Analysis — Implementation & Parameter Reference

## 1. Purpose

Bond Analysis is the application's fixed-income research module for government and corporate bonds. It separates discovery of the two universes, exposes source-backed market observations, and presents backend-calculated yield and risk analytics without duplicating financial calculations in browser JavaScript.

## 2. Bond Universes

The page keeps the two universes separate and lazy-loaded:

### Government

- G-Secs
- Treasury Bills (T-Bills)
- State Development Loans (SDLs)

Government records may originate from CCIL, NSE and RBI-backed source flows depending on the observation.

### Corporate

Corporate securities are normalized through the application's CDSL / Bond Central source integrations. Corporate-specific enrichment includes market observations and credit-rating information where the sources provide them.

Only the active universe is requested. Selecting Government does not require loading the Corporate universe, and vice versa.

## 3. Bond Identity

The application never invents a bond identifier.

Identity priority is:

1. Published **ISIN**, when present.
2. Backend-provided source-scoped **record_id**, when an ISIN is not published.

Government records without an ISIN can therefore still be selected through their backend `record_id`. Corporate and government detail routes are selected from the identity and active universe.

## 4. Selector Controls

### 4.1 Search

The selector supports search by:

- Security name
- ISIN
- Issuer

### 4.2 Government instrument type

Government filtering supports:

- **G-Sec**
- **SDL**
- **T-Bill**

### 4.3 Source filter

Where supported by the source data, Government results can be refined by:

- **CCIL**
- **NSE**
- **RBI**

### 4.4 Sorting

The selector supports sorting by:

- Maturity Date
- Market YTM
- Clean Price
- Coupon Rate
- Security Name
- Instrument Type

Sort direction is independently selectable:

- Ascending
- Descending

### 4.5 Range filters

The implemented client-side range state is:

| Parameter | Meaning | Unit / type | Applies |
|---|---|---|---|
| `couponMin` | Minimum coupon rate | % | Government and applicable corporate records |
| `couponMax` | Maximum coupon rate | % | Government and applicable corporate records |
| `yieldMin` | Minimum weighted-average yield | % | Corporate |
| `yieldMax` | Maximum weighted-average yield | % | Corporate |
| `maturityFrom` | Earliest maturity date | ISO date | Active universe |
| `maturityTo` | Latest maturity date | ISO date | Active universe |

The default slider/range bounds currently represented in the selector are 0–20% for coupon and 0–20% for corporate weighted-average yield. Empty maturity boundaries mean no date restriction.

### 4.6 Corporate-only filters

Corporate filtering additionally supports:

- **Trade Date**
- **Issuer**
- **Credit Rating** multi-select

Trade Date and Issuer are mapped only to the corporate endpoint. They are not sent to the Government endpoint.

Credit ratings are normalized into canonical selection keys. Missing/NA-like values map to **Unknown**; an explicit **Unrated** value remains distinct from Unknown.

## 5. Result Row Parameters

A selectable bond result can display:

- Security Name
- ISIN, or Record ID when no ISIN is published
- Instrument Type
- Credit Rating, when supplied
- Issuer
- Maturity Date
- Headline YTM
- Market-data flag

The headline yield uses source `ytm` when available. For corporate rows it can fall back to `weighted_average_yield` when the source does not provide `ytm`.

Market flags include source-backed states such as:

- **Traded**
- **Indicative**
- **Stale Nd** when the backend reports a freshness age beyond the implemented threshold

The flag is descriptive of the supplied observation and is not an investment-quality ranking.

## 6. Bond Detail

The normalized detail model can expose the bond's identity and contract terms, including where supplied:

- Security name
- ISIN / Record ID
- Instrument type
- Issuer
- Maturity date
- Coupon rate
- Coupon frequency
- Coupon basis/type
- Face value
- Issue price
- Issue size
- Outstanding amount
- Redemption type
- Redemption date
- Redemption premium
- Perpetual status
- Secured / unsecured status
- Seniority
- Exchange/listing status
- Credit rating
- Rating agency
- Rating status
- Rating outlook
- Rating-action date
- Call option and call dates
- Put option and put dates

The application preserves source-specific fields where available instead of silently dropping them during normalization.

## 7. Market Observation Parameters

The market observation layer can expose:

| Parameter | Meaning |
|---|---|
| Clean Price | Price excluding accrued interest |
| Dirty Price | Price including accrued interest |
| Market YTM | Source-reported yield to maturity |
| Bid Price | Published bid price |
| Bid Yield | Published bid yield |
| Offer Price | Published offer price |
| Offer Yield | Published offer yield |
| Last Traded Price | Last traded price where supplied |
| Last Traded Yield | Last traded yield where supplied |
| Traded Value | Value of trades |
| Traded Quantity | Quantity traded |
| Trade Count | Number of trades |
| VWAP | Volume-weighted average price where supplied |
| Volume-weighted average yield | Volume-weighted average yield where supplied |
| Observation / Trade Date | Date of the market observation |
| Observation / Trade Time | Time of the observation where supplied |
| Source | Provider/source identity |
| Data Type | Observation classification such as traded or indicative |
| As-of Date | Source/data timestamp or effective date |
| Freshness | Age/status information supplied by the bond layer |

**Market YTM and Calculated YTM are separate fields.** A source-reported market yield is not silently replaced by the calculated result.

## 8. Yield and Accrued-Interest Analytics

The backend analytics engine can provide:

### Current Yield

Current Yield relates the annual coupon cash amount to the relevant clean market price. It is a price/yield observation rather than a full yield-to-maturity calculation.

### Calculated YTM

Calculated YTM is independently derived from the bond's contract terms, cash flows, price, settlement assumptions, coupon frequency and day-count convention where required inputs are available.

### Market YTM

Market YTM is the yield reported by the source/market observation. It is retained separately for comparison and validation.

### Accrued Interest

The analytics can expose:

- Accrued Interest amount
- Accrued-interest days
- Settlement date
- Clean price
- Dirty price

Clean and dirty prices are kept conceptually separate. Where the backend has enough information to derive one from the other, that calculation remains in the backend analytics layer.

## 9. Duration, Convexity and DV01

### Macaulay Duration

Weighted-average time to receive the bond's cash flows, expressed in years.

### Modified Duration

Approximate percentage price sensitivity to a 1% change in yield. It is a first-order price/yield sensitivity measure.

### Convexity

Second-order price/yield sensitivity. Convexity describes how the duration relationship changes as yield changes.

### DV01

Approximate price/value change for a **0.01% (one basis point)** yield move, normally expressed per 100 of face value in the application's analytics conventions.

These calculations are performed in the backend analytics service rather than duplicated in browser JavaScript.

## 10. Cash Flows

The detail view can expose the coupon and redemption cash-flow schedule used by the analytics. Contract terms may include coupon dates, coupon amount/frequency, redemption date and redemption amount/premium.

For callable/puttable corporate securities, call and put terms are preserved when supplied. A perpetual security is represented as perpetual rather than inventing a maturity date.

## 11. Corporate Credit Ratings

Corporate rating observations are source-published observations. The application can retain:

- Rating
- Rating agency
- Rating status
- Outlook
- Rating-action date

Multiple agency observations/actions are not silently collapsed into a single invented rating. Selector filtering can include standard ratings, **Unknown** for unavailable/missing rating data, and **Unrated** when the source explicitly says so.

## 12. Source and Freshness

The bond service normalizes multiple source feeds behind a common model. The UI can expose source identity and source-health information for configured providers.

Market observations may be classified as:

- Traded
- Indicative
- MTM
- Reference
- Auction
- Historical
- Unknown

These are data classifications, not quality scores.

## 13. Calculation Conventions

Bond analytics treat the following as explicit inputs whenever available:

- Settlement date
- Maturity date
- Coupon rate
- Coupon frequency
- Day-count convention
- Price type (clean/dirty)
- Accrued interest
- Contract cash flows
- Redemption terms

If the required inputs are unavailable or inconsistent, the application keeps the affected analytic unavailable rather than silently substituting another metric.

## 14. Missing Data

The application distinguishes missing data from a valid zero and does not fabricate:

- Price
- Yield
- Rating
- Cash-flow event
- Duration
- Convexity
- DV01
- Accrued interest
- Contract terms

A source-reported Market YTM is not used as a replacement for Calculated YTM merely because the latter is unavailable.

## 15. Detail Endpoint Model

Government bonds can use:

- `GET /api/bonds/{isin}`
- `GET /api/bonds/{isin}/market`
- `GET /api/bonds/{isin}/analytics`
- `GET /api/bonds/record/{record_id}` for source records without ISIN

Corporate bonds can use the corporate detail and analytics routes, including the ISIN-based corporate detail route and its analytics route where supported.

The frontend chooses the endpoint from the real identity returned by the backend. It never fabricates an ISIN to make a row selectable.

## 16. Architecture

```text
Bond Analysis UI
      ↓
FastAPI Bond Routes
      ↓
Bond Services / Analytics
      ↓
Normalized Bond Models
      ↓
CCIL / NSE / RBI / CDSL / Bond Central integrations
```

Government and Corporate universes remain independent at discovery time. Deterministic financial calculations remain in the backend analytics layer.

## 17. Help & Methodology

The in-application Help & Methodology page should document the same terminology as this file, including every selector control, search field, sort parameter, range filter, corporate filter, result-row field, market observation, contract term, calculated yield/risk metric, credit-rating field, source/freshness field, and missing-data convention.

This file is the repository-level implementation reference; the Help page is the user-facing explanation.
