#!/usr/bin/env python3
"""Use the VERIFIED HENGCE 2018–2026 research mother to fill 8 PRICE history gaps.

DATA RECOVERY ONLY. No separate vendor data pipe, no TDCC fabrication, no
provisional selection promotion, no use as clean 2026-11-06 PIT evidence.
Only the pinned eight original-mother extraction days can be substituted
in an independent research report; existing canonical EOD files never change.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from hengce_retail_top5_vessel_bridge import DataBlocked, read_eod_price, validate_output_target
from hengce_retail_top5_readiness import expected_sessions, latest_friday, read_json
from hengce_twse_calendar import load_manifest, is_trading_day

TW = ZoneInfo("Asia/Taipei")
MANIFEST = "eod/source_recovery_20261110/recovery_manifest.json"
PINNED_EXTRACT_SHA = "1832a9766a6bbefe68fa4a3290f25c046409cdeab4aebdd4dc33d627b29ce678"
PINNED_PARENT_SHA = "b3275f8d58779fbec864a05066414d27e80cef8a68a76a08051f93808f1f8c93"
PERMITTED_RESEARCH_FALLBACK_ERRORS = {
    "EOD_DATE_OR_PRICE_NOT_VERIFIED",
    "EOD_ORIGINAL_MOTHER_NOT_READY",
}
COLUMNS = ["Date", "Ticker", "Close", "Volume", "Turnover"]


def _finite(raw, *, positive=False, integral=False, optional=False):
    if raw is None or str(raw).strip() == "" or (optional and str(raw).strip() == "--"):
        if optional:
            return ""
        raise DataBlocked("MOTHER_REQUIRED_NUMERIC_MISSING")
    try:
        x = float(str(raw).strip())
    except (ValueError, OverflowError):
        raise DataBlocked("MOTHER_NUMERIC_UNPARSABLE") from None
    if not math.isfinite(x) or (positive and x <= 0) or (not positive and x < 0):
        raise DataBlocked("MOTHER_NUMERIC_OUT_OF_RANGE")
    if integral and not x.is_integer():
        raise DataBlocked("MOTHER_VOLUME_NOT_INTEGER")
    return (str(int(x)) if integral else format(x, ".12g"))


def verified_research_extract(root: Path, *, sha_override=None):
    """Load pinned original-mother slice; the *entire parent* was hashed at extraction.

    sha_override exists only for isolated test fixtures, never CLI or workflow.
    """
    manifest = read_json(root / MANIFEST)
    if not isinstance(manifest, dict):
        raise DataBlocked("RESEARCH_MOTHER_MANIFEST_MISSING")
    required = {
        "schema": "HENGCE_V22_MOTHER_PRICE_RECOVERY_MANIFEST_V1",
        "canonical_source_sha256": PINNED_PARENT_SHA,
        "canonical_source_total_rows": 2111682,
        "canonical_independent_qa_status": "PASS",
        "canonical_source_not_available_before": "2026-11-07",
        "slice_path": "eod/source_recovery_20261110/mother_research_backfill_8dates.csv",
        "slice_total_rows": 8692,
        "recovery_stage_required": "FORMAL_2026_PRICE_LEG",
        "original_source_tier_required": "TWSE_2026_CANONICAL_PRICE",
        "point_in_time": "RETROSPECTIVE_EXPLORATION_ONLY_NOT_CLEAN_DECISION_TIME_PROOF",
        "may_replace_formal_eod": False,
        "may_replace_formal_tdcc": False,
        "broker_execution": False,
        "original_vessels_mutated": False,
    }
    for key, expected in required.items():
        if manifest.get(key) != expected:
            raise DataBlocked("RESEARCH_MOTHER_MANIFEST_CONTRACT_MISMATCH:" + key)
    if manifest.get("slice_sha256") != PINNED_EXTRACT_SHA:
        raise DataBlocked("RESEARCH_MOTHER_MANIFEST_HASH_MISMATCH")
    file = root / required["slice_path"]
    if not file.is_file():
        raise DataBlocked("RESEARCH_MOTHER_SLICE_ABSENT")
    raw = file.read_bytes()
    if hashlib.sha256(raw).hexdigest() != (sha_override or PINNED_EXTRACT_SHA):
        raise DataBlocked("RESEARCH_MOTHER_SLICE_SHA_MISMATCH")
    meta = manifest.get("slice_dates")
    if not isinstance(meta, list) or len(meta) != 8:
        raise DataBlocked("RESEARCH_MOTHER_EXPECTED_DATES_INVALID")
    wanted = {x["date"]: x for x in meta if isinstance(x, dict) and "date" in x}
    if len(wanted) != 8:
        raise DataBlocked("RESEARCH_MOTHER_DUPLICATE_DATES")
    rows = defaultdict(list)
    seen = set()
    blank_count = Counter()
    try:
        import io
        reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
        if set(reader.fieldnames or []) != set(COLUMNS + ["RecoveryStage", "OriginalSourceTier"]):
            raise DataBlocked("RESEARCH_MOTHER_SLICE_COLUMNS_INVALID")
        for r in reader:
            d, t = r["Date"], r["Ticker"]
            if d not in wanted or len(t) != 4 or not t.isdigit() or (d, t) in seen:
                raise DataBlocked("RESEARCH_MOTHER_ROW_KEY_OR_DATE_INVALID")
            seen.add((d, t))
            if (r["RecoveryStage"] != required["recovery_stage_required"]
                or r["OriginalSourceTier"] != required["original_source_tier_required"]):
                raise DataBlocked("RESEARCH_MOTHER_SOURCE_STAGE_INVALID")
            close = _finite(r["Close"], positive=True, optional=True)
            volume = _finite(r["Volume"], integral=True)
            turnover = _finite(r["Turnover"])
            if not close:
                blank_count[d] += 1
            rows[d].append([d, t, close, volume, turnover])
    except (UnicodeError, csv.Error, KeyError) as exc:
        raise DataBlocked("RESEARCH_MOTHER_SLICE_DECODE_ERROR:" + type(exc).__name__) from None
    if len(seen) != 8692:
        raise DataBlocked("RESEARCH_MOTHER_ROW_TOTAL_MISMATCH")
    for d, x in wanted.items():
        if (not isinstance(x.get("rows"), int) or len(rows[d]) != x["rows"]
            or len(rows[d]) < 900 or blank_count[d] != x.get("missing_close")):
            raise DataBlocked("RESEARCH_MOTHER_DATE_COVERAGE_MISMATCH:" + d)
    return dict(rows), manifest


def assemble(root: Path, decision: date, *, today: date | None = None,
             read_canonical=read_eod_price, load_extract=verified_research_extract):
    now = today or datetime.now(TW).date()
    out = {
        "schema": "HENGCE_V22_MOTHER_HISTORICAL_PRICE_RECOVERY_V1",
        "mode": "RESEARCH_DATA_REPAIR_ONLY_NOT_CLEAN_PIT",
        "decision": decision.isoformat(),
        "source_status": "BLOCKED", "research_price_continuity": False,
        "historical_pit_certified": False,
        "source_mother_first_available_date": "2026-11-07",
        "canonical_sources_unchanged": True,
        "tdcc_status": "UNREPAIRED_BY_PRICE_MOTHER",
        "model_selection_performed": False,
        "selection_authority": False,
        "top5": [], "authorized_lots": 0,
        "capital_authority_twd": 0, "broker_execution": False,
        "canonical_eod_days": 0, "mother_research_recovered_days": 0,
        "total_daily_rows": 0, "origin_by_day": [],
        "blockers": [],
    }
    if (decision.year != 2026 or decision.weekday() != 4 or decision > now):
        out["blockers"].append("DATE_NOT_ELIGIBLE_FOR_RESEARCH_RECOVERY")
        return out, []
    try:
        calendar, _, lineage = load_manifest()
        if not is_trading_day(decision, calendar):
            out["blockers"].append("DECISION_NOT_TWSE_TRADING_DAY")
            return out, []
        expected = expected_sessions(decision, calendar)
        if len(expected) != 21:
            out["blockers"].append("OFFICIAL_21_SESSIONS_NOT_AVAILABLE")
            return out, []
        out["calendar_lineage"] = lineage
        out["official_21_sessions"] = expected
        mother, manifest = load_extract(root)
        out["mother_research_extract_sha256"] = manifest["slice_sha256"]
        out["canonical_parent_mother_sha256"] = manifest["canonical_source_sha256"]
        all_rows = []
        for day in expected:
            current = date.fromisoformat(day)
            try:
                rows, proof = read_canonical(root, current)
                origin = {"date": day, "origin": "VERIFIED_ORIGINAL_EOD",
                          "stock_rows": len(rows), "verified_price_leg_sha256": proof["sha256"]}
                out["canonical_eod_days"] += 1
            except (DataBlocked, OSError, csv.Error) as exc:
                reason = str(exc)
                expected_status = root / "eod" / day.replace("-", "") / "status.json"
                absent_source = (not expected_status.exists()
                                 and reason.startswith("UNREADABLE_JSON:")
                                 and reason.endswith(":FileNotFoundError"))
                if reason not in PERMITTED_RESEARCH_FALLBACK_ERRORS and not absent_source:
                    out["blockers"].append("CANONICAL_EOD_INTEGRITY_ERROR:" + day + ":" + reason)
                    continue
                if day not in mother:
                    out["blockers"].append("NO_RESEARCH_MOTHER_SLICE_FOR_SESSION:" + day)
                    continue
                rows = mother[day]
                origin = {"date": day, "origin": "CANONICAL_MOTHER_RESEARCH_RETROSPECTIVE",
                          "stock_rows": len(rows), "original_eod_reason": reason,
                          "not_available_at_friday_20261106": day <= "2026-11-06"}
                out["mother_research_recovered_days"] += 1
            # Never use a "0" or fabricated close for an illiquid security.
            if len(rows) < 900 or any(r[0] != day or len(r) != len(COLUMNS) for r in rows):
                out["blockers"].append("DAILY_SCHEMA_OR_COVERAGE_INVALID:" + day)
                continue
            out["origin_by_day"].append(origin)
            all_rows.extend(rows)
        dates = {x["date"] for x in out["origin_by_day"]}
        out["missing_sessions_after_recovery"] = [d for d in expected if d not in dates]
        out["total_daily_rows"] = len(all_rows)
        if len(dates) == 21 and not out["blockers"]:
            out["source_status"] = "RESEARCH_PRICE_21_SESSIONS_RECOVERED_NO_PIT"
            out["research_price_continuity"] = True
        else:
            out["source_status"] = "BLOCKED_INCOMPLETE_RESEARCH_PRICE_HISTORY"
        # No separate source for small-holder <=10 lots may be inferred from the
        # capital/large-holder research mother. V2.2 selection stays disabled.
        return out, all_rows if out["research_price_continuity"] else []
    except (DataBlocked, OSError, KeyError, ValueError, TypeError) as exc:
        out["blockers"].append("MOTHER_RECOVERY_VERIFY_FAILED:" + str(exc))
        return out, []


def save(root: Path, destination: Path, report: dict, rows: list[list[str]]):
    p = validate_output_target(root, destination)
    p.mkdir(parents=True, exist_ok=False)
    (p / "mother_recovery_status.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    if report["research_price_continuity"]:
        with (p / "price_21session_research_only.csv").open("x", encoding="utf-8-sig", newline="") as fd:
            writer = csv.writer(fd)
            writer.writerow(COLUMNS)
            writer.writerows(rows)


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    cli.add_argument("--decision", help="Friday, defaults to Taipei most recent Friday")
    cli.add_argument("--output", type=Path, required=True)
    args = cli.parse_args()
    try:
        decision = date.fromisoformat(args.decision) if args.decision else latest_friday(datetime.now(TW).date())
        report, data = assemble(args.repo_root, decision)
        save(args.repo_root, args.output, report, data)
        print(json.dumps({
            "research_status": report["source_status"],
            "original_eod_days": report["canonical_eod_days"],
            "mother_recovered_days": report["mother_research_recovered_days"],
            "daily_rows": report["total_daily_rows"],
            "missing_sessions": report.get("missing_sessions_after_recovery", []),
            "top5_count": 0,
            "broker_execution": False
        }, ensure_ascii=False))
        return 0
    except (DataBlocked, OSError, ValueError, TypeError) as exc:
        cli.exit(2, "MOTHER_RESEARCH_RECOVERY_ERROR:" + str(exc) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
