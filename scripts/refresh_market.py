import json
import os
from datetime import datetime, timezone
from pathlib import Path

import requests

BASE = "https://shubhamnpk.github.io/yonepse/data/market"
ENDPOINTS = {
    "indices": f"{BASE}/indices.json",
    "summary": f"{BASE}/summary.json",
    "sectors": f"{BASE}/sector_indices.json",
    "top": f"{BASE}/top_stocks.json",
    "status": f"{BASE}/status.json",
}

ROOT = Path(__file__).resolve().parents[1]
LATEST = ROOT / "dashboard/data/latest.json"
ARCHIVE_DIR = ROOT / "market-data/auto"
ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)


def get_json(url):
    r = requests.get(url, timeout=20, headers={"User-Agent": "NEPSE-Daily-Intelligence/1.0"})
    r.raise_for_status()
    return r.json()


def find_number(obj, keys):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k.lower().replace("_", "") in {x.lower().replace("_", "") for x in keys} and isinstance(v, (int, float)):
                return v
        for v in obj.values():
            x = find_number(v, keys)
            if x is not None:
                return x
    elif isinstance(obj, list):
        for v in obj:
            x = find_number(v, keys)
            if x is not None:
                return x
    return None


def main():
    fetched = {name: get_json(url) for name, url in ENDPOINTS.items()}
    now = datetime.now(timezone.utc).astimezone()

    with LATEST.open(encoding="utf-8") as f:
        latest = json.load(f)

    indices = fetched["indices"]
    summary = fetched["summary"]
    status = fetched["status"]

    nepse = find_number(indices, ["nepse", "nepseindex", "current"])
    change = find_number(indices, ["changepercent", "percentchange", "pctchange", "change_pct"])
    turnover = find_number(summary, ["turnover", "totalturnover"])
    breadth_up = find_number(summary, ["positive", "gainers", "advancing", "advance"])
    breadth_down = find_number(summary, ["negative", "losers", "declining", "decline"])

    latest["updated_label"] = now.strftime("%Y-%m-%d %H:%M:%S %Z")
    latest["market"] = {
        **latest.get("market", {}),
        "nepse": nepse,
        "change_pct": change,
        "turnover": turnover,
        "breadth": {"up": breadth_up, "down": breadth_down},
        "source": "YONEPSE public market feed",
        "source_urls": list(ENDPOINTS.values()),
        "as_of": find_number(status, ["timestamp", "updatedat"]) or now.isoformat(),
    }
    latest["pipeline"] = {
        "status": "live-feed-connected",
        "refreshed_at": now.isoformat(),
        "interval": "5 minutes (GitHub Actions); source itself may refresh independently",
        "market_open": status.get("open", status.get("is_open", None)) if isinstance(status, dict) else None,
        "source": "YONEPSE public data feed",
        "note": "No price is invented. If the upstream feed fails, the previous verified snapshot is retained."
    }

    # Preserve raw upstream data for auditability.
    stamp = now.strftime("%Y-%m-%dT%H-%M-%S%z")
    archive = ARCHIVE_DIR / f"{stamp}.json"
    with archive.open("w", encoding="utf-8") as f:
        json.dump({"fetched_at": now.isoformat(), "source": ENDPOINTS, "data": fetched}, f, ensure_ascii=False, indent=2)
        f.write("\n")

    with LATEST.open("w", encoding="utf-8") as f:
        json.dump(latest, f, ensure_ascii=False, indent=2)
        f.write("\n")


if __name__ == "__main__":
    main()
