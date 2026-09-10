import json
import os
from datetime import datetime, timezone
from pathlib import Path

import requests

# Parse's managed wrapper over nepalstock.com.np.
# The API is independent of NEPSE; keep YONEPSE as a per-endpoint fallback.
PARSE_BASE = "https://api.parse.bot/scraper/200a3fbe-2c84-436d-8f67-6c08621de86e"
YONEPSE_BASE = "https://shubhamnpk.github.io/yonepse/data/market"

PARSE_ENDPOINTS = {
    "indices": f"{PARSE_BASE}/get_nepse_index",
    "prices": f"{PARSE_BASE}/get_today_prices",
    "summary": f"{PARSE_BASE}/get_market_summary",
}

YONEPSE_ENDPOINTS = {
    "indices": f"{YONEPSE_BASE}/indices.json",
    "summary": f"{YONEPSE_BASE}/summary.json",
    "sectors": f"{YONEPSE_BASE}/sector_indices.json",
    "top": f"{YONEPSE_BASE}/top_stocks.json",
    "status": f"{YONEPSE_BASE}/status.json",
}

ROOT = Path(__file__).resolve().parents[1]
LATEST = ROOT / "dashboard/data/latest.json"
ARCHIVE_DIR = ROOT / "market-data/auto"
ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "NEPSE-Daily-Intelligence/1.0"})


def get_json(url, *, headers=None, params=None):
    response = SESSION.get(url, timeout=20, headers=headers or {}, params=params or {})
    response.raise_for_status()
    payload = response.json()
    if isinstance(payload, dict) and payload.get("status") == "error":
        raise RuntimeError(payload.get("message") or "API returned an error")
    return payload


