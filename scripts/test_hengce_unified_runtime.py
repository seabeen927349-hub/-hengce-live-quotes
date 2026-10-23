#!/usr/bin/env python3
"""End-to-end offline runner/display/route contracts, including crash remnants."""
import contextlib
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from datetime import timedelta
from test_hengce_unified_boundaries import NOW, fixtures
from test_hengce_unified_q017 import canonical_q017
import hengce_unified_runner as runner
import hengce_unified_scan_display as display
import hengce_scan_once_router as router
import hengce_unified_candidate_adapter as adapter
from hengce_unified_contracts import digest

class Runtime(unittest.TestCase):
    def setUp(self):
        trust = patch.object(adapter, 'VERIFIED_Q017_PRODUCERS', frozenset({'0' * 40}))
        trust.start(); self.addCleanup(trust.stop)
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.env = patch.dict(os.environ, {'HENGCE_ROOT': str(self.root),
            'HENGCE_LIVE_JSON': str(self.root/'live.json')}, clear=True)
        self.env.start(); self.addCleanup(self.env.stop)
        self.legacy, self.live, self.ctx = fixtures()
        self.ctx.update(trade_date='2026-10-23', generated_at=NOW.isoformat())
        self.formal = self.root/'work_output/formal/production/v2_scan.json'
        self.context = self.root/'work_output/context/HENGCE_MARKET_CONTEXT.json'
        self.save(self.formal, self.legacy); self.save(self.context,self.ctx)
        self.save(self.root/'live.json',self.live)
        self.out = self.root/'work_output/intraday_action_board'
    def save(self,path,obj):
        path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(obj))
    def run_pipeline(self):
        with contextlib.redirect_stderr(io.StringIO()): return runner.run(NOW)
    def bundle(self):
        return {k: display.load(self.out/v) for k,v in runner.NAMES.items()}
    def render(self, now=NOW):
        x=self.bundle();return display.build(now,x['action'],x['base'],x['receipt'])
    def test_valid_bundle(self):
        self.assertEqual(self.run_pipeline(),0)
        x=self.render();self.assertEqual(x['binding_status'],'PASS')
        self.assertEqual(x['rows'][0]['FinalAction'],'REVIEW_ENTRY')
        self.assertEqual(x['capital_authority_twd'],0);self.assertIs(x['broker_order_execution'],False)
    def test_failure_revokes_old_pass(self):
        self.assertEqual(self.run_pipeline(),0)
        self.context.unlink();self.assertEqual(self.run_pipeline(),2)
        self.assertEqual(self.render()['binding_status'],'FAIL_CLOSED')
        self.assertEqual(self.bundle()['action']['rows'],[])
    def test_missing_legacy(self):
        self.formal.unlink();self.assertEqual(self.run_pipeline(),2)
    def test_stale_formal_and_context(self):
        for path,source in [(self.formal,self.legacy),(self.context,self.ctx)]:
            bad=copy.deepcopy(source);bad['trade_date']='2026-10-22';self.save(path,bad)
            self.assertEqual(self.run_pipeline(),2);self.save(path,source)
    def test_missing_session(self):
        del self.legacy['trade_date'];self.save(self.formal,self.legacy)
        self.assertEqual(self.run_pipeline(),2)
    def test_explicit_missing_override_does_not_fallback(self):
        os.environ['HENGCE_FORMAL_BASE_JSON']=str(self.root/'absent')
        self.assertEqual(self.run_pipeline(),2)
    def test_ambiguous_artifact_selection(self):
        self.save(self.formal.with_name('v3_scan.json'),self.legacy)
        self.assertEqual(self.run_pipeline(),2)
    def test_live_age_cannot_be_weakened(self):
        os.environ['HENGCE_LIVE_MAX_AGE_SECONDS']='999999'
        self.assertEqual(self.run_pipeline(),2)
    def test_unsupported_runtime_override(self):
        os.environ['HENGCE_INTRADAY_BRIDGE']='scripts/hengce_intraday_action_board.py'
        self.assertEqual(self.run_pipeline(),2)
    def test_partial_publication_and_tampering(self):
        self.assertEqual(self.run_pipeline(),0);x=self.bundle()
        for key in ('action','base','receipt'):
            broken=dict(x);broken[key]=None
            self.assertEqual(display.build(NOW,broken['action'],broken['base'],broken['receipt'])['binding_status'],'FAIL_CLOSED')
        x['action']['rows'][0]['LegacyScore']=999
        self.assertEqual(display.build(NOW,x['action'],x['base'],x['receipt'])['binding_status'],'FAIL_CLOSED')
    def test_stale_display_cannot_refresh_source_age(self):
        self.assertEqual(self.run_pipeline(),0)
        self.assertEqual(self.render(NOW+timedelta(minutes=9))['binding_status'],'FAIL_CLOSED')
        x=self.bundle();x['action']['generated_at']=(NOW+timedelta(minutes=9)).isoformat()
        x['receipt'].update(generated_at=x['action']['generated_at'],action_hash=digest(x['action']))
        self.assertEqual(display.build(NOW+timedelta(minutes=9),x['action'],x['base'],x['receipt'])['binding_status'],'FAIL_CLOSED')
    def test_q017_only_and_both(self):
        for symbol, provenance in [('3008','Q017'),('2330.TW','BOTH')]:
            q=canonical_q017(symbol);self.save(self.root/'hengce/q017_canonical/latest.json',q)
            self.assertEqual(self.run_pipeline(),0)
            x=self.render();self.assertEqual(x['binding_status'],'PASS')
            row=next(r for r in x['rows'] if r['SourceProvenance']==provenance)
            self.assertNotIn('UnifiedScore',row)
            if provenance=='Q017':
                self.assertEqual(row['FinalAction'],'ABSTAIN');self.assertEqual(row['GeometryStatus'],'UNAVAILABLE')
            else:
                self.assertEqual(row['FinalAction'],'REVIEW_ENTRY');self.assertEqual(row['LegacyScore'],.9)
    def test_unverified_producer_cannot_self_certify_canonical_authority(self):
        self.save(self.root/'hengce/q017_canonical/latest.json', canonical_q017())
        with patch.object(adapter, 'VERIFIED_Q017_PRODUCERS', frozenset()):
            self.assertEqual(self.run_pipeline(), 0)
        self.assertEqual(self.render()['q017_contract_status'], 'FAIL_CLOSED_CONTRACT_MISMATCH')
        self.assertEqual(len(self.render()['rows']), 1)
    def test_bad_q017_isolated_without_legacy_promotion(self):
        path=self.root/'hengce/q017_canonical/latest.json';path.parent.mkdir(parents=True)
        for raw in ['{', '{"schema_version":999}', '{"module":"Q017_V5","top_n":3}']:
            path.write_text(raw);self.assertEqual(self.run_pipeline(),0)
            x=self.render();self.assertEqual(x['q017_contract_status'],'FAIL_CLOSED_CONTRACT_MISMATCH')
            self.assertTrue(all(r['SourceProvenance']=='LEGACY' for r in x['rows']))
    def test_atomic_unique_writes(self):
        from hengce_unified_contracts import atomic
        atomic(self.root/'x.json', {'ok':1});atomic(self.root/'x.json',{'ok':2})
        self.assertEqual(json.loads((self.root/'x.json').read_text()),{'ok':2})
        self.assertEqual(list(self.root.glob('.x.json.*')),[])
    def test_scan_refresh_never_runs_legacy_producer(self):
        with patch.object(router,'run_step',side_effect=AssertionError('producer invoked')):
            for hour in (7,8,9,10,13,15,18): self.assertEqual(router.refresh(NOW.replace(hour=hour)),[])
    def test_scan_failed_attempt_cannot_show_old_pass(self):
        fake=type('Result',(),{'stdout':json.dumps({'system':'HENGCE','binding_status':'PASS','rows':[{'FinalAction':'REVIEW_ENTRY'}]}),'returncode':0})()
        with patch.object(sys,'argv',['router','--now',NOW.isoformat()]), patch.object(router,'run_step',return_value={'ok':False}),patch.object(router.subprocess,'run',return_value=fake),contextlib.redirect_stdout(io.StringIO()) as stream:
            rc=router.main()
        obj=json.loads(stream.getvalue());self.assertEqual(rc,2);self.assertEqual(obj['rows'],[])
        self.assertTrue(obj['scan_once_router']['single_hengce_output'])
    def test_source_change_during_computation_stops(self):
        import hengce_unified_action_board as board
        original = board.build
        def changed(*args, **kwargs):
            result = original(*args, **kwargs)
            modified = copy.deepcopy(self.legacy);modified['run_id'] = 'NEWER'
            self.save(self.formal, modified)
            return result
        with patch.object(board, 'build', side_effect=changed):
            self.assertEqual(self.run_pipeline(), 2)
        self.assertEqual(self.render()['binding_status'], 'FAIL_CLOSED')
    def test_publication_lock_does_not_clobber_other_writer(self):
        import fcntl
        self.assertEqual(self.run_pipeline(), 0)
        before = (self.out/runner.NAMES['receipt']).read_bytes()
        with (self.out/'.publication.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.assertEqual(self.run_pipeline(), 2)
        self.assertEqual((self.out/runner.NAMES['receipt']).read_bytes(), before)
    def test_duplicate_exact_is_idempotent_and_order_deterministic(self):
        self.legacy['rows'].append(copy.deepcopy(self.legacy['rows'][0]))
        self.assertEqual(adapter.build(self.legacy)['candidate_count'],1)
        second=dict(self.legacy['rows'][0],Ticker='2454');self.legacy['rows'].append(second)
        one=adapter.build(self.legacy)['rows'];self.legacy['rows'].reverse()
        self.assertEqual(adapter.build(self.legacy)['rows'],one)
    def test_q017_invalid_rank_numeric_and_evidence(self):
        for field,value in [('rank',1.5),('rank',True),('score',float('nan')),('score',999),('qualified','true')]:
            q=canonical_q017();q['candidates'][0][field]=value
            result=adapter.build(self.legacy,q)
            self.assertNotEqual(result['q017_contract_status'],'PASS');self.assertEqual(result['candidate_count'],1)
        q=canonical_q017();q['candidates'].append(copy.deepcopy(q['candidates'][0]))
        self.assertNotEqual(adapter.build(self.legacy,q)['q017_contract_status'],'PASS')

if __name__=='__main__':unittest.main(argv=[__file__])
