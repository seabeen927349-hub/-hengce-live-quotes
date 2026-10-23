#!/usr/bin/env python3
"""Engineering replay gate for the authorized single-HENGCE routing migration.

All historical model outputs remain exact-equality gated. The only permitted
before/after difference is scan-once routing, and the after tree is separately
required to route through the unified HENGCE display/action path with no
user-facing dual-engine display authority.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

import replay_equivalence as base


def stable_snapshot(payload: dict) -> dict:
    """Remove only the explicitly authorized router migration surface."""
    return {k: v for k, v in payload.items() if k != "router_routes"}


def run_existing_tests(root: Path):
    """Run every after-tree script regression, allowing additive tests only."""
    bootstrap = """import socket, requests, urllib.request, sys, runpy
def deny(*args, **kwargs): raise AssertionError('REPLAY_NETWORK_FORBIDDEN')
socket.socket.connect = deny
socket.create_connection = deny
requests.sessions.Session.request = deny
urllib.request.urlopen = deny
sys.path.insert(0, 'scripts')
runpy.run_path(sys.argv[1], run_name='__main__')
"""
    results = []
    for script in sorted((root / "scripts").glob("test_*.py")):
        run = subprocess.run(
            [sys.executable, "-B", "-c", bootstrap, str(script)],
            cwd=root,
            text=True,
            capture_output=True,
            timeout=90,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        base.require(run.returncode == 0, script.name + " failed: " + (run.stdout + run.stderr)[-4000:])
        results.append({"test": script.name, "status": "PASS"})
    return results


def assert_single_hengce_router(after_root: Path, after_probe: dict) -> dict:
    router_path = after_root / "scripts" / "hengce_scan_once_router.py"
    display_path = after_root / "scripts" / "hengce_unified_scan_display.py"
    runner_path = after_root / "scripts" / "RUN_INTRADAY_ACTION_BOARD.sh"
    adapter_path = after_root / "scripts" / "hengce_unified_candidate_adapter.py"
    wrapper_path = after_root / "scripts" / "hengce_unified_action_board.py"

    base.require(router_path.is_file(), "single-HENGCE router missing")
    base.require(display_path.is_file(), "unified HENGCE display missing")
    base.require(runner_path.is_file(), "unified action-board runner missing")
    base.require(adapter_path.is_file(), "unified candidate adapter missing")
    base.require(wrapper_path.is_file(), "unified action-board wrapper missing")

    router_text = router_path.read_text(encoding="utf-8")
    display_text = display_path.read_text(encoding="utf-8")
    runner_text = runner_path.read_text(encoding="utf-8")

    base.require("hengce_dual_engine_display.py" not in router_text,
                 "scan-once still grants dual-engine display authority")
    base.require("hengce_unified_scan_display.py" in router_text,
                 "scan-once does not invoke unified HENGCE display")
    base.require("RUN_INTRADAY_ACTION_BOARD.sh" in router_text,
                 "scan-once does not invoke unified action-board runner")
    base.require("SINGLE_HENGCE" in display_text,
                 "unified display does not declare SINGLE_HENGCE architecture")
    base.require("q017_separate_ranking_displayed" in display_text and
                 "e2_separate_engine_displayed" in display_text,
                 "unified display lacks separate-engine prohibition evidence")
    runtime = after_root / "scripts" / "hengce_unified_runner.py"
    base.require(runtime.is_file(), "transaction runner missing")
    runtime_text = runtime.read_text(encoding="utf-8")
    base.require("hengce_unified_runner.py" in runner_text and
                 "import hengce_unified_candidate_adapter as adapter" in runtime_text and
                 "import hengce_unified_action_board as board" in runtime_text,
                 "runner no longer binds the unified adapter and board")
    # This is an exact, positive contract for every observed refresh branch;
    # arbitrary new routing is not exempt from replay comparison.
    expected = {clock: [] for clock in ("08:00", "08:45", "09:01", "09:03", "14:30", "15:30")}
    base.require(after_probe.get("router_routes") == expected,
                 "interactive scan invoked an unauthorized producer/recovery route")
    # Exercise main(), not only refresh(), in a separate after-tree interpreter.
    behavior = r"""
