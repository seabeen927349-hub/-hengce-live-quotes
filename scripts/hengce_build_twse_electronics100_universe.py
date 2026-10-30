#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Taipei")
MASTER_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"
DAILY_URL = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
PINS_PATH = Path("hengce/legacy/live_pins.json")
OUT_PATH = Path("hengce/legacy/live_universe.json")
ELECTRONICS_CODES = {"24", "25", "26", "27", "28", "29", "30", "31"}
POLICY = "TWSE_LISTED_ELECTRONICS_100_HARD_BIND"
SCOPE = "TWSE_LISTED_ELECTRONICS_ONLY"
TARGET_COUNT = 100


def get_json(url: str):
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "HENGCE-TWSE-ELECTRONICS100/1.0",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def pick(row: dict, keys: list[str]):
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return None


def norm_code(value) -> str:
    s = str(value or "").strip()
    return s if re.fullmatch(r"[1-9]\d{3}", s) else ""


def norm_industry(value) -> str:
    s = str(value or "").strip()
    m = re.match(r"^(\d{2})", s)
    return m.group(1) if m else s


def number(value) -> float:
    if value in (None, "", "--"):
        return 0.0
    try:
        return float(str(value).replace(",", "").strip())
    except Exception:
        return 0.0


def sha_obj(obj) -> str:
    raw = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def load_master():
    data = get_json(MASTER_URL)
    if not isinstance(data, list) or not data:
        raise SystemExit("TWSE_MASTER_EMPTY_OR_INVALID")
    members = {}
    for row in data:
        if not isinstance(row, dict):
            continue
        code = norm_code(pick(row, ["公司代號", "公司代碼", "證券代號", "股票代號", "Code"]))
        industry = norm_industry(pick(row, ["產業別", "產業別代碼", "IndustryCode", "Industry"] ))
        if not code or industry not in ELECTRONICS_CODES:
            continue
        name = str(pick(row, ["公司簡稱", "公司名稱", "證券名稱", "Name"]) or "").strip()
        members[code] = {
            "Ticker": code,
            "Name": name,
            "market": "TWSE",
            "industry_code": industry,
        }
    if len(members) < TARGET_COUNT:
        raise SystemExit(f"TWSE_ELECTRONICS_MEMBER_COUNT_TOO_SMALL:{len(members)}")
    return members


def load_liquidity():
    status = "PASS"
    values = {}
    source_date = None
    try:
        data = get_json(DAILY_URL)
        if not isinstance(data, list) or not data:
            raise RuntimeError("EMPTY")
        for row in data:
            if not isinstance(row, dict):
                continue
            code = norm_code(pick(row, ["Code", "證券代號", "股票代號", "公司代號"]))
            if not code:
                continue
            val = number(pick(row, ["TradeValue", "成交金額", "交易金額", "成交值"]))
            values[code] = val
            if source_date is None:
                source_date = pick(row, ["Date", "日期", "交易日期"])
    except Exception as exc:
        status = f"UNAVAILABLE_FALLBACK_TICKER_ORDER:{type(exc).__name__}"
    return values, status, source_date


def load_pins():
    if not PINS_PATH.exists():
        return []
    obj = json.loads(PINS_PATH.read_text(encoding="utf-8"))
    return [str(x).strip() for x in obj.get("symbols", []) if norm_code(x)]


def build():
    now = datetime.now(TZ)
    members = load_master()
    trade_value, liquidity_status, liquidity_date = load_liquidity()
    pins = load_pins()

    valid_pins = []
    rejected_pins = []
    seen = set()
    for code in pins:
        if code in members and code not in seen:
            valid_pins.append(code)
            seen.add(code)
        elif code not in members:
            rejected_pins.append(code)

    remainder = [code for code in members if code not in seen]
    remainder.sort(key=lambda code: (-trade_value.get(code, 0.0), int(code)))
    symbols = (valid_pins + remainder)[:TARGET_COUNT]
    if len(symbols) != TARGET_COUNT or len(set(symbols)) != TARGET_COUNT:
        raise SystemExit("ELECTRONICS100_SELECTION_COUNT_OR_DUPLICATE_FAILURE")

    rows = []
    pin_set = set(valid_pins)
    for rank, code in enumerate(symbols, start=1):
        base = dict(members[code])
        base.update({
            "selection_rank": rank,
            "selection_reason": "HENGCE_PIN" if code in pin_set else ("TWSE_TRADE_VALUE" if trade_value else "TICKER_ORDER_FALLBACK"),
            "reference_trade_value": trade_value.get(code),
        })
        rows.append(base)

    payload = {
        "system": "HENGCE",
        "artifact": "LEGACY_LIVE_UNIVERSE",
        "version": f"HENGCE_TWSE_ELECTRONICS100_{now.strftime('%Y%m%d')}",
        "generated_at_taipei": now.isoformat(),
        "target_date": now.date().isoformat(),
        "source_run_id": f"HENGCE_TWSE_ELECTRONICS100_{now.strftime('%Y%m%d')}",
        "policy": POLICY,
        "scope": SCOPE,
        "authority": "QUOTE_TRANSPORT_MEMBERSHIP_ONLY_NO_MODEL_RANKING_AUTHORITY",
        "membership_source": MASTER_URL,
        "membership_industry_codes": sorted(ELECTRONICS_CODES),
        "liquidity_source": DAILY_URL,
        "liquidity_source_status": liquidity_status,
        "liquidity_source_date": liquidity_date,
        "requested_count": TARGET_COUNT,
        "pin_count": len(valid_pins),
        "valid_pins": valid_pins,
        "rejected_pins_not_twse_electronics": rejected_pins,
        "symbols": symbols,
        "rows": rows,
    }
    payload["payload_sha256"] = sha_obj({k: v for k, v in payload.items() if k != "payload_sha256"})

    if any(r.get("market") != "TWSE" or r.get("industry_code") not in ELECTRONICS_CODES for r in rows):
        raise SystemExit("NON_TWSE_ELECTRONICS_MEMBER_DETECTED")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": "PASS",
        "requested_count": TARGET_COUNT,
        "pin_count": len(valid_pins),
        "rejected_pins": rejected_pins,
        "liquidity_status": liquidity_status,
        "first10": symbols[:10],
    }, ensure_ascii=False))


if __name__ == "__main__":
    build()
