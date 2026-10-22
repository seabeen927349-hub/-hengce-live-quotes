"""Issue #20: 20 offline fault scenarios; no live APIs or production outcomes."""
import ast
import copy
import csv
from datetime import datetime
import hashlib
import io
import json
from pathlib import Path
import socket
import subprocess
import sys
import unittest
from unittest.mock import patch

import test_writer_races as races
sys.path.insert(0,str(races.ROOT/'scripts'))
import hengce_recovery_transaction as r
import hengce_publish as pub

DAY='2026-10-22'; COMPACT='20261022'; NOW=datetime.fromisoformat(DAY+'T09:50:00+08:00')
Q='hengce/q017_radar/'; E='hengce/e2_live/'; DISPLAY='hengce/dual_engine/latest.json'


def raw(o):return json.dumps(o,ensure_ascii=False,indent=2)+'\n'
def hashed(o,key):
    o=copy.deepcopy(o);o[key]=r.digest({k:v for k,v in o.items() if k!=key});return o


def qfiles(backup=False):
    o=hashed(dict(schema_version=5,module='Q017_0901_OBSERVATION_LOCK',trade_date=DAY,
        generated_at_taipei=DAY+'T09:01:10+08:00',binding_status='PASS',
        observation_lock=dict(cutoff_label='09:01',immutable=True,window_valid=True,
            capture_started_at_taipei=DAY+'T09:01:01+08:00',capture_finished_at_taipei=DAY+'T09:01:10+08:00'),
        universe_lock=dict(scope='TWSE_LISTED_ELECTRONICS_ONLY',source='TWSE_MI_INDEX_TYPE_13_ELECTRONICS_HISTORY',
            membership_date='2026-10-21',members=['1111'],member_count=1,universe_sha256=r.digest(['1111'])),
        quotes={'1111':dict(ticker='1111',open=90,reference_close=100,fetched_at_taipei=DAY+'T09:01:05+08:00')},
        eligible_models=[dict(ticker='1111',beta=1,previous_close=100)],
        data_status=dict(eligible_beta_count=1,provider_returned_count=1,provider_coverage=1,provider_coverage_required=1,
            eligible_quote_row_count=1,eligible_quote_row_coverage=1,opened_by_decision_count=1,opened_coverage=1,
            quote_present_but_no_open_count=0,coverage_semantics='QUOTE_ROW_COVERAGE_IS_DATA_COMPLETENESS;OPENED_COVERAGE_IS_CAUSAL_MARKET_STATE',
            critical_set_complete=True,critical_missing=[]),market_inputs=dict(sox=dict(sox_1d=0,sox_5d=0),dxy=dict(dxy_5d=0))), 'observation_snapshot_sha256')
    folder='backup_observations' if backup else 'observations'
    alias='backup_observation_latest.json' if backup else 'observation_latest.json'
    history='backup_observation_history' if backup else 'history'
    files={Q+folder+'/'+COMPACT+'_0901_observation.json':raw(o),Q+alias:raw(o),Q+history+'/synthetic_OBSERVATION.json':raw(o)}
    if backup:
        files[Q+'backup_observation_status.json']=raw(dict(observation_snapshot_sha256=o['observation_snapshot_sha256'],status='BACKUP_OBSERVATION_READY'))
        return files
    d=hashed(dict(schema_version=5,module='Q017_SOX_ELECTRONICS_DECISION_LOCK',trade_date=DAY,
        generated_at_taipei=DAY+'T09:02:00+08:00',binding_status='PASS',market_state='CASH',top3=[],
        observation_snapshot_sha256=o['observation_snapshot_sha256'],universe_lock=o['universe_lock'],
        decision_lock=dict(immutable=True,window_valid=True,authority_semantics='OBSERVATION_TIME_LOCK')),'decision_snapshot_sha256')
    files.update({Q+'decision/'+COMPACT+'_0901.json':raw(d),Q+'decision_latest.json':raw(d),Q+'latest.json':raw(d),
        Q+'history/synthetic_DECISION.json':raw(d),Q+'signal_ledger.jsonl':json.dumps(dict(date=DAY,event='Q017_DECISION_FROM_0901_OBSERVATION_V5',
            decision_snapshot_sha256=d['decision_snapshot_sha256'],observation_snapshot_sha256=o['observation_snapshot_sha256']))+'\n'})
    return files


