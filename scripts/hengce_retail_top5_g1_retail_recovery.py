#!/usr/bin/env python3
"""Recover original HENGCE G1 15-tier <=10-lot holder observations for V2.2.

Verifies the pre-existing 457-week G1 research-mother three-week derivative.
This is NOT evidence of historical FIRST OBSERVED / real-time publication,
NOT a canonical ownership replacement, and never a live candidate authority.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from hengce_retail_top5_vessel_bridge import DataBlocked, validate_output_target

TW = ZoneInfo("Asia/Taipei")
MANIFEST_FILE = "ownership/tdcc/research_recovery_20261110/v22_g1_3w_retro_manifest.json"
ORIGINAL_PARENT_SHA = "71083d73a791b6bf25770139c65e8d29012a44e31c39f66479806bf5a562bc88"
EXTRACT_SHA = "65d6d4e14cab9520296453c8af1ea8b98b1521af32ed8d47f29427c9ad7d595e"
EXPECTED_DATES = ["20261008", "20261016", "20261022"]
EXPECTED_COUNTS = {"20261008": 1082, "20261016": 1082, "20261022": 1084}
EXPECTED_RAW_SHAS = {
    "20261008": "6031bad8b0e053fc1bef9244455496ce295942290dcf653c52b28a832dd79385",
    "20261016": "96afe96211f82c3c2fddb0ed3ee26a1f22171441f25bff33a8c2b5837484c3b2",
    "20261022": "3da86219dc7f100e70fc9e08df79010534b88ed217f142c4cee6dc56c23c7523",
}
COLUMNS = ["SnapshotDate", "Ticker", "HolderLe10Lots", "RetailPeopleValid",
           "RawSourceKind", "RawSourceSHA256", "PITReleaseStatus"]


def expected_decision(decision: date):
    if decision != date(2026, 11, 6):
        raise DataBlocked("RESEARCH_SLICE_ONLY_VALID_FOR_2026_11_06")


def verified_panel(root: Path, decision: date):
    expected_decision(decision)
    manifest_path = root / MANIFEST_FILE
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise DataBlocked("G1_RETAIL_MOTHER_MANIFEST_UNAVAILABLE") from exc
    expected_manifest = {
        "schema": "HENGCE_V22_G1_TDCC_3W_MOTHER_EXTRACT_V1",
        "parent_sha256": ORIGINAL_PARENT_SHA,
        "parent_audit_status": "SOURCE_FULL_WEEK_PANEL_AUDITED_RESTRICTED_RETROSPECTIVE_ONLY",
        "parent_matched_stockweeks": 443341,
        "parent_source_generated_as_of": "2026-11-07",
        "decision": "2026-11-06",
        "lag_calendar_days": 14,
        "cutoff": "2026-10-23",
        "weekly_dates": EXPECTED_DATES,
        "rows_by_week": EXPECTED_COUNTS,
        "raw_source_sha256_by_week": EXPECTED_RAW_SHAS,
        "extracted_total_rows": 3248,
        "extracted_sha256": EXTRACT_SHA,
        "extracted_path": "ownership/tdcc/research_recovery_20261110/v22_g1_retail_20261008_16_22_retro.csv",
        "first_observed_proof": "UNVERIFIED_FOR_ALL_HISTORICAL_SLICES",
        "research_authority": "RETROSPECTIVE_ONLY_NOT_POINT_IN_TIME_APPROVED",
        "formal_tdcc_vessel_mutated": False,
        "formal_selection_authority": False,
        "trading_authority": False,
        "authorized_lots": 0,
    }
    for key, expect in expected_manifest.items():
        if manifest.get(key) != expect:
            raise DataBlocked("G1_RETAIL_MOTHER_MANIFEST_MISMATCH:" + key)
    cutoff = decision - timedelta(days=14)
    if date.fromisoformat("2026-10-22") > cutoff:
        raise DataBlocked("G1_RETAIL_LAG_CUTOFF_VIOLATION")
    p = root / manifest["extracted_path"]
    try:
        binary = p.read_bytes()
    except OSError as exc:
        raise DataBlocked("G1_RETAIL_PANEL_SLICE_UNAVAILABLE") from exc
    if hashlib.sha256(binary).hexdigest() != EXTRACT_SHA:
        raise DataBlocked("G1_RETAIL_PANEL_SLICE_SHA_MISMATCH")
    try:
        reader = csv.DictReader(io.StringIO(binary.decode("utf-8")))
        if reader.fieldnames != COLUMNS:
            raise DataBlocked("G1_RETAIL_PANEL_FIELDS_INVALID")
        rows = []
        seen = set()
        counts = Counter()
        for row in reader:
            d = row["SnapshotDate"]; ticker = row["Ticker"]
            if (d not in EXPECTED_DATES or not (len(ticker) == 4 and ticker.isdigit())
                or (d, ticker) in seen):
                raise DataBlocked("G1_RETAIL_PANEL_KEY_INVALID")
            seen.add((d, ticker))
            if (row["RawSourceKind"] != "TDCC_OFFICIAL_CSV"
                or row["RawSourceSHA256"] != EXPECTED_RAW_SHAS[d]
                or row["PITReleaseStatus"] != "FIRST_OBSERVED_CANNOT_ASSUME_ON_REFERENCE_DATE"
                or row["RetailPeopleValid"] != "true"):
                raise DataBlocked("G1_RETAIL_PANEL_SOURCE_OR_VALIDITY_INVALID")
            raw_people = row["HolderLe10Lots"]
            if not raw_people.isdecimal() or int(raw_people) < 0:
                raise DataBlocked("G1_RETAIL_PANEL_PEOPLE_INVALID")
            counts[d] += 1
            rows.append([d, ticker, raw_people, "true"])
    except (UnicodeError, csv.Error, KeyError) as exc:
        raise DataBlocked("G1_RETAIL_PANEL_PARSE_ERROR") from exc
    if dict(counts) != EXPECTED_COUNTS or len(rows) != 3248:
        raise DataBlocked("G1_RETAIL_PANEL_COUNTS_UNVERIFIED")
    return rows, manifest


def audit(root: Path, decision: date, *, today=None, importer=verified_panel):
    today = today or datetime.now(TW).date()
    status = {
        "schema": "HENGCE_V22_G1_RESEARCH_TDCC_MOTHER_RECOVERY_V1",
        "mode": "RETROSPECTIVE_RETAIL_DATA_RECOVERY_NO_PIT",
        "decision": decision.isoformat(),
        "research_data_status": "BLOCKED",
        "official_pit_first_observed_verified": False,
        "formal_eod_mutated": False,
        "formal_tdcc_mutated": False,
        "live_selector_active": False,
        "model_selection_performed": False,
        "top5": [],
        "formal_selection_authority": False,
        "trading_authority": False,
        "authorized_lots": 0,
        "capital_authority_twd": 0,
        "broker_execution": False,
        "blockers": [],
        "source_provenance": None,
    }
    if decision > today:
        status["blockers"].append("DECISION_IN_FUTURE")
        return status, []
    try:
        rows, manifest = importer(root, decision)
        status["source_provenance"] = {
            "original_g1_457_week_panel_sha256": manifest["parent_sha256"],
            "extracted_sha256": manifest["extracted_sha256"],
            "matched_stockweeks": manifest["parent_matched_stockweeks"],
            "per_snapshot": manifest["rows_by_week"],
            "raw_sha_by_snapshot": manifest["raw_source_sha256_by_week"],
            "last_snapshot": EXPECTED_DATES[-1],
            "data_available_as_of": manifest["parent_source_generated_as_of"],
            "historical_publication_time": "UNVERIFIED",
        }
        status["research_data_status"] = "THREE_WEEK_RETAIL_MOTHER_RECOVERED_RETROSPECTIVE_ONLY"
        return status, rows
    except (DataBlocked, ValueError, TypeError, OSError) as exc:
        status["blockers"].append("RESEARCH_G1_RECOVERY_FAILED:" + str(exc))
        return status, []


def save(repo: Path, dest: Path, status: dict, rows):
    target = validate_output_target(repo, dest)
    target.mkdir(parents=True, exist_ok=False)
    (target / "retail_mother_recovery_status.json").write_text(
        json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if status["research_data_status"] == "THREE_WEEK_RETAIL_MOTHER_RECOVERED_RETROSPECTIVE_ONLY":
        with (target / "weekly_3snapshot_research_only.csv").open("x", encoding="utf-8-sig", newline="") as file:
            writer = csv.writer(file); writer.writerow(COLUMNS[:4]); writer.writerows(rows)


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    cli.add_argument("--decision", default="2026-11-06")
    cli.add_argument("--output", type=Path, required=True)
    args = cli.parse_args()
    try:
        decision = date.fromisoformat(args.decision)
        status, rows = audit(args.repo_root, decision)
        save(args.repo_root, args.output, status, rows)
        print(json.dumps({
            "status": status["research_data_status"],
            "retail_rows": len(rows),
            "snapshots": EXPECTED_DATES,
            "historical_pit_verified": False,
            "selection_ran": False,
            "top5_count": 0,
            "broker_execution": False,
            "blockers": status["blockers"],
        }, ensure_ascii=False))
        return 0
    except (DataBlocked, ValueError, OSError) as exc:
        cli.exit(2, "G1_RESEARCH_RECOVERY_ERROR:" + str(exc) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
