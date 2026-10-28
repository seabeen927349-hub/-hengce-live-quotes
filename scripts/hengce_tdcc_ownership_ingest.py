#!/usr/bin/env python3
"""HENGCE official TDCC ownership-distribution vessel.

Source: TDCC open data dataset 1-5 (集保戶股權分散表).

Governance:
- official TDCC only; no third-party fallback;
- daily check, but persist only when TDCC snapshot DataDate changes;
- raw source bytes are preserved;
- 400-lot holders = grades 12-15;
- 1000-lot holders = grade 15;
- grades 16/17 are adjustment/total and are not included in big-holder sums;
- no technical-analysis/model authority is created here;
- same-date source revision is fail-closed for manual review.

This vessel is weekly ownership evidence even though the downloader checks daily.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

TZ = ZoneInfo("Asia/Taipei")
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "ownership" / "tdcc"
SOURCE_URL = "https://opendata.tdcc.com.tw/getOD.ashx?id=1-5"
EXPECTED = ["資料日期", "證券代號", "持股分級", "人數", "股數", "占集保庫存數比例%"]
SUMMARY_COLS = [
    "SnapshotDate", "ObservedAtTaipei", "Ticker",
    "Big400Holders", "Big400Shares", "Big400Pct",
    "Big1000Holders", "Big1000Shares", "Big1000Pct",
    "TotalHolders", "TotalShares", "AdjustmentShares", "Source"
]


def now_tw() -> datetime:
    return datetime.now(TZ)


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def atomic_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    os.close(fd)
    try:
        Path(tmp).write_bytes(data)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def atomic_text(path: Path, text: str) -> None:
    atomic_bytes(path, text.encode("utf-8"))


def atomic_json(path: Path, obj: dict) -> None:
    atomic_text(path, json.dumps(obj, ensure_ascii=False, indent=2) + "\n")


def decode_csv(raw: bytes) -> tuple[str, str]:
    for enc in ("utf-8-sig", "utf-8", "cp950", "big5"):
        try:
            text = raw.decode(enc)
            if "資料日期" in text and "證券代號" in text and "持股分級" in text:
                return text, enc
        except UnicodeDecodeError:
            pass
    raise RuntimeError("TDCC_ENCODING_OR_HEADER_UNRECOGNIZED")


def norm_header(x: str) -> str:
    return str(x or "").replace("\ufeff", "").strip()


def clean_int(x) -> int:
    s = str(x or "").replace(",", "").strip()
    if s in ("", "-", "--"):
        return 0
    return int(float(s))


def clean_float(x) -> float:
    s = str(x or "").replace(",", "").replace("%", "").strip()
    if s in ("", "-", "--"):
        return 0.0
    return float(s)


def fetch() -> bytes:
    r = requests.get(
        SOURCE_URL,
        timeout=45,
        headers={
            "User-Agent": "Mozilla/5.0 HENGCE-TDCC-OWNERSHIP/1.0",
            "Accept": "text/csv,*/*;q=0.8",
            "Referer": "https://www.tdcc.com.tw/",
        },
    )
    r.raise_for_status()
    if len(r.content) < 100_000:
        raise RuntimeError(f"TDCC_RESPONSE_TOO_SMALL:{len(r.content)}")
    return r.content


def parse(raw: bytes):
    text, enc = decode_csv(raw)
    rd = csv.DictReader(io.StringIO(text))
    headers = [norm_header(x) for x in (rd.fieldnames or [])]
    missing = [c for c in EXPECTED if c not in headers]
    if missing:
        raise RuntimeError("TDCC_MISSING_COLUMNS:" + ",".join(missing))

    rows = []
    for row0 in rd:
        row = {norm_header(k): v for k, v in row0.items()}
        ds = str(row.get("資料日期", "")).strip()
        ticker = str(row.get("證券代號", "")).strip()
        grade_s = str(row.get("持股分級", "")).strip()
        if not ds or not ticker or not grade_s:
            continue
        if not re.fullmatch(r"\d{8}", ds):
            raise RuntimeError(f"TDCC_BAD_DATE:{ds}")
        try:
            grade = int(grade_s)
        except Exception as e:
            raise RuntimeError(f"TDCC_BAD_GRADE:{grade_s}") from e
        if grade < 1 or grade > 17:
            raise RuntimeError(f"TDCC_GRADE_OUT_OF_RANGE:{grade}")
        rows.append({
            "date": ds,
            "ticker": ticker,
            "grade": grade,
            "holders": clean_int(row.get("人數")),
            "shares": clean_int(row.get("股數")),
            "pct": clean_float(row.get("占集保庫存數比例%")),
        })

    if len(rows) < 10_000:
        raise RuntimeError(f"TDCC_ROWS_TOO_SMALL:{len(rows)}")
    dates = sorted({r["date"] for r in rows})
    if len(dates) != 1:
        raise RuntimeError("TDCC_MULTIPLE_SNAPSHOT_DATES:" + ",".join(dates))
    snapshot = dates[0]
    stock_rows = [r for r in rows if re.fullmatch(r"[1-9]\d{3}", r["ticker"])]
    stock_tickers = sorted({r["ticker"] for r in stock_rows})
    if len(stock_tickers) < 900:
        raise RuntimeError(f"TDCC_4D_STOCK_TICKERS_TOO_SMALL:{len(stock_tickers)}")

    # Require a total row for almost every 4-digit stock and grades 12-15 to be parseable.
    grade_map = {}
    for r in stock_rows:
        grade_map.setdefault(r["ticker"], {})[r["grade"]] = r
    total_count = sum(1 for t in stock_tickers if 17 in grade_map.get(t, {}))
    if total_count < int(len(stock_tickers) * 0.95):
        raise RuntimeError(f"TDCC_TOTAL_ROW_COVERAGE_TOO_LOW:{total_count}/{len(stock_tickers)}")

    return rows, stock_tickers, grade_map, snapshot, enc


def summarize(stock_tickers, grade_map, snapshot: str, observed: str):
    out = []
    for ticker in stock_tickers:
        gm = grade_map[ticker]
        big = [gm[g] for g in (12, 13, 14, 15) if g in gm]
        g15 = gm.get(15)
        g16 = gm.get(16)
        g17 = gm.get(17)
        if not big or g15 is None or g17 is None:
            continue
        out.append({
            "SnapshotDate": snapshot,
            "ObservedAtTaipei": observed,
            "Ticker": ticker,
            "Big400Holders": sum(x["holders"] for x in big),
            "Big400Shares": sum(x["shares"] for x in big),
            "Big400Pct": round(sum(x["pct"] for x in big), 6),
            "Big1000Holders": g15["holders"],
            "Big1000Shares": g15["shares"],
            "Big1000Pct": round(g15["pct"], 6),
            "TotalHolders": g17["holders"],
            "TotalShares": g17["shares"],
            "AdjustmentShares": g16["shares"] if g16 else 0,
            "Source": SOURCE_URL,
        })
    if len(out) < 900:
        raise RuntimeError(f"TDCC_SUMMARY_ROWS_TOO_SMALL:{len(out)}")
    return out


def csv_text(rows: list[dict], cols: list[str]) -> str:
    s = io.StringIO(newline="")
    w = csv.DictWriter(s, fieldnames=cols, lineterminator="\n")
    w.writeheader()
    for r in rows:
        w.writerow({c: r.get(c, "") for c in cols})
    return s.getvalue()


def main():
    observed = now_tw().replace(microsecond=0).isoformat()
    raw = fetch()
    source_sha = sha256_bytes(raw)
    rows, stock_tickers, grade_map, snapshot, enc = parse(raw)
    summary = summarize(stock_tickers, grade_map, snapshot, observed)

    snap_dir = OUT / snapshot
    raw_path = snap_dir / "tdcc_1_5_raw.csv"
    summary_path = snap_dir / "tdcc_ownership_4d.csv"
    receipt_path = snap_dir / "receipt.json"

    if raw_path.exists():
        old_sha = sha256_bytes(raw_path.read_bytes())
        if old_sha != source_sha:
            raise RuntimeError(f"TDCC_SAME_DATE_SOURCE_CHANGED:{snapshot}:{old_sha}:{source_sha}")
        # Already persisted. Refresh only latest/check receipt; do not rewrite snapshot provenance.
        latest = {
            "system": "HENGCE",
            "artifact": "TDCC_OWNERSHIP_LATEST_POINTER",
            "status": "UNCHANGED",
            "snapshot_date": snapshot,
            "checked_at_taipei": observed,
            "source_sha256": source_sha,
            "snapshot_path": f"ownership/tdcc/{snapshot}",
            "source": SOURCE_URL,
            "model_authority_created": False,
        }
        atomic_json(OUT / "latest.json", latest)
        print(json.dumps(latest, ensure_ascii=False))
        return 0

    snap_dir.mkdir(parents=True, exist_ok=True)
    atomic_bytes(raw_path, raw)
    atomic_text(summary_path, csv_text(summary, SUMMARY_COLS))
    summary_sha = sha256_bytes(summary_path.read_bytes())

    receipt = {
        "system": "HENGCE",
        "artifact": "TDCC_OWNERSHIP_ORIGINAL_VESSEL_RECEIPT",
        "status": "COMPLETE",
        "snapshot_date": snapshot,
        "observed_at_taipei": observed,
        "source": SOURCE_URL,
        "source_owner": "TDCC",
        "source_dataset": "1-5 集保戶股權分散表",
        "source_encoding": enc,
        "source_rows": len(rows),
        "stock_4d_tickers": len(stock_tickers),
        "summary_rows": len(summary),
        "source_sha256": source_sha,
        "summary_sha256": summary_sha,
        "big400_definition": "holding grades 12+13+14+15 (>=400,001 shares)",
        "big1000_definition": "holding grade 15 (>=1,000,001 shares)",
        "snapshot_frequency": "WEEKLY_TDCC_LAST_BUSINESS_DAY",
        "download_frequency": "DAILY_CHECK_IDEMPOTENT",
        "same_date_revision_policy": "FAIL_CLOSED_MANUAL_REVIEW",
        "point_in_time_policy": "USE_OBSERVED_AT; DO_NOT BACKFILL INTO EARLIER DAILY STATES",
        "model_authority_created": False,
    }
    atomic_json(receipt_path, receipt)
    atomic_json(OUT / "latest.json", {
        "system": "HENGCE",
        "artifact": "TDCC_OWNERSHIP_LATEST_POINTER",
        "status": "COMPLETE",
        "snapshot_date": snapshot,
        "observed_at_taipei": observed,
        "source_sha256": source_sha,
        "summary_sha256": summary_sha,
        "summary_rows": len(summary),
        "snapshot_path": f"ownership/tdcc/{snapshot}",
        "source": SOURCE_URL,
        "model_authority_created": False,
    })
    print(json.dumps(receipt, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
