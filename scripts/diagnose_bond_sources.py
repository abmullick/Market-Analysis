"""Opt-in live CCIL/NSE diagnostic; never imported by the unit-test suite.

Run: python scripts/diagnose_bond_sources.py
Uses the production HTTP clients, parsers and normalizers without retries or
endpoint substitution. JSON goes to stdout; provider logs go to stderr.
No cookies, authorization headers or response bodies are logged.
"""
from __future__ import annotations

import asyncio
import csv
import io
import json
import math
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.config.settings import Settings
from backend.models.bonds import DataType, DayCountConvention, InstrumentType
from backend.services.bonds import bond_normalizer as normalizer
from backend.services.data.bonds import ccil, nse
from backend.utils.logging import handler

SAMPLE_FIELDS = (
    "source", "data_type", "instrument_type", "isin", "security_name", "issuer",
    "maturity_date", "coupon_rate", "price", "clean_price", "dirty_price", "ytm",
)
SAFE_HEADERS = {"user-agent", "accept", "accept-language", "content-type"}


def present(value):
    return value is not None and str(value).strip().lower() not in {
        "", "-", "n/a", "na", "null", "none",
    }


class Capture:
    def __init__(self):
        self.requests = []
        self.responses = []

    async def request(self, request):
        self.requests.append({
            "url": str(request.url), "method": request.method,
            "headers": {k: v for k, v in request.headers.items() if k in SAFE_HEADERS},
            "payload": None if not request.content else "[body omitted]",
        })

    async def response(self, response):
        await response.aread()
        self.responses.append(response)
        self.requests[-1].update({
            "status": response.status_code,
            "content_type": response.headers.get("content-type"),
            "bytes": len(response.content),
        })

    async def attach(self, provider):
        client = await provider._get_client()
        client.event_hooks = {"request": [self.request], "response": [self.response]}


def audit(rows, parse_row, normalize, field_values, rejection_reason):
    counts = Counter(raw_records=len(rows))
    reasons, invalid_dates, invalid_numbers = Counter(), Counter(), Counter()
    classes, source_isins, normalized_isins = Counter(), Counter(), Counter()
    samples = {}
    for row in rows:
        fields = field_values(row)
        for key in ("isin", "maturity_date"):
            counts[f"raw_missing_{key}"] += not present(fields.get(key))
        if present(fields.get("isin")):
            source_isins[str(fields["isin"]).strip()] += 1
        for key, value in fields.items():
            if not present(value):
                if key in {"price", "yield_pct", "coupon_rate", "face_value", "lta", "tta"}:
                    counts["blank_numeric_fields"] += 1
                continue
            if key.endswith("date") and normalizer.parse_date(str(value)) is None:
                invalid_dates[f"{key}: {value}"] += 1
            if key in {"price", "yield_pct", "coupon_rate", "face_value", "lta", "tta"}:
                number = normalizer.parse_float(str(value))
                if number is None or not math.isfinite(number):
                    invalid_numbers[f"{key}: {value}"] += 1
        try:
            raw = parse_row(row)
            if raw is None:
                reasons[rejection_reason(row)] += 1
                continue
            counts["parsed_records"] += 1
            bond = normalize(raw)
            if bond is None:
                reasons["normalization: unsupported/non-government instrument or empty description"] += 1
                continue
            counts["normalized_records"] += 1
            counts["normalized_missing_isin"] += bond.isin is None
            counts["normalized_missing_maturity_date"] += bond.maturity_date is None
            for key, enum in (("data_type", DataType), ("instrument_type", InstrumentType),
                              ("day_count_convention", DayCountConvention)):
                counts["invalid_enum_classifications"] += not isinstance(getattr(bond, key), enum)
            classes[f"{bond.source}/{bond.instrument_type.value}/{bond.data_type.value}"] += 1
            if bond.isin:
                normalized_isins[bond.isin] += 1
            tags = [bond.instrument_type.value, bond.data_type.value]
            if bond.isin is None:
                tags.append("missing_isin")
            if bond.maturity_date is None:
                tags.append("missing_maturity")
            if bond.price is None:
                tags.append("missing_price")
            for tag in tags:
                samples.setdefault(tag, bond.model_dump(mode="json", include=set(SAMPLE_FIELDS)))
        except Exception as exc:
            reasons[f"parse/normalize exception: {type(exc).__name__}"] += 1
    for key in ("parsed_records", "normalized_records", "invalid_enum_classifications",
                "raw_missing_isin", "raw_missing_maturity_date", "normalized_missing_isin",
                "normalized_missing_maturity_date", "blank_numeric_fields"):
        counts.setdefault(key, 0)
    return {
        **counts, "rejected_records": sum(reasons.values()), "rejection_reasons": dict(reasons),
        "invalid_date_count": sum(invalid_dates.values()),
        "invalid_date_values": dict(invalid_dates),
        "invalid_numeric_count": sum(invalid_numbers.values()),
        "invalid_numeric_values": dict(invalid_numbers),
        "raw_duplicate_isin_count": sum(n - 1 for n in source_isins.values()),
        "normalized_duplicate_isin_count": sum(n - 1 for n in normalized_isins.values()),
        "classifications": dict(classes), "samples": samples,
    }


