#!/usr/bin/env python3
"""Read-only, zero-authority operational health audit for the CURRENT HENGCE system.

Does not reuse the retired Q017 system-health contract, fetch market data,
generate signals, alter rankings, write to governed vessels, or place orders.
Optional GitHub Actions metadata is solely for workflow liveness.
"""
import argparse
from datetime import date, datetime, timedelta
import hashlib
import json
import os
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Taipei")
WORKFLOWS = {
    "eod_workflow": "hengce-original-eod-ingest.yml",
    "tdcc_workflow": "hengce-tdcc-ownership-daily.yml",
    "hba_workflow": "hengce-hba-daily-surveillance.yml",
    "overseas_workflow": "hengce-overseas-sox-vix-premarket.yml",
    "v22_weekly_workflow": "hengce-v22-weekly-existing-vessel-research.yml",
}
ZERO = {"selection_authority": False, "signal_authority": False,
        "capital_authority_twd": 0, "broker_order_execution": False}


def load(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None


def item(state, reason, **evidence):
    return {"state": state, "reason": reason, "evidence": evidence}


def digest(path):
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def day(value):
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value) if "-" in value else datetime.strptime(value, "%Y%m%d").date()
    except ValueError:
        return None


def timestamp(value):
    try:
        t = datetime.fromisoformat(value)
        return t.astimezone(TZ) if t.tzinfo else None
    except (TypeError, ValueError):
        return None


def latest_prior_weekday(today):
    d = today - timedelta(days=1)
    while d.weekday() > 4:
        d -= timedelta(days=1)
    return d


