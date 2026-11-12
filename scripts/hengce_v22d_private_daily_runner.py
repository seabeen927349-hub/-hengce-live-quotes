#!/usr/bin/env python3
"""Private V2.2D continuation from existing HENGCE EOD three-leg receipts.

NO NEW MARKET COLLECTOR. NO PRIVATE MODEL OR MOTHER UPLOAD. NO ORDERS.
Reads a local checkout of the ORIGINAL eod/YYYYMMDD shards and joins onto a
SHA-pinned, PRIVATE 2026 canonical mother in a PRIVATE working directory.
Then calls the original checkpoint inference and the existing scan router.
All outputs remain research-only, because historical TDCC first-release PIT
is still not fully certified.
"""
from __future__ import annotations

import argparse
import csv
from datetime import date, datetime, timedelta
import hashlib
import json
import os
from pathlib import Path
import shutil
from zoneinfo import ZoneInfo

try:
    from scripts.hengce_v22d_private_original_inference import (
        infer, digest, KNOWN_20261111_CANONICAL_HASH)
except ModuleNotFoundError:
    from hengce_v22d_private_original_inference import (
        infer, digest, KNOWN_20261111_CANONICAL_HASH)

TZ = ZoneInfo("Asia/Taipei")
COLUMNS = ["Date", "Ticker", "Name", "Volume", "Turnover", "Open", "High",
           "Low", "Close", "Margin_MarginBalance", "ForeignNet",
           "TrustNet", "TotalNet"]
REQUIRED = {
    "price": {"Date", "Ticker", "Name", "VolumeShares", "TurnoverTWD",
              "Open", "High", "Low", "Close"},
    "margin": {"Date", "Ticker", "MarginBalance"},
    "institutional": {"Date", "Ticker", "ForeignNet", "TrustNet", "TotalNet"},
}


class DailyBlocked(ValueError):
    pass


def read_json(path):
    try:
        obj = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(obj, dict):
            raise ValueError("not object")
        return obj
    except (OSError, ValueError, UnicodeError) as exc:
        raise DailyBlocked("ORIGINAL_RECEIPT_UNREADABLE:" + str(path)) from exc


def official_days(root, first, last):
    cal = read_json(root / "governance/TWSE_TRADING_CALENDAR_2026_v1.json")
    extra = read_json(root / "governance/TWSE_EXTRAORDINARY_CLOSURES_2026_v1.json")
    if (cal.get("market") != "TWSE" or cal.get("calendar_year") != 2026 or
        extra.get("market") != "TWSE" or extra.get("calendar_year") != 2026):
        raise DailyBlocked("ORIGINAL_TWSE_CALENDAR_UNVERIFIED")
    closed = set(cal["closed_dates"])
    closed.update(x["date"] for x in extra["closures"] if x["kind"] == "CLOSED")
    out = []
    d = first + timedelta(days=1)
    while d <= last:
        if d.weekday() < 5 and d.isoformat() not in closed:
            out.append(d)
        d += timedelta(days=1)
    return out


def recent_mother_date(path, expected_hash=KNOWN_20261111_CANONICAL_HASH):
    if digest(path) != expected_hash:
        raise DailyBlocked("PRIVATE_CANONICAL_PIN_MISMATCH")
    maximum = None
    seen = 0
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != COLUMNS:
            raise DailyBlocked("PRIVATE_CANONICAL_SCHEMA_MISMATCH")
        for row in reader:
            seen += 1
            value = row["Date"]
            if maximum is None or value > maximum:
                maximum = value
    if not maximum or seen < 100000:
        raise DailyBlocked("PRIVATE_CANONICAL_COVERAGE_INSUFFICIENT")
    return date.fromisoformat(maximum)


