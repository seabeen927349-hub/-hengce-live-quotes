#!/usr/bin/env python3
"""HENGCE IF-07 V0.1 Stage B exact metadata executor v0.2.

Execution-only engineering correction. ZERO prices/returns.
Frozen behavior restored:
- exact admitted 187-event authority only
- exact 128 candidate tickers derived from that manifest
- deterministic ticker order
- ONE blank-year official t57 query per ticker
- ZERO retry / ZERO backoff rescue
- any transport/rate-limit/structural ambiguity => fail closed
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup

CHALLENGER = "IF07_EARNINGS_QUALITY_ZERO_RED_FLAG_V0_1"
EXPECTED_ROWS_SHA256 = "64ea76312f99413965edc8ca9797864ef04d3ba8c2cee1f47bf950ffa9fa3bfb"
EXPECTED_CANDIDATES = 187
EXPECTED_UNIQUE_TICKERS = 128
URL = "https://doc.twse.com.tw/server-java/t57sb01"
UA = "Mozilla/5.0 HENGCE-IF07-stage-b-exact-metadata-v0.2"
QMAP = {"一": 1, "二": 2, "三": 3, "四": 4}
RE_PERIOD = re.compile(r"(?P<roc>\d+)\s*年\s*第(?P<q>[一二三四])季")
RE_UPLOAD = re.compile(r"(?P<roc>\d{2,3})/(?P<m>\d{2})/(?P<d>\d{2})\s+(?P<h>\d{2}):(?P<mi>\d{2}):(?P<s>\d{2})")
BLOCK_MARKERS = (
    "查詢過量",
    "access denied",
    "this page can not be accessed",
    "this page cannot be accessed",
    "for security reasons",
)
MEMBERSHIP_SHA256 = {
    2023: "296f19c0c676e558007b22f12e08ba9f81045ad3706d9609b7a151974b6ece3e",
    2024: "13c8ffe2cb6cfaaa2516c90482d0aecda933cb33ae4eb1cffbbc90e49d77bd7d",
    2025: "da4a8c6deb7cad5d221d453b64e2685b771242db6ce8fc5128d11aa21cfe7e14",
}
MEMBERSHIP_PARENT_COMMIT = "f5abef555d9174e3919a9dca52e9bfb07351e02e"


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_upload(value: str) -> dt.datetime | None:
    m = RE_UPLOAD.fullmatch(value.strip())
    if not m:
        return None
    try:
        return dt.datetime(
            int(m["roc"]) + 1911,
            int(m["m"]), int(m["d"]),
            int(m["h"]), int(m["mi"]), int(m["s"]),
        )
    except ValueError:
        return None


def blocked(text: str) -> bool:
    low = text.lower()
    return any(x.lower() in low for x in BLOCK_MARKERS)


def parse_t57(text: str, ticker: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(text, "lxml")
    rows: list[dict[str, Any]] = []
    for tr in soup.find_all("tr"):
        cells = [" ".join(td.stripped_strings) for td in tr.find_all(["td", "th"])]
        if len(cells) < 11 or ticker not in cells:
            continue
        if cells[5] != "IFRSs合併財報":
            continue
        pm = RE_PERIOD.search(cells[1])
        if not pm:
            continue
        upload = parse_upload(cells[9])
        rows.append({
            "ticker": ticker,
            "fiscal_year": int(pm["roc"]) + 1911,
            "quarter": QMAP[pm["q"]],
            "period_text": cells[1],
            "report_type": cells[5],
            "file_name": cells[7],
            "file_size_text": cells[8],
            "upload_text": cells[9],
            "upload_ts_taipei": upload.isoformat() if upload else None,
            "correction_field": cells[10],
            "correction_exact_none": cells[10] == "無",
            "cells": cells,
        })
    return rows


def fetch_once(session: requests.Session, ticker: str, raw_dir: Path) -> dict[str, Any]:
    params = {"step": "1", "colorchg": "1", "co_id": ticker, "year": "", "seamon": "", "mtype": "A"}
    try:
        r = session.get(URL, params=params, timeout=45)
        raw = r.content
        text = raw.decode("big5", errors="replace")
        raw_path = raw_dir / f"{ticker}.html"
        raw_path.write_bytes(raw)
        is_blocked = blocked(text)
        rows = parse_t57(text, ticker) if r.status_code == 200 and not is_blocked else []
        status = "RESOLVED_RESPONSE" if r.status_code == 200 and not is_blocked else "FAIL_CLOSED_TRANSPORT_OR_RATE_LIMIT"
        return {
            "ticker": ticker,
            "request_count": 1,
            "retry_count": 0,
            "request_params": params,
            "http_status": r.status_code,
            "bytes": len(raw),
            "sha256": sha256_bytes(raw),
            "blocked": is_blocked,
            "status": status,
            "rows": rows,
            "raw_file": raw_path.name,
            "error": None,
        }
    except Exception as e:
        return {
            "ticker": ticker,
            "request_count": 1,
            "retry_count": 0,
            "request_params": params,
            "http_status": None,
            "bytes": None,
            "sha256": None,
            "blocked": False,
            "status": "FAIL_CLOSED_TRANSPORT_OR_RATE_LIMIT",
            "rows": [],
            "raw_file": None,
            "error": f"{type(e).__name__}:{e}",
        }


def load_sessions(path: Path) -> list[dt.date]:
    o = json.loads(path.read_text(encoding="utf-8"))
    dates: list[dt.date] = []
    for y in sorted(o["years"], key=int):
        dates.extend(dt.date.fromisoformat(x) for x in o["years"][y]["dates"])
    return sorted(set(dates))


def resolve_signal(upload_ts: dt.datetime, sessions: list[dt.date]) -> dt.date | None:
    sset = set(sessions)
    d = upload_ts.date()
    if d in sset and upload_ts.time() < dt.time(13, 30, 0):
        return d
    for sd in sessions:
        if sd > d:
            return sd
    return None


def load_membership(path: Path, year: int) -> tuple[set[tuple[str, str]], set[str], dict[str, Any]]:
    actual = sha256_file(path)
    expected = MEMBERSHIP_SHA256[year]
    if actual != expected:
        raise RuntimeError(f"MEMBERSHIP_SHA256_MISMATCH:{year}:{actual}!={expected}")
    pairs: set[tuple[str, str]] = set()
    dates: set[str] = set()
    count = 0
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != ["Date", "Ticker", "Name"]:
            raise RuntimeError(f"MEMBERSHIP_SCHEMA_MISMATCH:{year}:{reader.fieldnames}")
        for row in reader:
            date = str(row["Date"]).strip()
            ticker = str(row["Ticker"]).strip()
            if not date or not ticker:
                raise RuntimeError(f"MEMBERSHIP_BLANK_KEY:{year}:{count+2}")
            pairs.add((date, ticker))
            dates.add(date)
            count += 1
    return pairs, dates, {
        "year": year,
        "path": str(path),
        "rows": count,
        "dates": len(dates),
        "sha256": actual,
        "parent_commit": MEMBERSHIP_PARENT_COMMIT,
    }


def horizon_dates(signal_date: str, sessions: list[dt.date], horizon: int = 20) -> dict[str, str | None]:
    sd = dt.date.fromisoformat(signal_date)
    try:
        si = sessions.index(sd)
    except ValueError:
        return {"entry_date": None, "exit_date": None}
    entry_i = si + 1
    exit_i = entry_i + horizon - 1
    if entry_i >= len(sessions) or exit_i >= len(sessions):
        return {"entry_date": None, "exit_date": None}
    return {"entry_date": sessions[entry_i].isoformat(), "exit_date": sessions[exit_i].isoformat()}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--stage-a-rows", type=Path, required=True)
    ap.add_argument("--sessions", type=Path, required=True)
    ap.add_argument("--membership-2023", type=Path, required=True)
    ap.add_argument("--membership-2024", type=Path, required=True)
    ap.add_argument("--membership-2025", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()

    out = args.out_dir
    raw_dir = out / "raw_t57"
    raw_dir.mkdir(parents=True, exist_ok=True)

    stage_a_sha = sha256_file(args.stage_a_rows)
    if stage_a_sha != EXPECTED_ROWS_SHA256:
        raise RuntimeError(f"STAGE_A_ROWS_SHA256_MISMATCH:{stage_a_sha}")

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    if manifest.get("verdict") != "PASS_STAGE_B_MANIFEST_ADMISSION_NO_NETWORK":
        raise RuntimeError("OFFLINE_ADMISSION_NOT_PASS")
    if manifest.get("input_stage_a_rows_sha256") != EXPECTED_ROWS_SHA256:
        raise RuntimeError("MANIFEST_STAGE_A_SHA_MISMATCH")
    req = manifest.get("request_rows", [])
    if len(req) != EXPECTED_CANDIDATES:
        raise RuntimeError(f"CANDIDATE_COUNT_MISMATCH:{len(req)}")
    tickers = sorted({str(r["ticker"]) for r in req})
    if len(tickers) != EXPECTED_UNIQUE_TICKERS:
        raise RuntimeError(f"UNIQUE_TICKER_COUNT_MISMATCH:{len(tickers)}")

    sessions = load_sessions(args.sessions)
    membership: dict[int, set[tuple[str, str]]] = {}
    membership_dates: dict[int, set[str]] = {}
    membership_receipts = []
    for year, path in [(2023, args.membership_2023), (2024, args.membership_2024), (2025, args.membership_2025)]:
        p, d, receipt = load_membership(path, year)
        membership[year] = p
        membership_dates[year] = d
        membership_receipts.append(receipt)

    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept-Language": "zh-TW,zh;q=0.9"})
    query_results = []
    by_key: dict[tuple[str, int, int], list[dict[str, Any]]] = defaultdict(list)
    transport_by_ticker: dict[str, str] = {}
    for i, ticker in enumerate(tickers, 1):
        qr = fetch_once(s, ticker, raw_dir)
        query_results.append(qr)
        transport_by_ticker[ticker] = qr["status"]
        for row in qr["rows"]:
            by_key[(ticker, int(row["fiscal_year"]), int(row["quarter"]))].append(row)
        print(f"t57 {i}/{len(tickers)} {ticker} {qr['status']} rows={len(qr['rows'])}", flush=True)

    write_json(out / "IF07_STAGE_B_V0_2_T57_RAW_INDEX_NO_RETURNS.json", {
        "system": "HENGCE",
        "artifact": "IF07_STAGE_B_V0_2_T57_RAW_INDEX_NO_RETURNS",
        "challenger": CHALLENGER,
        "contains_price_or_forward_return_data": False,
        "official_source": URL,
        "query_mode": "ONE_BLANK_YEAR_QUERY_PER_FROZEN_CANDIDATE_TICKER",
        "request_order": tickers,
        "request_count": len(query_results),
        "retry_count_total": 0,
        "query_results": query_results,
    })

    events = []
    reasons_count: Counter[str] = Counter()
    for r in req:
        ticker = str(r["ticker"])
        y = int(r["fiscal_year"])
        q = int(r["quarter"])
        reasons: list[str] = []
        cur_rows = by_key.get((ticker, y, q), [])
        prior_rows = by_key.get((ticker, y - 1, q), [])
        if transport_by_ticker.get(ticker) != "RESOLVED_RESPONSE":
            reasons.append("T57_TRANSPORT_OR_RATE_LIMIT_FAIL_CLOSED")
        if len(cur_rows) != 1:
            reasons.append(f"CURRENT_USABLE_ROW_COUNT_{len(cur_rows)}")
        if len(prior_rows) != 1:
            reasons.append(f"PRIOR_USABLE_ROW_COUNT_{len(prior_rows)}")
        cur = cur_rows[0] if len(cur_rows) == 1 else None
        prior = prior_rows[0] if len(prior_rows) == 1 else None
        if cur is not None:
            if cur["correction_field"] != "無":
                reasons.append("CURRENT_CORRECTION_NOT_EXACT_NONE")
            if not cur["upload_ts_taipei"]:
                reasons.append("CURRENT_UPLOAD_TS_UNPARSEABLE")
        if prior is not None:
            if prior["correction_field"] != "無":
                reasons.append("PRIOR_CORRECTION_NOT_EXACT_NONE")
            if not prior["upload_ts_taipei"]:
                reasons.append("PRIOR_UPLOAD_TS_UNPARSEABLE")

        signal_date = None
        pit_date_covered = None
        pit_member = None
        hd = {"entry_date": None, "exit_date": None}
        if not reasons and cur is not None:
            sd = resolve_signal(dt.datetime.fromisoformat(cur["upload_ts_taipei"]), sessions)
            if sd is None:
                reasons.append("SIGNAL_DATE_SESSION_COVERAGE_BLOCKED")
            else:
                signal_date = sd.isoformat()
                hd = horizon_dates(signal_date, sessions, 20)
                if hd["entry_date"] is None or hd["exit_date"] is None:
                    reasons.append("PRIMARY_HORIZON_SESSION_COVERAGE_BLOCKED")
                sy = sd.year
                if sy not in membership:
                    pit_date_covered = False
                    reasons.append(f"PIT_MEMBERSHIP_YEAR_NOT_LOADED_{sy}")
                elif signal_date not in membership_dates[sy]:
                    pit_date_covered = False
                    reasons.append("PIT_MEMBERSHIP_DATE_COVERAGE_BLOCKED")
                else:
                    pit_date_covered = True
                    pit_member = (signal_date, ticker) in membership[sy]
                    if not pit_member:
                        reasons.append("PIT_ELECTRONICS_MEMBERSHIP_FAIL")

        for reason in reasons:
            reasons_count[reason] += 1
        events.append({
            "event_id": f"{ticker}:{y}Q{q}",
            "ticker": ticker,
            "fiscal_year": y,
            "quarter": q,
            "stage_a_candidate": True,
            "current_metadata_rows": cur_rows,
            "prior_metadata_rows": prior_rows,
            "signal_date": signal_date,
            "primary_20_entry_date": hd["entry_date"],
            "primary_20_exit_date": hd["exit_date"],
            "pit_membership_date_covered": pit_date_covered,
            "pit_electronics_membership": pit_member,
            "stage_b_pass": not reasons,
            "exclusion_reasons": reasons,
        })

    if len({e["event_id"] for e in events}) != EXPECTED_CANDIDATES:
        raise RuntimeError("DUPLICATE_EVENT_ID_AFTER_STAGE_B")

    passed = [e for e in events if e["stage_b_pass"]]
    discovery = [e for e in passed if e["signal_date"] and "2023-01-01" <= e["signal_date"] <= "2024-12-31"]
    disc_events = len(discovery)
    disc_tickers = len({e["ticker"] for e in discovery})
    disc_dates = len({e["signal_date"] for e in discovery})
    sufficient = disc_events >= 80 and disc_tickers >= 40 and disc_dates >= 20

    panel = {
        "system": "HENGCE",
        "artifact": "IF07_STAGE_B_V0_2_NO_RETURN_EVENT_PANEL",
        "challenger": CHALLENGER,
        "contains_price_or_forward_return_data": False,
        "input_stage_a_rows_sha256": stage_a_sha,
        "candidate_authority_count": len(events),
        "stage_b_pass_count": len(passed),
        "events": events,
    }
    write_json(out / "IF07_STAGE_B_V0_2_NO_RETURN_EVENT_PANEL.json", panel)

    audit = {
        "system": "HENGCE",
        "artifact": "IF07_STAGE_B_V0_2_NO_RETURN_AUDIT",
        "challenger": CHALLENGER,
        "contains_price_or_forward_return_data": False,
        "selection_rules_changed": False,
        "transport_policy": "ONE_BLANK_YEAR_REQUEST_PER_TICKER_ZERO_RETRY_FAIL_CLOSED",
        "input_stage_a_rows_sha256": stage_a_sha,
        "offline_admission_verdict": manifest["verdict"],
        "candidate_authority_count": len(events),
        "candidate_authority_unique_tickers": len(tickers),
        "official_t57_request_count": len(query_results),
        "official_t57_retry_count": 0,
        "t57_transport_fail_closed_tickers": sum(1 for x in query_results if x["status"] != "RESOLVED_RESPONSE"),
        "metadata_signal_pit_pass_count": len(passed),
        "metadata_signal_pit_excluded_count": len(events) - len(passed),
        "exclusion_reason_counts": dict(sorted(reasons_count.items())),
        "membership_receipts": membership_receipts,
        "discovery_count_only": {
            "events": disc_events,
            "unique_tickers": disc_tickers,
            "distinct_signal_dates": disc_dates,
            "minimum_events": 80,
            "minimum_unique_tickers": 40,
            "minimum_distinct_signal_dates": 20,
            "sufficient": sufficient,
        },
        "forward_returns_inspected": False,
        "discovery_returns_authorized": sufficient,
        "preregistered_no_return_gate_judgment": "PASS_AUTHORIZE_DISCOVERY_RETURNS" if sufficient else "INCONCLUSIVE_COUNT_INSUFFICIENT_DO_NOT_OPEN_RETURNS",
        "next_legal_step": "OPEN_DISCOVERY_RETURNS_UNDER_FROZEN_V0_1" if sufficient else "STOP_NO_RETURN_COUNT_GATE_INCONCLUSIVE",
        "github_run": {
            "repository": os.getenv("GITHUB_REPOSITORY"),
            "run_id": os.getenv("GITHUB_RUN_ID"),
            "run_attempt": os.getenv("GITHUB_RUN_ATTEMPT"),
            "sha": os.getenv("GITHUB_SHA"),
            "ref": os.getenv("GITHUB_REF"),
        },
    }
    write_json(out / "IF07_STAGE_B_V0_2_NO_RETURN_AUDIT.json", audit)

    checks = []
    for p in sorted(out.rglob("*")):
        if p.is_file() and p.name != "CHECKSUMS.json":
            checks.append({"path": str(p.relative_to(out)), "sha256": sha256_file(p), "bytes": p.stat().st_size})
    write_json(out / "CHECKSUMS.json", {"files": checks})

    print(json.dumps({
        "candidate_authority_count": len(events),
        "unique_candidate_tickers": len(tickers),
        "official_t57_request_count": len(query_results),
        "official_t57_retry_count": 0,
        "transport_fail_closed_tickers": audit["t57_transport_fail_closed_tickers"],
        "stage_b_pass_count": len(passed),
        "stage_b_excluded_count": len(events) - len(passed),
        "discovery_events": disc_events,
        "discovery_unique_tickers": disc_tickers,
        "discovery_distinct_signal_dates": disc_dates,
        "discovery_count_sufficient": sufficient,
        "judgment": audit["preregistered_no_return_gate_judgment"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