def parse_get(name):
    api_key = os.getenv("PARSE_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("PARSE_API_KEY is not configured")
    return get_json(PARSE_ENDPOINTS[name], headers={"X-API-Key": api_key})


def yonepse_get(name):
    return get_json(YONEPSE_ENDPOINTS[name])


def fetch_with_fallback(name, *, parse=True, fallback=True):
    errors = []
    if parse:
        try:
            return parse_get(name), "Parse NEPSE API"
        except Exception as exc:
            errors.append(f"Parse: {exc}")
    if fallback and name in YONEPSE_ENDPOINTS:
        try:
            return yonepse_get(name), "YONEPSE fallback"
        except Exception as exc:
            errors.append(f"YONEPSE: {exc}")
    raise RuntimeError(f"{name} unavailable; {' | '.join(errors)}")


def unwrap(payload):
    if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
        return payload["data"]
    return payload


def as_list(payload):
    value = unwrap(payload)
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        for key in ("items", "prices", "data", "content", "results", "stocks"):
            if isinstance(value.get(key), list):
                return value[key]
    return []


def norm_key(value):
    return str(value).lower().replace("_", "").replace("-", "").replace(" ", "")


def find_value(obj, keys):
    wanted = {norm_key(k) for k in keys}
    if isinstance(obj, dict):
        for key, value in obj.items():
            if norm_key(key) in wanted and value is not None:
                return value
        for value in obj.values():
            found = find_value(value, keys)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for value in obj:
            found = find_value(value, keys)
            if found is not None:
                return found
    return None


def find_number(obj, keys):
    value = find_value(obj, keys)
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def first_number(item, keys):
    return find_number(item, keys)


def normalize_index(payload):
    items = as_list(payload)
    nepse_item = next(
        (x for x in items if "nepse" in str(find_value(x, ["index", "name"]) or "").lower()),
        items[0] if items else {},
    )
    return {
        "nepse": first_number(nepse_item, ["currentValue", "current_value", "close", "closingIndex"]),
        "change_pct": first_number(nepse_item, ["perChange", "percentageChange", "changePercent", "change_pct"]),
        "point_change": first_number(nepse_item, ["change", "pointChange"]),
        "high": first_number(nepse_item, ["high", "highIndex"]),
        "low": first_number(nepse_item, ["low", "lowIndex"]),
        "previous_close": first_number(nepse_item, ["previousClose", "previous_close"]),
    }


def normalize_summary(payload):
    # Parse returns detail/value pairs; YONEPSE may use a different shape.
    metrics = {}
    value = unwrap(payload)
    if isinstance(value, dict):
        metrics.update(value)
    for item in as_list(payload):
        if not isinstance(item, dict):
            continue
        key = find_value(item, ["detail", "metric", "name", "key", "title"])
        val = find_value(item, ["value", "amount", "data"])
        if key is not None and val is not None:
            metrics[norm_key(key)] = val
    return metrics


def metric(metrics, *keys):
    wanted = {norm_key(k) for k in keys}
    for key, value in metrics.items():
        if norm_key(key) in wanted:
            try:
                return float(str(value).replace(",", ""))
            except (TypeError, ValueError):
                return value
    return None


def normalize_prices(payload):
    rows = []
    for item in as_list(payload):
        if not isinstance(item, dict):
            continue
        symbol = find_value(item, ["symbol", "stockSymbol", "ticker"])
        if not symbol:
            continue
        rows.append(
            {
                "symbol": str(symbol),
                "ltp": first_number(item, ["lastTradedPrice", "ltp", "closePrice", "close"]),
                "change_pct": first_number(item, ["percentageChange", "perChange", "changePercent"]),
                "volume": first_number(item, ["totalTradeQuantity", "volume", "tradedQuantity"]),
                "turnover": first_number(item, ["turnover", "totalTradeValue", "tradedValue"]),
                "open": first_number(item, ["openPrice", "open"]),
                "high": first_number(item, ["highPrice", "high"]),
                "low": first_number(item, ["lowPrice", "low"]),
                "previous_close": first_number(item, ["previousClose", "previous_close"]),
            }
        )
    return rows


def normalize_sectors(payload):
    rows = []
    for item in as_list(payload):
        if not isinstance(item, dict):
            continue
        name = find_value(item, ["sector", "sectorName", "name", "index"])
        change = first_number(item, ["percentageChange", "perChange", "changePercent", "change_pct"])
        if name:
            rows.append({"name": str(name), "change_pct": change})
    return rows


def derive_top_stocks(prices):
    valid = [x for x in prices if x.get("symbol") and x.get("ltp") is not None]
    gainers = sorted([x for x in valid if x.get("change_pct") is not None], key=lambda x: x["change_pct"], reverse=True)[:10]
    losers = sorted([x for x in valid if x.get("change_pct") is not None], key=lambda x: x["change_pct"])[:10]
    turnover = sorted([x for x in valid if x.get("turnover") is not None], key=lambda x: x["turnover"], reverse=True)[:10]
    return {"gainers": gainers, "losers": losers, "turnover": turnover}


def main():
    now = datetime.now(timezone.utc).astimezone()

    # Core market data: Parse first. Sector/status data stays on YONEPSE because
    # the selected Parse API does not expose those endpoints.
    indices, indices_source = fetch_with_fallback("indices")
    summary, summary_source = fetch_with_fallback("summary")
    prices, prices_source = fetch_with_fallback("prices", fallback=False)

    # Parse has no sector endpoint in this API, so use YONEPSE only for this panel.
    try:
        sectors_raw = yonepse_get("sectors")
        sectors_source = "YONEPSE fallback (sector endpoint)"
    except Exception:
        sectors_raw = None
        sectors_source = "unavailable"

    try:
        status_raw = yonepse_get("status")
        status_source = "YONEPSE fallback (status endpoint)"
    except Exception:
        status_raw = None
        status_source = "unavailable"

    with LATEST.open(encoding="utf-8") as f:
        latest = json.load(f)

    index = normalize_index(indices)
    summary_metrics = normalize_summary(summary)
    price_rows = normalize_prices(prices)
    derived = derive_top_stocks(price_rows)
    sectors = normalize_sectors(sectors_raw) if sectors_raw is not None else []

    turnover = metric(summary_metrics, "totalTurnover", "turnover", "total_turnover", "turnoverValue")
    if turnover is None:
        turnover = sum(x["turnover"] for x in price_rows if x.get("turnover") is not None)

    # Parse's today-prices endpoint is the source of truth for breadth.
    breadth_up = sum(1 for x in price_rows if (x.get("change_pct") or 0) > 0)
    breadth_down = sum(1 for x in price_rows if (x.get("change_pct") or 0) < 0)
    breadth_flat = sum(1 for x in price_rows if (x.get("change_pct") or 0) == 0)

    source_names = [indices_source, summary_source, prices_source]
    if sectors:
        source_names.append(sectors_source)

    latest["updated_label"] = now.strftime("%Y-%m-%d %H:%M:%S %Z")
    latest["market"] = {
        **latest.get("market", {}),
        "nepse": index["nepse"],
        "change_pct": index["change_pct"],
        "turnover": turnover,
        "breadth": {"up": breadth_up, "down": breadth_down, "flat": breadth_flat},
        "source": " + ".join(dict.fromkeys(source_names)),
        "source_urls": [PARSE_ENDPOINTS["indices"], PARSE_ENDPOINTS["summary"], PARSE_ENDPOINTS["prices"]],
        "as_of": now.isoformat(),
        "point_change": index["point_change"],
        "high": index["high"],
        "low": index["low"],
    }

    # Keep the existing dashboard schema intact while making live market data
    # available for future screener/BI panels.
    latest["market_data"] = {
        "prices": price_rows,
        "top": derived,
        "indices": unwrap(indices),
        "summary": summary_metrics,
    }
    if sectors:
        latest["sectors"] = sectors

    market_open = None
    if isinstance(status_raw, dict):
        market_open = find_value(status_raw, ["open", "is_open", "marketOpen", "market_open"])

    latest["pipeline"] = {
        "status": "live-feed-connected",
        "refreshed_at": now.isoformat(),
        "interval": "5 minutes (GitHub Actions); upstream freshness depends on source",
        "market_open": market_open,
        "sources": {
            "indices": indices_source,
            "summary": summary_source,
            "prices": prices_source,
            "sectors": sectors_source,
            "status": status_source,
        },
        "source": "Parse NEPSE API primary + YONEPSE fallback",
        "parse_api": {
            "configured": bool(os.getenv("PARSE_API_KEY", "").strip()),
            "base": PARSE_BASE,
            "note": "Parse is an independent managed wrapper over public nepalstock.com.np data, not an official NEPSE API."
        },
        "note": "No market price is invented. Parse is primary for core market data; YONEPSE is used per endpoint when Parse data is unavailable."
    }

    # Archive only the fetched payloads actually used by the pipeline.
    stamp = now.strftime("%Y-%m-%dT%H-%M-%S%z")
    archive = ARCHIVE_DIR / f"{stamp}.json"
    with archive.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "fetched_at": now.isoformat(),
                "sources": latest["pipeline"]["sources"],
                "data": {
                    "indices": indices,
                    "summary": summary,
                    "prices": prices,
                    "sectors": sectors_raw,
                    "status": status_raw,
                },
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
        f.write("\n")

    with LATEST.open("w", encoding="utf-8") as f:
        json.dump(latest, f, ensure_ascii=False, indent=2)
        f.write("\n")


if __name__ == "__main__":
    main()
