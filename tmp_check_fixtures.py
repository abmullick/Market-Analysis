import json
import pathlib

for name in ["central_market_watch", "state_market_watch", "tbill_market_watch"]:
    p = pathlib.Path("tests/data/fixtures/ccil") / f"{name}.json"
    raw = p.read_text()
    print("=====", name, "bytes", len(raw))
    print("wrapper keys:", list(json.loads(raw).keys()))
    rows = json.loads(json.loads(raw)["result1"])
    print("rows:", len(rows))
    print("row0:", rows[0])
    print()