import csv
import json
import shutil
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import hengce_retail_top5_g1_retail_recovery as g1


class ExistingG1RetailRecoveryTests(unittest.TestCase):
    def test_real_457week_mother_slice_and_raw_headcounts(self):
        rows, manifest = g1.verified_panel(ROOT, date(2026,11,6))
        self.assertEqual(len(rows), 3248)
        self.assertEqual(manifest["parent_sha256"], g1.ORIGINAL_PARENT_SHA)
        self.assertEqual(manifest["extracted_sha256"], g1.EXTRACT_SHA)
        self.assertEqual(manifest["weekly_dates"], g1.EXPECTED_DATES)
        sample = {row[0]: row[2] for row in rows if row[1] == "3042"}
        self.assertEqual(sample, {"20261008": "86168", "20261016": "88236", "20261022": "90066"})

    def test_readonly_retro_receipt_never_grants_strategy_authority(self):
        state, rows = g1.audit(ROOT, date(2026,11,6), today=date(2026,11,10))
        self.assertEqual(len(rows), 3248)
        self.assertEqual(state["research_data_status"], "THREE_WEEK_RETAIL_MOTHER_RECOVERED_RETROSPECTIVE_ONLY")
        self.assertFalse(state["official_pit_first_observed_verified"])
        self.assertFalse(state["formal_tdcc_mutated"])
        self.assertFalse(state["model_selection_performed"])
        self.assertEqual(state["top5"], [])
        self.assertEqual(state["authorized_lots"], 0)
        self.assertFalse(state["broker_execution"])

    def test_distinguishes_14_day_lag_from_undocumented_release(self):
        state, _ = g1.audit(ROOT, date(2026,11,6), today=date(2026,11,10))
        self.assertEqual(state["source_provenance"]["last_snapshot"], "20261022")
        self.assertEqual(state["source_provenance"]["historical_publication_time"], "UNVERIFIED")
        self.assertEqual(state["source_provenance"]["data_available_as_of"], "2026-11-07")

    def test_corrupt_slice_hash_blocks(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            p = root / "ownership/tdcc/research_recovery_20261110"
            p.mkdir(parents=True)
            source = ROOT / "ownership/tdcc/research_recovery_20261110"
            shutil.copy(source / "v22_g1_3w_retro_manifest.json", p)
            b = (source / "v22_g1_retail_20261008_16_22_retro.csv").read_bytes()
            (p / "v22_g1_retail_20261008_16_22_retro.csv").write_bytes(b + b"\n")
            with self.assertRaisesRegex(g1.DataBlocked, "SLICE_SHA_MISMATCH"):
                g1.verified_panel(root, date(2026,11,6))

    def test_manually_edited_manifest_parent_sha_blocks(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            p = root / "ownership/tdcc/research_recovery_20261110"
            p.mkdir(parents=True)
            source = ROOT / "ownership/tdcc/research_recovery_20261110"
            data = json.loads((source / "v22_g1_3w_retro_manifest.json").read_text())
            data["parent_sha256"] = "0" * 64
            (p / "v22_g1_3w_retro_manifest.json").write_text(json.dumps(data))
            with self.assertRaisesRegex(g1.DataBlocked, "MANIFEST_MISMATCH:parent_sha256"):
                g1.verified_panel(root, date(2026,11,6))

    def test_only_fixed_research_date_allowed(self):
        for d in [date(2026,11,13),date(2026,10,30)]:
            state, rows = g1.audit(ROOT, d, today=date(2026,11,14))
            self.assertEqual(state["research_data_status"], "BLOCKED")
            self.assertEqual(rows, [])

    def test_future_research_date_rejected(self):
        state, rows = g1.audit(ROOT, date(2026,11,13), today=date(2026,11,10))
        self.assertIn("DECISION_IN_FUTURE", state["blockers"])
        self.assertEqual(rows, [])

    def test_writes_only_outside_original_repo(self):
        state, rows = g1.audit(ROOT, date(2026,11,6), today=date(2026,11,10))
        with tempfile.TemporaryDirectory() as d:
            output=Path(d)/"g1_retro"
            g1.save(ROOT, output, state, rows)
            self.assertTrue((output/"weekly_3snapshot_research_only.csv").exists())
            self.assertFalse((output/"selection.json").exists())
            self.assertFalse((output/"orders.csv").exists())
            with (output/"weekly_3snapshot_research_only.csv").open(encoding="utf-8-sig") as f:
                self.assertEqual(len(list(csv.reader(f))), 3249)

    def test_cannot_write_into_existing_tdcc(self):
        state, rows = g1.audit(ROOT, date(2026,11,6), today=date(2026,11,10))
        with self.assertRaisesRegex(g1.DataBlocked, "OUTPUT_MUST_BE_OUTSIDE_HENGCE_REPOSITORY"):
            g1.save(ROOT, ROOT/"ownership/tdcc/20261106/overwritten", state, rows)


if __name__ == "__main__":
    unittest.main()