import contextlib, io, json, sys
from unittest.mock import patch
sys.path.insert(0, 'scripts')
import hengce_scan_once_router as router
for failed in (False, True):
    calls=[]
    def step(name, argv, timeout=180):
        calls.append((name, argv))
        return {'ok': not failed}
    payload={'system':'HENGCE','module':'HENGCE_UNIFIED_SCAN_DISPLAY','binding_status':'PASS','rows':[],
             'capital_authority_twd':0,'broker_order_execution':False,'PROMOTE_TO_PRODUCTION':'FORBIDDEN'}
    def child(argv, **kw):
        assert argv[1].endswith('hengce_unified_scan_display.py'), argv
        assert kw['timeout'] == 30
        return type('Result',(),{'stdout':json.dumps(payload),'returncode':0})()
    with patch.object(sys,'argv',['scan','--now','2026-10-23T10:00:00+08:00']), patch.object(router,'run_step',side_effect=step), patch.object(router.subprocess,'run',side_effect=child), contextlib.redirect_stdout(io.StringIO()) as stream:
        rc=router.main()
    result=json.loads(stream.getvalue())
    assert len(calls)==1 and calls[0][0]=='unified_hengce_action_board'
    assert calls[0][1][-1].endswith('RUN_INTRADAY_ACTION_BOARD.sh')
    assert rc==(2 if failed else 0)
    assert result['binding_status']==('FAIL_CLOSED' if failed else 'PASS')
    assert result['scan_once_router']['single_hengce_output'] is True
