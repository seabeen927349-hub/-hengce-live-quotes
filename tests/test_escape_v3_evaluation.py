import unittest,sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'research/escape_v3_20261104'))
from validate_v3 import confusion,episode_indices
class TestEvaluation(unittest.TestCase):
 def test_confusion_definitions(self):
  r=confusion([1,1,0,0],[1,0,1,0]);self.assertEqual([r[k] for k in ('tp','fp','fn','tn')],[1]*4)
  self.assertEqual(r['false_positive_rate'],.5);self.assertEqual(r['false_discovery_rate'],.5)
 def test_no_alert_not_zero_precision(self):self.assertIsNone(confusion([0,0],[1,0])['precision'])
 def test_no_events_not_zero_recall(self):self.assertIsNone(confusion([1,0],[0,0])['recall'])
 def test_empty_not_perfect(self):self.assertIsNone(confusion([],[])['precision'])
 def test_events_nonoverlap(self):
  ev=episode_indices(np.full(100,-.02),5,-.03)
  self.assertTrue(all(b[0]>=a[1] for a,b in zip(ev,ev[1:])))
 def test_event_crossing_strict_future(self):
  ev=episode_indices(np.array([0,-.01,-.02,-.03,0,0]),5,-.03)
  self.assertEqual(ev,[(0,5,3)])
 def test_incomplete_terminal_excluded(self):self.assertEqual(episode_indices(np.full(5,-.2),5,-.03),[])
 def test_missing_return_excluded(self):self.assertEqual(episode_indices(np.array([0,np.nan,-.2,-.2,-.2,-.2]),5,-.03),[])
if __name__=='__main__':unittest.main()
