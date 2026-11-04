"""Q017 operation retirement static regression checks."""
import json,pathlib,unittest
ROOT=pathlib.Path(__file__).resolve().parents[2]
class TestRetirement(unittest.TestCase):
    def test_no_workflows(self):self.assertEqual([],list((ROOT/".github/workflows").glob("*q017*.yml")))
    def test_no_runtime_scripts(self):self.assertEqual([],list((ROOT/"scripts").glob("*q017*.py")))
    def test_authority(self):
        c=json.loads((ROOT/"hengce/HENGCE_SCAN_ONCE_CONTRACT_LATEST.json").read_text())
        self.assertEqual(0,c["active_strategy_count"]);self.assertFalse(c["cross_chat_restore_required"])
        a=json.loads((ROOT/"hengce/HENGCE_Q017_RETIREMENT_LOCK_20261105.json").read_text())
        self.assertFalse(a["selection_authority"])
    def test_shared_eod(self):
        s=(ROOT/"scripts/hengce_daily_command_center_core_legacy.py").read_text()
        for key in ("TWSE_PRICE","TWSE_INST","TWSE_MARGIN","def get_json","def atomic_json"):self.assertIn(key,s)
        self.assertNotIn("def radar_run",s)
if __name__=="__main__":unittest.main()
