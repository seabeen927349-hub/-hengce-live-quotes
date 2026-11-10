#!/usr/bin/env python3
"""Run live-compatible infrastructure safety tests without invoking retired Q017.

All excluded cases are run in full (not skipped) by run_retired_suite.py in a
pinned pre-retirement worktree. Fail if a case silently disappears or if the
retirement lock is reactivated. New live-compatible tests are included by default.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "engineering"))

HISTORICAL_ONLY = {
    "writer": {
        "test_real_0745_0815_0850_0901_interleaving_publishes_both_captures",
        "test_decision_display_retains_e2_read_dependency",
    },
    "recovery": {
        "test_11_independent_primary_backup_and_duplicate_recovery",
        "test_18_manual_current_day_selftest_vs_historical_date",
    },
}
DECLARED_TEST_COUNT = {"writer": 31, "recovery": 20}
TEST_MODULES = {
    "writer": ("test_writer_races", "WriterRaceTests"),
    "recovery": ("test_recovery_faults", "RecoveryFaultTests"),
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", choices=sorted(TEST_MODULES), required=True)
    args = parser.parse_args()

    lock = json.loads((ROOT / "hengce/HENGCE_Q017_RETIREMENT_LOCK_20261105.json").read_text())
    if (lock.get("status") != "RETIRED_NO_ACTIVE_STRATEGY"
            or lock.get("active_strategy_count") != 0
            or lock.get("broker_order_execution") is not False):
        raise RuntimeError("CURRENT_RETIREMENT_LOCK_NOT_VERIFIED")

    import importlib
    module_name, class_name = TEST_MODULES[args.suite]
    module = importlib.import_module(module_name)
    test_class = getattr(module, class_name)
    found = set(unittest.defaultTestLoader.getTestCaseNames(test_class))
    archived = HISTORICAL_ONLY[args.suite]
    if len(found) != DECLARED_TEST_COUNT[args.suite] or not archived <= found:
        raise RuntimeError(f"TEST_COVERAGE_DRIFT: {len(found)} {sorted(archived - found)}")
    # Historical job must exercise the exact source suite in its entirety.
    from run_retired_suite import SUITES
    required_path = f"tests/engineering/{module_name}.py"
    if not any(case[0] == required_path for case in SUITES[args.suite][1]):
        raise RuntimeError("ARCHIVED_SAFETY_SUITE_NOT_SCHEDULED")

    live = sorted(found - archived)
    suite = unittest.TestSuite(test_class(name) for name in live)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        sys.exit(1)
    print(json.dumps({
        "status": "PASS",
        "suite": args.suite,
        "current_tests_passed": len(live),
        "archived_only_tests_run_by_historical_job": sorted(archived),
        "historical_tests_total": len(found),
        "retired_q017_reactivated": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
