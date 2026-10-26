#!/usr/bin/env python3
"""Synthetic PR admission tests against the actual GitHub workflow YAML.

GitHub pull_request without paths/branches/types filters admits every default PR
event regardless of its file list. Requiring that shape avoids approximating
GitHub's glob matcher and its changed-file limits with a different glob engine.
"""
from __future__ import annotations

import copy
from pathlib import Path
import unittest

import yaml
import replay_equivalence as replay

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/hengce-engineering-replay.yml"


def scripts_only_pr():
    return {"action": "synchronize", "base": "main", "head": "engineering-test",
            "changed_files": ["scripts/hengce_scan_once_router.py"]}


def assert_admitted(test, config, event):
    test.assertIn(event["action"], ("opened", "synchronize", "reopened"))
    test.assertTrue(event["changed_files"])
    test.assertIn("pull_request", config["on"])
    # An empty mapping/null uses GitHub's default unrestricted PR admission.
    trigger = config["on"]["pull_request"] or {}
    for restriction in ("paths", "paths-ignore", "branches", "branches-ignore", "types"):
        test.assertNotIn(restriction, trigger, "synthetic PR could be skipped by " + restriction)
    job = config["jobs"]["replay"]
    test.assertNotIn("if", job, "synthetic PR could be skipped at job level")
    steps = [step for step in job["steps"] if "--report" in step.get("run", "")]
    test.assertEqual(len(steps), 1)
    test.assertNotIn("if", steps[0], "synthetic PR could be skipped at replay step")


class WorkflowAdmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # BaseLoader preserves the YAML key 'on' instead of treating it as bool.
        cls.config = yaml.load(WORKFLOW.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)

    def test_scripts_only_pr_triggers_replay(self):
        event = scripts_only_pr()
        self.assertEqual(event["changed_files"], ["scripts/hengce_scan_once_router.py"])
        for action in ("opened", "synchronize", "reopened"):
            with self.subTest(action=action):
                assert_admitted(self, self.config, {**event, "action": action})

    def test_other_production_scripts_and_workflows_trigger(self):
        for path in ("scripts/hengce_e2_live.py", "scripts/nested/helper.py",
                     ".github/workflows/hengce-daily-command-center.yml",
                     ".github/workflows/hengce-q017-primary-observer.yml"):
            with self.subTest(path=path):
                assert_admitted(self, self.config, {**scripts_only_pr(), "changed_files": [path]})

    def test_bootstrap_path_filter_regression_is_detected(self):
        old = copy.deepcopy(self.config)
        old["on"]["pull_request"] = {"paths": ["tests/engineering/**", "docs/engineering/**"]}
        with self.assertRaisesRegex(AssertionError, "paths"):
            assert_admitted(self, old, scripts_only_pr())

    def test_snapshot_is_still_pinned_and_base_head_are_dynamic(self):
        self.assertEqual(replay.SNAPSHOT, "900b0bc862e03a2b496129b0fc68d066c39542bf")
        self.assertEqual(replay.DAY, "2026-10-21")
        job = self.config["jobs"]["replay"]
        step = next(s for s in job["steps"] if "--report" in s.get("run", ""))
        self.assertIn("github.event.pull_request.base.sha", step["env"]["BEFORE_SHA"])
        self.assertIn("github.event.pull_request.head.sha", step["env"]["AFTER_SHA"])
        self.assertIn('--before "$BEFORE_SHA"', step["run"])
        self.assertIn('--after "$AFTER_SHA"', step["run"])
        self.assertIn('tests/engineering/q017_cleanup_audit.py', step['run'])
        self.assertEqual(self.config["permissions"], {"contents": "read"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
