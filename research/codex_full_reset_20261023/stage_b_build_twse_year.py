#!/usr/bin/env python3
"""Build one year of the research-only TWSE listed-electronics mother table.

The preserved point-in-time electronics membership is the authority for the admitted
(date, ticker) universe. Every fetched TWSE MI_INDEX type=13 daily table must match
that membership set exactly. Research only; no production/trading authority.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import re
import threading
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
RESET = ROOT / "research" / "codex_full_reset_20261023"
MEMBERSHIP = ROOT / "research" / "e2_profit_max" / "membership"
URL = "https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX"
UA = "Mozilla/5.0 (HENGCE full-reset research; official TWSE archive rebuild)"
MAX_WORKERS = 4
PRINT_LOCK = threading.Lock()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def decode(content: bytes) -> str:
    for enc in ("utf-8-sig", "utf-8", "cp950", "big5"):
        try:
            return content.decode(enc)
        except UnicodeDecodeError:
            pass
    return content.decode("utf-8", errors="replace")


def clean_num(value: str) -> str:
    s = (value or "").strip().replace(",", "")
    if s in {"", "--", "---", "----", "除權息", "除息", "除權"}:
        return ""
    return s


def parse_twse_csv(text: str) -> tuple[list[dict[str, str]], list[str] | None]:
    rows = list(csv.reader(io.StringIO(text)))
    header_idx = None
    for i, row in enumerate(rows):
        joined = "|".join(row)
        if "證券代號" in joined and "證券名稱" in joined and "收盤價" in joined:
            header_idx = i
            break
    if header_idx is None:
        return [], None
    headers = [x.strip().replace("\ufeff", "") for x in rows[header_idx]]
    out: list[dict[str, str]] = []
    for row in rows[header_idx + 1:]:
        if not row or len(row) < 2:
            continue
        padded = row + [""] * max(0, len(headers) - len(row))
        rec = {headers[i]: padded[i].strip() for i in range(len(headers))}
        ticker = rec.get("證券代號", "").replace("=", "").replace('"', "").strip()
        name = rec.get("證券名稱", "").strip()
        if ticker and name and re.fullmatch(r"[0-9A-Za-z]{4,8}", ticker):
            out.append({
                "ticker": ticker,
                "name": name,
                "open": clean_num(rec.get("開盤價", "")),
                "high": clean_num(rec.get("最高價", "")),
                "low": clean_num(rec.get("最低價", "")),
                "close": clean_num(rec.get("收盤價", "")),
                "volume_shares": clean_num(rec.get("成交股數", "")),
                "turnover_ntd": clean_num(rec.get("成交金額", "")),
            })
    return out, headers


def load_expected(year: int) -> tuple[dict[str, set[str]], dict[tuple[str, str], str], dict[str, Any]]:
    path = MEMBERSHIP / f"twse_electronics_membership_{year}.csv"
    if not path.exists():
        raise RuntimeError(f"MISSING_MEMBERSHIP:{path}")
    by_date: dict[str, set[str]] = {}
    names: dict[tuple[str, str], str] = {}
    rows = 0
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            d = (row.get("Date") or row.get("date") or "").strip()
            ticker = (row.get("Ticker") or row.get("ticker") or "").strip()
            name = (row.get("Name") or row.get("name") or "").strip()
            if not d or not ticker:
                raise RuntimeError(f"BAD_MEMBERSHIP_ROW:{year}")
            by_date.setdefault(d, set()).add(ticker)
            names[(d, ticker)] = name
            rows += 1
    if not by_date:
        raise RuntimeError(f"EMPTY_MEMBERSHIP:{year}")
    return by_date, names, {
        "year": year,
        "path": str(path.relative_to(ROOT)),
        "rows": rows,
        "dates": len(by_date),
        "sha256": sha256_file(path),
    }


def fetch_day(date_s: str, expected: set[str]) -> tuple[str, str, list[dict[str, str]], dict[str, Any]]:
    ds = date_s.replace("-", "")
    query = urllib.parse.urlencode({"date": ds, "type": "13", "response": "csv"})
    url = f"{URL}?{query}"
    last = ""
    for attempt in range(5):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=22) as resp:
                content = resp.read()
                status_code = getattr(resp, "status", 200)
            if status_code != 200 or not content:
                last = f"HTTP_OR_EMPTY:{status_code}:{len(content)}"
            else:
                rows, headers = parse_twse_csv(decode(content))
                actual = {row["ticker"] for row in rows}
                missing = sorted(expected - actual)
                extra = sorted(actual - expected)
                duplicate_count = len(rows) - len(actual)
                if headers is None:
                    status = "HEADER_NOT_FOUND"
                elif duplicate_count:
                    status = "DUPLICATE_TICKERS"
                elif missing or extra:
                    status = "MEMBERSHIP_SET_MISMATCH"
                else:
                    status = "PASS"
                return date_s, status, rows, {
                    "date": date_s,
                    "status": status,
                    "expected_tickers": len(expected),
                    "actual_rows": len(rows),
                    "actual_unique_tickers": len(actual),
                    "duplicate_count": duplicate_count,
                    "missing_count": len(missing),
                    "extra_count": len(extra),
                    "missing_sample": missing[:10],
                    "extra_sample": extra[:10],
                    "response_sha256": hashlib.sha256(content).hexdigest(),
                    "response_bytes": len(content),
                    "attempt": attempt + 1,
                }
        except Exception as exc:
            last = f"{type(exc).__name__}:{str(exc)[:300]}"
        time.sleep(0.6 * (2 ** attempt))
    return date_s, "FETCH_ERROR", [], {
        "date": date_s,
        "status": "FETCH_ERROR",
        "expected_tickers": len(expected),
        "error": last,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", required=True, type=int, choices=(2023, 2024, 2025))
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()
    year = args.year
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    expected_by_date, expected_names, source = load_expected(year)
    dates = sorted(expected_by_date)
    fetched: dict[str, list[dict[str, str]]] = {}
    qa: list[dict[str, Any]] = []
    done = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(fetch_day, d, expected_by_date[d]): d for d in dates}
        for future in as_completed(futures):
            d, status, rows, q = future.result()
            qa.append(q)
            if status == "PASS":
                fetched[d] = rows
            done += 1
            if done % 25 == 0 or status != "PASS":
                with PRINT_LOCK:
                    print(f"TWSE {year} {done}/{len(dates)} date={d} status={status}", flush=True)

    qa.sort(key=lambda x: x["date"])
    failures = [x for x in qa if x["status"] != "PASS"]
    qa_path = out_dir / f"TWSE_MOTHER_QA_{year}.jsonl"
    with qa_path.open("w", encoding="utf-8") as f:
        for row in qa:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")

    mother_path = out_dir / f"TWSE_ELECTRONICS_DAILY_{year}.csv.gz"
    fields = ["date", "ticker", "name", "open", "high", "low", "close", "volume_shares", "turnover_ntd"]
    total_rows = 0
    with gzip.open(mother_path, "wt", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for d in dates:
            for row in sorted(fetched.get(d, []), key=lambda x: x["ticker"]):
                ticker = row["ticker"]
                writer.writerow({
                    "date": d,
                    "ticker": ticker,
                    "name": expected_names.get((d, ticker), row["name"]),
                    "open": row["open"],
                    "high": row["high"],
                    "low": row["low"],
                    "close": row["close"],
                    "volume_shares": row["volume_shares"],
                    "turnover_ntd": row["turnover_ntd"],
                })
                total_rows += 1

    receipt = {
        "schema_version": 1,
        "stage": "B_YEARLY_OFFICIAL_MOTHER_REBUILD",
        "year": year,
        "source": "TWSE MI_INDEX type=13 historical daily CSV",
        "source_url": URL,
        "retrieval_time_utc": datetime.now(timezone.utc).isoformat(),
        "expected_trading_dates": len(dates),
        "pass_dates": sum(x["status"] == "PASS" for x in qa),
        "failed_dates": len(failures),
        "rows_written": total_rows,
        "membership_source": source,
        "qa_path": qa_path.name,
        "qa_sha256": sha256_file(qa_path),
        "mother_path": mother_path.name,
        "mother_sha256": sha256_file(mother_path),
        "first_failures": failures[:20],
        "status": "PASS_EXACT_MEMBERSHIP_SET" if not failures else "FAIL_CLOSED_DATE_OR_MEMBERSHIP_MISMATCH",
        "universe": "TWSE_LISTED_ELECTRONICS_PIT_DAILY",
        "authority": {
            "research_only": True,
            "signal_authority": False,
            "ranking_authority": False,
            "capital_authority_twd": 0,
            "broker_order_execution": False,
            "production_promotion": False
        }
    }
    receipt_path = out_dir / f"TWSE_MOTHER_RECEIPT_{year}.json"
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"year": year, "status": receipt["status"], "dates": len(dates), "rows": total_rows}, sort_keys=True), flush=True)
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
