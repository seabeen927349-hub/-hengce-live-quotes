#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

LATEST = Path("latest.json")
ACTIVE = Path("live/active.json")
STATUS = Path("live/status.json")
QUOTE_DIR = Path("live/quotes")

ROLE = "TRANSPORT_TRIAL_PRICE_SEMANTICS_GUARD_NO_AUTHORITY"
POLICY = "FUGLE_LASTPRICE_MAY_INCLUDE_TRIAL;TRIAL_ONLY_NEVER_PROMOTED_TO_EXECUTED_PRICE"


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def dump(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def classify(row):
    is_trial = bool(row.get("is_trial"))
    last_trade_available = row.get("last_trade_time") not in (None, "") and row.get("price") is not None

    row["trial_guard_role"] = ROLE
    row["trial_price_never_promoted_to_executed_price"] = True

    if is_trial:
        row["trial_price_non_execution"] = True
        if last_trade_available:
            row["price_source"] = "LAST_EXECUTED_TRADE_DURING_TRIAL"
            row["executed_price_available"] = True
        else:
            row["price"] = None
            row["change"] = None
            row["change_percent"] = None
            row["price_source"] = "TRIAL_ONLY_NO_EXECUTED_TRADE"
            row["executed_price_available"] = False
    else:
        row["trial_price_non_execution"] = False
        if last_trade_available:
            row["price_source"] = "LAST_EXECUTED_TRADE"
            row["executed_price_available"] = True
        elif row.get("price") is not None:
            row["price_source"] = "SOURCE_LAST_PRICE_NONTRIAL_FALLBACK"
            row["executed_price_available"] = True
        else:
            row["price_source"] = "NO_EXECUTED_PRICE"
            row["executed_price_available"] = False

    return row


def validate_row(row):
    if row.get("trial_guard_role") != ROLE:
        raise SystemExit("TRIAL_GUARD_ROLE_MISSING:" + str(row.get("symbol")))
    if row.get("trial_price_never_promoted_to_executed_price") is not True:
        raise SystemExit("TRIAL_GUARD_POLICY_MISSING:" + str(row.get("symbol")))
    for key in ("ranking_authority", "signal_authority", "capital_authority", "broker_order_execution", "legacy_v3_rank_authority"):
        if row.get(key) is not False:
            raise SystemExit("TRIAL_GUARD_AUTHORITY_VIOLATION:" + str(row.get("symbol")) + ":" + key)

    if row.get("is_trial"):
        if row.get("trial_price_non_execution") is not True:
            raise SystemExit("TRIAL_PRICE_MUST_BE_NON_EXECUTION:" + str(row.get("symbol")))
        if row.get("last_trade_time") in (None, ""):
            if row.get("price") is not None:
                raise SystemExit("TRIAL_ONLY_PRICE_PROMOTED:" + str(row.get("symbol")))
            if row.get("price_source") != "TRIAL_ONLY_NO_EXECUTED_TRADE":
                raise SystemExit("TRIAL_ONLY_SOURCE_INVALID:" + str(row.get("symbol")))
            if row.get("executed_price_available") is not False:
                raise SystemExit("TRIAL_ONLY_EXECUTED_FLAG_INVALID:" + str(row.get("symbol")))
        else:
            if row.get("price_source") != "LAST_EXECUTED_TRADE_DURING_TRIAL":
                raise SystemExit("TRIAL_LAST_TRADE_SOURCE_INVALID:" + str(row.get("symbol")))
            if row.get("executed_price_available") is not True:
                raise SystemExit("TRIAL_LAST_TRADE_EXECUTED_FLAG_INVALID:" + str(row.get("symbol")))


def apply_guard():
    if not LATEST.exists():
        raise SystemExit("LATEST_MISSING")
    payload = load(LATEST)
    rows = payload.get("data") or []
    if not rows:
        raise SystemExit("LATEST_DATA_EMPTY")

    for row in rows:
        classify(row)
        validate_row(row)

    trial_rows = [row for row in rows if row.get("is_trial")]
    trial_without_execution = [row for row in trial_rows if not row.get("executed_price_available")]

    payload["trial_guard_role"] = ROLE
    payload["trial_semantics_policy"] = POLICY
    payload["trial_price_never_promoted_to_executed_price"] = True
    payload["trial_count"] = len(trial_rows)
    payload["trial_with_executed_trade_count"] = len(trial_rows) - len(trial_without_execution)
    payload["trial_without_executed_trade_count"] = len(trial_without_execution)
    payload["trial_guard_status"] = "PASS"

    dump(LATEST, payload)
    dump(ACTIVE, payload)

    status = {key: value for key, value in payload.items() if key != "data"}
    status["healthy"] = int(payload.get("success_count", 0)) > 0
    dump(STATUS, status)

    QUOTE_DIR.mkdir(parents=True, exist_ok=True)
    for row in rows:
        symbol = str(row.get("symbol") or "")
        if symbol:
            dump(QUOTE_DIR / f"{symbol}.json", row)

    print("HENGCE LIVE TRIAL GUARD PASS", "trial_count", len(trial_rows), "with_executed_trade", len(trial_rows) - len(trial_without_execution), "trial_only", len(trial_without_execution))


def validate_latest():
    payload = load(LATEST)
    rows = payload.get("data") or []
    if payload.get("trial_guard_role") != ROLE:
        raise SystemExit("TRIAL_GUARD_TOPLEVEL_ROLE_MISSING")
    if payload.get("trial_semantics_policy") != POLICY:
        raise SystemExit("TRIAL_GUARD_POLICY_MISMATCH")
    if payload.get("trial_price_never_promoted_to_executed_price") is not True:
        raise SystemExit("TRIAL_GUARD_TOPLEVEL_LOCK_MISSING")
    if payload.get("trial_guard_status") != "PASS":
        raise SystemExit("TRIAL_GUARD_STATUS_NOT_PASS")

    for row in rows:
        validate_row(row)

    trials = [row for row in rows if row.get("is_trial")]
    trial_only = [row for row in trials if not row.get("executed_price_available")]
    if payload.get("trial_count") != len(trials):
        raise SystemExit("TRIAL_COUNT_MISMATCH")
    if payload.get("trial_without_executed_trade_count") != len(trial_only):
        raise SystemExit("TRIAL_ONLY_COUNT_MISMATCH")
    if payload.get("trial_with_executed_trade_count") != len(trials) - len(trial_only):
        raise SystemExit("TRIAL_WITH_EXECUTED_COUNT_MISMATCH")

    print("HENGCE LIVE TRIAL GUARD VERIFIED", len(trials), len(trials) - len(trial_only), len(trial_only))


def self_test():
    base = {"symbol": "TEST", "ranking_authority": False, "signal_authority": False, "capital_authority": False, "broker_order_execution": False, "legacy_v3_rank_authority": False}

    row = dict(base, is_trial=True, last_trade_time="2026-10-20T12:00:00+08:00", price=10.0, trial_price=9.5, change=1.0, change_percent=10.0)
    classify(row)
    validate_row(row)
    assert row["price"] == 10.0
    assert row["price_source"] == "LAST_EXECUTED_TRADE_DURING_TRIAL"

    row = dict(base, is_trial=True, last_trade_time=None, price=9.5, trial_price=9.5, change=0.5, change_percent=5.0)
    classify(row)
    validate_row(row)
    assert row["price"] is None
    assert row["change"] is None
    assert row["change_percent"] is None
    assert row["price_source"] == "TRIAL_ONLY_NO_EXECUTED_TRADE"

    row = dict(base, is_trial=False, last_trade_time=None, price=8.0, trial_price=None, change=0.0, change_percent=0.0)
    classify(row)
    validate_row(row)
    assert row["price"] == 8.0
    assert row["price_source"] == "SOURCE_LAST_PRICE_NONTRIAL_FALLBACK"

    print(json.dumps({"self_test": "PASS", "role": ROLE, "trial_only_never_promoted": True, "last_trade_preserved_during_trial": True, "no_authority": True}, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("apply", "validate", "self-test"), default="apply")
    mode = parser.parse_args().mode
    {"apply": apply_guard, "validate": validate_latest, "self-test": self_test}[mode]()


if __name__ == "__main__":
    main()
