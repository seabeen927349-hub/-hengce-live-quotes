import sys,unittest,copy
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import HENGCE_ESCAPE_STATE_ENGINE_V3_RESEARCH as v3
import HENGCE_ESCAPE_FEATURE_DETECTOR_V1 as det
import HENGCE_ESCAPE_STATE_ENGINE_V2 as v2
from datetime import date,timedelta

def packet(i=0):
 return {'trade_date':str(date(2020,1,1)+timedelta(days=i)),'session_index':i,'phase':'EOD_FORMAL','research_only':True,'source_integrity_verified':True,'data_gate':{'pit_pass':False},'metric_contract_version':det.METRIC_CONTRACT_VERSION,'metric_contract_sha256':det.METRIC_CONTRACT_SHA256,'metrics_history':{m:[1.]*66 for m in det.METRICS}}

class TestV3(unittest.TestCase):
 def sequence(self,levels):
  e=v3.ResearchStateEngine();out=[]
  for i,l in enumerate(levels):
   with patch.object(v3.frozen,'evaluate',return_value={'escape_level':l}):out.append(e.evaluate(packet(i)))
  return out
 def test_bounded_release_all_levels(self):
  for high in range(1,7):
   for low in range(high):
    out=self.sequence([high]+[low]*5)
    self.assertEqual([o['persistent_state_level'] for o in out],[high]*5+[low])
 def test_escalation_immediate(self):
  self.assertEqual([x['persistent_state_level'] for x in self.sequence([0,1,2,3,4,5,6])],list(range(7)))
 def test_rolling_max_invariant(self):
  import random
  r=random.Random(121);seq=[r.randrange(7) for _ in range(1000)]
  self.assertEqual([x['persistent_state_level'] for x in self.sequence(seq)],[max(seq[max(0,i-4):i+1]) for i in range(len(seq))])
 def test_no_single_day_drop(self):self.assertEqual(self.sequence([6,0])[-1]['persistent_state_level'],6)
 def test_recovery_to_zero(self):self.assertTrue(self.sequence([6]+[0]*5)[-1]['recovery_to_zero'])
 def test_reescalation(self):self.assertEqual(self.sequence([6]+[0]*5+[5])[-1]['transition'],'ESCALATE')
 def test_missing_resets_confirmation(self):
  e=v3.ResearchStateEngine()
  with patch.object(v3.frozen,'evaluate',return_value={'escape_level':6}):e.evaluate(packet(0))
  with patch.object(v3.frozen,'evaluate',return_value={'escape_level':0}):
   for i in range(1,4):e.evaluate(packet(i))
   p=packet(4);p['metrics_history']['foreign_relative_flow_5'][-1]=None
   self.assertEqual(e.evaluate(p)['status'],'UNVERIFIED')
   for i in range(5,9):self.assertEqual(e.evaluate(packet(i))['persistent_state_level'],6)
   self.assertEqual(e.evaluate(packet(9))['persistent_state_level'],0)
 def test_gap_resets_confirmation(self):
  e=v3.ResearchStateEngine()
  with patch.object(v3.frozen,'evaluate',return_value={'escape_level':6}):e.evaluate(packet())
  with patch.object(v3.frozen,'evaluate',return_value={'escape_level':0}):
   for i in range(3,7):self.assertEqual(e.evaluate(packet(i))['persistent_state_level'],6)
   self.assertEqual(e.evaluate(packet(7))['persistent_state_level'],0)
 def test_order_rejected(self):
  e=v3.ResearchStateEngine();e.evaluate(packet(2));self.assertEqual(e.evaluate(packet(1))['reason'],'NON_MONOTONIC_OBSERVATION')
 def test_duplicate_rejected(self):
  e=v3.ResearchStateEngine();e.evaluate(packet());self.assertEqual(e.evaluate(packet())['reason'],'NON_MONOTONIC_OBSERVATION')
 def test_wrong_contract(self):
  p=packet();p['metric_contract_sha256']='wrong';self.assertEqual(v3.ResearchStateEngine().evaluate(p)['status'],'UNVERIFIED')
 def test_research_mode_required(self):
  p=packet();p['research_only']=False;self.assertEqual(v3.ResearchStateEngine().evaluate(p)['status'],'UNVERIFIED')
 def test_integrity_required(self):
  p=packet();p['source_integrity_verified']=False;self.assertEqual(v3.ResearchStateEngine().evaluate(p)['status'],'UNVERIFIED')
 def test_no_intraday_flow(self):
  p=packet();p['phase']='INTRADAY';self.assertEqual(v3.ResearchStateEngine().evaluate(p)['status'],'UNVERIFIED')
 def test_nonfinite_rejected(self):
  for x in (None,float('nan'),float('inf')):
   p=packet();p['metrics_history']['foreign_relative_flow_5'][-1]=x;self.assertEqual(v3.ResearchStateEngine().evaluate(p)['status'],'UNVERIFIED')
 def test_short_history_rejected(self):
  p=packet();p['metrics_history']={m:[1.]*40 for m in det.METRICS};self.assertEqual(v3.ResearchStateEngine().evaluate(p)['status'],'UNVERIFIED')
 def test_no_input_mutation(self):
  p=packet();before=copy.deepcopy(p);v3.ResearchStateEngine().evaluate(p);self.assertEqual(p,before)
 def test_false_pit_preserved(self):
  r=v3.ResearchStateEngine().evaluate(packet());self.assertFalse(r['source_gates']['pit_pass']);self.assertEqual(r['formal_escape_state'],'UNVERIFIED')
 def test_no_trading_authority(self):
  for r in self.sequence(list(range(7))):self.assertEqual(r['trading_authority'],'NONE')
 def test_manual_level_ignored(self):
  a=packet();b=packet();b.update(raw_level=6,prior_level=6,detector_output={'events':{'x':True}})
  self.assertEqual(v3.ResearchStateEngine().evaluate(a),v3.ResearchStateEngine().evaluate(b))
 def test_actual_frozen_gate_fails(self):
  self.assertEqual(det.detect(packet())['status'],'UNVERIFIED');self.assertEqual(v2.evaluate(packet())['status'],'UNVERIFIED')
 def test_detector_past_only_baseline(self):
  self.assertEqual(det.empirical_adverse([1.]*60+[0.],60,'low'),1)
 def test_real_detector_evaluation(self):
  r=v3.ResearchStateEngine().evaluate(packet());self.assertEqual(r['status'],'RESEARCH_ONLY_COUNTERFACTUAL');self.assertIsInstance(r['raw_risk_level'],int)

if __name__=='__main__':unittest.main()