def evaluate(root, now, workflow_runs=None, collection_error=None):
    """Pure evaluator; workflow_runs maps exact workflow YAML filenames to API rows."""
    root = Path(root)
    now = now.astimezone(TZ)
    today = now.date()
    parts = {}

    scan = load(root / "hengce/HENGCE_SCAN_ONCE_CONTRACT_LATEST.json") or {}
    active = load(root / "governance/HENGCE_ACTIVE_STRATEGY_AUTHORITY_20261105.json") or {}
    locked = (scan.get("status") == active.get("status") == "NO_ACTIVE_SELECTION_STRATEGY"
              and scan.get("active_strategy_count") == active.get("active_strategy_count") == 0
              and scan.get("broker_order_execution") is False
              and active.get("broker_order_execution") is False
              and scan.get("capital_authority_twd") == active.get("capital_authority_twd") == 0
              and active.get("selection_authority") is False
              and active.get("q017") == "RETIRED_ALL_OPERATIONAL_PATHS")
    parts["governance"] = item("PASS" if locked else "FAIL_CLOSED",
                               "ZERO_ORDER_AUTHORITY_VERIFIED" if locked else "AUTHORITY_CONTRACT_UNVERIFIED")

    eods = []
    for p in (root / "eod").glob("20??????/status.json"):
        d = day(p.parent.name)
        if d is not None and d <= today:
            eods.append((d, p))
    eods.sort(reverse=True)
    eod_day = None
    if not eods:
        parts["eod"] = item("UNKNOWN", "NO_COMMITTED_EOD_STATUS")
    else:
        d, p = eods[0]
        s = load(p) or {}
        complete = (s.get("status") == "COMPLETE"
                    and s.get("formal_complete_day") is True
                    and s.get("downstream_ready") is True
                    and s.get("mother_status") == "COMPLETE"
                    and all(s.get(k + "_status") == "COMPLETE" for k in ("price", "institutional", "margin"))
                    and all(s.get(k + "_date") == d.isoformat() for k in ("price", "institutional", "margin"))
                    and all(isinstance(s.get(k + "_rows"), int) and s[k + "_rows"] > 0
                            for k in ("price", "institutional", "margin")))
        eod_day = d if complete else None
        expected = latest_prior_weekday(today)
        state = ("FAIL_CLOSED" if not complete else
                 "STALE" if d < expected else "PASS")
        parts["eod"] = item(state, "EOD_THREE_LEG_VERIFIED" if state == "PASS" else
                             "EOD_INCOMPLETE" if not complete else "LATEST_PRIOR_TRADING_DAY_MISSING",
                             latest=d.isoformat(), expected_weekday=expected.isoformat(),
                             calendar_limitation="TWSE holiday exceptions require manual verification",
                             price_rows=s.get("price_rows"), institutional_rows=s.get("institutional_rows"),
                             margin_rows=s.get("margin_rows"))

    tdcc = load(root / "ownership/tdcc/latest.json") or {}
    td = day(tdcc.get("snapshot_date"))
    age = (today - td).days if td else None
    tdcc_ok = (tdcc.get("status") == "COMPLETE" and tdcc.get("summary_rows", 0) >= 1000
               and isinstance(tdcc.get("source_sha256"), str)
               and len(tdcc["source_sha256"]) == 64 and age is not None and age >= 0)
    parts["tdcc"] = item("FAIL_CLOSED" if not tdcc_ok else "STALE" if age > 12 else "PASS",
                         "TDCC_UNVERIFIED" if not tdcc_ok else
                         "TDCC_SNAPSHOT_STALE" if age > 12 else "TDCC_CANONICAL_SNAPSHOT_PRESENT",
                         snapshot=tdcc.get("snapshot_date"), age_days=age,
                         historical_latency=tdcc.get("historical_latency_status"))

    hba_path = root / "research/hba_surveillance/decision_latest.json"
    hba = load(hba_path) or {}
    ha = hba.get("authority") or {}
    source_hashes = hba.get("input_sha256") or {}
    evidence_ok = all(source_hashes.get(k) == digest(root / p) for k, p in (
        ("original_hba", "research/hba_surveillance/latest.json"),
        ("integrated_hba", "research/hba_surveillance/integrated_latest.json")))
    hba_ok = (hba.get("status") == "RESEARCH_ADVISORY_READY"
              and ha.get("active_selection_strategy_count") == 0
              and ha.get("broker_execution") is False and ha.get("capital_twd") == 0
              and ha.get("formal_selection") is False
              and hba.get("not_live_quotes") is True
              and evidence_ok and (hba.get("research_summary") or {}).get("market_covered", 0) >= 500)
    hba_day = day(hba.get("observed_eod_date"))
    hba_state = ("FAIL_CLOSED" if not hba_ok else
                 "STALE" if not eod_day or hba_day != eod_day else "PASS")
    parts["hba"] = item(hba_state, "HBA_EVIDENCE_HASH_AND_EOD_MATCH" if hba_state == "PASS" else
                         "HBA_RECEIPT_UNVERIFIED" if not hba_ok else "HBA_EOD_NOT_CURRENT",
                         observed_eod=hba.get("observed_eod_date"),
                         market_covered=(hba.get("research_summary") or {}).get("market_covered"),
                         evidence_hash_match=evidence_ok)

    weekly = load(root / "research/retail_top5/v22_weekly_latest.json")
    if weekly is None:
        parts["v22_weekly"] = item("UNKNOWN", "NO_PUBLISHED_WEEKLY_V22_RECEIPT",
                                   historical_replay_must_not_be_promoted=True)
    else:
        d = day(weekly.get("decision_date"))
        safe = (weekly.get("research_only") is True and
                weekly.get("broker_execution") is False and
                weekly.get("selection_authority") is False and
                weekly.get("authorized_lots") == 0 and
                weekly.get("capital_authority_twd") == 0 and
                weekly.get("buy_signal") is False and weekly.get("sell_signal") is False)
        state = "FAIL_CLOSED" if not safe or d is None or d > today else (
            "STALE" if (today - d).days > 9 else "PASS")
        parts["v22_weekly"] = item(state, "RESEARCH_ONLY_RECEIPT_PRESENT" if state == "PASS"
                                    else "WEEKLY_RESEARCH_INVALID_OR_STALE",
                                    decision_date=weekly.get("decision_date"),
                                    research_only=weekly.get("research_only"))

    overseas = load(root / "overseas_premarket/latest.json") or {}
    od = day(overseas.get("target_tw_date"))
    generated = timestamp(overseas.get("generated_at_taipei"))
    overseas_ok = (overseas.get("status") == "PASS_VERIFIED_VENDOR_EOD"
                   and od == today and generated is not None and generated.date() == today
                   and generated.hour < 9)
    parts["overseas"] = item("PASS" if overseas_ok else "UNKNOWN",
                             "VERIFIED_SAME_DAY_PREOPEN_PACKET" if overseas_ok else
                             "NO_VERIFIED_SAME_DAY_PREOPEN_PACKET",
                             target=overseas.get("target_tw_date"))

    live = load(root / "live/status.json") or {}
    expires = timestamp(live.get("cache_expires_at_taipei"))
    is_fresh = (expires is not None and expires > now and
                live.get("transport_health_status") == "PASS"
                and live.get("broker_order_execution") is False)
    parts["quote_transport"] = item("PASS" if is_fresh else "STALE",
                                     "ACTIVE_NONTRIAL_SNAPSHOT" if is_fresh else
                                     "COMMITTED_QUOTE_CACHE_EXPIRED_NOT_LIVE",
                                     generated=live.get("generated_at_taipei"),
                                     expires=live.get("cache_expires_at_taipei"))

    for module in ("s5", "escape", "rms"):
        parts[module] = item("UNKNOWN", "NO_CURRENT_FORMAL_RUNTIME_RECEIPT_VERIFIED",
                             do_not_infer_from_hba_or_shadow=True)

    if workflow_runs is None:
        parts["workflows"] = item("UNKNOWN", "GITHUB_ACTIONS_RUN_HISTORY_NOT_FETCHED",
                                   collection_error=collection_error)
    else:
        seen = {}
        for label, filename in WORKFLOWS.items():
            rows = workflow_runs.get(filename)
            if not isinstance(rows, list):
                seen[label] = item("UNKNOWN", "RUN_METADATA_MISSING")
                continue
            production = [x for x in rows if x.get("head_branch") == "main" and
                          x.get("event") in ("schedule", "push", "workflow_run", "workflow_dispatch")]
            production.sort(key=lambda x: x.get("created_at") or "", reverse=True)
            # Empty/skipped jobs are not evidence that a producer worked.
            active_runs = [x for x in production if x.get("conclusion") != "skipped"]
            if not active_runs:
                seen[label] = item("UNKNOWN", "NO_NONSKIPPED_PRODUCTION_RUN")
                continue
            latest = active_runs[0]
            good = latest.get("status") == "completed" and latest.get("conclusion") == "success"
            seen[label] = item("PASS" if good else "FAIL_CLOSED",
                               "LAST_PRODUCTION_RUN_SUCCESS" if good else "LAST_PRODUCTION_RUN_NOT_SUCCESS",
                               run_id=latest.get("id"), event=latest.get("event"),
                               created_at=latest.get("created_at"), conclusion=latest.get("conclusion"))
        parts["workflows"] = {"state": ("FAIL_CLOSED" if any(x["state"] == "FAIL_CLOSED"
                                          for x in seen.values()) else
                                          "UNKNOWN" if any(x["state"] == "UNKNOWN"
                                          for x in seen.values()) else "PASS"),
                              "reason": "PRODUCTION_RUNS_ONLY", "evidence": seen}

    statuses = [v["state"] for v in parts.values()]
    overall = ("FAIL_CLOSED" if "FAIL_CLOSED" in statuses else
               "DEGRADED" if any(x != "PASS" for x in statuses) else "PASS")
    return {"schema": "HENGCE_OPERATIONAL_INTEGRITY_V1",
            "observed_at_taipei": now.isoformat(), "overall": overall,
            "not_a_market_signal": True, "formal_health_not_inferred_from_old_q017": True,
            "no_new_data_collector": True, "authority": dict(ZERO),
            "modules": parts}


