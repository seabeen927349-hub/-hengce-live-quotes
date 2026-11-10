#!/usr/bin/env python3
"""Run retired-engineering regression suites in frozen pre-retirement worktrees.

These checks are HISTORICAL ONLY.  They must not be evaluated against main:
Q017 executables and the old health scheduler were removed on 2026-11-05.
A historical PASS never grants current model, ranking, capital or order authority.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
# Pre-retirement Phase 1.5 hardening baseline, including both safety suites.
SAFETY_BASE = "42f4d4edd4b327c693290416d54d1e7622733969"
# Reviewed single-HENGCE routing merge, while Q017 was still present.
REPLAY_BASE = "5d411cf4fa298baddd34eb945bb341597f68793e"
SUITES = {
    "writer": (SAFETY_BASE, [
        ["tests/engineering/test_health_dependency_audit.py"],
        ["tests/engineering/test_writer_workflows.py"],
    ]),
    "recovery": (SAFETY_BASE, [
        ["tests/engineering/test_recovery_workflows.py"],
        ["tests/engineering/test_recovery_base_characterization.py"],
        ["tests/engineering/test_recovery_faults.py"],
    ]),
    "replay": (REPLAY_BASE, [
        ["tests/engineering/replay_equivalence_single_hengce.py", "--self-test"],
        ["tests/engineering/replay_equivalence_single_hengce.py",
         "--before", REPLAY_BASE, "--after", REPLAY_BASE],
    ]),
}


def invoke(argv: list[str], *, cwd: Path) -> None:
    print("+", " ".join(argv), flush=True)
    subprocess.run(argv, cwd=cwd, check=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", choices=sorted(SUITES), required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    pinned_sha, cases = SUITES[args.suite]
    invoke(["git", "cat-file", "-e", pinned_sha + "^{commit}"], cwd=ROOT)
    if args.report:
        args.report = args.report.resolve()
        args.report.unlink(missing_ok=True)
        args.report.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="hengce-retired-history-") as td:
        old_root = Path(td) / "checkout"
        invoke(["git", "worktree", "add", "--detach", str(old_root), pinned_sha], cwd=ROOT)
        try:
            for index, case in enumerate(cases):
                command = [sys.executable, "-B", *case]
                if args.suite == "replay" and index == 1 and args.report:
                    command += ["--report", str(args.report)]
                invoke(command, cwd=old_root)
        finally:
            invoke(["git", "worktree", "remove", "--force", str(old_root)], cwd=ROOT)

    if args.report and not args.report.is_file():
        raise RuntimeError("ARCHIVED_REPLAY_EVIDENCE_MISSING")
    print(json.dumps({
        "suite": args.suite, "historical_commit": pinned_sha,
        "scope": "FROZEN_PRE_RETIREMENT_ENGINEERING_REGRESSION_ONLY",
        "live_q017_authority": False, "live_health_scheduler_restored": False,
        "current_runtime_verified_by_this_suite": False, "status": "PASS",
    }, sort_keys=True))


if __name__ == "__main__":
    main()
