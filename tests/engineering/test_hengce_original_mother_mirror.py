"""Read-only invariants for original EOD -> existing canonical Mother receipts.

No alternative mother construction, no model weights, no source data rewriting.
"""
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


class OriginalMotherMirrorTests(unittest.TestCase):
    def test_latest_verified_20261116_library_bridge_is_mirrored(self):
        root=ROOT/"eod/20261116"
        eod=read(root/"status.json")
        mother=read(root/"receipts/mother.json")
        self.assertEqual(eod["mother_status"],"COMPLETE")
        self.assertTrue(eod["downstream_ready"])
        self.assertEqual(mother["target_date"],"2026-11-16")
        self.assertEqual(mother["mother_rows"],1036445)
        self.assertEqual(mother["mother_sha256"],
                         "51f4301b2abdc887750a510b85e18026209f99ca8265341bec59115af456cce0")
        self.assertEqual(mother["integrity_status"],"PASS")
        self.assertEqual(mother["mother_rows"]-1035354,eod["price_rows"])
        self.assertEqual(mother["source_workflow_run_id"],43902069972)
        self.assertEqual(mother["canonical_library_incremental_receipt"],
                         "/HENGCE_CANONICAL/HENGCE_HIST_MOTHER_INCREMENTAL_RECEIPT_20261116.json")

    def test_promoted_original_eod_hashes_and_status_are_consistent(self):
        paths=sorted((ROOT/"eod").glob("202611*/status.json"))
        self.assertTrue(paths)
        for p in paths:
            status=read(p)
            with self.subTest(date=p.parent.name):
                self.assertEqual(status["target_date"],p.parent.name[:4]+"-"+
                                 p.parent.name[4:6]+"-"+p.parent.name[6:])
                if status.get("mother_status")!="COMPLETE":
                    self.assertFalse(status.get("downstream_ready",False))
                    continue
                mother=read(p.parent/"receipts/mother.json")
                self.assertEqual(mother["status"],"PASS")
                self.assertEqual(mother["target_date"],status["target_date"])
                self.assertEqual(mother["mother_latest_date"],status["target_date"])
                self.assertFalse(mother["second_mother"])
                self.assertEqual(mother["mother_sha256"],status["mother_sha256"])
                self.assertTrue(status["downstream_ready"])
                self.assertTrue(status["three_leg_complete"])
                for leg in ("price","institutional","margin"):
                    self.assertEqual(mother["promoted_leg_sha256"][leg],
                                     status[leg+"_sha256"])
                    self.assertEqual(read(p.parent/"receipts"/(leg+".json"))["sha256"],
                                     status[leg+"_sha256"])


if __name__=="__main__":
    unittest.main()
