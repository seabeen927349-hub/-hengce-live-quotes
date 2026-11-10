import json
import shutil
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import hengce_retail_top5_mother_price_recovery as m


class MotherResearchRecoveryTests(unittest.TestCase):
    def test_parent_and_extracted_slice_are_pinned_to_original_mother(self):
        rows, meta = m.verified_research_extract(ROOT)
        self.assertEqual(meta["canonical_source_sha256"], m.PINNED_PARENT_SHA)
        self.assertEqual(meta["slice_sha256"], m.PINNED_EXTRACT_SHA)
        self.assertEqual(len(rows), 8)
        self.assertEqual(sum(len(rows[d]) for d in rows), 8692)
        self.assertEqual(len(rows["2026-10-15"]), 1085)

    def test_actual_20261106_21_session_research_recovery(self):
        status, rows = m.assemble(ROOT, date(2026, 11, 6), today=date(2026, 11, 10))
        self.assertEqual(status["source_status"], "RESEARCH_PRICE_21_SESSIONS_RECOVERED_NO_PIT",
                         status["blockers"])
        self.assertEqual(status["canonical_eod_days"], 13)
        self.assertEqual(status["mother_research_recovered_days"], 8)
        self.assertEqual(len(status["origin_by_day"]), 21)
        self.assertGreater(len(rows), 21*900)
        self.assertFalse(status["historical_pit_certified"])
        self.assertFalse(status["selection_authority"])
        self.assertFalse(status["broker_execution"])
        self.assertFalse(status["model_selection_performed"])
        self.assertEqual(status["top5"], [])
        self.assertEqual(status["authorized_lots"], 0)
        recovered = [x for x in status["origin_by_day"]
                     if x["origin"] == "CANONICAL_MOTHER_RESEARCH_RETROSPECTIVE"]
        self.assertTrue(all(x["not_available_at_friday_20261106"] for x in recovered))

    def test_reject_if_canonical_integrity_not_verified(self):
        def corrupt(root, day):
            raise m.DataBlocked("EOD_PRICE_SHA_MISMATCH")
        result, rows = m.assemble(ROOT, date(2026, 11, 6),
                                  today=date(2026, 11, 10), read_canonical=corrupt)
        self.assertFalse(result["research_price_continuity"])
        self.assertEqual(rows, [])
        self.assertTrue(any("CANONICAL_EOD_INTEGRITY_ERROR" in e for e in result["blockers"]))

    def test_reject_if_missing_session_not_covered_by_verified_mother(self):
        def missing(root, day):
            raise m.DataBlocked("EOD_DATE_OR_PRICE_NOT_VERIFIED")
        result, rows = m.assemble(ROOT, date(2026, 11, 6),
                                  today=date(2026, 11, 10), read_canonical=missing)
        self.assertFalse(result["research_price_continuity"])
        self.assertEqual(rows, [])
        self.assertTrue(any("NO_RESEARCH_MOTHER_SLICE_FOR_SESSION" in e for e in result["blockers"]))

    def test_corrupted_slice_hash_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            parent = root / "eod/source_recovery_20261110"
            parent.mkdir(parents=True)
            src = ROOT / "eod/source_recovery_20261110"
            shutil.copy(src/"recovery_manifest.json", parent/"recovery_manifest.json")
            data = (src/"mother_research_backfill_8dates.csv").read_bytes()
            (parent/"mother_research_backfill_8dates.csv").write_bytes(data+b" ")
            with self.assertRaisesRegex(m.DataBlocked, "SLICE_SHA_MISMATCH"):
                m.verified_research_extract(root)

    def test_manifest_origin_protection(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            parent = root / "eod/source_recovery_20261110"
            parent.mkdir(parents=True)
            src = ROOT / "eod/source_recovery_20261110"
            mft = json.loads((src/"recovery_manifest.json").read_text())
            mft["canonical_source_sha256"] = "0"*64
            (parent/"recovery_manifest.json").write_text(json.dumps(mft))
            with self.assertRaisesRegex(m.DataBlocked, "MANIFEST_CONTRACT_MISMATCH"):
                m.verified_research_extract(root)

    def test_future_and_non_friday_dates_fail_closed(self):
        for day in [date(2026,11,13), date(2026,11,9)]:
            report, data = m.assemble(ROOT,day,today=date(2026,11,10))
            self.assertEqual(report["top5"], [])
            self.assertEqual(data, [])
            self.assertEqual(report["source_status"], "BLOCKED")

    def test_outside_repo_research_artifact_only(self):
        report, rows = m.assemble(ROOT,date(2026,11,6),today=date(2026,11,10))
        self.assertTrue(report["research_price_continuity"])
        with tempfile.TemporaryDirectory() as d:
            output = Path(d)/"weekly"
            m.save(ROOT,output,report,rows)
            self.assertTrue((output/"price_21session_research_only.csv").exists())
            self.assertTrue((output/"mother_recovery_status.json").exists())
            self.assertFalse((output/"selection.json").exists())
            self.assertFalse((output/"orders.csv").exists())

    def test_no_mutation_into_original_eod(self):
        report, rows = m.assemble(ROOT,date(2026,11,6),today=date(2026,11,10))
        with self.assertRaisesRegex(m.DataBlocked, "OUTPUT_MUST_BE_OUTSIDE_HENGCE_REPOSITORY"):
            m.save(ROOT,ROOT/"eod/overwrite",report,rows)


if __name__ == "__main__":
    unittest.main()