def efiles(generated=DAY+'T09:50:00+08:00'):
    state=dict(schema_version=2,module='E2_PROFIT_MAX_STATE',binding_status='PASS',engine_status='OFF',
        signal_asof='2026-10-21',generated_at_taipei='2026-10-21T17:00:00+08:00',paper_position={'state':'IDLE'},
        capital_authority_twd=0,broker_order_execution=False)
    morning=dict(module='E2_PROFIT_MAX_MORNING_BRIDGE',trade_date=DAY,generated_at_taipei=generated,
        source_signal_asof=state['signal_asof'],binding_status='PASS',paper_position=state['paper_position'],
        capital_authority_twd=0,broker_order_execution=False)
    display=dict(architecture='DUAL_ENGINE',rankings_separate=True,mixed_ranking_forbidden=True,
        legacy_v3_display_authority=False,generated_at_taipei=generated,
        q017={'status':'DATA_PENDING','formal_buy_count':0},e2=dict(state,status=state['engine_status']))
    return {E+'state_latest.json':raw(state),E+'morning_latest.json':raw(morning),DISPLAY:raw(display)}


def eodfiles():
    folder='eod/'+COMPACT+'/';files={};status=dict(target_date=DAY,mother_status='PENDING',downstream_ready=False)
    for leg in ('price','institutional','margin'):
        rows=[]
        for i in range(r.EOD_MIN[leg]):
            row={k:'0' for k in r.EOD_COLUMNS[leg]};row.update(Date=DAY,Ticker=str(1000+i));rows.append(row)
        stream=io.StringIO();w=csv.DictWriter(stream,fieldnames=r.EOD_COLUMNS[leg]);w.writeheader();w.writerows(rows)
        name=leg+'_1.csv';content=stream.getvalue();files[folder+name]=content
        h=hashlib.sha256(name.encode()+b'\0'+content.encode()+b'\0').hexdigest()
        files[folder+'receipts/'+leg+'.json']=raw(dict(artifact='EOD_ORIGINAL_VESSEL_LEG_RECEIPT',target_date=DAY,
            leg=leg,status='COMPLETE',files=[name],rows=len(rows),sha256=h))
        status.update({leg+'_status':'COMPLETE',leg+'_date':DAY,leg+'_rows':len(rows),leg+'_sha256':h})
    status.update(three_leg_complete=True,formal_complete_day=True)
    files[folder+'status.json']=raw(status);return files


