#!/usr/bin/env python3
"""HENGCE targeted TDCC historical backfill for frozen Monster BUY V1 events.

Purpose
-------
Fill only the TDCC weekly ownership snapshots needed to evaluate the already-frozen
Monster BUY V1 2026 event set. This is a research backfill sidecar, not canonical
or production authority.

Governance
----------
- Official TDCC historical endpoint only.
- Frozen Monster event universe; do not expand/tune the model universe.
- Conservative historical PIT proxy: a TDCC reference date is eligible for an
  event only when ReferenceDate + 7 calendar days <= EventDate.
- Fetch seven eligible weekly snapshots per event (enough to compute six weekly
  deltas around the prior ~20-trading-day lifecycle window).
- Preserve raw HTML in a ZIP and SHA-256 every response.
- Missing/invalid queries stay missing; never forward-fill or reconstruct.
- COMPLETE requires every required event/ticker/reference-date key to validate.
- Historical retrieval time is recorded as RetrievedAtTaipei and MUST NOT be
  interpreted as proof of event-time availability.
- No model authority is created.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import time
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import requests

TZ = ZoneInfo("Asia/Taipei")
ROOT = Path(__file__).resolve().parents[1]
EVENT_FILE = ROOT / "research" / "tdcc" / "monster_v1_frozen_events_20261029.csv"
OUT = ROOT / "ownership" / "tdcc" / "backfill_candidate" / "monster_v1_20261029"
ENDPOINT = "https://www.tdcc.com.tw/portal/zh/smWeb/qryStock"
FROZEN_EVENT_SOURCE_SHA256 = "c42cbcca0b60aaac6e4ebd9b3575899b1a6054035c5db64e811197db46abd37c"
WEEK_DATES = """20261008 20261002 20260924 20260918 20260911 20260904 20260828 20260821 20260814 20260807 20260731 20260724 20260717 20260709 20260703 20260626 20260618 20260612 20260605 20260529 20260522 20260515 20260508 20260430 20260424 20260417 20260410 20260402 20260327 20260320 20260313 20260306 20260226 20260213 20260206 20260130 20260123 20260116 20260109 20260102 20251226 20251219 20251212 20251205 20251128 20251121 20251114 20251107 20251031 20251023 20251017""".split()
PIT_LAG_DAYS = 7
SNAPSHOTS_PER_EVENT = 7

SUMMARY_COLS = [
    "EventDate", "Ticker", "Name", "ReferenceDate", "PITProxyAvailableDate",
    "RetrievedAtTaipei", "Big400Holders", "Big400Shares", "Big400Pct",
    "Big1000Holders", "Big1000Shares", "Big1000Pct", "TotalHolders",
    "TotalShares", "ResponseSHA256", "Source", "PITAuthority"
]


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def now_tw() -> str:
    return datetime.now(TZ).replace(microsecond=0).isoformat()


def clean_int(x):
    s = str(x if x is not None else "").replace(",", "").strip()
    if s in ("", "-", "--", "nan", "None"):
        return None
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    return int(float(m.group())) if m else None


def clean_float(x):
    s = str(x if x is not None else "").replace(",", "").replace("%", "").strip()
    if s in ("", "-", "--", "nan", "None"):
        return None
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    return float(m.group()) if m else None


def flatten_col(c) -> str:
    if isinstance(c, tuple):
        parts = [str(x).strip() for x in c if str(x).strip() and str(x) != "nan"]
        return " ".join(parts)
    return str(c).strip()


def parse_level(x):
    s = str(x).strip()
    m = re.match(r"^\s*(\d{1,2})(?:\D|$)", s)
    if m:
        n = int(m.group(1))
        if 1 <= n <= 17:
            return n
    return None


def find_data_table(html: str):
    tables = pd.read_html(io.StringIO(html))
    diagnostics = []
    for i, t in enumerate(tables):
        t = t.copy()
        t.columns = [flatten_col(c) for c in t.columns]
        cols = list(t.columns)
        diagnostics.append({"i": i, "rows": len(t), "cols": cols})
        has_holders = any("人數" in c for c in cols)
        has_shares = any("股數" in c or "單位數" in c for c in cols)
        has_holding = any("持股" in c or "分級" in c for c in cols)
        if has_holders and has_shares and has_holding and len(t) >= 15:
            return t, diagnostics
    raise RuntimeError("TDCC_HIST_TABLE_NOT_FOUND:" + json.dumps(diagnostics, ensure_ascii=False)[:3000])


def choose_col(cols, predicates, label):
    for c in cols:
        if all(p(c) for p in predicates):
            return c
    raise RuntimeError(f"TDCC_HIST_COL_NOT_FOUND:{label}:{cols}")


def summarize_table(t: pd.DataFrame):
    cols = list(t.columns)
    level_col = choose_col(
        cols,
        [lambda c: ("持股" in c or "分級" in c), lambda c: ("人數" not in c and "股數" not in c)],
        "level",
    )
    holders_col = choose_col(cols, [lambda c: "人數" in c], "holders")
    shares_candidates = [c for c in cols if ("股數" in c or "單位數" in c) and "比例" not in c and "分級" not in c]
    if not shares_candidates:
        raise RuntimeError(f"TDCC_HIST_COL_NOT_FOUND:shares:{cols}")
    shares_col = shares_candidates[0]
    pct_candidates = [c for c in cols if "比例" in c]
    if not pct_candidates:
        raise RuntimeError(f"TDCC_HIST_COL_NOT_FOUND:pct:{cols}")
    pct_col = pct_candidates[0]

    grades = {}
    total_row = None
    for _, row in t.iterrows():
        raw_level = row.get(level_col)
        lvl = parse_level(raw_level)
        rec = {
            "holders": clean_int(row.get(holders_col)),
            "shares": clean_int(row.get(shares_col)),
            "pct": clean_float(row.get(pct_col)),
            "raw_level": str(raw_level),
        }
        if lvl is not None:
            grades[lvl] = rec
        elif "合計" in str(raw_level) or "總計" in str(raw_level):
            total_row = rec

    need = {12, 13, 14, 15}
    if not need.issubset(grades):
        raise RuntimeError(f"TDCC_HIST_GRADES_INCOMPLETE:{sorted(grades)}")
    for g in need:
        if grades[g]["holders"] is None or grades[g]["shares"] is None or grades[g]["pct"] is None:
            raise RuntimeError(f"TDCC_HIST_GRADE_MISSING_VALUE:{g}:{grades[g]}")

    big400 = [grades[g] for g in (12, 13, 14, 15)]
    g15 = grades[15]
    total_holders = total_row["holders"] if total_row else (grades.get(17) or {}).get("holders")
    total_shares = total_row["shares"] if total_row else (grades.get(17) or {}).get("shares")

    return {
        "Big400Holders": sum(x["holders"] for x in big400),
        "Big400Shares": sum(x["shares"] for x in big400),
        "Big400Pct": round(sum(x["pct"] for x in big400), 6),
        "Big1000Holders": g15["holders"],
        "Big1000Shares": g15["shares"],
        "Big1000Pct": round(g15["pct"], 6),
        "TotalHolders": total_holders,
        "TotalShares": total_shares,
        "ParsedGrades": sorted(grades),
    }


def get_token(session: requests.Session):
    r = session.get(ENDPOINT, timeout=45, verify=False)
    r.raise_for_status()
    m = re.search(r'name=["\']SYNCHRONIZER_TOKEN["\'][^>]*value=["\']([^"\']*)["\']', r.text)
    if not m:
        raise RuntimeError("TDCC_TOKEN_NOT_FOUND")
    return m.group(1)


def fetch_one(session, ticker: str, ref_date: str):
    last_err = None
    for attempt in range(1, 4):
        try:
            token = get_token(session)
            data = {
                "SYNCHRONIZER_TOKEN": token,
                "SYNCHRONIZER_URI": "/portal/zh/smWeb/qryStock",
                "method": "submit",
                "firDate": ref_date,
                "scaDate": ref_date,
                "sqlMethod": "StockNo",
                "stockNo": ticker,
                "stockName": "",
            }
            r = session.post(ENDPOINT, data=data, timeout=60, verify=False)
            r.raise_for_status()
            if "查無此資料" in r.text:
                raise RuntimeError("TDCC_NO_DATA")
            summary = summarize_table(find_data_table(r.text)[0])
            return r.content, r.text, summary
        except Exception as e:
            last_err = e
            if attempt < 3:
                time.sleep(1.2 * attempt)
    raise RuntimeError(f"TDCC_QUERY_FAILED:{ticker}:{ref_date}:{type(last_err).__name__}:{last_err}")


def load_events():
    if not EVENT_FILE.exists():
        raise RuntimeError(f"EVENT_FILE_MISSING:{EVENT_FILE}")
    d = pd.read_csv(EVENT_FILE, dtype={"Ticker": str})
    if list(d.columns) != ["Ticker", "Name", "Date"]:
        raise RuntimeError(f"EVENT_FILE_BAD_HEADER:{list(d.columns)}")
    if len(d) != 40 or d["Ticker"].nunique() != 37:
        raise RuntimeError(f"EVENT_UNIVERSE_CHANGED:rows={len(d)} unique={d['Ticker'].nunique()}")
    d["Date"] = pd.to_datetime(d["Date"], errors="raise")
    return d


def required_keys(events):
    ref_dates = sorted(datetime.strptime(x, "%Y%m%d").date() for x in WEEK_DATES)
    required = []
    for _, r in events.sort_values(["Date", "Ticker"]).iterrows():
        ed = r["Date"].date()
        cutoff = ed - timedelta(days=PIT_LAG_DAYS)
        eligible = [x for x in ref_dates if x <= cutoff]
        selected = eligible[-SNAPSHOTS_PER_EVENT:]
        if len(selected) != SNAPSHOTS_PER_EVENT:
            raise RuntimeError(f"INSUFFICIENT_REFERENCE_DATES:{r['Ticker']}:{ed}:{len(selected)}")
        for rd in selected:
            required.append({
                "EventDate": ed.isoformat(),
                "Ticker": str(r["Ticker"]),
                "Name": str(r["Name"]),
                "ReferenceDate": rd.strftime("%Y%m%d"),
                "PITProxyAvailableDate": (rd + timedelta(days=PIT_LAG_DAYS)).isoformat(),
            })
    if len(required) != 280:
        raise RuntimeError(f"REQUIRED_KEY_COUNT_CHANGED:{len(required)}")
    key3 = {(x["EventDate"], x["Ticker"], x["ReferenceDate"]) for x in required}
    if len(key3) != len(required):
        raise RuntimeError("DUPLICATE_EVENT_TICKER_REFERENCE_KEY")
    return required


def csv_text(rows, cols):
    s = io.StringIO(newline="")
    w = csv.DictWriter(s, fieldnames=cols, lineterminator="\n")
    w.writeheader()
    for r in rows:
        w.writerow({c: r.get(c, "") for c in cols})
    return s.getvalue()


def main():
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    events = load_events()
    required = required_keys(events)
    OUT.mkdir(parents=True, exist_ok=True)
    retrieved = now_tw()

    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 HENGCE-TDCC-MONSTER-PIT-BACKFILL/1.0",
        "Referer": ENDPOINT,
        "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.5",
    })

    rows = []
    invalid = []
    raw_zip_path = OUT / "raw_html.zip"
    seen_query = {}
    written_entries = set()
    with zipfile.ZipFile(raw_zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for i, k in enumerate(required, 1):
            ticker, ref = k["Ticker"], k["ReferenceDate"]
            qkey = (ticker, ref)
            print(f"[{i}/{len(required)}] {k['EventDate']} {ticker} {ref}", flush=True)
            try:
                if qkey in seen_query:
                    raw, text, sm = seen_query[qkey]
                else:
                    raw, text, sm = fetch_one(session, ticker, ref)
                    seen_query[qkey] = (raw, text, sm)
                    time.sleep(0.12)
                response_sha = sha256_bytes(raw)
                entry_name = f"{ticker}/{ref}.html"
                if entry_name not in written_entries:
                    z.writestr(entry_name, raw)
                    written_entries.add(entry_name)
                row = dict(k)
                row.update({
                    "RetrievedAtTaipei": retrieved,
                    "Big400Holders": sm["Big400Holders"],
                    "Big400Shares": sm["Big400Shares"],
                    "Big400Pct": sm["Big400Pct"],
                    "Big1000Holders": sm["Big1000Holders"],
                    "Big1000Shares": sm["Big1000Shares"],
                    "Big1000Pct": sm["Big1000Pct"],
                    "TotalHolders": sm["TotalHolders"],
                    "TotalShares": sm["TotalShares"],
                    "ResponseSHA256": response_sha,
                    "Source": ENDPOINT,
                    "PITAuthority": "HISTORICAL_PIT_PROXY_RESEARCH_ONLY",
                })
                rows.append(row)
            except Exception as e:
                err = f"{type(e).__name__}:{e}"
                invalid.append({**k, "error": err})
                print("INVALID", ticker, ref, err, flush=True)

    summary_path = OUT / "tdcc_monster_v1_pit_backfill.csv"
    summary_path.write_text(csv_text(rows, SUMMARY_COLS), encoding="utf-8")
    summary_sha = sha256_bytes(summary_path.read_bytes())
    raw_zip_sha = sha256_bytes(raw_zip_path.read_bytes())

    required_count = len(required)
    valid_count = len(rows)
    status = "COMPLETE" if valid_count == required_count and not invalid else "PARTIAL_FAIL_CLOSED"

    manifest = {
        "system": "HENGCE",
        "artifact": "TDCC_MONSTER_V1_TARGETED_HISTORICAL_BACKFILL",
        "status": status,
        "authority": "RESEARCH_BACKFILL_CANDIDATE_NO_CANONICAL_AUTHORITY",
        "model_authority_created": False,
        "frozen_model": "MONSTER_BUY_V1",
        "frozen_event_count": int(len(events)),
        "frozen_unique_tickers": int(events["Ticker"].nunique()),
        "frozen_source_archive_event_csv_sha256": FROZEN_EVENT_SOURCE_SHA256,
        "event_file": str(EVENT_FILE.relative_to(ROOT)),
        "event_file_sha256": sha256_bytes(EVENT_FILE.read_bytes()),
        "source_owner": "TDCC",
        "source_endpoint": ENDPOINT,
        "retrieved_at_taipei": retrieved,
        "reference_week_source": "existing HENGCE 51W fixed weekly calendar",
        "pit_proxy_rule": f"ReferenceDate + {PIT_LAG_DAYS} calendar days <= EventDate",
        "pit_proxy_note": "Conservative retrospective eligibility proxy only. RetrievedAtTaipei is the true observation time of this backfill; this artifact does not prove historical publication timestamps and must not be promoted to formal live authority.",
        "snapshots_per_event": SNAPSHOTS_PER_EVENT,
        "required_key_count": required_count,
        "valid_key_count": valid_count,
        "invalid_key_count": len(invalid),
        "invalid": invalid,
        "summary_sha256": summary_sha,
        "raw_html_zip_sha256": raw_zip_sha,
        "big400_definition": "historical TDCC rows/grades 12+13+14+15 (>=400,001 shares)",
        "big1000_definition": "historical TDCC row/grade 15 (>=1,000,001 shares)",
        "no_forward_fill": True,
        "technical_fallback": "PROHIBITED",
        "monster_v1_retuned": False,
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({
        "status": status,
        "required": required_count,
        "valid": valid_count,
        "invalid": len(invalid),
        "summary_sha256": summary_sha,
        "raw_zip_sha256": raw_zip_sha,
    }, ensure_ascii=False), flush=True)

    if status != "COMPLETE":
        raise SystemExit(f"FAIL_CLOSED_BACKFILL_INCOMPLETE:{valid_count}/{required_count}")


if __name__ == "__main__":
    main()
