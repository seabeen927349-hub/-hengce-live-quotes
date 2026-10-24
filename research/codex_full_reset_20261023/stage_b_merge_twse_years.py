#!/usr/bin/env python3
"""Merge verified yearly TWSE electronics shards into the Stage-B mother artifact."""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any
from stage_b_build_twse_year import CORPUS_BASE, load_expected, validate_daily

YEARS = (2023, 2024, 2025)
FIELDS = ["date", "ticker", "name", "open", "high", "low", "close", "volume_shares", "turnover_ntd"]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--input-dir", required=True)
    p.add_argument("--output-dir", required=True)
    args = p.parse_args()
    inp = Path(args.input_dir)
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    expected={};expected_names={}
    for year in YEARS:
        daily,names,_=load_expected(year);expected.update(daily);expected_names.update(names)
    raw_records={}
    receipts = []
    total_expected_dates = 0
    total_pass_dates = 0
    total_failed_dates = 0
    expected_rows = 0
    for year in YEARS:
        rp = inp / f"TWSE_MOTHER_RECEIPT_{year}.json"
        mp = inp / f"TWSE_ELECTRONICS_DAILY_{year}.csv.gz"
        qp = inp / f"TWSE_MOTHER_QA_{year}.jsonl"
        for path in (rp, mp, qp):
            if not path.exists():
                raise RuntimeError(f"MISSING_YEAR_ARTIFACT:{path}")
        r = load_json(rp)
        if r.get("status") != "PASS_EXACT_MEMBERSHIP_SET" or r.get("failed_dates") != 0:
            raise RuntimeError(f"YEAR_NOT_PASS:{year}:{r.get('status')}")
        if r.get("universe") != "TWSE_LISTED_ELECTRONICS_PIT_DAILY":
            raise RuntimeError(f"YEAR_SCOPE_MISMATCH:{year}")
        if r.get("mother_sha256") != sha256_file(mp):
            raise RuntimeError(f"YEAR_MOTHER_SHA_MISMATCH:{year}")
        if r.get("qa_sha256") != sha256_file(qp):
            raise RuntimeError(f"YEAR_QA_SHA_MISMATCH:{year}")
        if r.get('frozen_corpus_base') != CORPUS_BASE or r.get('year') != year:
            raise RuntimeError('YEAR_CORPUS_BINDING_MISMATCH')
        seen_qa=set()
        for line in qp.read_text().splitlines():
            q=json.loads(line);d=q['date']
            if d in seen_qa or d not in expected or not d.startswith(str(year)) or q.get('status')!='PASS':
                raise RuntimeError('INVALID_YEAR_QA:'+str(d))
            seen_qa.add(d)
            raw_path=(inp/q['raw_source_path']).resolve()
            if not raw_path.is_relative_to(inp.resolve()) or sha256_file(raw_path)!=q['raw_archive_sha256']:
                raise RuntimeError('RAW_ARCHIVE_BINDING_MISMATCH')
            raw=gzip.decompress(raw_path.read_bytes())
            if hashlib.sha256(raw).hexdigest()!=q['response_sha256']:
                raise RuntimeError('RAW_RESPONSE_HASH_MISMATCH')
            from stage_b_build_twse_year import decode
            parsed,verified=validate_daily(decode(raw),d,expected[d])
            if verified['status']!='PASS':raise RuntimeError('RAW_REVALIDATION_FAILED:'+d)
            for row in parsed:raw_records[(d,row['ticker'])]=row
            dest=out/q['raw_source_path'];dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(raw_path,dest)
        if seen_qa!={d for d in expected if d.startswith(str(year))}:
            raise RuntimeError('YEAR_QA_DATE_SET_INCOMPLETE')
        receipts.append(r)
        total_expected_dates += int(r["expected_trading_dates"])
        total_pass_dates += int(r["pass_dates"])
        total_failed_dates += int(r["failed_dates"])
        expected_rows += int(r["rows_written"])

    mother_out = out / "TWSE_ELECTRONICS_DAILY_2023_2025.csv.gz"
    qa_out = out / "TWSE_MOTHER_QA_2023_2025.jsonl"
    rows_written = 0
    seen_dates = set()
    seen_keys = set()
    with gzip.open(mother_out, "wt", encoding="utf-8", newline="") as fout:
        writer = csv.DictWriter(fout, fieldnames=FIELDS)
        writer.writeheader()
        for year in YEARS:
            mp = inp / f"TWSE_ELECTRONICS_DAILY_{year}.csv.gz"
            with gzip.open(mp, "rt", encoding="utf-8-sig", newline="") as fin:
                reader = csv.DictReader(fin)
                if list(reader.fieldnames or []) != FIELDS:
                    raise RuntimeError(f"YEAR_HEADER_MISMATCH:{year}:{reader.fieldnames}")
                for row in reader:
                    d = (row.get("date") or "").strip()
                    ticker = (row.get("ticker") or "").strip()
                    if not d or not ticker or not d.startswith(str(year)):
                        raise RuntimeError(f"BAD_YEAR_ROW:{year}:{d}:{ticker}")
                    key = (d, ticker)
                    if key in seen_keys:
                        raise RuntimeError(f"DUPLICATE_KEY:{d}:{ticker}")
                    original=raw_records.get(key)
                    if original is None or any(row[k]!=original[k] for k in FIELDS if k not in {'date','name'}):
                        raise RuntimeError('MOTHER_RAW_VALUE_MISMATCH:'+str(key))
                    if row['name']!=expected_names[key]:
                        raise RuntimeError('MOTHER_PIT_NAME_MISMATCH:'+str(key))
                    seen_keys.add(key)
                    seen_dates.add(d)
                    writer.writerow({k: row.get(k, "") for k in FIELDS})
                    rows_written += 1

    with qa_out.open("w", encoding="utf-8") as fout:
        for year in YEARS:
            qp = inp / f"TWSE_MOTHER_QA_{year}.jsonl"
            text = qp.read_text(encoding="utf-8")
            fout.write(text)
            if text and not text.endswith("\n"):
                fout.write("\n")

    if seen_keys != {(d,t) for d,tickers in expected.items() for t in tickers}:
        raise RuntimeError('MERGED_EXACT_MEMBERSHIP_MISMATCH')
    if rows_written != expected_rows:
        raise RuntimeError(f"ROW_COUNT_MISMATCH:{rows_written}:{expected_rows}")
    if len(seen_dates) != total_expected_dates or total_pass_dates != total_expected_dates or total_failed_dates != 0:
        raise RuntimeError(f"DATE_COUNT_MISMATCH:{len(seen_dates)}:{total_expected_dates}:{total_pass_dates}:{total_failed_dates}")

    receipt = {
        "schema_version": 2,
        "frozen_corpus_base":CORPUS_BASE,
        "raw_responses_revalidated":len(seen_dates),
        "stage": "B_OFFICIAL_MOTHER_REBUILD",
        "mode": "PARALLEL_YEAR_SHARDS_THEN_HASH_VERIFIED_MERGE",
        "source": "TWSE MI_INDEX type=13 historical daily CSV",
        "universe": "TWSE_LISTED_ELECTRONICS_PIT_DAILY",
        "historical_window": ["2023-01-01", "2025-12-31"],
        "expected_trading_dates": total_expected_dates,
        "pass_dates": total_pass_dates,
        "failed_dates": total_failed_dates,
        "rows_written": rows_written,
        "unique_dates": len(seen_dates),
        "unique_date_ticker_keys": len(seen_keys),
        "year_receipts": [
            {
                "year": r["year"],
                "expected_trading_dates": r["expected_trading_dates"],
                "rows_written": r["rows_written"],
                "mother_sha256": r["mother_sha256"],
                "qa_sha256": r["qa_sha256"],
                "membership_source": r["membership_source"],
            }
            for r in receipts
        ],
        "qa_path": qa_out.name,
        "qa_sha256": sha256_file(qa_out),
        "mother_path": mother_out.name,
        "mother_sha256": sha256_file(mother_out),
        "status": "PASS_EXACT_MEMBERSHIP_SET",
        "pit_limitation": "RETROSPECTIVE_OFFICIAL_ARCHIVE; original publication/first-seen/revision history is not proven and must not be invented.",
        "authority": {
            "research_only": True,
            "signal_authority": False,
            "ranking_authority": False,
            "capital_authority_twd": 0,
            "broker_order_execution": False,
            "production_promotion": False
        }
    }
    receipt_path = out / "TWSE_MOTHER_RECEIPT.json"
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": receipt["status"], "dates": len(seen_dates), "rows": rows_written, "mother_sha256": receipt["mother_sha256"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
