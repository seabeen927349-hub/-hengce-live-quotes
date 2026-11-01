#!/usr/bin/env python3
"""HENGCE official TDCC ownership-distribution canonical vessel.

Source: TDCC open data dataset 1-5 (集保戶股權分散表).

Governance:
- official TDCC only; no third-party fallback;
- one network response per canonical check; ownership + availability provenance
  are derived from the exact same response bytes;
- raw source bytes are preserved;
- prospective first-observed provenance is append-only and never backdated;
- official_published_at remains null without independent official proof;
- 400-lot holders = grades 12-15;
- 1000-lot holders = grade 15;
- grades 16/17 are adjustment/total and are not included in big-holder sums;
- no technical-analysis/model/trading authority is created here;
- same-date source revision is fail-closed for manual review.

This vessel checks frequently for prospective availability provenance, while TDCC
ownership snapshots themselves remain weekly evidence.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

TZ = ZoneInfo("Asia/Taipei")
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "ownership" / "tdcc"
PROV = OUT / "provenance"
SOURCE_URL = "https://opendata.tdcc.com.tw/getOD.ashx?id=1-5"
PROTOCOL_COMMIT = "08497a8106ac6acd8799a4fe256eb102dca2bb9c"
PROVENANCE_SOURCE_AUTHORITY = "CANONICAL_VESSEL_RESPONSE_ONLY"
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


def github_event_schedule() -> str | None:
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if not event_path:
        return None
    p = Path(event_path)
    if not p.exists():
        return None
    try:
        event = json.loads(p.read_text(encoding="utf-8"))
        value = event.get("schedule")
        return str(value) if value is not None else None
    except Exception:
        return None


def fetch() -> tuple[bytes, dict]:
    request_started = now_tw()
    r = requests.get(
        SOURCE_URL,
        timeout=45,
        headers={
            "User-Agent": "Mozilla/5.0 HENGCE-TDCC-OWNERSHIP/2.0-CANONICAL-PROVENANCE",
            "Accept": "text/csv,*/*;q=0.8",
            "Referer": "https://www.tdcc.com.tw/",
        },
    )
    raw = r.content
    response_received = now_tw()
    r.raise_for_status()
    if len(raw) < 100_000:
        raise RuntimeError(f"TDCC_RESPONSE_TOO_SMALL:{len(raw)}")
    return raw, {
        "request_started_at_taipei": request_started.isoformat(),
        "response_received_at_taipei": response_received.isoformat(),
        "http_status": r.status_code,
        "http_date": r.headers.get("Date"),
        "http_last_modified": r.headers.get("Last-Modified"),
        "http_etag": r.headers.get("ETag"),
        "http_content_type": r.headers.get("Content-Type"),
        "http_content_length": r.headers.get("Content-Length"),
    }


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
    grade_map = {}
    for r in stock_rows:
        grade_map.setdefault(r["ticker"], {})[r["grade"]] = r
    total_count = sum(1 for t in stock_tickers if 17 in grade_map.get(t, {}))
    if total_count < int(len(stock_tickers) * 0.95):
        raise RuntimeError(f"TDCC_TOTAL_ROW_COVERAGE_TOO_LOW:{total_count}/{len(stock_tickers)}")
    return rows, stock_tickers, grade_map, snapshot, enc, headers


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


def record_provenance(raw: bytes, snapshot: str, source_encoding: str, csv_headers: list[str], fetch_meta: dict) -> tuple[bool, Path]:
    """Persist prospective provenance from the SAME canonical response bytes. No network I/O."""
    payload_sha = sha256_bytes(raw)
    received = datetime.fromisoformat(fetch_meta["response_received_at_taipei"])
    payloads = PROV / "payloads"
    first_dir = PROV / "first_observed"
    attempts = PROV / "attempts" / received.strftime("%Y") / received.strftime("%m") / received.strftime("%d")
    for p in (payloads, first_dir, attempts):
        p.mkdir(parents=True, exist_ok=True)
    payload_path = payloads / f"{payload_sha}.csv"
    if not payload_path.exists():
        atomic_bytes(payload_path, raw)
    elif sha256_bytes(payload_path.read_bytes()) != payload_sha:
        raise RuntimeError(f"TDCC_PROVENANCE_PAYLOAD_HASH_MISMATCH:{payload_sha}")

    first_path = first_dir / f"{payload_sha}.json"
    is_new = not first_path.exists()
    event_name = os.environ.get("GITHUB_EVENT_NAME")
    schedule = github_event_schedule()
    run_id = os.environ.get("GITHUB_RUN_ID")
    run_attempt = os.environ.get("GITHUB_RUN_ATTEMPT")
    common = {
        "schema_version": 4,
        "endpoint": SOURCE_URL,
        "payload_sha256": payload_sha,
        "snapshot_reference_date": datetime.strptime(snapshot, "%Y%m%d").date().isoformat(),
        "request_started_at_taipei": fetch_meta["request_started_at_taipei"],
        "response_received_at_taipei": fetch_meta["response_received_at_taipei"],
        "http_status": fetch_meta.get("http_status"),
        "http_date": fetch_meta.get("http_date"),
        "http_last_modified": fetch_meta.get("http_last_modified"),
        "http_etag": fetch_meta.get("http_etag"),
        "github_event_name": event_name,
        "github_schedule": schedule,
        "github_run_id": run_id,
        "github_run_attempt": run_attempt,
        "github_workflow": os.environ.get("GITHUB_WORKFLOW"),
        "github_workflow_ref": os.environ.get("GITHUB_WORKFLOW_REF"),
        "github_sha_at_trigger": os.environ.get("GITHUB_SHA"),
        "schedule_proof": event_name == "schedule",
        "prospective_protocol_commit": PROTOCOL_COMMIT,
        "historical_latency_status": "DATA_BLOCKED",
        "prospective_live_latency_status": "COLLECTING",
        "official_published_at": None,
        "provenance_source_authority": PROVENANCE_SOURCE_AUTHORITY,
        "network_fetch_count_for_this_payload": 1,
        "ownership_and_provenance_share_exact_response_bytes": True,
        "authority": "SHADOW_PROSPECTIVE_AVAILABILITY_RESEARCH_ONLY_NO_TRADING_AUTHORITY",
    }
    if is_new:
        atomic_json(first_path, {
            **common,
            "first_observed_at_taipei": fetch_meta["response_received_at_taipei"],
            "first_observed_at_utc": received.astimezone(timezone.utc).isoformat(),
            "decoded_encoding": source_encoding,
            "csv_header": csv_headers,
            "payload_path": str(payload_path.relative_to(ROOT)),
            "publication_provenance_status": "OFFICIAL_PUBLICATION_TIMESTAMP_NOT_INDEPENDENTLY_PROVEN",
            "availability_semantics": "CANONICAL_VESSEL_FIRST_OBSERVED_PUBLIC_ENDPOINT_RECEIPT_NOT_OFFICIAL_PUBLISHED_AT",
        })
    stamp = received.strftime("%Y%m%dT%H%M%S%f%z")
    attempt_id = f"TDCC_CANONICAL_{stamp}_RUN{run_id or 'LOCAL'}_A{run_attempt or '0'}"
    atomic_json(attempts / f"{attempt_id}.json", {
        **common,
        "attempt_id": attempt_id,
        "new_payload_first_observed": is_new,
        "first_observed_record": str(first_path.relative_to(ROOT)),
    })
    atomic_json(PROV / "current.json", {
        **common,
        "last_canonical_response_received_at_taipei": fetch_meta["response_received_at_taipei"],
        "first_observed_record": str(first_path.relative_to(ROOT)),
        "new_payload_first_observed": is_new,
        "publication_provenance_status": "OFFICIAL_PUBLICATION_TIMESTAMP_NOT_INDEPENDENTLY_PROVEN",
    })
    return is_new, first_path


def main():
    raw, fetch_meta = fetch()
    observed = fetch_meta["response_received_at_taipei"]
    source_sha = sha256_bytes(raw)
    rows, stock_tickers, grade_map, snapshot, enc, headers = parse(raw)
    summary = summarize(stock_tickers, grade_map, snapshot, observed)
    snap_dir = OUT / snapshot
    raw_path = snap_dir / "tdcc_1_5_raw.csv"
    summary_path = snap_dir / "tdcc_ownership_4d.csv"
    receipt_path = snap_dir / "receipt.json"

    if raw_path.exists():
        old_sha = sha256_bytes(raw_path.read_bytes())
        if old_sha != source_sha:
            raise RuntimeError(f"TDCC_SAME_DATE_SOURCE_CHANGED:{snapshot}:{old_sha}:{source_sha}")
    else:
        snap_dir.mkdir(parents=True, exist_ok=True)
        atomic_bytes(raw_path, raw)
        atomic_text(summary_path, csv_text(summary, SUMMARY_COLS))
        summary_sha = sha256_bytes(summary_path.read_bytes())
        atomic_json(receipt_path, {
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
            "download_frequency": "CANONICAL_FREQUENT_CHECK_IDEMPOTENT",
            "same_date_revision_policy": "FAIL_CLOSED_MANUAL_REVIEW",
            "point_in_time_policy": "USE_RESPONSE_RECEIVED_AT; DO NOT BACKFILL INTO EARLIER DAILY STATES",
            "provenance_source_authority": PROVENANCE_SOURCE_AUTHORITY,
            "model_authority_created": False,
        })

    is_new_provenance, first_path = record_provenance(raw, snapshot, enc, headers, fetch_meta)
    summary_sha = sha256_bytes(summary_path.read_bytes()) if summary_path.exists() else None
    latest = {
        "system": "HENGCE",
        "artifact": "TDCC_OWNERSHIP_LATEST_POINTER",
        "status": "COMPLETE" if is_new_provenance else "UNCHANGED",
        "snapshot_date": snapshot,
        "checked_at_taipei": observed,
        "source_sha256": source_sha,
        "summary_sha256": summary_sha,
        "summary_rows": len(summary),
        "snapshot_path": f"ownership/tdcc/{snapshot}",
        "source": SOURCE_URL,
        "provenance_first_observed_record": str(first_path.relative_to(ROOT)),
        "provenance_source_authority": PROVENANCE_SOURCE_AUTHORITY,
        "historical_latency_status": "DATA_BLOCKED",
        "prospective_live_latency_status": "COLLECTING",
        "model_authority_created": False,
        "trading_authority_created": False,
    }
    atomic_json(OUT / "latest.json", latest)
    print(json.dumps(latest, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
