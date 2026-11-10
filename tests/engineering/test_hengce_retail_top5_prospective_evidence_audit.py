import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(REPO/"scripts"))
import hengce_retail_top5_prospective_evidence_audit as cap

NOW = datetime.fromisoformat("2026-11-10T21:35:00+08:00")
DECISION = date(2026,11,6)


class ProspectiveEvidenceAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)/"repo"
        self.root.mkdir(parents=True)
        for d in ["20261008","20261016","20261022"]:
            (self.root/"ownership"/"tdcc"/d).mkdir(parents=True)

    def fake_price(self,root,day):
        return [["test"]]*1001,{"date":day.isoformat(),"sha256":"fixture-price-hash"}

    def fake_tdcc(self,raw_path,receipt_path,*,cutoff,asof_datetime):
        d=receipt_path.parent.name
        return [["test"]]*1001,{"snapshot_date":d,"raw_sha256":"fixture-tdcc-hash",
                               "observed_at_taipei":"2026-10-23T12:00:00+08:00"}

    def check(self,**kwargs):
        return cap.diagnose(self.root,DECISION,now=NOW,
                            eod_reader=kwargs.pop("eod_reader",self.fake_price),
                            tdcc_reader=kwargs.pop("tdcc_reader",self.fake_tdcc),
                            **kwargs)

    def test_full_provenance_capability_never_promotes_model(self):
        result=self.check()
        self.assertEqual(result["data_readiness"],"PIT_CANONICAL_DATA_PREPARED_RESEARCH_ONLY")
        self.assertEqual(len(result["verified_eod_sessions"]),21)
        self.assertEqual(len(result["tdcc_verifications"]),3)
        self.assertEqual(result["tdcc_eligible_snapshots"],
                         ["20261008","20261016","20261022"])
        self.assertEqual(result["research_top5"],[])
        self.assertFalse(result["model_ready_for_publication"])
        self.assertFalse(result["historical_pit_rehabilitated"])
        self.assertFalse(result["selection_performed"])
        self.assertFalse(result["broker_execution"])
        self.assertEqual(result["authorized_lots"],0)

    def test_original_repo_current_data_fails_closed_and_reports_reasons(self):
        report=cap.diagnose(REPO,DECISION,now=NOW)
        self.assertEqual(report["data_readiness"],"BLOCKED")
        self.assertTrue(report["blockers"])
        self.assertEqual(report["research_top5"],[])
        self.assertFalse(report["model_ready_for_publication"])
        self.assertFalse(report["broker_execution"])
        self.assertLess(len(report["tdcc_verifications"]),3)
        self.assertEqual(report["tdcc_cutoff"],"2026-10-23")

    def test_missing_one_canonical_eod_day_blocks(self):
        def missing(root,day):
            if day==date(2026,10,15):
                raise cap.DataBlocked("PRICE_CHAIN_HASH_MISMATCH")
            return self.fake_price(root,day)
        report=self.check(eod_reader=missing)
        self.assertEqual(report["data_readiness"],"BLOCKED")
        self.assertIn("CANONICAL_21_SESSION_PRICE_CHAIN_INCOMPLETE",report["blockers"])
        self.assertEqual(len(report["eod_issues"]),1)
        self.assertEqual(report["eod_issues"][0]["date"],"2026-10-15")
        self.assertFalse(report["broker_execution"])

    def test_missing_tdcc_receipt_or_first_observed_blocks(self):
        def no_proof(raw,receipt,*,cutoff,asof_datetime):
            if receipt.parent.name=="20261016":
                raise cap.DataBlocked("TDCC_FIRST_OBSERVED_PROOF_ABSENT")
            return self.fake_tdcc(raw,receipt,cutoff=cutoff,asof_datetime=asof_datetime)
        report=self.check(tdcc_reader=no_proof)
        self.assertIn("CANONICAL_TDCC_PIT_CHAIN_INCOMPLETE",report["blockers"])
        self.assertEqual(report["tdcc_issues"][0]["snapshot_date"],"20261016")
        self.assertEqual(len(report["tdcc_verifications"]),2)

    def test_missing_tdcc_week_never_downgrades_two_week_requirement(self):
        (self.root/"ownership"/"tdcc"/"20261008").rmdir()
        report=self.check()
        self.assertEqual(report["tdcc_eligible_snapshots"],["20261016","20261022"])
        self.assertIn("THREE_CANONICAL_TDCC_SNAPSHOTS_ABSENT",report["blockers"])
        self.assertIn("INSUFFICIENT_THREE_VERIFIED_TDCC_WEEKS",report["blockers"])
        self.assertEqual(report["data_readiness"],"BLOCKED")

    def test_no_backfill_or_past_asof_repair_by_date_label(self):
        fake_date=date(2026,11,6)
        def late_observation(raw,receipt,*,cutoff,asof_datetime):
            if receipt.parent.name=="20261022":
                raise cap.DataBlocked("TDCC_FIRST_OBSERVED_AFTER_DECISION")
            return self.fake_tdcc(raw,receipt,cutoff=cutoff,asof_datetime=asof_datetime)
        report=self.check(tdcc_reader=late_observation)
        self.assertFalse(report["historical_pit_rehabilitated"])
        self.assertFalse(report["mother_backfill_used"])
        self.assertEqual(report["data_readiness"],"BLOCKED")
        self.assertEqual(report["research_top5"],[])

    def test_future_non_friday_and_wrong_year_block_without_reading_data(self):
        for d in [date(2026,11,13),date(2026,11,9),date(2027,1,1)]:
            out=cap.diagnose(self.root,d,now=NOW,
                             eod_reader=lambda *_:self.fail("must not read EOD"))
            self.assertEqual(out["data_readiness"],"BLOCKED")
            self.assertEqual(out["blockers"],["DECISION_MUST_BE_PAST_2026_FRIDAY"])

    def test_artifact_written_only_outside_repository(self):
        report=self.check()
        out=self.root.parent/"result"
        cap.save(self.root,out,report)
        self.assertTrue((out/"prospective_pit_evidence.json").exists())
        self.assertFalse((out/"selection.json").exists())
        self.assertFalse((out/"orders.csv").exists())
        with self.assertRaisesRegex(cap.DataBlocked,"OUTPUT_MUST_BE_OUTSIDE_HENGCE_REPOSITORY"):
            cap.save(self.root,self.root/"eod"/"upstream",report)

    def test_snapshot_directory_does_not_accept_invalid_names(self):
        root=self.root/"ownership"/"tdcc"
        for name in ["bad","2026116","2026-10-10","20269999"]:
            (root/name).mkdir()
        found=cap._canonical_tdcc_dirs(self.root,date(2026,10,23))
        self.assertEqual([x[1].name for x in found],
                         ["20261008","20261016","20261022"])


if __name__=="__main__":
    unittest.main()
