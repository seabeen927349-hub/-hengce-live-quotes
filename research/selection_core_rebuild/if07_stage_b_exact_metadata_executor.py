#!/usr/bin/env python3
"""HENGCE IF-07 V0.1 Stage B exact-metadata + no-return PIT gate executor.

Execution-only implementation of frozen contracts. It has zero Selection authority,
does not inspect prices/returns, and cannot change candidate identities or rules.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import re
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup

CHALLENGER = "IF07_EARNINGS_QUALITY_ZERO_RED_FLAG_V0_1"
EXPECTED_ROWS_SHA256 = "64ea76312f99413965edc8ca9797864ef04d3ba8c2cee1f47bf950ffa9fa3bfb"
EXPECTED_CANDIDATES = 187
EXPECTED_UNIQUE_TICKERS = 128
EXPECTED_MEMBERSHIP_SHA256 = {
    2023: "296f19c0c676e558007b22f12e08ba9f81045ad3706d9609b7a151974b6ece3e",
    2024: "13c8ffe2cb6cfaaa2516c90482d0aecda933cb33ae4eb1cffbbc90e49d77bd7d",
    2025: "da4a8c6deb7cad5d221d453b64e2685b771242db6ce8fc5128d11aa21cfe7e14",
}
MEMBERSHIP_PARENT_COMMIT = "f5abef555d9174e3919a9dca52e9bfb07351e02e"
URL = "https://doc.twse.com.tw/server-java/t57sb01"
QMAP = {"一": 1, "二": 2, "三": 3, "四": 4}
RE_PERIOD = re.compile(r"(?P<roc>\d+)\s*年\s*第(?P<q>[一二三四])季")
RE_UPLOAD = re.compile(
    r"(?P<roc>\d{2,3})/(?P<m>\d{2})/(?P<d>\d{2})\s+"
    r"(?P<h>\d{2}):(?P<mi>\d{2}):(?P<s>\d{2})"
)
BLOCK_MARKERS = (
    "查詢過量",
    "access denied",
    "this page can not be accessed",
    "this page cannot be accessed",
    "for security reasons",
)
UA = "Mozilla/5.0 HENGCE-IF07-stage-b-exact-metadata/0.1"


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def atomic_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def parse_upload(text: str | None) -> dt.datetime | None:
    if not text:
        return None
    m = RE_UPLOAD.fullmatch(text.strip())
    if not m:
        return None
    try:
        return dt.datetime(
            int(m["roc"]) + 1911, int(m["m"]), int(m["d"]),
            int(m["h"]), int(m["mi"]), int(m["s"])
        )
    except ValueError:
        return None


def load_sessions(path: Path) -> list[dt.date]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    dates: list[dt.date] = []
    for y in sorted(obj["years"], key=int):
        dates.extend(dt.date.fromisoformat(x) for x in obj["years"][y]["dates"])
    return sorted(set(dates))


def resolve_signal_date(upload_ts: dt.datetime, sessions: list[dt.date]) -> dt.date | None:
    session_set = set(sessions)
    d = upload_ts.date()
    if d in session_set and upload_ts.time() < dt.time(13, 30, 0):
        return d
    for sd in sessions:
        if sd > d:
            return sd
    return None


def load_membership(path: Path, year: int) -> tuple[set[tuple[str, str]], set[str], dict[str, Any]]:
    actual = sha256_file(path)
    expected = EXPECTED_MEMBERSHIP_SHA256[year]
    if actual != expected:
        raise RuntimeError(f"MEMBERSHIP_SHA256_MISMATCH:{year}:{actual}!={expected}")
    pairs: set[tuple[str, str]] = set()
    dates: set[str] = set()
    rows = 0
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != ["Date", "Ticker", "Name"]:
            raise RuntimeError(f"MEMBERSHIP_SCHEMA_MISMATCH:{year}:{reader.fieldnames}")
        for r in reader:
            date = str(r["Date"]).strip()
            ticker = str(r["Ticker"]).strip()
            if not date or not ticker:
                raise RuntimeError(f"MEMBERSHIP_BLANK_KEY:{year}:{rows+2}")
            pairs.add((date, ticker))
            dates.add(date)
            rows += 1
    return pairs, dates, {
        "year": year,
        "path": str(path),
        "rows": rows,
        "dates": len(dates),
        "sha256": actual,
        "parent_commit": MEMBERSHIP_PARENT_COMMIT,
    }


def response_blocked(text: str) -> bool:
    low = text.lower()
    return any(m.lower() in low for m in BLOCK_MARKERS)


def parse_t57_rows(text: str, ticker: str, year: int) -> list[dict[str, Any]]:
    soup = BeautifulSoup(text, "lxml")
    out: list[dict[str, Any]] = []
    for tr in soup.find_all("tr"):
        cells = [" ".join(td.stripped_strings) for td in tr.find_all(["td", "th"])]
        if len(cells) < 11 or ticker not in cells:
            continue
        if cells[5] != "IFRSs合併財報":
            continue
        pm = RE_PERIOD.search(cells[1])
        if not pm:
            continue
        fy = int(pm["roc"]) + 1911
        q = QMAP[pm["q"]]
        if fy != year:
            continue
        upload = parse_upload(cells[9])
        out.append({
            "ticker": ticker,
            "fiscal_year": fy,
            "quarter": q,
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
    return out


def fetch_t57(session: requests.Session, ticker: str, year: int, raw_dir: Path) -> dict[str, Any]:
    params = {
        "step": "1", "colorchg": "1", "co_id": ticker,
        "year": str(year - 1911), "seamon": "", "mtype": "A",
    }
    delays = [0, 2, 5, 10, 20, 40]
    attempts: list[dict[str, Any]] = []
    last_error: str | None = None
    for attempt, delay in enumerate(delays, 1):
        if delay:
            time.sleep(delay)
        try:
            r = session.get(URL, params=params, timeout=60)
            raw = r.content
            text = raw.decode("big5", errors="replace")
            raw_path = raw_dir / f"{ticker}_{year}_attempt{attempt}.html"
            raw_path.write_bytes(raw)
            blocked = response_blocked(text)
            attempts.append({
                "attempt": attempt,
                "http_status": r.status_code,
                "bytes": len(raw),
                "sha256": sha256_bytes(raw),
                "blocked": blocked,
                "raw_file": raw_path.name,
                "body_text_prefix": " ".join(BeautifulSoup(text, "lxml").stripped_strings)[:300],
            })
            if r.status_code == 200 and not blocked:
                return {
                    "ticker": ticker,
                    "year": year,
                    "roc_year": year - 1911,
                    "request_params": params,
                    "status": "RESOLVED_RESPONSE",
                    "attempts": attempts,
                    "rows": parse_t57_rows(text, ticker, year),
                    "error": None,
                }
            last_error = f"HTTP_OR_BLOCK:{r.status_code}:blocked={blocked}"
        except Exception as e:
            last_error = f"{type(e).__name__}:{e}"
            attempts.append({
                "attempt": attempt, "http_status": None, "bytes": None,
                "sha256": None, "blocked": False, "raw_file": None, "error": last_error,
            })
    return {
        "ticker": ticker, "year": year, "roc_year": year - 1911,
        "request_params": params, "status": "UNRESOLVED_TRANSPORT",
        "attempts": attempts, "rows": [], "error": last_error,
    }


def event_horizon_dates(signal_date: str, sessions: list[dt.date], horizon: int = 20) -> dict[str, str | None]:
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
    out.mkdir(parents=True, exist_ok=True)
    raw_dir = out / "raw_t57"
    raw_dir.mkdir(parents=True, exist_ok=True)

    stage_a_sha = sha256_file(args.stage_a_rows)
    if stage_a_sha != EXPECTED_ROWS_SHA256:
        raise RuntimeError(f"STAGE_A_ROWS_SHA256_MISMATCH:{stage_a_sha}")
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    if manifest.get("verdict") != "PASS_STAGE_B_MANIFEST_ADMISSION_NO_NETWORK":
        raise RuntimeError(f"ADMISSION_NOT_PASS:{manifest.get('verdict')}")
    if manifest.get("input_stage_a_rows_sha256") != EXPECTED_ROWS_SHA256:
        raise RuntimeError("MANIFEST_INPUT_SHA_MISMATCH")
    req = manifest.get("request_rows", [])
    if len(req) != EXPECTED_CANDIDATES:
        raise RuntimeError(f"MANIFEST_CANDIDATE_COUNT:{len(req)}")
    if len({str(r["ticker"]) for r in req}) != EXPECTED_UNIQUE_TICKERS:
        raise RuntimeError("MANIFEST_UNIQUE_TICKER_COUNT_MISMATCH")

    sessions = load_sessions(args.sessions)
    membership: dict[int, set[tuple[str, str]]] = {}
    membership_dates: dict[int, set[str]] = {}
    membership_receipts: list[dict[str, Any]] = []
    for year, path in [(2023, args.membership_2023), (2024, args.membership_2024), (2025, args.membership_2025)]:
        p, d, rec = load_membership(path, year)
        membership[year] = p
        membership_dates[year] = d
        membership_receipts.append(rec)

    needed_pairs = sorted(
        {(str(r["ticker"]), int(r["fiscal_year"])) for r in req}
        | {(str(r["ticker"]), int(r["fiscal_year"]) - 1) for r in req}
    )
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept-Language": "zh-TW,zh;q=0.9"})
    query_results: list[dict[str, Any]] = []
    lookup: dict[tuple[str, int, int], list[dict[str, Any]]] = defaultdict(list)
    for i, (ticker, year) in enumerate(needed_pairs, 1):
        qr = fetch_t57(s, ticker, year, raw_dir)
        query_results.append(qr)
        for row in qr["rows"]:
            lookup[(ticker, int(row["fiscal_year"]), int(row["quarter"]))].append(row)
        print(f"t57 {i}/{len(needed_pairs)} {ticker} {year} {qr['status']} rows={len(qr['rows'])}", flush=True)
        time.sleep(0.35)

    atomic_json(out / "IF07_STAGE_B_T57_QUERY_RESULTS_RAW_INDEX.json", {
        "system": "HENGCE", "artifact": "IF07_STAGE_B_T57_QUERY_RESULTS_RAW_INDEX",
        "challenger": CHALLENGER, "contains_price_or_forward_return_data": False,
        "official_source": URL, "query_mode": "CANDIDATE_ONLY_EXPLICIT_TICKER_X_YEAR",
        "query_count": len(query_results), "query_results": query_results,
    })

    events: list[dict[str, Any]] = []
    exclusion_counts: Counter[str] = Counter()
    for r in req:
        ticker = str(r["ticker"]); y = int(r["fiscal_year"]); q = int(r["quarter"])
        current_qr = next((x for x in query_results if x["ticker"] == ticker and x["year"] == y), None)
        prior_qr = next((x for x in query_results if x["ticker"] == ticker and x["year"] == y - 1), None)
        reasons: list[str] = []
        cur_rows = lookup.get((ticker, y, q), [])
        prev_rows = lookup.get((ticker, y - 1, q), [])
        if current_qr is None or current_qr["status"] != "RESOLVED_RESPONSE": reasons.append("CURRENT_METADATA_TRANSPORT_UNRESOLVED")
        if prior_qr is None or prior_qr["status"] != "RESOLVED_RESPONSE": reasons.append("PRIOR_METADATA_TRANSPORT_UNRESOLVED")
        if len(cur_rows) != 1: reasons.append(f"CURRENT_USABLE_ROW_COUNT_{len(cur_rows)}")
        if len(prev_rows) != 1: reasons.append(f"PRIOR_USABLE_ROW_COUNT_{len(prev_rows)}")
        cur = cur_rows[0] if len(cur_rows) == 1 else None
        prev = prev_rows[0] if len(prev_rows) == 1 else None
        if cur is not None:
            if cur["correction_field"] != "無": reasons.append("CURRENT_CORRECTION_NOT_EXACT_NONE")
            if not cur["upload_ts_taipei"]: reasons.append("CURRENT_UPLOAD_TS_UNPARSEABLE")
        if prev is not None:
            if prev["correction_field"] != "無": reasons.append("PRIOR_CORRECTION_NOT_EXACT_NONE")
            if not prev["upload_ts_taipei"]: reasons.append("PRIOR_UPLOAD_TS_UNPARSEABLE")

        signal_date: str | None = None
        pit_membership: bool | None = None
        pit_coverage: bool | None = None
        horizon_dates = {"entry_date": None, "exit_date": None}
        if not reasons and cur is not None:
            sd = resolve_signal_date(dt.datetime.fromisoformat(cur["upload_ts_taipei"]), sessions)
            if sd is None:
                reasons.append("SIGNAL_DATE_SESSION_COVERAGE_BLOCKED")
            else:
                signal_date = sd.isoformat()
                horizon_dates = event_horizon_dates(signal_date, sessions, 20)
                if horizon_dates["entry_date"] is None or horizon_dates["exit_date"] is None:
                    reasons.append("PRIMARY_HORIZON_SESSION_COVERAGE_BLOCKED")
                sy = sd.year
                if sy not in membership:
                    pit_coverage = False; reasons.append(f"PIT_MEMBERSHIP_YEAR_NOT_LOADED_{sy}")
                elif signal_date not in membership_dates[sy]:
                    pit_coverage = False; reasons.append("PIT_MEMBERSHIP_DATE_COVERAGE_BLOCKED")
                else:
                    pit_coverage = True
                    pit_membership = (signal_date, ticker) in membership[sy]
                    if not pit_membership: reasons.append("PIT_ELECTRONICS_MEMBERSHIP_FAIL")

        for reason in reasons: exclusion_counts[reason] += 1
        events.append({
            "ticker": ticker, "fiscal_year": y, "quarter": q,
            "event_id": f"{ticker}:{y}Q{q}", "stage_a_candidate": True,
            "current_metadata_rows": cur_rows, "prior_metadata_rows": prev_rows,
            "signal_date": signal_date, "pit_membership_date_covered": pit_coverage,
            "pit_electronics_membership": pit_membership,
            "primary_20_entry_date": horizon_dates["entry_date"],
            "primary_20_exit_date": horizon_dates["exit_date"],
            "stage_b_pass": len(reasons) == 0, "exclusion_reasons": reasons,
        })

    if len({e["event_id"] for e in events}) != len(events):
        raise RuntimeError("DUPLICATE_EVENT_ID_AFTER_STAGE_B")
    passed = [e for e in events if e["stage_b_pass"]]
    discovery = [e for e in passed if e["signal_date"] and "2023-01-01" <= e["signal_date"] <= "2024-12-31"]
    validation = [e for e in passed if e["signal_date"] and "2025-01-01" <= e["signal_date"] <= "2026-10-31"]
    disc_events = len(discovery)
    disc_tickers = len({e["ticker"] for e in discovery})
    disc_dates = len({e["signal_date"] for e in discovery})
    discovery_count_sufficient = disc_events >= 80 and disc_tickers >= 40 and disc_dates >= 20
    query_unresolved = sum(1 for x in query_results if x["status"] != "RESOLVED_RESPONSE")
    coverage_blocked_events = sum(1 for e in events if any("COVERAGE_BLOCKED" in x or "YEAR_NOT_LOADED" in x for x in e["exclusion_reasons"]))

    atomic_json(out / "IF07_STAGE_B_NO_RETURN_EVENT_PANEL.json", {
        "system": "HENGCE", "artifact": "IF07_STAGE_B_NO_RETURN_EVENT_PANEL",
        "challenger": CHALLENGER, "contains_price_or_forward_return_data": False,
        "input_stage_a_rows_sha256": stage_a_sha, "candidate_authority_count": len(events),
        "stage_b_pass_count": len(passed), "events": events,
    })
    audit = {
        "system": "HENGCE", "artifact": "IF07_STAGE_B_NO_RETURN_AUDIT", "challenger": CHALLENGER,
        "contains_price_or_forward_return_data": False, "selection_rules_changed": False,
        "input_stage_a_rows_sha256": stage_a_sha, "admission_verdict": manifest["verdict"],
        "candidate_authority_count": len(events),
        "candidate_authority_unique_tickers": len({e["ticker"] for e in events}),
        "t57_query_count": len(query_results), "t57_query_unresolved_count": query_unresolved,
        "metadata_and_pit_pass_count": len(passed), "metadata_and_pit_excluded_count": len(events) - len(passed),
        "exclusion_reason_counts": dict(sorted(exclusion_counts.items())),
        "membership_receipts": membership_receipts, "coverage_blocked_event_count": coverage_blocked_events,
        "discovery_count_only": {
            "events": disc_events, "unique_tickers": disc_tickers, "distinct_signal_dates": disc_dates,
            "minimum_events": 80, "minimum_unique_tickers": 40, "minimum_distinct_signal_dates": 20,
            "sufficient": discovery_count_sufficient,
        },
        "validation_count_only_observed_now": {
            "events": len(validation), "unique_tickers": len({e["ticker"] for e in validation}),
            "distinct_signal_dates": len({e["signal_date"] for e in validation}),
            "note": "Not a Validation return decision; returns remain unopened here.",
        },
        "forward_returns_inspected": False,
        "discovery_returns_authorized": bool(discovery_count_sufficient),
        "next_legal_step": "OPEN_DISCOVERY_RETURNS_UNDER_FROZEN_V0_1" if discovery_count_sufficient else "STOP_INCONCLUSIVE_NO_RETURNS_COUNT_INSUFFICIENT",
        "github_run": {
            "repository": os.getenv("GITHUB_REPOSITORY"), "run_id": os.getenv("GITHUB_RUN_ID"),
            "run_attempt": os.getenv("GITHUB_RUN_ATTEMPT"), "sha": os.getenv("GITHUB_SHA"), "ref": os.getenv("GITHUB_REF"),
        },
    }
    atomic_json(out / "IF07_STAGE_B_NO_RETURN_AUDIT.json", audit)
    checksum_rows = []
    for p in sorted(out.rglob("*")):
        if p.is_file(): checksum_rows.append({"path": str(p.relative_to(out)), "sha256": sha256_file(p), "bytes": p.stat().st_size})
    atomic_json(out / "CHECKSUMS.json", {"files": checksum_rows})
    print(json.dumps({
        "candidate_authority_count": len(events), "stage_b_pass_count": len(passed),
        "stage_b_excluded_count": len(events) - len(passed), "t57_query_unresolved_count": query_unresolved,
        "coverage_blocked_event_count": coverage_blocked_events, "discovery_events": disc_events,
        "discovery_unique_tickers": disc_tickers, "discovery_distinct_signal_dates": disc_dates,
        "discovery_count_sufficient": discovery_count_sufficient, "next_legal_step": audit["next_legal_step"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
