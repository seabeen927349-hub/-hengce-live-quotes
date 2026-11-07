#!/usr/bin/env python3
"""HENGCE: historical TWSE 3-leg recovery through the existing original-vessel parsers.

Transport/archive research only. No mutation of current canonical, rankings or trading.
Source: official TWSE price MI_INDEX, institutional T86, margin MI_MARGN.
Process historical sessions as-of historical trade DATE; today's retrospective retrieval
is NOT proof of an actual archived first-seen timestamp or historical company identity.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import re
import time
from datetime import date, timedelta
from pathlib import Path

import requests
import hengce_daily_command_center_core_legacy as core
import hengce_eod_incremental_ingest as vessel

LEGS = ("price", "institutional", "margin")
MIN_ROWS = {"price": 650, "institutional": 650, "margin": 350}
SOURCE = {"price": core.TWSE_PRICE, "institutional": core.TWSE_INST, "margin": core.TWSE_MARGIN}
ROOT = Path(__file__).resolve().parents[1]
SESSION = requests.Session()
REQUEST_DELAY = 0.45
CAPTURE = {}
ACTIVE = None
LAST_FETCH = 0.0

def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def fetch_exact(url: str, params=None, timeout=45):
    """Replace ONLY the original helper transport while calling the pinned parser."""
    global LAST_FETCH
    if url not in SOURCE.values():
        raise ValueError("unapproved endpoint")
    elapsed = time.monotonic() - LAST_FETCH
    if elapsed < REQUEST_DELAY:
        time.sleep(REQUEST_DELAY - elapsed)
    latest_exc = None
    for attempt in range(1, 5):
        try:
            resp = SESSION.get(url, params=params, headers={
                "User-Agent": "Mozilla/5.0 HENGCE-HIST-ORIGINAL-VESSEL-REPLAY/1.0",
                "Accept": "application/json",
                "Referer": "https://www.twse.com.tw/"
            }, timeout=timeout)
            LAST_FETCH = time.monotonic()
            resp.raise_for_status()
            raw = resp.content
            payload = json.loads(raw.decode("utf-8-sig"))
            if not isinstance(payload, dict):
                raise RuntimeError("upstream JSON is not object")
            key = (ACTIVE or {}).get("leg")
            assert key in LEGS
            record = {"url": resp.url, "sha256": sha256(raw), "bytes": len(raw),
                      "stat": str(payload.get("stat", "")),
                      "api_date": str(payload.get("date", "")),
                      "retrieved_at_utc": __import__("datetime").datetime.now(
                          __import__("datetime").timezone.utc).isoformat()}
            CAPTURE[key] = {"record": record, "raw": raw}
            return payload
        except (requests.RequestException, ValueError, RuntimeError) as exc:
            latest_exc = repr(exc)
            time.sleep(min(12, 2 * attempt))
    raise RuntimeError(f"TWSE_TRANSPORT_RETRIES_EXHAUSTED:{latest_exc}")

def check_rows(leg: str, rows: list, iso: str) -> dict:
    if len(rows) < MIN_ROWS[leg]:
        raise RuntimeError(f"{leg} too few 4-digit equity records: {len(rows)}")
    keys = [(str(r.get("Date", "")), str(r.get("Ticker", ""))) for r in rows]
    if len(keys) != len(set(keys)):
        raise RuntimeError(f"{leg} duplicate Date/Ticker")
    if any(d != iso or not re.fullmatch(r"[1-9]\d{3}", t) for d, t in keys):
        raise RuntimeError(f"{leg} invalid Date or Ticker")
    for r in rows:
        rkeys = set(r)
        if set(vessel.COLS[leg]) != rkeys:
            raise RuntimeError(f"{leg} original vessel columns mismatch")
    return {"rows": len(rows), "tickers": sorted(set(t for _, t in keys))}

def write_csv_gz(dest: Path, leg: str, rows: list):
    path = dest / f"{leg}.csv.gz"
    with gzip.open(path, "wt", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=vessel.COLS[leg])
        w.writeheader()
        w.writerows(sorted(rows, key=lambda r: (r["Date"], r["Ticker"])))
    return {"file": path.name, "bytes": path.stat().st_size,
            "sha256": sha256(path.read_bytes()), "rows": len(rows)}

def run(year: int, output: Path):
    if not 2018 <= year <= 2022:
        raise ValueError("guard: historical missing 2018-2022 only")
    output.mkdir(parents=True, exist_ok=True)
    rawdir = output / "raw"
    rawdir.mkdir(exist_ok=True)
    allrows = {leg: [] for leg in LEGS}
    manifest = {"schema": "HENGCE_ORIGINAL_VESSEL_HISTORICAL_BACKFILL_V1",
        "year": year, "source": "TWSE_OFFICIAL_HISTORICAL_RETRIEVAL",
        "original_parser": "scripts/hengce_eod_incremental_ingest.py",
        "repository": "seabeen927349-hub/-hengce-live-quotes",
        "purpose": "HISTORICAL_THREE_LEG_RECOVERY_DATA_ONLY",
        "canonical_mutated": False, "second_mother": False,
        "model_authority": False, "trading_authority": False,
        "pit_historical_first_seen_proven": False,
        "missing_as_zero": False, "sessions": []}
    core.get_json = fetch_exact   # existing pinned vessel FETCH parser stays unchanged
    start, end = date(year, 1, 1), date(year, 12, 31)
    day = start
    failures = []
    while day <= end:
        if day.weekday() >= 5:
            day += timedelta(days=1)
            continue
        iso, ds = day.isoformat(), day.strftime("%Y%m%d")
        CAPTURE.clear()
        state = {"date": iso, "legs": {}}
        dayrows = {}
        try:
            for leg in LEGS:
                global ACTIVE
                ACTIVE = {"leg": leg}
                try:
                    rows = vessel.FETCH[leg](ds, iso)
                    information = check_rows(leg, rows, iso)
                    dayrows[leg] = rows
                    state["legs"][leg] = {"state": "VALID", "rows": information["rows"]}
                except vessel.NotReady as e:
                    state["legs"][leg] = {"state": "NOT_READY", "reason": str(e)}
                except Exception as e:
                    state["legs"][leg] = {"state": "FAILED", "reason": f"{type(e).__name__}:{e}"}
                if leg in CAPTURE:
                    capture = CAPTURE[leg]
                    state["legs"][leg].update(capture["record"])
                    # Retain original source bytes for independent re-parsing and SHA validation
                    p = rawdir / f"{ds}_{leg}.json.gz"
                    with gzip.open(p, "wb") as fh:
                        fh.write(capture["raw"])
                    state["legs"][leg]["raw_archive"] = str(p.relative_to(output))
                    state["legs"][leg]["raw_archive_sha256"] = sha256(p.read_bytes())
                # On an official no-data PRICE session, do not need to download absent legs
                if leg == "price" and state["legs"][leg]["state"] == "NOT_READY":
                    break
        except Exception as e:
            state["unhandled"] = repr(e)
        statuses = [state["legs"].get(k, {}).get("state") for k in LEGS]
        if statuses == ["VALID"] * 3:
            for k in LEGS:
                allrows[k].extend(dayrows[k])
            state["full_session"] = True
        else:
            state["full_session"] = False
            # Market-closed weekdays: price endpoint explicitly says NOT_READY
            if statuses[0] != "NOT_READY":
                failures.append({"date": iso, "states": statuses})
        manifest["sessions"].append(state)
        print(json.dumps({"date": iso, "states": statuses}, ensure_ascii=False), flush=True)
        day += timedelta(days=1)

    count = sum(s.get("full_session", False) for s in manifest["sessions"])
    manifest["complete_dates"] = count
    manifest["nontrading_or_no_price_weekdays"] = sum(
        s["legs"].get("price", {}).get("state") == "NOT_READY"
        for s in manifest["sessions"])
    manifest["failed_trading_dates"] = failures
    manifest["files"] = {k: write_csv_gz(output, k, allrows[k]) for k in LEGS}
    manifest["status"] = "PASS" if 220 <= count <= 255 and not failures else "FAIL_CLOSED"
    manifest["dates"] = sorted(s["date"] for s in manifest["sessions"] if s.get("full_session"))
    manifest["complete_days_have_three_legs"] = True
    manifest["recorded_at_utc"] = __import__("datetime").datetime.now(
        __import__("datetime").timezone.utc).isoformat()
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k:v for k,v in manifest.items()
            if k not in ("sessions", "dates", "files")}, ensure_ascii=False), flush=True)
    return 0 if manifest["status"] == "PASS" else 2

if __name__ == "__main__":
    a = argparse.ArgumentParser()
    a.add_argument("--year", type=int, required=True)
    a.add_argument("--out", type=Path, required=True)
    opt = a.parse_args()
    raise SystemExit(run(opt.year, opt.out))
