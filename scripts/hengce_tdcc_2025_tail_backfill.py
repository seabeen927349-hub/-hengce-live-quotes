#!/usr/bin/env python3
"""HENGCE TDCC 2025 tail full-market backfill.

Uses the already-verified HENGCE TDCC transport/parser and the frozen 3,091-ticker
candidate union. 2025 dates are intentionally limited to the part still expected
to be inside TDCC's public one-year historical window as of 2026-10-29.

Governance:
- TDCC official historical stock/date query only.
- Fresh SYNCHRONIZER_TOKEN for every stock/date query.
- Big400/Big1000 semantics are inherited unchanged from the verified HENGCE parser.
- 1101 and 2330 must both return VALID before a date is allowed to run. This prevents
  an expired historical date from being misclassified as a market-wide explicit NO_DATA.
- 3,091 candidates must all resolve VALID or explicit TDCC NO_DATA, invalid=0.
- No forward-fill, reconstruction, alternate source, or parser relaxation.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import hengce_tdcc_2026_jan_apr_backfill as b
from hengce_tdcc_2026_full_market_runner import load_candidates_from_parent

ROOT = Path(__file__).resolve().parents[1]
OUT_ROOT = ROOT / "ownership" / "tdcc" / "backfill_candidate" / "full_market_2025_tail"
ALLOWED_DATES = {
    "20251031",
    "20251107",
    "20251114",
    "20251121",
    "20251128",
    "20251205",
    "20251212",
    "20251219",
    "20251226",
}
SENTINELS = ("1101", "2330")


def date_preflight(ref: str) -> list[dict]:
    proof = []
    for ticker in SENTINELS:
        state, payload, raw = b.fetch_classified(ref, ticker)
        proof.append({
            "ticker": ticker,
            "state": state,
            "raw_sha256": payload.get("RawSHA256") if isinstance(payload, dict) else None,
            "error": payload.get("error") if isinstance(payload, dict) else None,
        })
        if state != "VALID":
            raise RuntimeError(f"TDCC_2025_DATE_NOT_LIVE_OR_QUERY_FAILED:{ref}:{ticker}:{state}:{payload}")
    return proof


def main():
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True)
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()
    ref = args.date.replace("-", "")
    if ref not in ALLOWED_DATES:
        raise SystemExit(f"DATE_NOT_IN_FROZEN_2025_TAIL_SET:{ref}")
    if not 1 <= args.workers <= 8:
        raise SystemExit(f"WORKERS_OUT_OF_RANGE:{args.workers}")

    preflight = date_preflight(ref)
    candidates = load_candidates_from_parent()
    out = OUT_ROOT / ref
    out.mkdir(parents=True, exist_ok=True)
    retrieved = b.now_tw()

    valid, no_data, invalid = [], [], []
    completed = 0
    zpath = out / "raw_html.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        with ThreadPoolExecutor(max_workers=args.workers, thread_name_prefix=f"tdcc-{ref}") as ex:
            futures = {ex.submit(b.fetch_classified, ref, t): t for t in candidates}
            for fut in as_completed(futures):
                ticker = futures[fut]
                try:
                    state, payload, raw = fut.result()
                except Exception as e:
                    state, raw = "INVALID", None
                    payload = {"SnapshotDate": ref, "Ticker": ticker, "error": f"FUTURE_{type(e).__name__}:{e}"}
                completed += 1
                if state == "VALID":
                    valid.append(payload)
                    z.writestr(f"valid/{ticker}.html", raw)
                elif state == "NO_DATA":
                    no_data.append(payload)
                    z.writestr(f"no_data/{ticker}.html", raw)
                else:
                    invalid.append(payload)
                if completed == 1 or completed % 100 == 0 or completed == len(candidates):
                    print(f"[{ref}] {completed}/{len(candidates)} valid={len(valid)} no_data={len(no_data)} invalid={len(invalid)}", flush=True)

    valid.sort(key=lambda x: x["Ticker"])
    no_data.sort(key=lambda x: x["Ticker"])
    invalid.sort(key=lambda x: x["Ticker"])

    summary_path = out / "tdcc_ownership_4d.csv"
    no_data_path = out / "explicit_no_data.csv"
    invalid_path = out / "invalid.json"
    b.write_csv(summary_path, valid, b.COLS)
    b.write_csv(no_data_path, no_data, b.NO_DATA_COLS)
    invalid_path.write_text(json.dumps(invalid, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    resolved = len(valid) + len(no_data)
    status = "COMPLETE" if resolved == len(candidates) and not invalid else "PARTIAL_FAIL_CLOSED"
    manifest = {
        "system": "HENGCE",
        "artifact": "TDCC_2025_TAIL_FULL_MARKET_WEEKLY_BACKFILL_DATE",
        "status": status,
        "reference_date": ref,
        "date_liveness_preflight": preflight,
        "candidate_universe": "HENGCE_TDCC_HISTORICAL_UNION_3091",
        "candidate_rows": len(candidates),
        "candidate_union_sha256": "70229d9b1bcef321deaad73b96fcb65c84227e30d173cd0b20a7e7e524a52936",
        "candidate_parent_gzip_sha256": "d10a3576e09f42041135dae3884f59c73e555c05ce23e524131feee94f1e8b8f",
        "valid_rows": len(valid),
        "explicit_no_data_rows": len(no_data),
        "resolved_candidates": resolved,
        "invalid_rows": len(invalid),
        "retrieved_at_taipei": retrieved,
        "query_workers": args.workers,
        "fresh_token_per_query": True,
        "token_reuse": "PROHIBITED_BY_VERIFIED_HENGCE_PROBE_FALSE_NO_DATA_RISK",
        "source": "TDCC official historical qryStock endpoint",
        "parser": "existing verified HENGCE ordinal parser",
        "summary_sha256": b.sha256_bytes(summary_path.read_bytes()),
        "explicit_no_data_sha256": b.sha256_bytes(no_data_path.read_bytes()),
        "raw_html_zip_sha256": b.sha256_bytes(zpath.read_bytes()),
        "raw_html_zip_bytes": zpath.stat().st_size,
        "authority": "RESEARCH_BACKFILL_CANDIDATE_NO_CANONICAL_AUTHORITY",
        "pit_authority": "HISTORICAL_PIT_PROXY_RESEARCH_ONLY",
        "no_forward_fill": True,
        "no_reconstruction": True,
        "technical_fallback": "PROHIBITED",
    }
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False))
    if status != "COMPLETE":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
