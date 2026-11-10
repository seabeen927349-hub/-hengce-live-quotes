#!/usr/bin/env python3
"""Verify future V2.2 research data capability using ONLY existing canonical vessels.

No new data supplier, no historical backfill promotion, no ranking, no orders.
This is a POINT-IN-TIME (PIT) *evidence diagnostic*, not a selector. Even a
fully complete report does not grant a literature gate PASS or model authority.
"""
from __future__ import annotations

import argparse
import json
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from hengce_retail_top5_readiness import expected_sessions, latest_friday
from hengce_retail_top5_vessel_bridge import DataBlocked, read_eod_price, tdcc, validate_output_target
from hengce_twse_calendar import is_trading_day, load_manifest

TW = ZoneInfo("Asia/Taipei")


def _date_from_dir(name: str) -> date:
    if len(name) != 8 or not name.isdigit():
        raise ValueError("NOT_YYYYMMDD")
    return date.fromisoformat(name[:4] + "-" + name[4:6] + "-" + name[6:])


def _canonical_tdcc_dirs(root: Path, cutoff: date) -> list[tuple[date,Path]]:
    tdcc_dir = root / "ownership" / "tdcc"
    result = []
    if not tdcc_dir.exists():
        return []
    for p in tdcc_dir.iterdir():
        if not p.is_dir():
            continue
        try:
            d = _date_from_dir(p.name)
        except ValueError:
            continue
        if d <= cutoff:
            result.append((d,p))
    return sorted(result)[-3:]


def diagnose(root: Path, decision: date, *, now: datetime | None = None,
             eod_reader=read_eod_price, tdcc_reader=tdcc,
             calendar_loader=load_manifest, session_check=is_trading_day):
    now = (now or datetime.now(TW)).astimezone(TW)
    record = {
        "schema": "HENGCE_V22_PROSPECTIVE_PIT_EVIDENCE_CAPABILITY_V1",
        "decision": decision.isoformat(),
        "generated_at_taipei": now.isoformat(),
        "mode": "CANONICAL_SOURCE_CAPABILITY_ONLY_NO_SELECTION",
        "canonical_eod_only": True, "canonical_tdcc_only": True,
        "mother_backfill_used": False, "historical_pit_rehabilitated": False,
        "selection_performed": False, "research_top5": [],
        "formal_selection_authority": False, "trading_signal": False,
        "authorized_lots": 0, "capital_authority_twd": 0,
        "broker_execution": False, "literature_gate": "NOT_PASSED",
        "expected_eod_sessions": [], "verified_eod_sessions": [],
        "eod_issues": [], "tdcc_eligible_snapshots": [],
        "tdcc_verifications": [], "tdcc_issues": [],
        "blockers": [], "data_readiness": "BLOCKED",
        "model_ready_for_publication": False,
    }
    if decision.year != 2026 or decision.weekday() != 4 or decision > now.date():
        record["blockers"].append("DECISION_MUST_BE_PAST_2026_FRIDAY")
        return record
    try:
        cal, _, lineage = calendar_loader()
        record["calendar_lineage"] = lineage
        if not session_check(decision, cal):
            record["blockers"].append("DECISION_NOT_TWSE_SESSION")
            return record
        expected = expected_sessions(decision, cal, 21)
    except (OSError, ValueError, KeyError, TypeError):
        record["blockers"].append("OFFICIAL_TRADING_CALENDAR_NOT_VERIFIED")
        return record
    record["expected_eod_sessions"] = expected
    if len(expected) != 21:
        record["blockers"].append("OFFICIAL_21_SESSION_LOOKBACK_MISSING")
        return record
    for ds in expected:
        d = date.fromisoformat(ds)
        try:
            rows, proof = eod_reader(root, d)
            if len(rows) < 900 or proof.get("date") != ds:
                raise DataBlocked("EOD_VERIFIED_ROWS_OR_DATE_INVALID")
            record["verified_eod_sessions"].append({
                "date": ds, "rows": len(rows), "price_sha256": proof.get("sha256"),
            })
        except (DataBlocked, ValueError, TypeError, KeyError, OSError) as exc:
            record["eod_issues"].append({
                "date": ds, "status": "NOT_CANONICAL_VERIFIED",
                "reason": str(exc),
            })
    if record["eod_issues"]:
        record["blockers"].append("CANONICAL_21_SESSION_PRICE_CHAIN_INCOMPLETE")
    cutoff = decision - timedelta(days=14)
    record["tdcc_cutoff"] = cutoff.isoformat()
    snapshots = _canonical_tdcc_dirs(root, cutoff)
    record["tdcc_eligible_snapshots"] = [p.name for _,p in snapshots]
    if len(snapshots) != 3:
        record["blockers"].append("THREE_CANONICAL_TDCC_SNAPSHOTS_ABSENT")
    decision_cutoff = datetime.combine(decision,time.max,tzinfo=TW)
    proven = []
    for snap,p in snapshots:
        try:
            rows, proof = tdcc_reader(
                p / "tdcc_1_5_raw.csv",
                p / "receipt.json",
                cutoff=cutoff,
                asof_datetime=decision_cutoff,
            )
            if len(rows) < 900 or proof.get("snapshot_date") != p.name:
                raise DataBlocked("TDCC_VERIFIED_ROWS_OR_DATE_INVALID")
            record["tdcc_verifications"].append({
                "snapshot_date": p.name, "verified_holder_rows": len(rows),
                "raw_sha256": proof.get("raw_sha256"),
                "first_observed_at_taipei": proof.get("observed_at_taipei"),
                "source": "EXISTING_CANONICAL_TDCC_ONLY",
            })
            proven.append(snap)
        except (DataBlocked, ValueError, TypeError, KeyError, OSError) as exc:
            record["tdcc_issues"].append({
                "snapshot_date": p.name,
                "status": "FIRST_OBSERVED_OR_RECEIPT_NOT_VERIFIED",
                "reason": str(exc),
            })
    if record["tdcc_issues"]:
        record["blockers"].append("CANONICAL_TDCC_PIT_CHAIN_INCOMPLETE")
    if len(proven) != 3 or len(snapshots) != 3:
        record["blockers"].append("INSUFFICIENT_THREE_VERIFIED_TDCC_WEEKS")
    else:
        if any((b-a).days not in range(5,11) for a,b in zip(proven,proven[1:])):
            record["blockers"].append("TDCC_WEEK_GAP_INVALID")
        if (cutoff-proven[-1]).days > 7:
            record["blockers"].append("LAST_TDCC_WEEK_STALE")
    if not record["blockers"]:
        record["data_readiness"] = "PIT_CANONICAL_DATA_PREPARED_RESEARCH_ONLY"
    return record


