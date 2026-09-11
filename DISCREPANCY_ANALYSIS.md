# Analysis of Ranking vs Select Funds Discrepancy

## The Observation

**Ranking Page:**
- Category: Equity - Mid Cap
- Filter: First NAV Date < 2015-09-11
- Result: 17 of 34 funds match

**Select Funds Page:**
- Search: "mid cap"
- Filter: 10+ years
- Result: No matching funds

## Root Cause Analysis

### Code Path Differences

#### Ranking Endpoint (`POST /api/mutual-funds/rank`)
1. Uses `get_ranking_candidates_by_category("Equity - Mid Cap")` 
2. Returns **representative schemes only** (one per underlying fund family)
3. For 34 Mid Cap funds, there are 34 representative scheme codes
4. TigZig metadata enrichment happens for these 34 representatives
5. All 34 have valid `first_nav_date` from TigZig

#### Search Endpoint (`GET /api/mutual-funds/search?q=mid+cap`)
1. Text search matches "mid cap" against: scheme_name, amc, category, scheme_code
2. Returns **ALL schemes** where category contains "Mid Cap" - including:
   - Direct plans (e.g., scheme codes ending in different variants)
   - Regular plans  
   - Growth/Dividend options
   - Legacy/retired schemes
3. The actual count of "mid cap" matches is likely **much higher than 34**

### The Critical Issue: `first_nav_date` Availability

In `search_schemes()` (fetcher.py lines 394-402):

```python
first_nav_date = None
try:
    tigzig_meta = await get_tigzig_metadata().get_metadata()
    code_int = int(s.scheme_code)
    if code_int in tigzig_meta:
        first_nav_date = tigzig_meta[code_int].get("first_date")
except Exception:
    pass  # TigZig metadata unavailable; first_nav_date stays None
```

**The problem**: If a scheme code is NOT in TigZig metadata, or if `first_date` is missing for that scheme, `first_nav_date` remains `None`.

In the frontend filter (portfolio-select-funds/index.js lines 113-127):

```javascript
if (state.fundAge !== 'any') {
    var minYears = parseInt(state.fundAge);
    if (fund.first_nav_date) {  // <-- Only processes funds WITH first_nav_date
        // Parse and compare dates
    }
    // Funds WITHOUT first_nav_date are EXCLUDED from results
}
```

### Why 17 Funds Pass in Ranking but 0 in Select Funds

**Scenario A: Different scheme codes between the two APIs**

The 34 Mid Cap funds in Ranking use representative scheme codes. When you search "mid cap" on Select Funds, you get ALL schemes in that category, which may include:

1. **Additional variants** not in the 34 representatives (e.g., all plan/option combinations)
2. **Some variants may not have `first_nav_date`** in TigZig metadata

If even ONE fund in the search results lacks `first_nav_date`, and that fund would have passed the 10+ year filter, the search results will be incomplete.

**BUT** - the key issue is likely:

**Scenario B: The search returns schemes WITHOUT `first_nav_date` populated**

When searching "mid cap", the results include schemes where:
- `first_nav_date` is `null` because the scheme code isn't in TigZig metadata
- OR the scheme is a variant that TigZig doesn't have metadata for

The frontend filter **requires** `first_nav_date` to be present. If the 17 funds that pass the Ranking filter have `first_nav_date` populated, but the search results for those same funds show `first_nav_date: null`, they won't pass the frontend filter.

### Verification Steps Needed

To confirm the exact cause, you would need to:

1. **Call the search API directly**: `GET /api/mutual-funds/search?q=mid+cap&limit=5000`
2. **Check how many results have `first_nav_date` populated**
3. **Compare the scheme codes** between:
   - The 34 Ranking funds (representatives)
   - The search results for "mid cap"
4. **Check if the 17 passing funds from Ranking appear in search results** and whether they have `first_nav_date`

### Most Likely Root Cause

Based on code analysis:

**The search endpoint returns ALL scheme variants, but `first_nav_date` is only populated for schemes that exist in the TigZig metadata snapshot.** 

The Ranking endpoint works because:
1. It uses representative scheme codes that ARE in TigZig metadata
2. It enriches AFTER selecting representatives

The Select Funds search fails because:
1. It returns all matching schemes (potentially 50+ for "mid cap")
2. Some of those schemes may not have `first_nav_date` in TigZig
3. The frontend filter excludes any fund without `first_nav_date`
4. Even if the 17 qualifying funds ARE in the search results, if their `first_nav_date` is `null`, they're filtered out

### Specific Technical Issue

Looking at the TigZig metadata parsing (tigzig.py lines 613-614):

```python
if entry.get("aaum_cr_quarterly_avg") is not None or entry.get("first_date"):
    metadata[code] = entry
```

A scheme is ONLY added to the metadata dictionary if it has EITHER `aaum_cr_quarterly_avg` OR `first_date`. 

**If a scheme has neither, it won't be in the metadata at all**, and `search_schemes()` will set `first_nav_date = None` for that scheme.

## Conclusion

The discrepancy is caused by:

1. **Search returns a superset of schemes** (all variants) compared to Ranking (representatives only)
2. **Some schemes in the search results lack `first_nav_date`** in TigZig metadata
3. **The frontend filter requires `first_nav_date`** to be present to apply age filtering
4. **Funds without `first_nav_date` are silently excluded** from the filtered results

The 17 funds that pass the Ranking filter DO have `first_nav_date`, but they may not appear in the Select Funds search results with that field populated, OR there may be other funds in the search results that don't have `first_nav_date` and the filtering logic behaves unexpectedly.

To debug further, examine the actual API response from `GET /api/mutual-funds/search?q=mid+cap` and check which results have `first_nav_date: null`.
