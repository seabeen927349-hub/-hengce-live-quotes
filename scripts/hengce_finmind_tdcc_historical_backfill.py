#!/usr/bin/env python3
"""HENGCE historical TDCC/FinMind data bridge (RESEARCH ONLY).

Fetches FinMind TaiwanStockHoldingSharesPer into a separate candidate area.
Never modifies the official TDCC weekly sidecar, the three-leg mother, or any model.
Never imputes unavailable dates, shareholding levels, or publish timestamps.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import os
import re
import sys
import time
from datetime import datetime, date, timezone
from pathlib import Path
from urllib import parse, request, error

ROOT = Path(__file__).resolve().parents[1]
API = "https://api.finmindtrade.com/api/v4/data"
FIELDS = ("date", "stock_id", "HoldingSharesLevel", "people", "percent", "unit")
DEST = ROOT / "ownership/tdcc/backfill_candidate/finmind_history"
DATE_PATTERN = re.compile(r"^20\d\d-\d\d-\d\d$")
FOUR_DIGIT = re.compile(r"^[1-9]\d{3}$")


class FinMindAccessError(RuntimeError):
    pass


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fetch(token: str, ticker: str, start: str, end: str) -> tuple[list[dict], dict]:
    params = parse.urlencode({
        "dataset": "TaiwanStockHoldingSharesPer",
        "data_id": ticker,
        "start_date": start,
        "end_date": end,
    })
    url = API + "?" + params
    req = request.Request(url, headers={
        "Authorization": "Bearer " + token,
        "Accept": "application/json",
        "User-Agent": "HENGCE-TDCC-FinMind-Research-1.0",
    })
    for attempt in range(4):
        try:
            with request.urlopen(req, timeout=90) as resp:
                raw = resp.read()
                http_status = resp.status
                break
        except error.HTTPError as exc:
            # Never log bearer token, request headers or token-bearing URLs.
            if exc.code == 429 and attempt < 3:
                retry = min(60.0, 10.0 * (attempt + 1))
                time.sleep(retry)
                continue
            raise FinMindAccessError(f"FINMIND_HTTP_{exc.code}") from None
        except Exception as exc:
            if attempt < 3:
                time.sleep(3 * (attempt + 1))
                continue
            raise RuntimeError(f"FINMIND_NETWORK_{type(exc).__name__}") from None
    try:
        body = json.loads(raw)
    except (ValueError, TypeError):
        raise RuntimeError("FINMIND_JSON_INVALID") from None
    if not isinstance(body, dict):
        raise RuntimeError("FINMIND_NOT_OBJECT")
    status = body.get("status")
    data = body.get("data")
    if status != 200 or not isinstance(data, list):
        raise FinMindAccessError(f"FINMIND_DATASET_BLOCKED_OR_INVALID_STATUS_{status}")
    return data, {
        "http_status": http_status,
        "finmind_status": status,
        "raw_json_sha256": sha256(raw),
        "raw_json_length": len(raw),
    }


def validate(rows: list[dict], ticker: str, start: str, end: str) -> dict:
    if not isinstance(rows, list):
        raise ValueError("ROWS_NOT_ARRAY")
    observed_dates = set()
    levels = set()
    keys = set()
    adjustment_rows = 0
    adjustment_keys = []
    for row in rows:
        if not isinstance(row, dict) or any(k not in row for k in FIELDS):
            raise ValueError("SCHEMA_MISSING_FIELDS")
        sid = str(row["stock_id"]).strip()
        ds = str(row["date"]).strip()
        lvl = str(row["HoldingSharesLevel"]).strip()
        if sid != ticker or not DATE_PATTERN.fullmatch(ds) or not start <= ds <= end or not lvl:
            raise ValueError("KEY_OR_DATE_INVALID")
        key = (ds, sid, lvl)
        if key in keys:
            raise ValueError("DUPLICATE_DATE_TICKER_LEVEL")
        keys.add(key)
        observed_dates.add(ds)
        levels.add(lvl)
        try:
            p = float(row["percent"])
            people = int(row["people"])
            units = int(row["unit"])
        except (TypeError, ValueError):
            raise ValueError("NUMERIC_FIELD_INVALID") from None
        # FinMind/TDCC sometimes includes signed accounting reconciliation rows,
        # e.g. 差異數調整（說明4） with unit=-1999. Preserve these verbatim
        # but they are NOT a shareholder holding tier and MUST be excluded
        # from the Big400/Big1000 aggregations.
        is_adjustment = "差異數調整" in lvl
        if not (0 <= p <= 100 and people >= 0 and (units >= 0 or is_adjustment)):
            raise ValueError(f"NUMERIC_OUT_OF_RANGE stock={ticker} date={ds} level={lvl} percent={p} people={people} unit={units}")
        if is_adjustment:
            adjustment_rows += 1
            adjustment_keys.append({"date": ds, "level": lvl, "unit": units})
    return {
        "rows": len(rows),
        "snapshots": len(observed_dates),
        "first_snapshot": min(observed_dates) if observed_dates else None,
        "last_snapshot": max(observed_dates) if observed_dates else None,
        "levels": sorted(levels),
        "accounting_adjustment_rows": adjustment_rows,
        "accounting_adjustment_examples": adjustment_keys[:10],
        "holding_tier_only_derived_metrics": False,
    }


def write_verified(ticker: str, rows: list[dict], out: Path) -> str:
    out.parent.mkdir(parents=True, exist_ok=True)
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=FIELDS, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    writer.writerows(sorted(rows, key=lambda x: (str(x["date"]), str(x["HoldingSharesLevel"]))))
    payload = gzip.compress(buf.getvalue().encode("utf-8"), compresslevel=6, mtime=0)
    out.write_bytes(payload)
    return sha256(payload)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("probe", "sample"), required=True)
    parser.add_argument("--start", default="2018-01-01")
    parser.add_argument("--end", default="2025-10-30")
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--out", default=str(DEST))
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    observed = datetime.now(timezone.utc).isoformat()
    receipt = {
        "system": "HENGCE",
        "artifact": "FINMIND_TDCC_HISTORICAL_CANDIDATE_V1",
        "requested_window": [args.start, args.end],
        "mode": args.mode,
        "source": "FinMind TaiwanStockHoldingSharesPer /api/v4/data",
        "observed_at_utc": observed,
        "source_snapshot_is_not_publication_timestamp": True,
        "research_only": True,
        "no_model_or_trading_authority": True,
        "no_canonical_mutation": True,
        "no_imputation": True,
        "no_same_date_revisions_ignored": True,
        "status": "PENDING",
        "results": [],
    }
    token = os.environ.get("FINMIND_TOKEN", "").strip()
    try:
        if not token:
            raise FinMindAccessError("FINMIND_TOKEN_MISSING")
        if args.mode == "probe":
            targets = [
                ("2330", "2018-01-01", "2018-03-31"),
                ("2330", "2025-11-01", "2025-12-01"),
                ("1101", "2024-01-01", "2024-02-01"),
            ]
        else:
            sys.path.insert(0, str(ROOT / "scripts"))
            from hengce_tdcc_2026_full_market_runner import load_candidates_from_parent
            candidates = load_candidates_from_parent()
            if not (1 <= args.limit <= 100):
                raise ValueError("SAMPLE_LIMIT_MUST_BE_1_TO_100")
            targets = [(ticker, args.start, args.end) for ticker in candidates[:args.limit]]
            receipt["frozen_union_count"] = len(candidates)
            receipt["deterministic_sample_first_tickers"] = candidates[:args.limit]
        for ticker, start, end in targets:
            try:
                rows, transport = fetch(token, ticker, start, end)
                quality = validate(rows, ticker, start, end)
                if not rows:
                    raise ValueError("NO_ROWS_FAIL_CLOSED")
                name = f"finmind_{ticker}_{start}_{end}.csv.gz"
                digest = write_verified(ticker, rows, out / name)
                receipt["results"].append({
                    "ticker": ticker,
                    "window": [start, end],
                    "status": "PASS",
                    "data_path": name,
                    "gzip_sha256": digest,
                    "quality": quality,
                    "transport": transport,
                })
                print(f"PASS stock={ticker} snapshot_count={quality['snapshots']} row_count={quality['rows']}", flush=True)
            except (FinMindAccessError, ValueError, RuntimeError) as exc:
                receipt["results"].append({"ticker": ticker, "window": [start, end], "status": "BLOCKED", "error": str(exc)})
                raise
            # Avoid API bursts even when the connected plan has generous quota.
            time.sleep(0.6)
        receipt["status"] = "PASS_RESEARCH_CANDIDATE"
    except (FinMindAccessError, ValueError, RuntimeError) as exc:
        receipt["status"] = "BLOCKED_FAIL_CLOSED"
        receipt["blocker"] = str(exc)
    finally:
        (out / "manifest.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("HENGCE_FINMIND_TDCC_STATUS", receipt["status"], receipt.get("blocker", ""), flush=True)
    return 0 if receipt["status"] == "PASS_RESEARCH_CANDIDATE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
