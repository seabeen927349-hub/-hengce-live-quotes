"""Offline authority attacks against real preserved schema-5 evidence."""
import contextlib
import copy
from datetime import datetime, timedelta
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import hengce_q017_authority_guard_v5 as guard
import hengce_q017_formal_output as boundary
import hengce_q017_observation_lock_v5 as q
import hengce_q017_recovery_compute_v5 as recovery
import hengce_dual_engine_display as dual
import hengce_unified_scan_display as ui
import hengce_scan_once_router as router
from hengce_unified_contracts import ZERO_AUTHORITY, digest

NOW = datetime.fromisoformat('2026-10-22T10:00:00+08:00')


class Q017Cleanup(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); self.radar = self.root / 'hengce/q017_radar'
        self.observation = json.loads((ROOT/'hengce/q017_radar/observations/20261022_0901_observation.json').read_text())
        self.decision = json.loads((ROOT/'hengce/q017_radar/decision/20261022_0901.json').read_text())
        self.op = self.radar/'observations/20261022_0901_observation.json'
        self.dp = self.radar/'decision/20261022_0901.json'
        self.save(self.op, self.observation); self.save(self.dp, self.decision)

    def save(self, path, obj):
        path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps(obj))

    def test_missing_observation_or_decision_has_no_formal_output(self):
        for path in (self.op, self.dp):
            data = path.read_bytes(); path.unlink()
            with self.assertRaises((OSError, ValueError)): boundary.current_decision(NOW, self.root)
            path.write_bytes(data)

    def test_missing_primary_and_backup_fails_closed_without_fetch(self):
        with self.assertRaisesRegex(RuntimeError, 'NO_CANONICAL_OR_BACKUP'):
            recovery.promote_if_needed(NOW.date(), self.root/'absent', self.root/'also_absent')

    def test_late_quotes_and_incomplete_coverage_cannot_be_repaired(self):
        for minute in ('02', '03'):
            bad = copy.deepcopy(self.observation)
            bad['quotes'][next(iter(bad['quotes']))]['fetched_at_taipei'] = '2026-10-22T09:'+minute+':00+08:00'
            bad['observation_snapshot_sha256'] = q.csha({k:v for k,v in bad.items() if k != 'observation_snapshot_sha256'})
            self.save(self.op, bad)
            with self.assertRaisesRegex(ValueError, 'OBS_QUOTE_NOT_0901'): boundary.current_decision(NOW, self.root)

    def test_hash_tampering_rejected(self):
        for key in ('decision_snapshot_sha256', 'observation_snapshot_sha256'):
            bad = copy.deepcopy(self.decision); bad[key] = '0'*64; self.save(self.dp, bad)
            with self.assertRaises(ValueError): boundary.current_decision(NOW, self.root)
        bad = copy.deepcopy(self.decision); bad['universe_lock']['universe_sha256'] = '0'*64; self.save(self.dp, bad)
        with self.assertRaisesRegex(ValueError, 'UNIVERSE_HASH'): boundary.current_decision(NOW, self.root)

    def test_stale_or_forged_latest_cannot_override_dated_authority(self):
        for payload in ({'module':'NOVA','schema_version':5,'trade_date':'2026-10-22','top3':[{'ticker':'2603'}]},
                        {'module':'Q017_OLD','trade_date':'2026-10-21'}, {'authority':'NO_FORMAL_SIGNAL'}):
            self.save(self.radar/'latest.json',payload); self.save(self.radar/'decision_latest.json',payload)
            self.assertEqual(boundary.current_decision(NOW,self.root), self.decision)

    def test_research_models_cannot_be_formal_even_with_q017_label(self):
        for engine in ('NOVA','V43','W1','Q1','E2','M1','HENGCE_CANONICAL_Q017_CANDIDATES'):
            bad=copy.deepcopy(self.decision); bad['module']=engine; self.save(self.dp,bad)
            with self.assertRaisesRegex(ValueError,'MODULE_INVALID'): boundary.current_decision(NOW,self.root)

    def test_future_decision_not_available(self):
        with self.assertRaisesRegex(ValueError,'FUTURE_DECISION'): boundary.current_decision(NOW.replace(hour=9,minute=1,second=0),self.root)

    def test_malformed_evidence_fails_closed(self):
        for key in ('universe_lock','observation_lock','data_status'):
            bad=copy.deepcopy(self.observation);bad[key]=['not an object'];self.save(self.op,bad)
            with self.assertRaises(ValueError):boundary.current_decision(NOW,self.root)

    def test_monitor_cannot_change_scores_gate_or_members(self):
        monitor=copy.deepcopy(self.decision); monitor.update(module=guard.MONITOR_MODULE, generated_at_taipei=NOW.isoformat(), monitor={'rerank_performed':False,'ranking_frozen':True})
        with patch.object(guard,'RADAR',self.radar):
            self.assertTrue(guard.validate(monitor)[0])
            for mutation in ('score','state','universe'):
                bad=copy.deepcopy(monitor)
                if mutation=='score': bad['top3'][0]['score']+=.000000000000001
                elif mutation=='state': bad['market_state']='GO' if bad['market_state']!='GO' else 'CASH'
                else: bad['universe_lock']['members'].append('2603')
                self.assertEqual(guard.validate(bad),(False,'MONITOR_DECISION_FIELDS_CHANGED'))

    def bundle(self):
        # Synthetic transaction envelope around an ORIGINAL preserved Q017 row;
        # never stored as historical market evidence or a production decision.
        source=self.decision['top3'][0]
        row={'Ticker':source['ticker'],'SourceProvenance':'BOTH','LegacyScore':None,
             'Q017Score':source['score'],'Q017Rank':1,'LegacyEvidence':{},'Q017Evidence':{},
             'FormalCandidate':False,'FinalAction':'ABSTAIN'}
        base={'schema_version':2,'system':'HENGCE','module':'HENGCE_UNIFIED_CANDIDATE_ADAPTER',**ZERO_AUTHORITY,
              'transaction_id':'test','run_id':'test','rows':[row], 'candidate_union_policy':boundary.Q017_ONLY_POLICY,
              'q017_is_only_active_candidate_source':True,'q017_contract_status':'PASS',
              'q017_observation_snapshot_sha256':self.decision['observation_snapshot_sha256'],
              'q017_decision_snapshot_sha256':self.decision['decision_snapshot_sha256']}
        action={'schema_version':2,'system':'HENGCE','module':'HENGCE_UNIFIED_INTRADAY_ACTION_BOARD',**ZERO_AUTHORITY,
                'binding_status':'PASS','transaction_id':'test','BaseRunId':'test','trade_date':NOW.date().isoformat(),
                'generated_at':NOW.isoformat(),'LiveGeneratedAt':NOW.isoformat(),'rows':[copy.deepcopy(row)]}
        receipt={'schema_version':3,'system':'HENGCE',**ZERO_AUTHORITY,'binding_status':'PASS','transaction_id':'test',
                 'trade_date':NOW.date().isoformat(),'generated_at':NOW.isoformat()}
        self.seal(action,base,receipt);return action,base,receipt

    def seal(self,action,base,receipt):
        action['base_hash']=digest(base);receipt.update(base_hash=digest(base),action_hash=digest(action))

    def test_router_requires_full_hash_bound_current_q017_bundle(self):
        action,base,receipt=self.bundle()
        paths=[self.root/n for n in ('action.json','base.json','receipt.json')]
        with patch.multiple(router,ROOT=self.root,ACTION=paths[0],BASE=paths[1],RECEIPT=paths[2]):
            for path,obj in zip(paths,(action,base,receipt)):self.save(path,obj)
            self.assertEqual(router._current_q017_action(NOW),action)
            action['rows'][0]['LegacyScore']=99;self.save(paths[0],action)
            self.assertIsNone(router._current_q017_action(NOW))
            self.seal(action,base,receipt)
            for path,obj in zip(paths,(action,base,receipt)):self.save(path,obj)
            self.assertIsNone(router._current_q017_action(NOW+timedelta(minutes=9)))
            base['rows'][0]['SourceProvenance']='LEGACY';action['rows'][0]['SourceProvenance']='LEGACY'
            self.seal(action,base,receipt)
            for path,obj in zip(paths,(action,base,receipt)):self.save(path,obj)
            self.assertIsNone(router._current_q017_action(NOW))

    def test_daily_canonical_without_schema5_binding_is_quarantined(self):
        action,base,receipt=self.bundle();del base['q017_decision_snapshot_sha256']
        self.seal(action,base,receipt)
        shown=ui.build(NOW,action,base,receipt)
        with self.assertRaisesRegex(ValueError,'NOT_BOUND_TO_SCHEMA5'): boundary.require_q017_publication(shown,base,NOW,self.root)

    def test_public_display_cli_rejects_hash_valid_legacy_bundle(self):
        action,base,receipt=self.bundle();base['q017_is_only_active_candidate_source']=False
        self.seal(action,base,receipt)
        paths=[self.root/n for n in ('action.json','base.json','receipt.json')]
        for path,obj in zip(paths,(action,base,receipt)):self.save(path,obj)
        argv=['display','--no-write','--now',NOW.isoformat(),'--action',str(paths[0]),'--base',str(paths[1]),'--receipt',str(paths[2])]
        with patch.object(ui,'ROOT',self.root),patch.object(sys,'argv',argv),contextlib.redirect_stdout(io.StringIO()) as stream:
            self.assertEqual(ui.main(),2)
        result=json.loads(stream.getvalue());self.assertEqual(result['rows'],[])
        self.assertEqual(result['authority'],'NO_FORMAL_HENGCE_OUTPUT')

    def test_retired_display_labels_and_valid_decision(self):
        self.save(self.radar/'latest.json',{'module':'NOVA','top3':[{'ticker':'2603'}]})
        with patch.object(dual,'ROOT',self.root),patch.object(guard,'RADAR',self.radar):
            result=dual.build(NOW)
        self.assertEqual(result['q017']['top3'],self.decision['top3'])
        self.assertEqual(result['formal_hengce_stock_output_engine'],'Q017')
        research=dual.e2_view({'module':'E2_PROFIT_MAX_STATE','schema_version':2})
        self.assertFalse(research['formal_authority']);self.assertTrue(research['research_only'])


if __name__=='__main__': unittest.main(verbosity=2)
