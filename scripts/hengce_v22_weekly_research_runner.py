#!/usr/bin/env python3
"""Original V2.2 screen on existing HENGCE EOD and <=10-lot TDCC research mother.

No new vendor/source. Uses original immutable PR #64 screen.py (not a fork);
existing verified canonical EOD, pinned historical mother for actual gaps, the
pinned 457-week G1 retail extract, and later canonical TDCC snapshots.
Publishes RESEARCH ONLY, with per-snapshot PIT caveats and zero order authority.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from hengce_retail_top5_vessel_bridge import (
    DataBlocked, parse_number, read_eod_price, tdcc, validate_output_target,
)
from hengce_retail_top5_mother_price_recovery import verified_research_extract
from hengce_retail_top5_g1_retail_recovery import verified_panel
from hengce_retail_top5_readiness import expected_sessions, latest_friday
from hengce_twse_calendar import is_trading_day, load_manifest
from hengce_retail_top5_original_v22_retro_replay import original_screen_module

TW = ZoneInfo("Asia/Taipei")
RESEARCH_START = date(2026, 11, 6)
MODEL_COMMIT = "4a0f98fd2bd2a65deb2ebaf61e15e77c6a7893d6"
CHIP_PARENT_SHA = "71083d73a791b6bf25770139c65e8d29012a44e31c39f66479806bf5a562bc88"
EOD_PARENT_SHA = "b3275f8d58779fbec864a05066414d27e80cef8a68a76a08051f93808f1f8c93"
RECONCILED_TDCC_DATE = "20261030"
RECONCILED_TDCC_SHA = "18b34f6eeb80229941f51200558fcc3fec9d405e9b7eb47aceca377e9f18f184"
DAILY_COLUMNS = ["Date", "Ticker", "Close", "Volume", "Turnover"]
CHIP_COLUMNS = ["SnapshotDate", "Ticker", "HolderLe10Lots", "RetailPeopleValid"]


def _dt(text: str) -> datetime:
    ts = datetime.fromisoformat(text)
    if ts.tzinfo is None:
        raise DataBlocked("NAIVE_PROVENANCE_TIMESTAMP")
    return ts.astimezone(TW)


def _parse_snap(s: str) -> date:
    if not (len(s) == 8 and s.isdigit()):
        raise DataBlocked("TDCC_SNAPSHOT_DATE_INVALID")
    return date.fromisoformat(f"{s[:4]}-{s[4:6]}-{s[6:]}")


def _parse_canonical_compat(root: Path, snap: str, *, decision: date):
    """Canonical original TDCC parser; tightly scoped 10/30 receipt-time mismatch.

    Existing original TDCC receipt says 2026-10-31; immutable first-observed
    proof says 2026-11-01. The latter (later) is used, never the earlier time.
    Other mismatches remain rejected. Does not rewrite TDCC canonical evidence.
    """
    folder = root / "ownership" / "tdcc" / snap
    rawpath, receiptpath = folder / "tdcc_1_5_raw.csv", folder / "receipt.json"
    cutoff = decision - timedelta(days=14)
    asof = datetime.combine(decision, time.max, tzinfo=TW)
    try:
        rows, evidence = tdcc(rawpath, receiptpath, cutoff=cutoff, asof_datetime=asof)
        return rows, {**evidence, "source_type": "CANONICAL_TDCC_FIRST_OBSERVED_STRICT",
                      "research_pit_confidence": "FIRST_OBSERVED_VERIFIED"}
    except DataBlocked as exc:
        if snap != RECONCILED_TDCC_DATE or str(exc) != "TDCC_RECEIPT_PROOF_TIME_MISMATCH":
            raise
    try:
        receipt = json.loads(receiptpath.read_text(encoding="utf-8"))
        raw = rawpath.read_bytes()
    except (ValueError, OSError) as exc:
        raise DataBlocked("TDCC_RECONCILE_SOURCE_UNREADABLE") from exc
    digest = hashlib.sha256(raw).hexdigest()
    if (digest != RECONCILED_TDCC_SHA or receipt.get("source_sha256") != digest
        or receipt.get("snapshot_date") != snap or receipt.get("status") != "COMPLETE"
        or receipt.get("source_owner") != "TDCC"
        or receipt.get("model_authority_created") is not False):
        raise DataBlocked("TDCC_RECONCILE_SOURCE_HASH_OR_AUTHORITY_BAD")
    proofpath = root / "ownership" / "tdcc" / "provenance" / "first_observed" / (digest + ".json")
    try:
        proof = json.loads(proofpath.read_text(encoding="utf-8"))
        obs = _dt(proof["first_observed_at_taipei"])
        receipt_obs = _dt(receipt["observed_at_taipei"])
    except (OSError, KeyError, TypeError, ValueError) as exc:
        raise DataBlocked("TDCC_RECONCILE_PROOF_UNREADABLE") from exc
    if (proof.get("payload_sha256") != digest
        or proof.get("snapshot_reference_date") != "2026-10-30"
        or proof.get("provenance_source_authority") != "CANONICAL_VESSEL_RESPONSE_ONLY"
        or proof.get("ownership_and_provenance_share_exact_response_bytes") is not True
        or proof.get("official_published_at") is not None
        or obs < receipt_obs or obs > asof or _parse_snap(snap) > cutoff):
        raise DataBlocked("TDCC_RECONCILE_PROOF_INVALID_OR_AFTER_DECISION")
    # Need to parse the SAME authenticated raw bytes, never synthesize a receipt.
    try:
        reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
        if not {"資料日期","證券代號","持股分級","人數","股數"}.issubset(reader.fieldnames or []):
            raise DataBlocked("TDCC_RECONCILE_RAW_COLUMNS_INVALID")
        grades = {}
        seen = set()
        for r in reader:
            t = str(r["證券代號"]).strip()
            if len(t) != 4 or not t.isdigit() or t[0] == "0":
                continue
            if r["資料日期"] != snap:
                raise DataBlocked("TDCC_RECONCILE_WRONG_RAW_DATE")
            g = parse_number(r["持股分級"], integral=True)
            if g not in (1,2,3):
                continue
            if (t,g) in seen:
                raise DataBlocked("TDCC_RECONCILE_DUPLICATE_GRADE")
            seen.add((t,g))
            people = parse_number(r["人數"], integral=True)
            shares = parse_number(r["股數"], integral=True)
            grades.setdefault(t,{})[g] = (people,shares)
        rows = [[snap,t,str(sum(g[gx][0] for gx in (1,2,3))),"true"]
                for t,g in grades.items() if set(g)=={1,2,3}]
    except (UnicodeError, csv.Error, TypeError, KeyError) as exc:
        raise DataBlocked("TDCC_RECONCILE_RAW_PARSE_BAD") from exc
    if len(rows) < 900:
        raise DataBlocked("TDCC_RECONCILE_TOO_FEW_HOLDERS")
    return rows, {
        "snapshot_date":snap, "valid_tickers":len(rows),"raw_sha256":digest,
        "observed_at_taipei":obs.isoformat(),
        "receipt_observed_at_taipei":receipt_obs.isoformat(),
        "source_type":"CANONICAL_TDCC_FIRST_OBSERVED_RECONCILED_RESEARCH_ONLY",
        "research_pit_confidence":"LATER_VERIFIED_FIRST_OBSERVED_TIME_USED",
        "note":"Original canonical receipt conflicts with immutable proof; research-only reconciliation",
    }


def inputs(root: Path, decision: date, *, asof: datetime | None = None,
           price_reader=read_eod_price, historical_price_reader=verified_research_extract,
           historical_retail_reader=verified_panel, tdcc_reader=_parse_canonical_compat):
    """Read only existing original HENGCE files, reject invalid/missing weekly inputs."""
    now = (asof or datetime.now(TW)).astimezone(TW)
    if decision.year != 2026 or decision.weekday() != 4 or decision < RESEARCH_START:
        raise DataBlocked("V22_RESEARCH_DECISION_NOT_2026_FRIDAY")
    if decision > now.date() or (decision == now.date() and now.hour < 18):
        raise DataBlocked("DECISION_EOD_NOT_YET_PUBLISHED")
    calendar, _, lineage = load_manifest()
    if not is_trading_day(decision,calendar):
        raise DataBlocked("DECISION_NOT_OFFICIAL_TWSE_SESSION")
    days = expected_sessions(decision,calendar,21)
    if len(days) != 21:
        raise DataBlocked("REQUIRED_21_TWSE_SESSIONS_ABSENT")
    prior_prices, parent_price = historical_price_reader(root)
    if parent_price.get("canonical_source_sha256") != EOD_PARENT_SHA:
        raise DataBlocked("ORIGINAL_MOTHER_PARENT_HASH_CHANGED")
    day_data, day_proofs, gap_days = [], [], []
    for day in days:
        d = date.fromisoformat(day)
        try:
            observations, proof = price_reader(root,d)
            day_proofs.append({"date":day, "source":"HENGCE_CANONICAL_EOD",
                               "price_sha256":proof["sha256"],"rows":len(observations)})
        except (DataBlocked,OSError) as exc:
            status = root / "eod" / day.replace("-","") / "status.json"
            missing = not status.is_file()
            permitted = (str(exc) in {"EOD_ORIGINAL_MOTHER_NOT_READY","EOD_DATE_OR_PRICE_NOT_VERIFIED"}
                         or (missing and "FileNotFoundError" in str(exc)))
            if not permitted or day not in prior_prices:
                raise DataBlocked("ORIGINAL_EOD_INVALID_NO_SAFE_RESEARCH_FALLBACK:"+day+":"+str(exc)) from exc
            observations = prior_prices[day]
            gap_days.append(day)
            day_proofs.append({"date":day,"source":"HENGCE_VERIFIED_GAP_MOTHER_RETROSPECTIVE",
                               "research_mother_sha256":parent_price["canonical_source_sha256"],
                               "rows":len(observations)})
        if len(observations) < 900 or any(r[0] != day or len(r) != 5 for r in observations):
            raise DataBlocked("PRICE_DAY_ROWS_OR_DATE_INVALID:"+day)
        day_data.extend(observations)

    seed_rows, retail_parent = historical_retail_reader(root, date(2026,11,6))
    if retail_parent.get("parent_sha256") != CHIP_PARENT_SHA:
        raise DataBlocked("G1_457_WEEK_MOTHER_HASH_CHANGED")
    seed = {}
    for r in seed_rows:
        seed.setdefault(r[0],[]).append(r)
    cutoff = decision-timedelta(days=14)
    canonical = root/"ownership"/"tdcc"
    canonical_dates = []
    if canonical.is_dir():
        for p in canonical.iterdir():
            if p.is_dir() and len(p.name)==8 and p.name.isdigit():
                try:
                    sn=_parse_snap(p.name)
                except ValueError:
                    continue
                if sn<=cutoff:
                    canonical_dates.append(p.name)
    eligible_days = set(seed)|set(canonical_dates)
    eligible_days = sorted(x for x in eligible_days if _parse_snap(x)<=cutoff)
    if len(eligible_days)<3:
        raise DataBlocked("THREE_TDCC_SNAPSHOTS_NOT_AVAILABLE")
    chosen = eligible_days[-3:]
    snap_dates = [_parse_snap(x) for x in chosen]
    if any((b-a).days < 5 or (b-a).days > 10 for a,b in zip(snap_dates,snap_dates[1:])):
        raise DataBlocked("TDCC_RECENT_THREE_SNAPSHOTS_NONCONSECUTIVE")
    if (cutoff-snap_dates[-1]).days > 7:
        raise DataBlocked("TDCC_LAST_REFERENCE_SNAPSHOT_TOO_OLD")
    weekly, proofs, retro_days = [], [], []
    for snap in chosen:
        rows, proof = None, None
        if snap in canonical_dates:
            try:
                rows,proof = tdcc_reader(root,snap,decision=decision)
            except (DataBlocked,OSError) as exc:
                if snap not in seed:
                    raise DataBlocked("CANONICAL_TDCC_NOT_VERIFIED:"+snap+":"+str(exc)) from exc
        if rows is None:
            if snap not in seed:
                raise DataBlocked("TDCC_NEITHER_CANONICAL_NOR_G1:"+snap)
            rows = seed[snap]
            retro_days.append(snap)
            proof = {"snapshot_date":snap,
                     "source_type":"HENGCE_EXISTING_G1_457_WEEK_RESEARCH_MOTHER",
                     "research_pit_confidence":"DERIVED_PARENT_AVAILABLE_2026_11_07_NOT_ORIGINAL_OBSERVATION",
                     "parent_sha256":retail_parent["parent_sha256"],
                     "available_as_of":"2026-11-07","valid_tickers":len(rows)}
            if decision < date(2026,11,7):
                proof["known_at_decision"]=False
            else:
                proof["known_at_decision"]=True
        if len(rows)<900 or any(r[0]!=snap or len(r)!=4 for r in rows):
            raise DataBlocked("TDCC_SNAPSHOT_ROWS_INVALID:"+snap)
        weekly.extend(rows)
        proofs.append(proof)
    pit_caveat = bool(gap_days and decision < date(2026,11,7)) or (
        decision < date(2026,11,7) and bool(retro_days))
    return day_data, weekly, {
        "decision":decision.isoformat(),
        "source_cutoff":cutoff.isoformat(),
        "calendar_lineage":lineage,
        "price_days":day_proofs,
        "price_mother_recovered_days":gap_days,
        "tdcc_snapshots":proofs,
        "tdcc_g1_mother_days":retro_days,
        "eod_research_mother_sha256":EOD_PARENT_SHA,
        "tdcc_g1_457_week_mother_sha256":CHIP_PARENT_SHA,
        "price_records":len(day_data), "tdcc_records":len(weekly),
        "historical_asof_proof_missing":pit_caveat,
        "source_mode":"HENGCE_ORIGINAL_EOD_PLUS_EXISTING_RESEARCH_MOTHER_AND_TDCC",
    }


def calculate(root: Path, original: Path, decision: date, *, now: datetime | None = None,
              prepared_inputs=inputs, source_module=original_screen_module):
    """Only call pinned ORIGINAL screen.py, with provenance and zero capital authority."""
    import pandas as pd
    when=(now or datetime.now(TW)).astimezone(TW)
    daily,weekly,source=prepared_inputs(root,decision,asof=when)
    orig=source_module(original)
    def csv_buffer(header,rows):
        output=io.StringIO()
        writer=csv.writer(output)
        writer.writerow(header)
        writer.writerows(rows)
        output.seek(0)
        return output
    prices=orig.read_daily(csv_buffer(DAILY_COLUMNS,daily))
    chips=orig.read_chips(csv_buffer(CHIP_COLUMNS,weekly))
    if (prices.Date.max()!=pd.Timestamp(decision)
        or prices.Date.nunique()!=21
        or chips.Date.nunique()!=3
        or chips.Date.max()!=pd.Timestamp(date.fromisoformat(source["tdcc_snapshots"][-1]["snapshot_date"][:4]+"-"+source["tdcc_snapshots"][-1]["snapshot_date"][4:6]+"-"+source["tdcc_snapshots"][-1]["snapshot_date"][6:]))):
        raise DataBlocked("ORIGINAL_SCREEN_PREPARED_INPUT_DATE_MISMATCH")
    rows=orig.eligible_stocks(prices,chips,lag=14,decision=pd.Timestamp(decision))
    rows=rows.sort_values(["liquidity","ticker"],ascending=[False,True],kind="stable")
    if rows.ticker.duplicated().any():
        raise DataBlocked("V22_DUPLICATE_ELIGIBLE_TICKERS")
    by_ticker=prices[prices.Date.eq(pd.Timestamp(decision))].set_index("Ticker")
    ranked=[]
    for rank,r in enumerate(rows.itertuples(index=False),1):
        c=float(by_ticker.loc[r.ticker,"Close"])
        if not math.isfinite(c) or c<=0:
            raise DataBlocked("RANKED_TICKER_DECISION_CLOSE_NOT_VALID")
        ranked.append({
            "rank":rank, "ticker":r.ticker, "reference_close":c,
            "r20_pct":round(float(r.r20)*100,4),
            "r5_pct":round(float(r.r5)*100,4),
            "retail_2week_pct":round(float(r.retail_delta)*100,4),
            "median_20d_turnover_twd":int(round(float(r.liquidity))),
            "chip_date":r.chip_date.strftime("%Y-%m-%d"),
            "authorized_lots":0,
        })
    report={
        "schema":"HENGCE_V22_WEEKLY_RESEARCH_SCREEN_V1",
        "mode":"RESEARCH_TOP5_ONLY_NO_ORDER",
        "system":"HENGCE",
        "decision_date":decision.isoformat(),
        "observed_at_taipei":when.isoformat(),
        "original_screen_commit":MODEL_COMMIT,
        "source_lineage":source,
        "research_only":True,
        "research_signal_label":"UNVALIDATED_RESEARCH_RANKING_NOT_BUY_INSTRUCTION",
        "fully_prospective_performance_verified":False,
        "historical_asof_proof_missing":source["historical_asof_proof_missing"],
        "qualified_count":len(ranked),
        "top5":ranked[:5],
        "all_qualified":ranked,
        "selection_authority":False,
        "buy_signal":False,"sell_signal":False,
        "broker_execution":False,
        "capital_authority_twd":0,
        "authorized_lots":0,
        "formal_strategy_promoted":False,
    }
    return report


def save(root: Path, dest: Path, report: dict):
    target=validate_output_target(root,dest)
    target.mkdir(parents=True,exist_ok=False)
    (target/"v22_weekly_research.json").write_text(
        json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+"\n",
        encoding="utf-8",
    )
    with (target/"v22_all_qualified.csv").open("x",encoding="utf-8-sig",newline="") as file:
        writer=csv.DictWriter(file,fieldnames=[
            "rank","ticker","reference_close","r20_pct","r5_pct",
            "retail_2week_pct","median_20d_turnover_twd","chip_date","authorized_lots"])
        writer.writeheader()
        writer.writerows(report["all_qualified"])


def main():
    arg=argparse.ArgumentParser(description=__doc__)
    arg.add_argument("--repo-root",type=Path,default=Path(__file__).resolve().parents[1])
    arg.add_argument("--original-model-checkout",type=Path,required=True)
    arg.add_argument("--decision",help="Friday YYYY-MM-DD; default latest Friday Taipei")
    arg.add_argument("--output",type=Path,required=True)
    x=arg.parse_args()
    try:
        decision=date.fromisoformat(x.decision) if x.decision else latest_friday(datetime.now(TW).date())
        result=calculate(x.repo_root,x.original_model_checkout,decision)
        save(x.repo_root,x.output,result)
        print(json.dumps({
            "decision":result["decision_date"],"qualified":result["qualified_count"],
            "research_top5":[x["ticker"] for x in result["top5"]],
            "tdcc_snapshots":[x["snapshot_date"] for x in result["source_lineage"]["tdcc_snapshots"]],
            "historical_asof_proof_missing":result["historical_asof_proof_missing"],
            "broker_execution":False,
        },ensure_ascii=False))
    except (DataBlocked,ValueError,TypeError,KeyError,OSError,ImportError) as exc:
        arg.exit(2,"V22_WEEKLY_RESEARCH_INPUT_OR_SCREEN_BLOCKED:"+str(exc)+"\n")


if __name__=="__main__":
    main()
