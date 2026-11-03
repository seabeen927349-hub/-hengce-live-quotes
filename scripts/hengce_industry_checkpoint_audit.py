#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

TZ = ZoneInfo("Asia/Taipei")
URL = "https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX"
OUT_DIR = Path("research/industry_supply_chain_lead_lag_20261103")
SNAPSHOT_CSV = OUT_DIR / "04_INDUSTRY_CHECKPOINT_SNAPSHOTS.csv"
AUDIT_JSON = OUT_DIR / "05_INDUSTRY_CHECKPOINT_AUDIT.json"

INDUSTRIES = {
    "24": "半導體業",
    "25": "電腦及週邊設備業",
    "26": "光電業",
    "27": "通信網路業",
    "28": "電子零組件業",
    "29": "電子通路業",
    "30": "資訊服務業",
    "31": "其他電子業",
}

CHECKPOINT_DATES = [
"2018-01-02","2018-01-31","2018-02-27","2018-03-31","2018-04-16","2018-04-30","2018-05-31","2018-06-28","2018-06-29","2018-07-10","2018-07-16","2018-07-31","2018-08-31","2018-09-28","2018-10-01","2018-10-17","2018-10-31","2018-11-28","2018-11-30","2018-12-05","2018-12-12","2018-12-28","2019-01-14","2019-01-17","2019-01-30","2019-02-27","2019-03-27","2019-03-29","2019-04-02","2019-04-17","2019-04-30","2019-05-31","2019-06-28","2019-07-31","2019-08-30","2019-09-27","2019-10-31","2019-11-25","2019-11-29","2019-12-12","2019-12-19","2019-12-31","2020-01-31","2020-02-27","2020-03-31","2020-04-15","2020-04-30","2020-05-29","2020-06-30","2020-07-31","2020-08-31","2020-09-30","2020-10-30","2020-11-30","2020-12-11","2020-12-14","2020-12-24","2020-12-31","2021-01-06","2021-01-19","2021-01-20","2021-01-29","2021-02-26","2021-03-22","2021-03-24","2021-03-31","2021-04-29","2021-05-13","2021-05-31","2021-06-30","2021-07-30","2021-08-31","2021-09-30","2021-10-25","2021-10-29","2021-11-30","2021-12-06","2021-12-08","2021-12-30","2022-01-03","2022-01-07","2022-01-13","2022-01-19","2022-01-26","2022-02-25","2022-03-31","2022-04-29","2022-05-12","2022-05-31","2022-06-30","2022-07-29","2022-08-18","2022-08-25","2022-08-31","2022-09-01","2022-09-21","2022-09-30","2022-10-31","2022-11-04","2022-11-10","2022-11-30","2022-12-15","2022-12-30","2023-01-31","2023-02-24","2023-03-21","2023-03-31","2023-04-28","2023-05-31","2023-06-30","2023-07-31","2023-08-31","2023-09-28","2023-10-19","2023-10-31","2023-11-02","2023-11-08","2023-11-09","2023-11-30","2023-12-05","2023-12-12","2023-12-29","2024-01-29","2024-01-31","2024-02-29","2024-03-07","2024-03-26","2024-03-29","2024-04-30","2024-05-09","2024-05-15","2024-05-16","2024-05-31","2024-06-27","2024-06-28","2024-07-31","2024-08-30","2024-09-30","2024-10-23","2024-10-30","2024-11-26","2024-11-29","2024-12-03","2024-12-11","2024-12-31","2025-01-22","2025-02-27","2025-03-13","2025-03-31","2025-04-30","2025-05-21","2025-05-29","2025-06-13","2025-06-30","2025-07-31","2025-08-06","2025-08-29","2025-09-26","2025-09-30","2025-10-16","2025-10-31","2025-11-04","2025-11-19","2025-11-25","2025-11-27","2025-11-28","2025-12-22","2025-12-23","2025-12-31","2026-01-16","2026-01-30","2026-02-26","2026-03-25","2026-03-30","2026-03-31","2026-04-30","2026-05-07","2026-05-29","2026-06-30","2026-07-16","2026-07-28","2026-07-31","2026-08-31","2026-09-22","2026-09-30","2026-10-27"
]

UA = {
    "User-Agent": "Mozilla/5.0 HENGCE-INDUSTRY-CHECKPOINT-AUDIT/1.0",
    "Accept": "application/json",
    "Referer": "https://www.twse.com.tw/",
}


def get_json(date_iso: str, type_code: str) -> dict:
    ds = date_iso.replace("-", "")
    last = None
    for attempt in range(6):
        try:
            r = requests.get(URL, params={"date": ds, "type": type_code, "response": "json"}, headers=UA, timeout=45)
            r.raise_for_status()
            obj = r.json()
            if not isinstance(obj, dict):
                raise RuntimeError("NON_OBJECT_JSON")
            if str(obj.get("stat")) != "OK":
                raise RuntimeError(f"STAT_{obj.get('stat')}")
            if str(obj.get("date")) != ds:
                raise RuntimeError(f"DATE_MISMATCH_{obj.get('date')}")
            return obj
        except Exception as exc:
            last = repr(exc)
            time.sleep(min(12, 1.5 * (2 ** attempt)))
    raise RuntimeError(f"FETCH_FAIL:{date_iso}:{type_code}:{last}")


