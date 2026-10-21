#!/usr/bin/env python3
"""Offline, isolated replay of the pinned HENGCE engineering baseline.

Production modules run unchanged in disposable git archives. Full candidate
rankings are observed at function return, never reconstructed with another model.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile

SNAPSHOT = "900b0bc862e03a2b496129b0fc68d066c39542bf"
DAY = "2026-10-21"
OBS = "hengce/q017_radar/observations/20261021_0901_observation.json"
DECISION = "hengce/q017_radar/decision/20261021_0901.json"
E2_STATE = "hengce/e2_live/state_latest.json"


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def require(condition, message):
    if not condition:
        raise RuntimeError("STOP: " + message)


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def probe(root):
    # No provider calls are legal, including an accidental seed/history refresh.
    import socket
    import requests
    import urllib.request
    from datetime import datetime
    from unittest.mock import patch

    def no_network(*args, **kwargs):
        raise AssertionError("REPLAY_NETWORK_FORBIDDEN")

    socket.socket.connect = no_network
    socket.create_connection = no_network
    requests.sessions.Session.request = no_network
    urllib.request.urlopen = no_network
    sys.path.insert(0, str(root / "scripts"))
    import hengce_q017_observation_lock_v5 as q
    import hengce_q017_authority_guard_v5 as guard
    import hengce_e2_live as e2
    import hengce_dual_engine_display as display
    import hengce_scan_once_router as router

    observation = read(root / OBS)
    locked = read(root / DECISION)
    e2_locked = read(root / E2_STATE)
    rankings = {}

    def profile(frame, event, arg):
        if event == "return" and frame.f_code is q.build_decision_from_observation.__code__:
            rankings["q017"] = json.loads(json.dumps(frame.f_locals["cand"]))
        if event == "return" and frame.f_code is e2.prepare_features.__code__:
            rankings["e2"] = json.loads(json.dumps(arg[1]))

    require(q.validate_observation(observation)[0], "invalid pinned observation")
    sys.setprofile(profile)
    try:
        decision = q.build_decision_from_observation(
            observation, datetime.fromisoformat(locked["generated_at_taipei"]))
        # Refresh is replaced by an offline no-op; original sox_features still
        # reads the pinned CSV. No fabricated/replacement market values are used.
        with patch.object(e2.core, "refresh_sox", return_value=None), patch.object(
                e2.core, "now_tw", return_value=datetime.fromisoformat(e2_locked["generated_at_taipei"])):
            e2_result = e2.build_postclose(datetime.fromisoformat(DAY).date())
    finally:
        sys.setprofile(None)
    compare({"historical_q017": locked}, {"historical_q017": decision})
    compare({"historical_e2": e2_locked}, {"historical_e2": e2_result})
    require(guard.validate_decision_payload(decision)[0], "historical decision rejected")
    require(e2_result["capital_authority_twd"] == 0, "E2 capital authority")
    require(e2_result["broker_order_execution"] is False, "E2 broker execution")

    # Exercise actual CLI fail-closed handlers with fixed clock and inputs.
    failures = {}
    op = root / OBS
    original = op.read_bytes()
    variants = {}
    bad = json.loads(json.dumps(observation))
    del bad["quotes"][next(iter(bad["quotes"]))]
    variants["missing_quote"] = bad
    bad = json.loads(json.dumps(observation))
    bad["quotes"][next(iter(bad["quotes"]))]["fetched_at_taipei"] = DAY + "T09:02:00+08:00"
    variants["late_quote"] = bad
    bad = json.loads(json.dumps(observation))
    bad["universe_lock"]["universe_sha256"] = "invalid"
    variants["universe_hash"] = bad
    bad = json.loads(json.dumps(observation))
    bad["observation_snapshot_sha256"] = "invalid"
    variants["observation_hash"] = bad
    variants["missing_observation"] = None
    try:
        for name, payload in variants.items():
            if payload is None:
                op.unlink()
            else:
                op.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            with patch.object(q.core, "now_tw", return_value=datetime.fromisoformat(locked["generated_at_taipei"])), patch.object(
                    sys, "argv", ["q017", "--mode", "compute", "--date", DAY]), contextlib.redirect_stdout(io.StringIO()):
                rc = q.main()
            fail = read(q.LATEST)
            require(rc == 2 and fail["authority"] == "NO_FORMAL_SIGNAL" and fail["formal_buy_count"] == 0,
                    "Q017 did not fail closed: " + name)
            failures[name] = {"exit_code": rc, "payload": fail}
    finally:
        op.write_bytes(original)
        q.LATEST.write_text(json.dumps(locked, ensure_ascii=False), encoding="utf-8")

    with patch.object(e2, "tw_rows_through", side_effect=RuntimeError("FIXED_HISTORY_UNAVAILABLE")), patch.object(
            e2.core, "now_tw", return_value=datetime.fromisoformat(e2_locked["generated_at_taipei"])), patch.object(
            sys, "argv", ["e2", "--mode", "postclose", "--date", DAY]), contextlib.redirect_stdout(io.StringIO()):
        rc = e2.main()
    e2_failure = read(e2.STATE)
    require(rc == 2 and e2_failure["authority"] == "NO_E2_SIGNAL", "E2 did not fail closed")
    require(e2_failure["capital_authority_twd"] == 0 and e2_failure["broker_order_execution"] is False,
            "E2 failure created capital authority")
    failures["e2_history_unavailable"] = {"exit_code": rc, "payload": e2_failure}
    e2.STATE.write_text(json.dumps(e2_locked, ensure_ascii=False), encoding="utf-8")
    shown = display.build(datetime.fromisoformat(locked["generated_at_taipei"]))
    require(shown["legacy_v3_display_authority"] is False and shown["mixed_ranking_forbidden"] is True,
            "display isolation changed")
    require(shown["e2"]["capital_authority_twd"] == 0, "display capital authority")
    # Public legacy radar kill switch must remain in force.
    import hengce_daily_command_center as command
    with patch.object(sys, "argv", ["daily", "--mode", "radar"]), patch.object(
            command, "now_tw", return_value=datetime.fromisoformat(locked["generated_at_taipei"])), contextlib.redirect_stdout(io.StringIO()):
        legacy_rc = command.main()
    legacy_failure = read(command.DATA_STATUS)
    require(legacy_rc == 2 and legacy_failure["authority"] == "NO_FORMAL_SIGNAL", "legacy kill switch")
    failures["legacy_radar_disabled"] = {"exit_code": legacy_rc, "payload": legacy_failure}
    # All router time branches are observed with subprocess execution disabled.
    routes = {}
    for clock in ("08:00", "08:45", "09:01", "09:03", "14:30", "15:30"):
        with patch.object(router, "run_step", side_effect=lambda name, argv, timeout=180: {"name": name, "argv": [str(x).replace(str(root), "<ROOT>") for x in argv], "ok": True, "timeout": timeout}):
            routes[clock] = router.refresh(datetime.fromisoformat(DAY + "T" + clock + ":00+08:00"))
    require(not any("RUN_HENGCE" in json.dumps(x) or "run_hengce_work" in json.dumps(x) for x in routes.values()),
            "legacy runner entered scan-once routes")
    return {"q017": decision, "e2": e2_result, "full_rankings": rankings,
            "display": shown, "fail_closed": failures, "router_routes": routes,
            "zero_new_capital_authority": True}


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args])


def export(repo, ref, destination):
    destination.mkdir()
    with tarfile.open(fileobj=io.BytesIO(git(repo, "archive", ref)), mode="r:") as archive:
        archive.extractall(destination, filter="data")


def compare(before, after):
    # Deliberately exact: no score tolerance, ignored timestamps, or normalized
    # official fields. A mismatch aborts before any success report is published.
    if before != after:
        differences = []

        def visit(a, b, path):
            if len(differences) >= 20 or a == b:
                return
            if isinstance(a, dict) and isinstance(b, dict):
                for key in sorted(a.keys() | b.keys()):
                    if key not in a or key not in b:
                        differences.append({"path": path + "/" + key, "before": a.get(key), "after": b.get(key)})
                    else:
                        visit(a[key], b[key], path + "/" + key)
            elif isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
                for index, (left, right) in enumerate(zip(a, b)):
                    visit(left, right, path + "/" + str(index))
            else:
                differences.append({"path": path, "before": a, "after": b})

        visit(before, after, "")
        raise RuntimeError("STOP: before/after replay mismatch: " + json.dumps(differences, ensure_ascii=False))
    return {name: "IDENTICAL" for name in (
        "top3", "full_ranking", "scores", "authority", "schema", "universe",
        "decision_hashes", "fail_closed", "display", "router_routes", "zero_new_capital_authority")}


def existing_tests(root):
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
        run = subprocess.run([sys.executable, "-B", "-c", bootstrap, str(script)], cwd=root,
                             text=True, capture_output=True, timeout=90,
                             env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        require(run.returncode == 0, script.name + " failed: " + (run.stdout + run.stderr)[-4000:])
        results.append({"test": script.name, "status": "PASS"})
    require(len(results) == 8, "expected eight existing script regressions")
    return results


def self_test():
    baseline = {"top3": ["1111", "2222"],
                "full_ranking": [{"ticker": "1111", "score": 1.0}, {"ticker": "2222", "score": 0.5}],
                "scores": [1.0, 0.5],
                "authority": "FIXED", "schema": 5, "universe": ["1111", "2222"],
                "decision_hash": "fixed", "fail_closed": {"count": 0},
                "display": {"rankings_separate": True, "legacy_v3_display_authority": False},
                "router_routes": {"09:03": ["q017_recovery", "e2_morning"]},
                "zero_new_capital_authority": True}
    compare(baseline, baseline)
    for key in baseline:
        changed = json.loads(json.dumps(baseline))
        changed[key] = "SYNTHETIC_TEST_DIFFERENCE"
        try:
            compare(baseline, changed)
        except RuntimeError as exc:
            require("STOP:" in str(exc) and "/" + key in str(exc), "missing mismatch evidence")
        else:
            raise RuntimeError("STOP: equivalence gate accepted a difference")
    # Tiny score changes must not be hidden by an epsilon or rounded comparison.
    changed = json.loads(json.dumps(baseline))
    changed["full_ranking"][1]["score"] += 1e-15
    try:
        compare(baseline, changed)
    except RuntimeError as exc:
        require("/full_ranking/1/score" in str(exc), "missing exact score difference")
    else:
        raise RuntimeError("STOP: equivalence gate accepted a tiny score difference")
    print(json.dumps({"status": "PASS", "synthetic_difference_rejection_cases": len(baseline) + 1}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--before", default=SNAPSHOT)
    parser.add_argument("--after", default="HEAD")
    parser.add_argument("--report", type=Path)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--probe", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    if args.probe:
        print(json.dumps(probe(args.probe.resolve()), ensure_ascii=False, allow_nan=False))
        return
    if args.report:
        args.report.unlink(missing_ok=True)
    before_sha = git(args.repo, "rev-parse", args.before + "^{commit}").decode().strip()
    after_sha = git(args.repo, "rev-parse", args.after + "^{commit}").decode().strip()
    changed = git(args.repo, "diff", "--name-only", before_sha, after_sha).decode().splitlines()
    # Source changes are allowed as inputs to replay; output equality, not an
    # infrastructure-only diff allowlist, decides whether engineering is safe.
    production_unchanged = all(p.startswith(("tests/engineering/", "docs/engineering/")) or
                               p == ".github/workflows/hengce-engineering-replay.yml" for p in changed)
    with tempfile.TemporaryDirectory(prefix="hengce-replay-") as td:
        base = Path(td)
        frozen = base / "snapshot"
        export(args.repo, SNAPSHOT, frozen)
        results = []
        for name, sha in (("before", before_sha), ("after", after_sha)):
            root = base / name
            export(args.repo, sha, root)
            for directory in ("hengce", "eod", "receipts", "research"):
                shutil.rmtree(root / directory, ignore_errors=True)
                shutil.copytree(frozen / directory, root / directory)
            env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONHASHSEED": "0"}
            run = subprocess.run([sys.executable, "-B", str(Path(__file__).resolve()), "--probe", str(root)],
                                 text=True, capture_output=True, timeout=120, env=env)
            require(run.returncode == 0, name + " replay failed: " + run.stderr[-6000:])
            results.append(json.loads(run.stdout))
        checks = compare(*results)
        regressions = existing_tests(root)
    result = results[0]
    report = {"status": "PASS", "before_commit": before_sha, "after_commit": after_sha,
              "snapshot_commit": SNAPSHOT, "snapshot_date": DAY, "changed_files": changed,
              "production_files_unchanged": production_unchanged, "checks": checks,
              "existing_regressions": regressions,
              "top3": [x["ticker"] for x in result["q017"]["top3"]],
              "full_ranking_counts": {k: len(v) for k, v in result["full_rankings"].items()},
              "full_ranking_sha256": {k: digest(v) for k, v in result["full_rankings"].items()},
              "q017_decision_sha256": result["q017"]["decision_snapshot_sha256"],
              "observation_sha256": result["q017"]["observation_snapshot_sha256"],
              "universe_sha256": result["q017"]["universe_lock"]["universe_sha256"],
              "fail_closed_cases": list(result["fail_closed"]),
              "zero_new_capital_authority": result["zero_new_capital_authority"],
              "replay_payload_sha256": digest(result)}
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