def ccil_fields(row, section):
    if not isinstance(row, dict):
        return {}
    return {
        "isin": row.get("isin"), "maturity_date": row.get("mrty_date"),
        "price": row.get("lty" if section in {"central", "state"} else "ltp"),
        "yield_pct": row.get("ltp" if section in {"central", "state"} else "lty"),
        "lta": row.get("lta"), "tta": row.get("tta"),
    }


async def diagnose_ccil(settings):
    provider, capture = ccil.CcilClient(settings), Capture()
    results = {}
    try:
        await capture.attach(provider)
        for section, fetch in (
            ("central", provider.fetch_central_market_watch),
            ("state", provider.fetch_state_market_watch),
            ("tbills", provider.fetch_tbill_market_watch),
        ):
            start = len(capture.requests)
            try:
                parsed = await fetch()
                wrapper = capture.responses[-1].json()
                rows = wrapper["result1"]
                if isinstance(rows, str):
                    rows = json.loads(rows)
                result = audit(
                    rows,
                    lambda row: ccil._row_to_record(row, section) if isinstance(row, dict) else None,
                    normalizer.normalize_ccil_record,
                    lambda row: ccil_fields(row, section),
                    lambda row: "non-object row" if not isinstance(row, dict) else "missing/short description",
                )
                result.update(structure={"wrapper_keys": list(wrapper), "result1": "list",
                                         "row_keys": list(rows[0]) if rows and isinstance(rows[0], dict) else []},
                              provider_parsed_records=len(parsed), status="validated")
                result["parser_count_matches"] = result["parsed_records"] == len(parsed)
            except Exception as exc:
                result = {"status": "retrieval_or_structure_failure", "error_type": type(exc).__name__,
                          "raw_records": None, "normalized_records": None}
            result["requests"] = capture.requests[start:]
            results[section] = result
    finally:
        await provider.close()
    return results


async def diagnose_nse(settings):
    provider, capture = nse.NseClient(settings), Capture()
    result = {"status": "retrieval_or_structure_failure", "raw_records": None,
              "normalized_records": None}
    try:
        await capture.attach(provider)
        parsed = await provider.fetch_all()
        result["provider_parsed_records"] = len(parsed)
        # The production client swallows retrieval errors. Inspect captured responses
        # so an HTTP error or unrecognised schema is not mistaken for an empty master.
        if not capture.responses:
            raise ValueError("No response received")
        metadata = capture.responses[0]
        metadata.raise_for_status()
        wrapper = metadata.json()
        result["metadata_keys"] = list(wrapper)
        result["metadata_report_count"] = len(wrapper.get("CurrentDay", []))
        if len(capture.responses) < 2:
            result["limitation"] = "No CSV response; metadata lookup or CSV retrieval failed"
            return result
        response = capture.responses[-1]
        response.raise_for_status()
        rows = [row for row in csv.reader(io.StringIO(response.text.lstrip("\ufeff")))
                if any(cell.strip() for cell in row)]
        header_index = next((i for i, row in enumerate(rows[:5])
                             if {nse._normalize_header(c) for c in row} & {"isin", "isinno", "isincode"}), None)
        if header_index is None:
            result["limitation"] = "CSV headers unrecognised"
            return result
        headers = rows[header_index]
        indices = {key: nse._header_index(headers, key) for key in nse._HEADER_ALIASES}

        def values(row):
            return {key: row[i] if i is not None and i < len(row) else None
                    for key, i in indices.items()}

        def reason(row):
            fields = values(row)
            if len(nse._clean(fields.get("security_description"))) < 2:
                return "missing/short description"
            return "missing or malformed ISIN (master parser contract)"

        result.update(audit(rows[header_index + 1:],
                            lambda row: nse._normalize_master_row(row, indices),
                            normalizer.normalize_nse_record, values, reason))
        result.update(status="validated", csv_headers=headers,
                      parser_count_matches=result["parsed_records"] == len(parsed))
    except Exception as exc:
        result["error_type"] = type(exc).__name__
    finally:
        result["requests"] = capture.requests
        await provider.close()
    return result


async def main():
    settings = Settings()
    report = {"observed_at": datetime.now(timezone.utc).isoformat(),
              "scope": "Existing CCIL Market Watch and NSE WDM master; no substituted endpoints",
              "page_methods": "GetCashflowSchedule/GetHistorydtls are CDSL, not implemented CCIL endpoints"}
    report["ccil"] = await diagnose_ccil(settings)
    report["nse"] = await diagnose_nse(settings)
    print(json.dumps(report, indent=2))
    return 0 if all(r["status"] == "validated" for r in report["ccil"].values()) and report["nse"]["status"] == "validated" else 1


if __name__ == "__main__":
    handler.setStream(sys.stderr)
    sys.exit(asyncio.run(main()))