def save(root: Path, output: Path, result: dict):
    dest = validate_output_target(root, output)
    dest.mkdir(parents=True,exist_ok=False)
    (dest/"prospective_pit_evidence.json").write_text(
        json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+"\n",
        encoding="utf-8",
    )
    return dest


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo-root",type=Path,default=Path(__file__).resolve().parents[1])
    p.add_argument("--decision",help="2026 Friday YYYY-MM-DD; default most recent Friday Taipei")
    p.add_argument("--output",type=Path,required=True)
    args = p.parse_args()
    try:
        today = datetime.now(TW)
        decision = date.fromisoformat(args.decision) if args.decision else latest_friday(today.date())
        result = diagnose(args.repo_root,decision,now=today)
        save(args.repo_root,args.output,result)
        print(json.dumps({
            "decision":result["decision"],
            "verified_eod":len(result["verified_eod_sessions"]),
            "expected_eod":len(result["expected_eod_sessions"]),
            "verified_tdcc":len(result["tdcc_verifications"]),
            "tdcc_reference_dates":result["tdcc_eligible_snapshots"],
            "eod_missing_dates":[z["date"] for z in result["eod_issues"]],
            "tdcc_issues":result["tdcc_issues"],
            "blockers":result["blockers"],
            "data_readiness":result["data_readiness"],
            "research_top5_count":0,"broker_execution":False
        },ensure_ascii=False))
        return 0  # Clear, machine-readable BLOCKED != silent successful selector.
    except (DataBlocked,OSError,ValueError,TypeError) as exc:
        p.exit(2,"PIT_CAPABILITY_AUDIT_ERROR:"+str(exc)+"\n")


if __name__=="__main__":
    raise SystemExit(main())
