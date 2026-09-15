"""Verify real CCIL fixture data through provider -> normalizer -> Bond."""
import json
import pathlib

from backend.services.bonds.bond_normalizer import normalize_ccil_record
from backend.services.data.bonds import ccil as ccil_mod

FIX = pathlib.Path("tests/data/fixtures/ccil")

for name, section in [
    ("central_market_watch", "central"),
    ("state_market_watch", "state"),
    ("tbill_market_watch", "tbills"),
]:
    text = (FIX / f"{name}.json").read_text()
    recs = ccil_mod._parse_ccil_json(text, section)
    print(f"===== {name} ({section}): {len(recs)} raw records")
    for rec in recs[:4]:
        bond = normalize_ccil_record(rec)
        print(
            f"  {bond.security_name!r}\n"
            f"     instrument_type={bond.instrument_type.value!r} "
            f"issuer={bond.issuer!r} coupon={bond.coupon_rate} isin={bond.isin!r}\n"
            f"     maturity={bond.maturity_date} price={bond.price} ytm={bond.ytm} "
            f"ltp={bond.last_traded_price} lty={bond.last_traded_yield} "
            f"traded_value={bond.traded_value} data_type={bond.data_type.value!r}"
        )
    print()