def valid_day(root, day, observed_at=None):
    """Check ALL original source receipts, digests, keys, schema and coverage."""
    observed_at = observed_at or datetime.now(TZ)
    if observed_at.tzinfo is None:
        raise DailyBlocked("OBSERVATION_TIMESTAMP_NAIVE")
    folder = root / "eod" / day.strftime("%Y%m%d")
    st = read_json(folder / "status.json")
    mother = read_json(folder / "receipts/mother.json")
    if (st.get("status") != "COMPLETE" or st.get("target_date") != day.isoformat() or
        st.get("three_leg_complete") is not True or st.get("formal_complete_day") is not True or
        st.get("downstream_ready") is not True or st.get("mother_status") != "COMPLETE" or
        st.get("second_mother") is not False or st.get("broker_order_execution") is not False or
        st.get("model_authority_created") is not False):
        raise DailyBlocked("ORIGINAL_EOD_THREE_LEG_NOT_COMPLETE:" + day.isoformat())
    if (mother.get("status") != "PASS" or
        mother.get("artifact") != "EOD_TO_CANONICAL_HISTORICAL_MOTHER_BRIDGE_RECEIPT" or
        mother.get("target_date") != day.isoformat() or
        mother.get("mother_latest_date") != day.isoformat() or
        mother.get("integrity_status") != "PASS" or
        mother.get("model_or_schema_mutated") is not False or
        mother.get("second_mother") is not False or
        mother.get("three_leg_complete") is not True or
        mother.get("missing_evidence_is_null") is not True or
        mother.get("mother_sha256") != st.get("mother_sha256")):
        raise DailyBlocked("ORIGINAL_EOD_MOTHER_RECEIPT_INVALID:" + day.isoformat())
    try:
        published = datetime.fromisoformat(st["updated_at_taipei"]).astimezone(TZ)
        if published > observed_at.astimezone(TZ):
            raise DailyBlocked("ORIGINAL_EOD_RECEIPT_FROM_FUTURE")
    except (ValueError, TypeError, KeyError) as exc:
        raise DailyBlocked("ORIGINAL_EOD_TIME_NOT_VERIFIED") from exc
    legs = {}
    proof = {"date": day.isoformat(), "mother_sha256": mother["mother_sha256"]}
    for leg in ("price", "margin", "institutional"):
        rec = read_json(folder / "receipts" / (leg + ".json"))
        files = sorted(folder.glob(leg + "_[1-9].csv"))
        expected_files = sorted(rec.get("files") or [])
        if (rec.get("status") != "COMPLETE" or rec.get("target_date") != day.isoformat()
            or rec.get("leg") != leg or rec.get("model_authority_created") is not False
            or not files or expected_files != [f.name for f in files]):
            raise DailyBlocked("ORIGINAL_EOD_LEG_SET_INVALID:" + leg)
        h = hashlib.sha256()
        for file in files:
            h.update(file.name.encode("utf-8"))
            h.update(b"\0")
            h.update(file.read_bytes())
            h.update(b"\0")
        sha = h.hexdigest()
        if (sha != rec.get("sha256") or sha != st.get(leg + "_sha256") or
            sha != mother.get("promoted_leg_sha256", {}).get(leg)):
            raise DailyBlocked("ORIGINAL_EOD_LEG_SHA_MISMATCH:" + leg)
        if (rec.get("rows") != st.get(leg + "_rows") or rec.get("rows", 0) < 900):
            raise DailyBlocked("ORIGINAL_EOD_LEG_COVERAGE_INVALID:" + leg)
        rows = {}
        for file in files:
            with file.open("r", encoding="utf-8-sig", newline="") as handle:
                rdr = csv.DictReader(handle)
                if not REQUIRED[leg].issubset(rdr.fieldnames or []):
                    raise DailyBlocked("ORIGINAL_EOD_LEG_SCHEMA_INVALID:" + leg)
                for row in rdr:
                    ticker = row["Ticker"].strip()
                    if (row["Date"] != day.isoformat() or len(ticker) != 4 or
                        not ticker.isdigit() or ticker.startswith("0") or ticker in rows):
                        raise DailyBlocked("ORIGINAL_EOD_LEG_ROW_INVALID:" + leg)
                    rows[ticker] = row
        if len(rows) != rec["rows"]:
            raise DailyBlocked("ORIGINAL_EOD_LEG_ROWCOUNT_MISMATCH:" + leg)
        legs[leg] = rows
        proof[leg + "_sha256"] = sha
        proof[leg + "_rows"] = len(rows)
    output = []
    for ticker, price in sorted(legs["price"].items()):
        margin = legs["margin"].get(ticker)
        inst = legs["institutional"].get(ticker)
        def clean(row, field):
            if row is None:
                return ""
            v = str(row.get(field, "") or "").replace(",", "").strip()
            return "" if v in ("-", "--", "---") else v
        output.append({
            "Date": day.isoformat(), "Ticker": ticker,
            "Name": clean(price, "Name"),
            "Volume": clean(price, "VolumeShares"),
            "Turnover": clean(price, "TurnoverTWD"),
            "Open": clean(price, "Open"), "High": clean(price, "High"),
            "Low": clean(price, "Low"), "Close": clean(price, "Close"),
            "Margin_MarginBalance": clean(margin, "MarginBalance"),
            "ForeignNet": clean(inst, "ForeignNet"),
            "TrustNet": clean(inst, "TrustNet"),
            "TotalNet": clean(inst, "TotalNet"),
        })
    return output, proof