def parse_stock_rows(obj: dict) -> dict[str, str]:
    for table in obj.get("tables") or []:
        fields = list(table.get("fields") or [])
        if "證券代號" not in fields or "證券名稱" not in fields:
            continue
        idx = {f: i for i, f in enumerate(fields)}
        data = table.get("data") or table.get("records") or []
        out = {}
        for row in data:
            i_code = idx["證券代號"]
            i_name = idx["證券名稱"]
            if i_code >= len(row):
                continue
            code = str(row[i_code]).replace("=", "").replace('"', "").strip()
            if not re.fullmatch(r"[1-9]\d{3}", code):
                continue
            name = str(row[i_name]).strip() if i_name < len(row) else ""
            out[code] = name
        return out
    raise RuntimeError("STOCK_TABLE_NOT_FOUND")


def fetch_one(date_iso: str, type_code: str):
    return type_code, parse_stock_rows(get_json(date_iso, type_code))


def audit_date(date_iso: str):
    wanted = ["13", *INDUSTRIES.keys()]
    fetched = {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(fetch_one, date_iso, code) for code in wanted]
        for fut in as_completed(futures):
            code, rows = fut.result()
            fetched[code] = rows
    expected = fetched["13"]
    classification = {}
    duplicates = {}
    for code in INDUSTRIES:
        for ticker, name in fetched[code].items():
            if ticker in classification and classification[ticker][0] != code:
                duplicates.setdefault(ticker, set()).update([classification[ticker][0], code])
            else:
                classification[ticker] = (code, name)
    expected_set = set(expected)
    class_set = set(classification)
    missing = sorted(expected_set - class_set)
    extra = sorted(class_set - expected_set)
    coverage = (len(expected_set & class_set) / len(expected_set)) if expected_set else 0.0
    rows = []
    for ticker in sorted(expected_set & class_set, key=int):
        code, class_name = classification[ticker]
        rows.append({
            "date": date_iso,
            "ticker": ticker,
            "name": expected.get(ticker) or class_name,
            "industry_code": code,
            "industry_name": INDUSTRIES[code],
            "source": URL,
        })
    return {
        "date": date_iso,
        "expected_type13_count": len(expected_set),
        "classified_24_31_count": len(class_set),
        "intersection_count": len(expected_set & class_set),
        "coverage": coverage,
        "missing_expected_tickers": missing,
        "extra_classified_tickers": extra,
        "duplicate_classifications": {k: sorted(v) for k, v in duplicates.items()},
    }, rows


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    all_rows = []
    audits = []
    by_ticker = {}
    for n, date_iso in enumerate(CHECKPOINT_DATES, start=1):
        audit, rows = audit_date(date_iso)
        audits.append(audit)
        all_rows.extend(rows)
        for row in rows:
            by_ticker.setdefault(row["ticker"], []).append((date_iso, row["industry_code"], row["industry_name"]))
        print(json.dumps({"checkpoint": n, "total": len(CHECKPOINT_DATES), "date": date_iso, "coverage": audit["coverage"], "missing": len(audit["missing_expected_tickers"]), "extra": len(audit["extra_classified_tickers"])}, ensure_ascii=False), flush=True)
        time.sleep(0.12)

    changes = []
    for ticker, seq in sorted(by_ticker.items(), key=lambda kv: int(kv[0])):
        prev = None
        for date_iso, code, name in seq:
            if prev is not None and code != prev[1]:
                changes.append({
                    "ticker": ticker,
                    "from_checkpoint": prev[0],
                    "from_industry_code": prev[1],
                    "to_checkpoint": date_iso,
                    "to_industry_code": code,
                    "exact_effective_date": "UNRESOLVED_REQUIRES_TRANSITION_REFINEMENT",
                })
            prev = (date_iso, code, name)

    with SNAPSHOT_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["date", "ticker", "name", "industry_code", "industry_name", "source"])
        w.writeheader()
        w.writerows(all_rows)

    min_cov = min((x["coverage"] for x in audits), default=0.0)
    zero_missing_dates = sum(1 for x in audits if not x["missing_expected_tickers"] and not x["duplicate_classifications"])
    payload = {
        "system": "HENGCE",
        "artifact": "INDUSTRY_CHECKPOINT_PIT_AUDIT",
        "generated_at_taipei": datetime.now(TZ).isoformat(),
        "authority": "DATA_FEASIBILITY_ONLY_NO_TRADING_AUTHORITY",
        "forward_outcomes_used": False,
        "source": URL,
        "universe": "TWSE listed electronics, standard four-digit tickers only",
        "checkpoint_design": "186 dates = canonical archive month-end trading sessions UNION canonical archive ticker first-appearance dates",
        "checkpoint_count": len(CHECKPOINT_DATES),
        "snapshot_rows": len(all_rows),
        "min_type13_to_24_31_coverage": min_cov,
        "dates_with_zero_missing_and_zero_duplicate": zero_missing_dates,
        "classification_change_intervals": changes,
        "classification_change_interval_count": len(changes),
        "exact_transition_dates_cleared": False,
        "daily_panel_cleared": False,
        "forward_return_gate": "SEALED",
        "next_step": "If checkpoint coverage is complete, refine only detected industry-change intervals to exact effective dates and separately address the possibility of within-interval round-trip changes before declaring a daily PIT panel complete.",
        "audits": audits,
    }
    AUDIT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "checkpoint_count": len(audits), "snapshot_rows": len(all_rows), "min_coverage": min_cov, "change_intervals": len(changes)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
