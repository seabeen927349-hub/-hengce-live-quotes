#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

TZ = ZoneInfo("Asia/Taipei")
URL = "https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX"
OUT = Path("research/industry_supply_chain_lead_lag_20261103/03_TYPE_ALL_DIAGNOSTIC_RESULT.json")
DATES = ["20180103", "20261027"]
TITLE_TO_CODE = {
    "半導體業": "24",
    "電腦及週邊設備業": "25",
    "光電業": "26",
    "通信網路業": "27",
    "電子零組件業": "28",
    "電子通路業": "29",
    "資訊服務業": "30",
    "其他電子業": "31",
}
UA = {
    "User-Agent": "Mozilla/5.0 HENGCE-INDUSTRY-PIT-AUDIT/1.0",
    "Accept": "application/json",
    "Referer": "https://www.twse.com.tw/",
}


def fetch(date: str) -> dict:
    last = None
    for attempt in range(5):
        try:
            r = requests.get(URL, params={"date": date, "type": "ALL", "response": "json"}, headers=UA, timeout=45)
            r.raise_for_status()
            obj = r.json()
            if not isinstance(obj, dict):
                raise RuntimeError("NON_OBJECT_JSON")
            return obj
        except Exception as exc:
            last = repr(exc)
            time.sleep(min(8, 2 ** attempt))
    raise RuntimeError(f"FETCH_FAIL:{date}:{last}")


def summarize(date: str, obj: dict) -> dict:
    tables = []
    detected = {}
    stock_tables = []
    for i, t in enumerate(obj.get("tables") or []):
        title = str(t.get("title") or "")
        fields = list(t.get("fields") or [])
        data = t.get("data") or t.get("records") or []
        is_stock = "證券代號" in fields and "證券名稱" in fields
        if is_stock:
            stock_tables.append(i)
        hit_codes = []
        for label, code in TITLE_TO_CODE.items():
            if label in title:
                detected[code] = {"table_index": i, "title": title, "rows": len(data)}
                hit_codes.append(code)
        tables.append({
            "index": i,
            "title": title,
            "fields": fields,
            "rows": len(data),
            "is_stock_level": is_stock,
            "matched_electronics_subindustry_codes": hit_codes,
        })
    codes = sorted(detected)
    return {
        "date": date,
        "stat": obj.get("stat"),
        "response_date": obj.get("date"),
        "table_count": len(tables),
        "stock_level_table_indexes": stock_tables,
        "detected_electronics_subindustry_codes": codes,
        "all_24_31_present": codes == ["24", "25", "26", "27", "28", "29", "30", "31"],
        "detected": detected,
        "tables": tables,
    }


def main() -> None:
    results = []
    for i, date in enumerate(DATES):
        obj = fetch(date)
        results.append(summarize(date, obj))
        if i + 1 < len(DATES):
            time.sleep(1.0)
    one_call_daily_possible = all(x["stat"] == "OK" and x["all_24_31_present"] for x in results)
    payload = {
        "system": "HENGCE",
        "artifact": "TWSE_MI_INDEX_TYPE_ALL_STRUCTURE_DIAGNOSTIC",
        "generated_at_taipei": datetime.now(TZ).isoformat(),
        "authority": "DATA_FEASIBILITY_ONLY_NO_TRADING_AUTHORITY",
        "forward_outcomes_used": False,
        "endpoint": URL,
        "request_type": "ALL",
        "dates_tested": DATES,
        "results": results,
        "one_call_per_day_subindustry_panel_possible": one_call_daily_possible,
        "decision_if_false": "DO_NOT_LAUNCH_24_31_DAILY_BULK_YET; USE_BOUNDED_RECOVERY_DESIGN_AND_RATE_LIMIT_AUDIT",
        "decision_if_true": "PERMIT_DAILY_PANEL_BUILDER_DESIGN_USING_TYPE_ALL, SUBJECT_TO COVERAGE_AND_TEMPORAL_CONSISTENCY_AUDIT",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": "PASS",
        "one_call_daily_possible": one_call_daily_possible,
        "dates": [{"date": x["date"], "stat": x["stat"], "codes": x["detected_electronics_subindustry_codes"], "tables": x["table_count"]} for x in results],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
