"""Local synthetic Git race regression for HBA publication; no vendor/model calls."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from hengce_publish import PROFILES, matches

PUBLISHER = ROOT / "scripts/hengce_publish.py"
BRIDGE = "escape_live/finmind_premarket_bridge_shadow.json"
MONITOR = "escape_live/intraday_monitor.json"
EOD = "eod/20261112/status.json"
HBA = "research/hba_surveillance/latest.json"


def git(repo, *args):
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        text=True, capture_output=True, check=True, timeout=20
    ).stdout.strip()


class HBAPublisherRaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="hba-publication-race-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.remote = self.root / "remote.git"
        subprocess.run(
            ["git", "init", "--bare", "--initial-branch=main", str(self.remote)],
            check=True, capture_output=True, timeout=20
        )
        initial = self.clone("initial")
        self.write(initial, HBA, '{"version":0}\n')
        self.write(initial, BRIDGE, '{"version":0}\n')
        self.write(initial, MONITOR, '{"version":0}\n')
        self.write(initial, EOD, '{"version":0}\n')
        git(initial, "add", ".")
        git(initial, "commit", "-m", "synthetic baseline")
        git(initial, "push", "origin", "HEAD:main")
        self.hba = self.clone("hba")
        self.writer = self.clone("writer")

    def clone(self, name):
        dest = self.root / name
        subprocess.run(
            ["git", "clone", str(self.remote), str(dest)],
            check=True, capture_output=True, timeout=20
        )
        git(dest, "config", "user.name", "Synthetic HBA")
        git(dest, "config", "user.email", "synthetic@example.invalid")
        return dest

    @staticmethod
    def write(repo, path, value):
        target = repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(value, encoding="utf-8")

    def advance_remote(self, path):
        self.write(self.writer, path, '{"version":1}\n')
        git(self.writer, "add", path)
        git(self.writer, "commit", "-m", "synthetic independent update")
        git(self.writer, "push", "origin", "HEAD:main")

    def publish_stale_hba(self):
        self.write(self.hba, HBA, '{"version":2}\n')
        git(self.hba, "add", HBA)
        git(self.hba, "commit", "-m", "synthetic HBA research output")
        reports = self.root / "publication-receipts"
        run = subprocess.run(
            [sys.executable, str(PUBLISHER), "--repo", str(self.hba),
             "--profile", "hba-surveillance", "--report-dir", str(reports)],
            text=True, capture_output=True, timeout=30
        )
        entries = [json.loads(p.read_text(encoding="utf-8"))
                   for p in sorted(reports.glob("*.json"))]
        self.assertTrue(entries, run.stdout + run.stderr)
        return run.returncode, entries

    def remote_read(self, path):
        git(self.writer, "fetch", "origin", "main")
        return git(self.writer, "show", "FETCH_HEAD:" + path)

    def test_scope_allows_only_hba_writes_and_excludes_only_proven_unrelated_bridge(self):
        profile = PROFILES["hba-surveillance"]
        self.assertTrue(matches(BRIDGE, profile["unrelated"]))
        self.assertTrue(matches("hengce/health/latest.json", profile["unrelated"]))
        for source in (MONITOR, EOD, "ownership/tdcc/20261106/receipt.json",
                       "overseas_premarket/latest.json",
                       "scripts/hengce_hba_context_bridge_v1.py",
                       "hengce/HENGCE_SCAN_ONCE_CONTRACT_LATEST.json",
                       "unknown/new_authoritative_source.json"):
            with self.subTest(source=source):
                self.assertFalse(matches(source, profile["unrelated"]))
        self.assertTrue(matches(HBA, profile["writes"]))
        self.assertTrue(matches("research/hba_surveillance/history/fixture.json", profile["writes"]))
        self.assertFalse(matches(EOD, profile["writes"]))
        self.assertFalse(matches("scripts/hengce_publish.py", profile["writes"]))

    def test_premarket_display_update_does_not_discard_fresh_hba_result(self):
        self.advance_remote(BRIDGE)
        code, entries = self.publish_stale_hba()
        self.assertEqual(code, 0, entries)
        self.assertIn("RETRY_REVALIDATED", [x["result"] for x in entries])
        self.assertEqual(entries[-1]["result"], "PUBLISHED")
        self.assertEqual(self.remote_read(HBA), '{"version":2}')
        self.assertEqual(self.remote_read(BRIDGE), '{"version":1}')

    def test_real_intraday_input_change_still_fails_closed(self):
        self.advance_remote(MONITOR)
        code, entries = self.publish_stale_hba()
        self.assertEqual(code, 2, entries)
        self.assertEqual(entries[-1]["result"], "CONFLICT_FAIL_CLOSED")
        self.assertIn("READ_DEPENDENCY_CHANGED:" + MONITOR,
                      entries[-1]["conflict_reason"])
        self.assertEqual(self.remote_read(HBA), '{"version":0}')

    def test_canonical_eod_change_still_fails_closed(self):
        self.advance_remote(EOD)
        code, entries = self.publish_stale_hba()
        self.assertEqual(code, 2, entries)
        self.assertIn("READ_DEPENDENCY_CHANGED:" + EOD,
                      entries[-1]["conflict_reason"])
        self.assertEqual(self.remote_read(HBA), '{"version":0}')


if __name__ == "__main__":
    unittest.main()