def collect_github_runs(repository, token):
    """Metadata only. Never contacts Fugle, FinMind, exchange or broker endpoints."""
    if not repository or not token:
        return None, "GITHUB_READ_CREDENTIALS_UNAVAILABLE"
    observed = {}
    for filename in WORKFLOWS.values():
        endpoint = ("https://api.github.com/repos/" + repository
                    + "/actions/workflows/" + quote(filename, safe="")
                    + "/runs?per_page=15")
        try:
            req = Request(endpoint, headers={"Authorization": "Bearer " + token,
                "Accept": "application/vnd.github+json", "User-Agent": "HENGCE-readonly-health"})
            with urlopen(req, timeout=15) as res:
                payload = json.load(res)
            if not isinstance(payload.get("workflow_runs"), list):
                return None, "INVALID_WORKFLOW_RUN_METADATA"
            observed[filename] = [{k: x.get(k) for k in
                                    ("id", "head_branch", "event", "status", "conclusion", "created_at")}
                                   for x in payload["workflow_runs"]]
        except Exception as exc:
            # Expose only exception type; do not leak tokens or remote URL payloads.
            return None, "WORKFLOW_METADATA_FETCH_FAILED_" + type(exc).__name__
    return observed, None


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument("--out", type=Path)
    p.add_argument("--fetch-runs", action="store_true")
    a = p.parse_args()
    runs, error = collect_github_runs(os.getenv("GITHUB_REPOSITORY"),
                                      os.getenv("GITHUB_TOKEN")) if a.fetch_runs else (None, None)
    report = evaluate(a.root, datetime.now(TZ), runs, error)
    raw = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(raw, encoding="utf-8")
    print(raw)


if __name__ == "__main__":
    main()