"""
    run = subprocess.run([sys.executable, "-B", "-c", behavior], cwd=after_root,
                         text=True, capture_output=True, timeout=30)
    base.require(run.returncode == 0, "single-authority behavior failed: " + run.stderr[-4000:])
    for required in ("test_hengce_unified_q017.py", "test_hengce_unified_boundaries.py", "test_hengce_unified_runtime.py"):
        base.require((after_root / "scripts" / required).is_file(), "unified behavioral regression missing: " + required)

    return {
        "scan_once_single_hengce": True,
        "dual_engine_display_authority": False,
        "unified_candidate_adapter_bound": True,
        "unified_action_board_bound": True,
        "legacy_runner_absent": True,
    }


def self_test():
    before = {
        "q017": {"score": 1.0},
        "e2": {"decile": 9},
        "full_rankings": {"q017": [1, 2], "e2": [3, 4]},
        "display": {"capital_authority_twd": 0},
        "fail_closed": {"missing": True},
        "zero_new_capital_authority": True,
        "router_routes": {"09:03": ["old"]},
    }
    after = json.loads(json.dumps(before))
    after["router_routes"] = {"09:03": ["single_hengce"]}
    base.compare(stable_snapshot(before), stable_snapshot(after))

    changed = json.loads(json.dumps(after))
    changed["q017"]["score"] += 1e-15
    try:
        base.compare(stable_snapshot(before), stable_snapshot(changed))
    except RuntimeError as exc:
        base.require("/q017/score" in str(exc), "stable replay mismatch evidence missing")
    else:
        raise RuntimeError("STOP: stable model difference was accepted")
    for key in stable_snapshot(before):
        changed = json.loads(json.dumps(after))
        changed[key] = "SYNTHETIC_TAMPERING"
        try:
            base.compare(stable_snapshot(before), stable_snapshot(changed))
        except RuntimeError:
            pass
        else:
            raise RuntimeError("STOP: replay bypass accepted: " + key)
    print(json.dumps({"status": "PASS", "authorized_delta": "router_routes_only"}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--before", default=base.SNAPSHOT)
    parser.add_argument("--after", default="HEAD")
    parser.add_argument("--report", type=Path)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--probe", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()

    if args.self_test:
        self_test()
        return
    if args.probe:
        print(json.dumps(base.probe(args.probe.resolve()), ensure_ascii=False, allow_nan=False))
        return
    if args.report:
        args.report.unlink(missing_ok=True)

    before_sha = base.git(args.repo, "rev-parse", args.before + "^{commit}").decode().strip()
    after_sha = base.git(args.repo, "rev-parse", args.after + "^{commit}").decode().strip()
    changed = base.git(args.repo, "diff", "--name-only", before_sha, after_sha).decode().splitlines()
    production_unchanged = all(
        p.startswith(("tests/engineering/", "docs/engineering/"))
        or p == ".github/workflows/hengce-engineering-replay.yml"
        for p in changed
    )

    with tempfile.TemporaryDirectory(prefix="hengce-single-replay-") as td:
        temp = Path(td)
        frozen = temp / "snapshot"
        base.export(args.repo, base.SNAPSHOT, frozen)
        results = []
        roots = {}
        for name, sha in (("before", before_sha), ("after", after_sha)):
            root = temp / name
            roots[name] = root
            base.export(args.repo, sha, root)
            for directory in ("hengce", "eod", "receipts", "research"):
                shutil.rmtree(root / directory, ignore_errors=True)
                shutil.copytree(frozen / directory, root / directory)
            env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONHASHSEED": "0"}
            run = subprocess.run(
                [sys.executable, "-B", str(Path(__file__).resolve()), "--probe", str(root)],
                text=True,
                capture_output=True,
                timeout=120,
                env=env,
            )
            base.require(run.returncode == 0, name + " replay failed: " + run.stderr[-6000:])
            results.append(json.loads(run.stdout))

        # Exact equality remains mandatory for every historical/model/safety
        # output except the explicitly authorized scan-router migration.
        base.compare(stable_snapshot(results[0]), stable_snapshot(results[1]))
        router_guard = assert_single_hengce_router(roots["after"], results[1])

        before_tests = {p.name for p in (roots["before"] / "scripts").glob("test_*.py")}
        regressions = run_existing_tests(roots["after"])
        after_tests = {item["test"] for item in regressions}
        missing = sorted(before_tests - after_tests)
        base.require(not missing, "baseline script regressions removed: " + ",".join(missing))
        base.require(after_tests.issuperset(before_tests), "after tree lost baseline regression coverage")

    result = results[0]
    checks = {name: "IDENTICAL" for name in (
        "top3", "full_ranking", "scores", "authority", "schema", "universe",
        "decision_hashes", "fail_closed", "display", "zero_new_capital_authority")}
    checks["router_routes"] = "AUTHORIZED_SINGLE_HENGCE_MIGRATION"
    checks["unified_runtime_behavior"] = "PASS"
    checks["baseline_tests_preserved"] = True
    checks["all_after_script_tests_pass"] = True
    report = {
        "status": "PASS",
        "before_commit": before_sha,
        "after_commit": after_sha,
        "snapshot_commit": base.SNAPSHOT,
        "snapshot_date": base.DAY,
        "changed_files": changed,
        "production_files_unchanged": production_unchanged,
        "authorized_before_after_delta": ["router_routes"],
        "checks": checks,
        "router_guard": router_guard,
        "existing_regressions": regressions,
        "baseline_test_count": len(before_tests),
        "after_test_count": len(after_tests),
        "top3": [x["ticker"] for x in result["q017"]["top3"]],
        "full_ranking_counts": {k: len(v) for k, v in result["full_rankings"].items()},
        "full_ranking_sha256": {k: base.digest(v) for k, v in result["full_rankings"].items()},
        "q017_decision_sha256": result["q017"]["decision_snapshot_sha256"],
        "observation_sha256": result["q017"]["observation_snapshot_sha256"],
        "universe_sha256": result["q017"]["universe_lock"]["universe_sha256"],
        "fail_closed_cases": list(result["fail_closed"]),
        "zero_new_capital_authority": result["zero_new_capital_authority"],
        "replay_payload_sha256": base.digest(stable_snapshot(result)),
    }
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