def extend_original_mother(repo_root, original_2026, target_date, work_dir,
                           baseline_sha=KNOWN_20261111_CANONICAL_HASH,
                           observed_at=None):
    """Only a disposable private input, NEVER a second published source mother."""
    repo_root = Path(repo_root)
    original_2026 = Path(original_2026)
    work_dir = Path(work_dir)
    observed_at = observed_at or datetime.now(TZ)
    old_date = recent_mother_date(original_2026, baseline_sha)
    decision = date.fromisoformat(target_date)
    if decision < old_date:
        raise DailyBlocked("TARGET_BEFORE_CANONICAL_CUTOFF")
    dates = official_days(repo_root, old_date, decision)
    if not dates:
        if decision != old_date:
            raise DailyBlocked("TARGET_SESSION_MISSING")
        return original_2026, baseline_sha, []
    work_dir.mkdir(parents=True, exist_ok=True)
    work_dir.chmod(0o700)
    target = work_dir / ("v22d_private_original_eod_input_" + target_date.replace("-", "") + ".csv")
    tmp = target.with_suffix(".tmp")
    proofs = []
    with original_2026.open("rb") as src, tmp.open("wb") as dest:
        shutil.copyfileobj(src, dest)
        # The existing canonical file must end at a line boundary.
        with original_2026.open("rb") as src_tail:
            src_tail.seek(-1, os.SEEK_END)
            if src_tail.read(1) not in (b"\n", b"\r"):
                raise DailyBlocked("ORIGINAL_CANONICAL_MISSING_FINAL_NEWLINE")
        with tmp.open("a", encoding="utf-8", newline="") as dest_text:
            writer = csv.DictWriter(dest_text, fieldnames=COLUMNS, lineterminator="\n")
            for day in dates:
                rows, proof = valid_day(repo_root, day, observed_at)
                writer.writerows(rows)
                proofs.append(proof)
    os.chmod(tmp, 0o600)
    os.replace(tmp, target)
    return target, digest(target), proofs


def latest_original_day(repo_root, now=None):
    now = now or datetime.now(TZ)
    today = now.astimezone(TZ).date()
    candidates = []
    for p in (Path(repo_root) / "eod").glob("[0-9]" * 8):
        if p.is_dir():
            try:
                d = date.strptime(p.name, "%Y%m%d")
            except (ValueError, AttributeError):
                try:
                    d = datetime.strptime(p.name, "%Y%m%d").date()
                except ValueError:
                    continue
            if d <= today and d.weekday() <= 3 and (p / "status.json").exists():
                # Candidate's complete three-leg and receipt is checked again
                # in extend_original_mother before it can enter the model.
                st = read_json(p / "status.json")
                if st.get("status") == "COMPLETE" and st.get("three_leg_complete") is True:
                    candidates.append(d)
    if not candidates:
        raise DailyBlocked("NO_COMPLETED_ORIGINAL_MON_THU_EOD")
    return max(candidates)


def run(args):
    from datetime import datetime as datetime_type
    try:
        from scripts.hengce_scan_once_router import report
    except ModuleNotFoundError:
        from hengce_scan_once_router import report
    now = datetime_type.now(TZ)
    date_string = args.decision_date or latest_original_day(args.repo_root, now).isoformat()
    decision = date.fromisoformat(date_string)
    if decision.weekday() > 3 or decision > now.date():
        raise DailyBlocked("NOT_VALID_ORIGINAL_V22D_DECISION_SESSION")
    p, sha, proofs = extend_original_mother(
        args.repo_root, args.original_2026_canonical, date_string,
        args.private_work_dir, observed_at=now)
    replay = infer(args.original_price_mother, args.original_tdcc_mother,
                   p, args.private_original_model, date_string, sha)
    path = Path(args.private_work_dir)
    path.mkdir(parents=True, exist_ok=True)
    path.chmod(0o700)
    replay_path = path / ("v22d_private_replay_" + decision.strftime("%Y%m%d") + ".json")
    scan_path = path / ("hengce_scan_once_" + decision.strftime("%Y%m%d") + ".json")
    replay["source_eod_receipts"] = proofs
    # Re-seal the report after adding original EOD proof lineage.
    replay.pop("receipt_sha256", None)
    replay["receipt_sha256"] = hashlib.sha256(
        json.dumps(replay, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    replay_path.write_text(json.dumps(replay, ensure_ascii=False, sort_keys=True,
                                      indent=2, allow_nan=False) + "\n", encoding="utf-8")
    os.chmod(replay_path, 0o600)
    scan = report(now, Path(args.repo_root), v22d_private_report=str(replay_path))
    state = scan["reporting"]["v22d_private_original_model_replay"]["status"]
    if state != "PRIVATE_V22D_ORIGINAL_REPLAY_VERIFIED_RESEARCH_ONLY":
        raise DailyBlocked("SCAN_ROUTER_REJECTED_PRIVATE_REPLAY:" + state)
    scan_path.write_text(json.dumps(scan, ensure_ascii=False, sort_keys=True,
                                    indent=2, allow_nan=False) + "\n", encoding="utf-8")
    os.chmod(scan_path, 0o600)
    return {"status": replay["status"], "decision_date": date_string,
            "fixed_universe": replay["fixed_cohort_count"],
            "qualified": replay["qualified_count"],
            "top5": [x["ticker"] for x in replay["top5"]],
            "eod_days_extended": [x["date"] for x in proofs],
            "report": str(replay_path), "scan": str(scan_path),
            "trading_authority": False}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo-root", type=Path, required=True)
    ap.add_argument("--original-price-mother", type=Path, required=True)
    ap.add_argument("--original-tdcc-mother", type=Path, required=True)
    ap.add_argument("--original-2026-canonical", type=Path, required=True)
    ap.add_argument("--private-original-model", type=Path, required=True)
    ap.add_argument("--private-work-dir", type=Path, required=True)
    ap.add_argument("--decision-date")
    args = ap.parse_args()
    print(json.dumps(run(args), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