class RecoveryFaultTests(unittest.TestCase):
    def setUp(self):
        f=races.WriterRaceTests();f.setUp();self.addCleanup(f.doCleanups);self.f=f
        self.network=patch.object(socket.socket,'connect',side_effect=AssertionError('OFFLINE_TEST'));self.network.start();self.addCleanup(self.network.stop)
        # Seed an unchanged, valid prior-close E2 state; all data is synthetic.
        f.commit(f.a,{E+'state_latest.json':efiles()[E+'state_latest.json']});races.git(f.a,'push','origin','HEAD:main')
        races.git(f.b,'fetch','origin','main');races.git(f.b,'reset','--hard','origin/main')

    def begin(self,root=None,lane='e2-morning',mode='morning'):
        root=root or self.f.a
        return r.prepare(root,lane,mode,DAY,NOW,self.f.root/'evidence')

    def propose(self,root=None,files=None,lane='e2-morning',mode='morning'):
        root=root or self.f.a;self.begin(root,lane,mode)
        for p,text in (files or efiles()).items():
            target=root/p;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(text)
        races.git(root,'add','-A');r.stage(root,now=NOW)
        races.git(root,'commit','-m','synthetic closure-valid transaction')
        return root

    def publish(self,root=None,profile='conservative-all'):
        root=root or self.f.a
        return pub.publish(root,self.f.root/('publish-'+root.name),profile,transaction_lane='e2-morning',now=NOW)

    def check(self,files,lane='q017-recovery',mode='compute',before=None):
        return r.validate_closure(files,lane,mode,DAY,set(files),before or {},NOW)

    def test_01_kill_between_each_canonical_alias_history_ledger_write(self):
        files=qfiles();self.check(files)
        for path in (Q+'observation_latest.json',Q+'decision_latest.json',Q+'latest.json',Q+'history/synthetic_DECISION.json',Q+'signal_ledger.jsonl'):
            with self.subTest(kill_before=path):
                bad=dict(files);bad.pop(path)
                with self.assertRaises(r.Blocked):self.check(bad)

    def test_02_truncated_write_once_canonical(self):
        files=qfiles();files[Q+'decision/'+COMPACT+'_0901.json']='{"truncated":'
        with self.assertRaises(r.Blocked):self.check(files)

    def test_03_compute_complete_without_commit_is_not_publication(self):
        self.begin();(self.f.a/'uncommitted').write_text('computed bytes')
        with self.assertRaises(r.Blocked):r.committed(self.f.a,'e2-morning',NOW)
        self.assertNotEqual(r.load(self.f.a)['state'],'REMOTE_ACCEPTED')

    def test_04_commit_without_push_has_no_remote_acceptance_and_fences_compute(self):
        self.propose();r.committed(self.f.a,'e2-morning',NOW)
        with self.assertRaises(r.Blocked):r.fence(self.f.a,now=NOW)
        self.assertEqual(self.f.read_remote(races.LATEST),'{"synthetic_version":0}')

    def test_05_accepted_push_ack_lost_is_reconciled_as_noop(self):
        self.propose();original=pub.subprocess.run;lost=[False]
        def run(args,*a,**kw):
            result=original(args,*a,**kw)
            if 'push' in args and not lost[0]:
                lost[0]=True;return subprocess.CompletedProcess(args,1,b'',b'ack lost')
            return result
        with patch.object(pub.subprocess,'run',side_effect=run):self.assertEqual(self.publish(),0)
        record=r.load(self.f.a);self.assertEqual(record['state'],'LOCAL_ADOPTED')
        self.assertTrue(record['accepted_remote_sha']);self.assertEqual(record['local_adoption'],'SUCCESS')

    def test_06_remote_accepted_local_adoption_failed_fences_later_computation(self):
        self.propose();health='hengce/health/latest.json'
        self.f.commit(self.f.b,{health:'zero-authority independent update'});races.git(self.f.b,'push','origin','HEAD:main')
        p=self.f.a/health;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('local untracked collision')
        self.assertEqual(self.publish(),2);record=r.load(self.f.a)
        self.assertTrue(record['accepted_remote_sha']);self.assertIn('E2_PROFIT_MAX_MORNING_BRIDGE',self.f.read_remote(races.LATEST))
        with self.assertRaises(r.Blocked):r.fence(self.f.a,now=NOW)
        with self.assertRaises(r.Blocked):self.begin()

    def test_07_kill_between_index_and_head_adoption_remains_fenced(self):
        self.propose();self.f.commit(self.f.b,{'hengce/health/latest.json':'independent'});races.git(self.f.b,'push','origin','HEAD:main')
        original=pub.git
        def killed(repo,*args,**kw):
            if args[:2]==('update-ref','HEAD'):raise pub.Stop('SYNTHETIC_KILL_BEFORE_HEAD_ADOPTION')
            return original(repo,*args,**kw)
        with patch.object(pub,'git',side_effect=killed):self.assertEqual(self.publish(),2)
        with self.assertRaises(r.Blocked):r.fence(self.f.a,now=NOW)
        clean=self.f.clone('clean-recovery');self.begin(clean)
        self.assertEqual(r.load(clean)['state'],'INPUTS_VALIDATED')

    def test_08_current_latest_missing_canonical_and_inverse(self):
        for path in (Q+'decision/'+COMPACT+'_0901.json',Q+'decision_latest.json'):
            files=qfiles();files.pop(path)
            with self.assertRaises(r.Blocked):self.check(files)

    def test_09_existing_decision_missing_history_or_ledger_is_blocked_no_repair(self):
        for path in (Q+'history/synthetic_DECISION.json',Q+'signal_ledger.jsonl'):
            files=qfiles();files.pop(path);before=copy.deepcopy(files)
            with self.assertRaises(r.Blocked):self.check(files)
            self.assertEqual(files,before)

    def test_10_identical_retry_noop_incompatible_retry_stop(self):
        self.propose(self.f.a);self.propose(self.f.b)
        self.assertEqual(self.publish(self.f.a),0);accepted=races.git(self.f.remote,'rev-parse','main')
        self.assertEqual(self.publish(self.f.b),0);self.assertEqual(races.git(self.f.remote,'rev-parse','main'),accepted)
        other=self.f.clone('incompatible');self.begin(other)
        files=efiles();x=json.loads(files[E+'morning_latest.json']);x['paper_position']={'state':'HOLDING'}
        files[E+'morning_latest.json']=raw(x)
        with self.assertRaises(r.Blocked):self.check(files,'e2-morning','morning')

    def test_11_independent_primary_backup_and_duplicate_recovery(self):
        self.f.test_independent_simultaneous_q017_capture_publication()
        self.assertNotEqual('hengce-q017-primary-observer','hengce-q017-backup-observer')
        files=qfiles();self.check(files);self.check(files)
        import hengce_q017_observation_lock_v5 as v5
        root=self.f.root/'locked-winner'
        for p,value in files.items():
            f=root/p;f.parent.mkdir(parents=True,exist_ok=True);f.write_text(value)
        with patch.object(v5,'OBS_DIR',root/Q/'observations'),patch.object(v5,'DECISION_DIR',root/Q/'decision'),\
             patch.object(v5.core,'now_tw',return_value=NOW),\
             patch.object(v5,'build_decision_from_observation',side_effect=AssertionError('ACCEPTED_DECISION_MUST_NOT_RECOMPUTE')):
            winner=v5.compute_decision(NOW.date())
            self.assertEqual(winner,json.loads(files[Q+'decision/'+COMPACT+'_0901.json']))

    def test_12_health_only_advancement_during_recovery_is_safe(self):
        self.propose();self.f.commit(self.f.b,{'hengce/health/latest.json':'independent diagnostics'});races.git(self.f.b,'push','origin','HEAD:main')
        self.assertEqual(self.publish(),0);self.assertEqual(self.f.read_remote('hengce/health/latest.json'),'independent diagnostics')

    def test_13_macro_history_universe_code_override_input_drift_stops_stale_output(self):
        paths=[races.MACRO,'hengce/q017_radar/data/twse_electronics_history_2026.csv','hengce/live_universe.json',
               'scripts/producer.py',E+'execution_override.json',E+'state_latest.json']
        for i,path in enumerate(paths):
            with self.subTest(input=path):
                a=self.f.clone('drift-a-'+str(i));b=self.f.clone('drift-b-'+str(i));self.propose(a)
                self.f.commit(b,{path:'changed authoritative input'});races.git(b,'push','origin','HEAD:main')
                self.assertEqual(self.publish(a),2)
                # Reset disposable remote only to separate fault scenarios.
                races.git(self.f.remote,'update-ref','refs/heads/main',races.git(self.f.a,'rev-parse','HEAD'))

    def test_14_closed_window_cannot_refetch_rebuild_or_blend(self):
        with self.assertRaises(r.Blocked):r.validate_inputs({},'q017-primary','observe',DAY,NOW)
        with self.assertRaises(r.Blocked):r.validate_inputs({},'q017-recovery','compute',DAY,NOW)
        files=qfiles();files.update(qfiles(True));self.check(files)
        bad=dict(files);bad[Q+'observations/'+COMPACT+'_0901_observation.json']='broken primary'
        with self.assertRaises(r.Blocked):self.check(bad)

    def test_15_e2_state_morning_history_display_partial_is_not_complete(self):
        files=efiles();self.check(files,'e2-morning','morning')
        for path in (E+'state_latest.json',E+'morning_latest.json',DISPLAY):
            bad=dict(files);bad.pop(path)
            with self.assertRaises(r.Blocked):self.check(bad,'e2-morning','morning')
        with self.assertRaises(r.Blocked):r.validate_inputs({},'e2-morning','morning',DAY,NOW)
        self.begin()
        target=self.f.a/(E+'morning_latest.json');target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(files[E+'morning_latest.json']);races.git(self.f.a,'add','-A')
        with self.assertRaises(r.Blocked):r.stage(self.f.a,now=NOW)
        self.assertEqual(r.load(self.f.a)['state'],'BLOCKED')

    def test_16_eod_partial_shards_missing_receipt_mother_mismatch(self):
        files=eodfiles();self.check(files,'eod','postclose')
        for path in ('price_1.csv','receipts/price.json'):
            bad=dict(files);bad.pop('eod/'+COMPACT+'/'+path)
            with self.assertRaises(r.Blocked):self.check(bad,'eod','postclose')
        bad=dict(files);p='eod/'+COMPACT+'/status.json';s=json.loads(bad[p]);s.update(mother_status='COMPLETE',downstream_ready=True);bad[p]=raw(s)
        with self.assertRaises(r.Blocked):self.check(bad,'eod','postclose')
        # A valid price + mother may be downstream-ready while margin is pending.
        ready=dict(files);status=json.loads(ready[p]);folder='eod/'+COMPACT+'/'
        ready.pop(folder+'margin_1.csv');ready.pop(folder+'receipts/margin.json')
        status.update(margin_status='PENDING',three_leg_complete=False,formal_complete_day=False,
                      mother_status='COMPLETE',downstream_ready=True,mother_sha256='a'*64,
                      mother_latest_date=DAY,mother_receipt='receipts/mother.json')
        receipt=dict(target_date=DAY,mother_latest_date=DAY,status='PASS',second_mother=False,mother_sha256='a'*64,
                     promoted_leg_sha256={k:status[k+'_sha256'] for k in ('price','institutional')})
        ready[p]=raw(status);ready[folder+'receipts/mother.json']=raw(receipt)
        self.check(ready,'eod','postclose')
        status['mother_sha256']='b'*64;ready[p]=raw(status)
        with self.assertRaises(r.Blocked):self.check(ready,'eod','postclose')

    def test_17_repeated_session_torn_history_timestamp_collision(self):
        ledger=hashed(dict(cohorts={'x':dict(signal_date=DAY,ticker='1111',sessions=[{'date':DAY},{'date':DAY}])}),'ledger_sha256')
        files={'hengce/q017_review_10d/ledger_latest.json':raw(ledger)}
        with self.assertRaises(r.Blocked):self.check(files,'review','postclose')
        path='hengce/q017_radar/data/twse_electronics_history_2026.csv'
        with self.assertRaises(r.Blocked):self.check({path:'date,ticker,open,close\n'+DAY+',1111,10\n'},'daily','postclose')
        self.f.test_existing_immutable_file_cannot_be_changed_even_on_fresh_base()

    def test_18_manual_current_day_selftest_vs_historical_date(self):
        self.assertEqual(r.current_request('e2-morning','self-test','',NOW),DAY)
        self.assertEqual(r.current_request('e2-morning','morning',DAY,NOW),DAY)
        for date in ('2026-10-21','2026-10-23'):
            with self.assertRaises(r.Blocked):r.current_request('q017-recovery','compute',date,NOW)
        import hengce_q017_recovery_compute_v5 as recovery
        marker=self.f.root/'synthetic-existing-observation.json';marker.write_text('UNCHANGED_PRODUCTION_SENTINEL')
        with patch.object(recovery.v5,'OBS_LATEST',marker):
            recovery.self_test()
        self.assertEqual(marker.read_text(),'UNCHANGED_PRODUCTION_SENTINEL')

    def test_19_late_e2_stays_late_after_display_and_health_regeneration(self):
        from test_system_health import fixtures,run_manifest,h
        now=datetime.fromisoformat(DAY+'T10:00:00+08:00');files=efiles(DAY+'T09:50:00+08:00')
        self.check(files,'e2-morning','morning');policy=json.loads(h.POLICY.read_text());artifacts=fixtures(now)
        for p,text in files.items():artifacts[p]=json.loads(text)
        out=h.evaluate(now,artifacts,run_manifest(now,policy),policy,'a'*40)
        self.assertIn('LATE_RECOVERY',out['artifact_freshness']['lanes']['e2_morning']['reason_codes'])
        self.assertTrue(h.zero_valid(out))

    def test_20_unknown_contract_state_fails_closed_and_evidence_zero_authority(self):
        self.begin();record=r.load(self.f.a)
        for key,value in r.ZERO.items():self.assertEqual(record[key],value)
        for mutate in ({'state':'UNKNOWN_NEW_STATE'},{'unexpected_contract_field':True},{'capital_authority_twd':1}):
            bad=dict(record);bad.update(mutate)
            with self.assertRaises(r.Blocked):r.validate_record(bad)
        with self.assertRaises(r.Blocked):r.current_request('unknown-lane','compute',DAY,NOW)
        self.propose();self.assertEqual(self.publish(),0)
        events=[json.loads(p.read_text()) for p in (self.f.root/'evidence/transactions').glob('*.json')]
        self.assertEqual({e['state'] for e in events},r.STATES-{'BLOCKED'})
        for event in events:
            for key,value in r.ZERO.items():self.assertIs(type(event[key]),type(value));self.assertEqual(event[key],value)


if __name__=='__main__':unittest.main(verbosity=2)
