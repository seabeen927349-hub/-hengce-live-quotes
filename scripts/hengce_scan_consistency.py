#!/usr/bin/env python3
"""Deterministic, read-only evidence guard for HENGCE 'scan once'.

This layer is an explanation/consistency ledger, not a market collector or selector.
It never promotes research to trading authority, and cannot verify GitHub Actions
runs by itself: repository-local receipts are not substitutes for live run metadata.
"""
import json
from datetime import datetime, timedelta, time
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Taipei")
LOCK_PATH = "governance/HENGCE_SCAN_ONCE_CONSISTENCY_LOCK_v1_0_20261111.json"
CALENDAR_PATH = "governance/TWSE_TRADING_CALENDAR_2026_v1.json"


def _read(root, relative):
    try:
        return json.loads((root / relative).read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None


def _session(d, calendar):
    """Conservative trading-day estimate from the existing official calendar."""
    if not isinstance(calendar, dict) or calendar.get("calendar_year") != d.year:
        return d.weekday() < 5, "WEEKDAY_ESTIMATE_CALENDAR_UNVERIFIED"
    iso = d.isoformat()
    if iso in calendar.get("closed_dates", []):
        return False, "EXISTING_TWSE_CALENDAR"
    if iso in calendar.get("explicit_open_dates", []):
        return True, "EXISTING_TWSE_CALENDAR"
    return d.weekday() < 5, "EXISTING_TWSE_CALENDAR"


def _prior_session(d, calendar):
    x = d - timedelta(days=1)
    for _ in range(14):
        if _session(x, calendar)[0]:
            return x.isoformat()
        x -= timedelta(days=1)
    return None


def _eod_receipt_complete(root, compact, obj):
    """Read and cross-check the original three-leg and canonical mother receipts."""
    if not isinstance(obj, dict):
        return False
    d = compact[:4] + "-" + compact[4:6] + "-" + compact[6:8]
    if not (obj.get("target_date") == d and obj.get("status") == "COMPLETE"
            and obj.get("formal_complete_day") is True
            and obj.get("three_leg_complete") is True
            and obj.get("mother_status") == "COMPLETE"
            and obj.get("mother_receipt_status") == "PASS"):
        return False
    for leg in ("price", "institutional", "margin"):
        if obj.get(leg + "_status") != "COMPLETE" or obj.get(leg + "_date") != d:
            return False
    mother = _read(root, "eod/" + compact + "/receipts/mother.json")
    if not (isinstance(mother, dict)
            and mother.get("target_date") == d
            and mother.get("status") == "PASS"
            and mother.get("three_leg_complete") is True
            and mother.get("integrity_status") == "PASS"
            and mother.get("mother_sha256") == obj.get("mother_sha256")):
        return False
    for leg in ("price", "institutional", "margin"):
        if mother.get("promoted_leg_sha256", {}).get(leg) != obj.get(leg + "_sha256"):
            return False
    return True


def _eod_context(root, now, calendar):
    today = now.date()
    session, calendar_source = _session(today, calendar)
    latest_date = None
    latest_status = None
    present_today = False
    todays_receipt_complete = False
    for folder in sorted((root / "eod").glob("[0-9]" * 8)) if (root / "eod").is_dir() else ():
        compact = folder.name
        if len(compact) != 8 or not compact.isdigit():
            continue
        date_string = compact[:4] + "-" + compact[4:6] + "-" + compact[6:8]
        if date_string > today.isoformat():
            continue
        record = _read(root, "eod/" + compact + "/status.json")
        if date_string == today.isoformat():
            present_today = record is not None
            todays_receipt_complete = _eod_receipt_complete(root, compact, record)
        if _eod_receipt_complete(root, compact, record):
            latest_date = date_string
            latest_status = "THREE_LEG_AND_MOTHER_RECEIPTS_COMPLETE"
    if todays_receipt_complete:
        state = "RECEIPT_COMPLETE"
    elif present_today:
        state = "TODAY_RECEIPT_INCOMPLETE_UNVERIFIED"
    elif not session:
        state = "MARKET_CLOSED_NO_NEW_EOD_EXPECTED"
    elif now.timetz().replace(tzinfo=None) >= time(23, 0):
        state = "AWAITING_PUBLISH_CONFIRMATION"
    else:
        prior = _prior_session(today, calendar)
        state = ("AWAITING_SCHEDULE" if latest_date is not None and latest_date >= prior
                 else "SOURCE_STALE_REVIEW_REQUIRED")
    return {
        "state": state,
        "today": today.isoformat(),
        "expected_original_vessel_schedule_taipei": "23:00",
        "trading_session_estimate": session,
        "calendar_source": calendar_source,
        "latest_complete_eod_date": latest_date,
        "latest_complete_eod_receipt": latest_status,
        "today_status_receipt_present": present_today,
        "failed_workflow_claim": False,
        "workflow_run_status": "NOT_CHECKED_IN_LOCAL_SNAPSHOT",
    }


def consistency_snapshot(now=None, root=None):
    """Return repeatable statuses. Missing evidence is never rewritten as failure."""
    now = now or datetime.now(TZ)
    now = (now if now.tzinfo else now.replace(tzinfo=TZ)).astimezone(TZ)
    root = Path(root) if root is not None else Path(__file__).resolve().parents[1]
    lock = _read(root, LOCK_PATH)
    valid = (
        isinstance(lock, dict)
        and lock.get("schema") == "HENGCE_SCAN_ONCE_CONSISTENCY_LOCK_V1"
        and lock.get("command") == "衡策掃一次"
        and lock.get("no_new_data_vessel") is True
        and lock.get("formal_selection_authority") is False
        and lock.get("buy_sell_signal_authority") is False
        and lock.get("broker_execution") is False
        and lock.get("capital_authority_twd") == 0
        and isinstance(lock.get("repairs"), list)
    )
    result = {
        "schema": "HENGCE_SCAN_ONCE_CONSISTENCY_EVIDENCE_V1",
        "status": "LOCK_APPLIED" if valid else "POLICY_LOCK_UNVERIFIED",
        "policy_path": LOCK_PATH,
        "as_of_taipei": now.isoformat(),
        "read_only": True,
        "does_not_run_market_collectors": True,
        "does_not_reverify_live_workflow_executions": True,
        "not_a_new_full_market_scan": True,
        "formal_selection_authority": False,
        "buy_signal": False,
        "sell_signal": False,
        "broker_execution": False,
        "capital_authority_twd": 0,
        "repair_baselines": [],
    }
    if not valid:
        result["source_status"] = "UNKNOWN_UNVERIFIED_POLICY"
        return result

    for repair in lock["repairs"]:
        if not isinstance(repair, dict):
            continue
        result["repair_baselines"].append({
            "repair_id": repair.get("id"),
            "merged_pr": repair.get("pr"),
            "merged_commit": repair.get("merged_commit"),
            "baseline": ("RECORDED_VERIFIED_REPAIR" if
                         repair.get("verification") == "HBA_WORKFLOW_COMPLETED_SUCCESS"
                         else "RECORDED_MERGED_IMPLEMENTATION"),
            "verification_run_id": repair.get("verified_run_id"),
            "current_execution_verified_by_this_guard": False,
        })

    calendar = _read(root, CALENDAR_PATH)
    result["eod"] = _eod_context(root, now, calendar)

    tdcc = _read(root, "ownership/tdcc/latest.json")
    result["tdcc"] = {
        "state": ("WEEKLY_RECEIPT_PRESENT" if isinstance(tdcc, dict)
                  and tdcc.get("status") == "COMPLETE"
                  and str(tdcc.get("snapshot_date", "")) <= now.date().strftime("%Y%m%d")
                  else "WEEKLY_RECEIPT_UNVERIFIED"),
        "snapshot_date": tdcc.get("snapshot_date") if isinstance(tdcc, dict) else None,
        "daily_retail_count_claimed": False,
    }

    hba = _read(root, "research/hba_surveillance/decision_latest.json")
    result["hba"] = {
        "state": ("RECORDED_RESEARCH_ADVISORY_READY" if isinstance(hba, dict)
                  and hba.get("status") == "RESEARCH_ADVISORY_READY"
                  and isinstance(hba.get("observed_eod_date"), str)
                  and hba["observed_eod_date"] <= now.date().isoformat()
                  else "CURRENT_RESEARCH_RECEIPT_UNVERIFIED"),
        "observed_eod_date": hba.get("observed_eod_date") if isinstance(hba, dict) else None,
        "market_covered": (hba.get("research_summary") or {}).get("market_covered")
                          if isinstance(hba, dict) else None,
        "macro": (hba.get("research_summary") or {}).get("macro")
                 if isinstance(hba, dict) else None,
    }

    weekly = _read(root, "research/retail_top5/v22_weekly_latest.json")
    historical = _read(root, "research/retail_top5/v22_research_latest.json")
    result["v22"] = {
        "state": ("WEEKLY_RESEARCH_RECEIPT_PRESENT_NEEDS_READER_VALIDATION"
                  if isinstance(weekly, dict)
                  else "HISTORICAL_RESEARCH_ONLY"
                  if isinstance(historical, dict)
                  and historical.get("status") == "RETROSPECTIVE_V22_TOP5_READY"
                  else "RESEARCH_RECEIPT_UNVERIFIED"),
        "date": (weekly.get("decision_date") if isinstance(weekly, dict)
                 else historical.get("decision_date") if isinstance(historical, dict)
                 else None),
        "formal_selector_status": "NOT_ENABLED",
        "current_buy_recommendation": False,
    }

    live = _read(root, "live/status.json")
    expire = live.get("cache_expires_at_taipei") if isinstance(live, dict) else None
    valid_cache = False
    if isinstance(expire, str):
        try:
            ex = datetime.fromisoformat(expire)
            valid_cache = ex.tzinfo is not None and ex.astimezone(TZ) >= now
        except ValueError:
            pass
    result["existing_quote_cache"] = {
        "state": ("UNEXPIRED_REPOSITORY_CACHE" if valid_cache
                  else "REPOSITORY_CACHE_STALE_OR_UNVERIFIED"),
        "snapshot_id": live.get("snapshot_id") if isinstance(live, dict) else None,
        "does_not_imply_all_fugle_quotes_broken": True,
    }

    result["runtime_modules"] = {
        "s5": "UNKNOWN_NO_CURRENT_RUNTIME_EVIDENCE",
        "escape": "UNKNOWN_NO_CURRENT_RUNTIME_EVIDENCE",
        "rms": "UNKNOWN_NO_CURRENT_RUNTIME_EVIDENCE",
    }
    result["claim_boundary"] = (
        "Existing receipts and recorded repair baselines only. Check current "
        "GitHub Actions run IDs separately before asserting a new failure "
        "or a complete fresh scan."
    )
    return result
