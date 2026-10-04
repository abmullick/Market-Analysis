# Recent Changes & Documentation Update — 4 October 2026

This document records the recent Stock Analysis and Stock Portfolio Builder changes that were added after the previous documentation synchronization.

## Stock Analysis

### 1. Historical analysis sections are now collapsible

The major historical-analysis areas are presented as consistent collapsible cards so long reports remain easier to navigate:

- Historical Growth & Return Trends.
- Company Pedigree & Trend Comparison.
- Earnings Quality, Capital Allocation & Dilution Comparison.

The presentation layer moves the existing chart grids into collapsible containers. It does not remove or recalculate the underlying charts.

### 2. Historical chart empty states are preserved in place

When a historical chart does not have sufficient usable observations, the application now keeps the intended chart/report area and presents a meaningful empty state instead of silently removing the chart. This preserves report structure and makes unavailable data distinguishable from a missing UI component.

### 3. Historical chart hover interaction was hardened

Stock historical chart tooltips were revised so mouse tracking works reliably without recursive Chart.js tooltip handling. The change is interaction-only; the underlying chart series and calculations are unchanged.

### 4. Stock comparison and analysis tables received a consistent visual treatment

Individual Stock Analysis and Compare tables were refined to improve hierarchy, spacing, headers and readability. These changes are presentation-only and do not introduce a blended comparison score or alter existing calculations.

### 5. Analysis loading feedback was added

Stock Analysis and ranking actions can show a non-invasive busy overlay while analysis is running. The overlay communicates progress without replacing the report or changing analytical results.

### 6. NSE symbol normalization was hardened

Stock API routes now normalize bare NSE symbols consistently before downstream processing. This improves reliability for symbol inputs while leaving the stock universe and analytical definitions unchanged.

## Stock Portfolio Builder

### 7. Portfolio analysis uses consistent collapsible-card presentation

Portfolio analysis sections follow the portfolio-builder interaction pattern with compact collapsed summaries and detailed content available on expansion.

### 8. Portfolio charts can be collapsed independently

Chart subcards allow individual visualisations to be hidden without removing their calculations or data. Existing Chart.js instances are resized when a previously hidden chart is displayed again.

### 9. Portfolio analysis has a blocking busy state

The Continue to Portfolio Analysis action now provides explicit busy feedback and prevents accidental repeated submissions while the analysis is being prepared.

### 10. Home-page action label is now live

The Stock Portfolio Builder home-page action changed from **Coming Soon** to **Build Portfolio**, reflecting that the feature is now available.

## Documentation updated

- `frontend/js/features/home/help-stock-portfolio.js` — expanded Help & Methodology with the recent Stock Analysis and Stock Portfolio Builder behaviour and interaction details.
- `STOCK_PORTFOLIO_BUILDER.md` — added the recent UI, loading-state, chart-card and chart-integrity documentation.
- `RECENT_CHANGES.md` — added as the consolidated recent-change record.

## Documentation deliberately not changed

The recent table polish, tooltip work, collapsible presentation and busy overlays do not change financial formulas, scoring, historical-period definitions or data methodology. The existing `README.md` and `STOCK_ANALYSIS.md` already describe the underlying analytical capabilities; the new details are documented here and in the in-application Help rather than duplicating large methodology sections unnecessarily.
