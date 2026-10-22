"""Fully synthetic/offline health cases; no market outcomes or live API calls."""
import copy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
import hengce_system_health as h
import hengce_health_collect_runs as collector
import hengce_publish as publisher


def clock(value='2026-10-22T17:25:00+08:00'):
    return h.stamp(value)


def observation(day='2026-10-22'):
    obj=dict(schema_version=5,module='Q017_0901_OBSERVATION_LOCK',binding_status='PASS',
        authority='CAUSAL_MARKET_OBSERVATION_ONLY',trade_date=day,generated_at_taipei=day+'T09:01:12+08:00',
        observation_lock=dict(cutoff_label='09:01',immutable=True,window_valid=True,
            capture_started_at_taipei=day+'T09:01:05+08:00',capture_finished_at_taipei=day+'T09:01:12+08:00'),
        universe_lock=dict(scope='TWSE_LISTED_ELECTRONICS_ONLY',source='TWSE_MI_INDEX_TYPE_13_ELECTRONICS_HISTORY',
            members=['1111'],member_count=1,universe_sha256=h.digest(['1111']),membership_date='2026-10-21'),
        eligible_models=[dict(ticker='1111',beta=1.0,previous_close=100.0)],
        quotes={'1111':dict(ticker='1111',fetched_at_taipei=day+'T09:01:06+08:00')},
        data_status=dict(eligible_beta_count=1,provider_returned_count=1,eligible_quote_row_count=1,
            provider_coverage=1.0,provider_coverage_required=1.0,eligible_quote_row_coverage=1.0,
            opened_by_decision_count=1,opened_coverage=1.0,quote_present_but_no_open_count=0,
            critical_set_complete=True,critical_missing=[]),
        market_inputs=dict(sox=dict(sox_1d=0.0,sox_5d=0.0),dxy=dict(dxy_5d=0.0)))
    obj['observation_snapshot_sha256']=h.digest(obj)
    return obj


def eod(day):
    return dict(target_date=day,updated_at_taipei=day+'T17:00:00+08:00',
        price_status='COMPLETE',institutional_status='COMPLETE',margin_status='COMPLETE',
        mother_status='COMPLETE',downstream_ready=True,three_leg_complete=True,formal_complete_day=True)


def fixtures(now):
    day=now.date().isoformat(); compact=now.strftime('%Y%m%d')
    obs=observation(day)
    artifacts={h.PATHS['q017']:obs, f'hengce/q017_radar/observations/{compact}_0901_observation.json':copy.deepcopy(obs),
        h.PATHS['e2_morning']:dict(module='E2_PROFIT_MAX_MORNING_BRIDGE',trade_date=day,
            generated_at_taipei=day+'T08:55:00+08:00',source_signal_asof='2026-10-21',binding_status='PASS',capital_authority_twd=0,broker_order_execution=False),
        h.EXTRA_PATHS[0]:dict(trade_date=day,schema_version=5,binding_status='PASS',generated_at_taipei=day+'T09:03:00+08:00'),
        h.EXTRA_PATHS[1]:dict(signal_asof='2026-10-21',generated_at_taipei='2026-10-21T17:00:00+08:00',binding_status='PASS',capital_authority_twd=0,broker_order_execution=False),
        h.PATHS['display']:dict(architecture='DUAL_ENGINE',rankings_separate=True,mixed_ranking_forbidden=True,
            legacy_v3_display_authority=False,generated_at_taipei=now.isoformat(),
            q017=dict(trade_date=day,status='CASH',formal_buy_count=0),
            e2=dict(signal_asof='2026-10-21',capital_authority_twd=0,broker_order_execution=False)),
        f'eod/{compact}/status.json':eod(day),'eod/20261021/status.json':eod('2026-10-21')}
    return artifacts


def run_manifest(now,policy):
    manifest=dict(schema_version=1,collected_at_utc=now.astimezone(timezone.utc).isoformat(),
        coverage_start_utc=(now-timedelta(hours=48)).isoformat(),coverage_end_utc=now.isoformat(),
        complete=True,errors=[],runs=[],**h.ZERO)
    for w in policy['workflows']:
        for due in h.occurrences(now,tuple(w['crons_utc'])):
            if due+timedelta(minutes=1)>now:continue
            manifest['runs'].append(dict(id=len(manifest['runs'])+1,workflow_file=w['file'],event='schedule',head_branch='main',
                created_at=due.isoformat(),run_started_at=(due+timedelta(minutes=1)).isoformat(),status='completed',conclusion='success'))
    return manifest


class HealthTests(unittest.TestCase):
    def setUp(self):
        self.p=json.loads(h.POLICY.read_text()); self.now=clock()
        self.a=fixtures(self.now); self.m=run_manifest(self.now,self.p)
        self.network_guard=patch.object(socket.socket,'connect',side_effect=AssertionError('TEST_NETWORK_FORBIDDEN'))
        self.network_guard.start(); self.addCleanup(self.network_guard.stop)

    def evaluate(self):
        before=copy.deepcopy((self.a,self.m,self.p))
        out=h.evaluate(self.now,self.a,self.m,self.p,'a'*40)
        self.assertEqual((self.a,self.m,self.p),before,'evaluator mutated inputs')
        self.assertTrue(h.zero_valid(out))
        return out

    def test_on_time_scheduled_runs_and_valid_capture_pass(self):
        x=self.evaluate()
        self.assertEqual(x['scheduler_liveness']['state'],'PASS')
        self.assertEqual(x['artifact_freshness']['lanes']['q017']['state'],'PASS')
        self.assertEqual(x['artifact_freshness']['lanes']['e2_morning']['reason_codes'],['ON_TIME'])
        self.assertEqual(x['state'],'PASS')

    def test_never_started_workflow_is_detected_without_heartbeat(self):
        self.m['runs']=[r for r in self.m['runs'] if r['workflow_file']!='hengce-q017-primary-observer.yml']
        x=self.evaluate()['scheduler_liveness']['workflows']['q017_primary']
        self.assertEqual(x['state'],'FAIL_CLOSED')
        self.assertIn('MISSING_SCHEDULED_RUN',x['slots'][0]['reason_codes'])

    def test_manual_run_cannot_mask_missing_schedule(self):
        for r in self.m['runs']:
            if r['workflow_file']=='hengce-q017-primary-observer.yml':r['event']='workflow_dispatch'
        self.assertEqual(self.evaluate()['scheduler_liveness']['workflows']['q017_primary']['state'],'FAIL_CLOSED')

    def test_late_start_is_distinct_from_absent(self):
        r=next(r for r in self.m['runs'] if r['workflow_file']=='hengce-q017-primary-observer.yml')
        r['run_started_at']='2026-10-22T08:05:00+08:00'
        x=self.evaluate()['scheduler_liveness']['workflows']['q017_primary']['slots'][0]
        self.assertIn('LATE_RUN',x['reason_codes']); self.assertNotIn('MISSING_SCHEDULED_RUN',x['reason_codes'])

    def test_queued_never_started_after_grace_fails(self):
        r=next(r for r in self.m['runs'] if r['workflow_file']=='hengce-q017-primary-observer.yml')
        r.update(status='queued',run_started_at=None,conclusion=None)
        x=self.evaluate()['scheduler_liveness']['workflows']['q017_primary']['slots'][0]
        self.assertEqual(x['state'],'FAIL_CLOSED'); self.assertIn('NOT_STARTED_AFTER_GRACE',x['reason_codes'])

    def test_current_date_e2_0950_is_late_recovery(self):
        self.a[h.PATHS['e2_morning']]['generated_at_taipei']='2026-10-22T09:50:04+08:00'
        x=self.evaluate()['artifact_freshness']['lanes']['e2_morning']
        self.assertEqual(x['state'],'DEGRADED'); self.assertEqual(x['reason_codes'],['LATE_RECOVERY'])

    def test_e2_recovery_window_and_stale_date_are_not_on_time(self):
        self.a[h.PATHS['e2_morning']]['generated_at_taipei']='2026-10-22T09:05:00+08:00'
        self.assertEqual(self.evaluate()['artifact_freshness']['lanes']['e2_morning']['reason_codes'],['RECOVERY_WINDOW'])
        self.a[h.PATHS['e2_morning']]['trade_date']='2026-10-21'
        self.assertEqual(self.evaluate()['artifact_freshness']['lanes']['e2_morning']['reason_codes'],['STALE_SOURCE_DATE'])

    def test_missing_q017_after_grace_fails_health_without_repair(self):
        del self.a[h.PATHS['q017']]
        x=self.evaluate()
        self.assertEqual(x['artifact_freshness']['lanes']['q017']['state'],'FAIL_CLOSED')
        self.assertNotIn('decision',x)

    def test_late_or_out_of_window_capture_rejected_even_with_rehashed_payload(self):
        obs=self.a[h.PATHS['q017']]
        obs['observation_lock']['capture_finished_at_taipei']='2026-10-22T09:02:00+08:00'
        obs['observation_snapshot_sha256']=h.digest({k:v for k,v in obs.items() if k!='observation_snapshot_sha256'})
        self.a['hengce/q017_radar/observations/20261022_0901_observation.json']=copy.deepcopy(obs)
        x=self.evaluate()['artifact_freshness']['lanes']['q017']
        self.assertEqual(x['state'],'FAIL_CLOSED'); self.assertIn('Q017_CAPTURE_LATE_OR_OUT_OF_WINDOW',x['reason_codes'])

    def test_hash_tamper_and_canonical_mismatch_fail(self):
        self.a[h.PATHS['q017']]['observation_snapshot_sha256']='bad'
        self.assertEqual(self.evaluate()['artifact_freshness']['lanes']['q017']['state'],'FAIL_CLOSED')
        self.a['hengce/q017_radar/observations/20261022_0901_observation.json']=copy.deepcopy(self.a[h.PATHS['q017']])
        self.assertEqual(self.evaluate()['artifact_freshness']['lanes']['q017']['reason_codes'],['Q017_OBSERVATION_HASH_INVALID'])

    def pending_eod(self):
        self.a['eod/20261022/status.json'].update(margin_status='PENDING',mother_status='PENDING',downstream_ready=False,formal_complete_day=False,three_leg_complete=False)

    def test_pending_eod_with_successful_final_retry_is_not_scheduler_failure(self):
        self.pending_eod(); x=self.evaluate()
        self.assertEqual(x['scheduler_liveness']['state'],'PASS')
        self.assertEqual(x['data_readiness']['lanes']['eod']['state'],'PENDING_DATA')
        self.assertIn('FINAL_RETRY_SOURCE_PENDING',x['data_readiness']['lanes']['eod']['reason_codes'])
        self.assertEqual(x['artifact_freshness']['lanes']['eod']['state'],'PASS')
        self.assertEqual(x['state'],'PENDING_DATA')

    def test_old_eod_status_is_not_fresh_after_completed_final_retry(self):
        self.pending_eod()
        self.a['eod/20261022/status.json']['updated_at_taipei']='2026-10-22T15:10:00+08:00'
        x=self.evaluate()
        self.assertEqual(x['scheduler_liveness']['state'],'PASS')
        self.assertEqual(x['artifact_freshness']['lanes']['eod']['state'],'DEGRADED')
        self.assertEqual(x['data_readiness']['lanes']['eod']['state'],'PENDING_DATA')

    def test_invalid_semantics_or_recovery_window_cannot_be_healthy(self):
        original=copy.deepcopy(self.p)
        self.p['artifacts'][0]['semantic_pass']['authority']='UNRECOGNIZED_AUTHORITY'
        self.assertEqual(self.evaluate()['state'],'FAIL_CLOSED')
        self.p=copy.deepcopy(original); self.p['artifacts'][1]['recovery_deadline']=None
        self.assertEqual(self.evaluate()['state'],'FAIL_CLOSED')

    def test_workflow_failure_and_pending_source_are_both_preserved(self):
        self.pending_eod()
        r=next(r for r in self.m['runs'] if r['workflow_file']=='hengce-daily-command-center.yml' and h.stamp(r['created_at']).hour==17)
        r['conclusion']='failure'; x=self.evaluate()
        self.assertEqual(x['scheduler_liveness']['workflows']['daily']['state'],'FAIL_CLOSED')
        self.assertEqual(x['data_readiness']['lanes']['eod']['state'],'PENDING_DATA')

    def test_new_display_does_not_launder_stale_source(self):
        self.a[h.EXTRA_PATHS[0]]['trade_date']='2026-10-21'
        self.a[h.PATHS['display']]['q017']['trade_date']='2026-10-21'
        x=self.evaluate()['artifact_freshness']['lanes']['display']
        self.assertEqual(x['state'],'DEGRADED'); self.assertIn('DISPLAY_STALE_OR_INCOHERENT_SOURCE',x['reason_codes'])

    def test_display_older_than_its_source_is_not_current(self):
        self.a[h.EXTRA_PATHS[0]]['generated_at_taipei']=(self.now+timedelta(seconds=1)).isoformat()
        self.assertEqual(self.evaluate()['artifact_freshness']['lanes']['display']['state'],'DEGRADED')

    def test_naive_evaluation_time_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'NAIVE_EVALUATION_TIME'):
            h.evaluate(datetime(2026,10,22,17,25),self.a,self.m,self.p,'a'*40)

    def test_malformed_source_structures_are_not_healthy(self):
        original=copy.deepcopy(self.a)
        for path in (h.PATHS['q017'],h.PATHS['display'],h.EXTRA_PATHS[0],h.EXTRA_PATHS[1]):
            self.a=copy.deepcopy(original); self.a[path]=['malformed synthetic source']
            with self.subTest(path=path):self.assertNotEqual(self.evaluate()['state'],'PASS')

    def test_weekend_not_due_and_calendar_is_not_invented(self):
        self.now=clock('2026-10-24T12:00:00+08:00'); self.m=run_manifest(self.now,self.p)
        x=self.evaluate(); self.assertEqual(x['state'],'NOT_DUE')
        self.assertFalse(x['calendar']['authoritative_exchange_calendar'])
        self.assertEqual(x['calendar']['market_data_expected'],'UNVERIFIED_EXCHANGE_SESSION')

    def test_collector_error_is_unknown_liveness_not_fake_missed_schedule(self):
        self.m.update(complete=False,errors=[{'reason':'synthetic API error'}],runs=[])
        x=self.evaluate()['scheduler_liveness']; self.assertEqual(x['state'],'DEGRADED')
        self.assertEqual(x['reason_codes'],['SCHEDULER_METADATA_UNAVAILABLE'])

    def test_unknown_contract_field_and_path_fail_conservatively(self):
        original=copy.deepcopy(self.p)
        for mutation in ('top','rule','path','workflow'):
            self.p=copy.deepcopy(original)
            if mutation=='top':self.p['unknown']=True
            elif mutation=='rule':self.p['artifacts'][0]['unknown']=True
            elif mutation=='path':self.p['artifacts'][0]['path']='hengce/q017_radar/decision/latest.json'
            else:self.p['workflows'][0]['file']='unknown.yml'
            with self.subTest(mutation=mutation):self.assertEqual(self.evaluate()['state'],'FAIL_CLOSED')

    def test_unsafe_sources_never_grant_health_authority(self):
        self.a[h.PATHS['e2_morning']].update(capital_authority_twd=100,broker_order_execution=True)
        x=self.evaluate(); self.assertEqual(x['authority_safety']['state'],'FAIL_CLOSED')
        self.assertTrue(h.zero_valid(x))

    def test_utc_cron_maps_previous_utc_day_to_monday_taipei(self):
        slots=h.occurrences(clock('2026-10-26T10:00:00+08:00'),('45 23 * * 0-4',))
        self.assertEqual([x.isoformat() for x in slots],['2026-10-26T07:45:00+08:00'])
        self.assertEqual(h.occurrences(clock('2026-10-24T12:00:00+08:00'),('45 23 * * 0-4',)),[])

    def test_collector_is_tested_with_synthetic_pages_only(self):
        calls=[]
        def fetch(url):
            calls.append(url); return {'workflow_runs':[]}
        x=collector.collect(self.p,'synthetic/repository',self.now,fetch)
        self.assertTrue(x['complete']); self.assertTrue(h.zero_valid(x)); self.assertEqual(len(calls),7)
        x=collector.collect(self.p,'synthetic/repository',self.now,lambda url:(_ for _ in ()).throw(RuntimeError('offline fixture')))
        self.assertFalse(x['complete']); self.assertEqual(len(x['errors']),7)

    def test_policy_matches_existing_producer_schedules_and_names(self):
        import yaml
        for w in self.p['workflows']:
            actual=yaml.load((ROOT/'.github/workflows'/w['file']).read_text(),Loader=yaml.BaseLoader)
            self.assertEqual(w['name'],actual['name'])
            self.assertEqual(w['crons_utc'],[x['cron'] for x in actual['on'].get('schedule',[])])

    def test_health_publication_is_namespaced_and_unrelated_to_q017(self):
        self.assertEqual(publisher.PROFILES['health-only']['writes'],('hengce/health/latest.json',))
        for profile in ('q017-primary-capture','q017-backup-capture','q017-decision-display'):
            self.assertTrue(publisher.matches('hengce/health/latest.json',publisher.PROFILES[profile]['unrelated']))
        self.assertFalse(publisher.matches('hengce/q017_radar/latest.json',publisher.PROFILES['health-only']['writes']))

    def test_cli_writes_only_health_namespace(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            subprocess.run(['git','init',str(root)],capture_output=True,check=True)
            subprocess.run(['git','-C',str(root),'-c','user.name=Synthetic','-c','user.email=synthetic@example.invalid','commit','--allow-empty','-m','fixture'],capture_output=True,check=True)
            runs=root/'runs.json'; runs.write_text(json.dumps(self.m))
            before=set(p.relative_to(root) for p in root.rglob('*') if p.is_file())
            command=[sys.executable,'-B',str(ROOT/'scripts/hengce_system_health.py'),'--root',str(root),'--runs',str(runs),'--now',self.now.isoformat(),'--write']
            r=subprocess.run(command,text=True,capture_output=True)
            self.assertEqual(r.returncode,0,r.stderr)
            after=set(p.relative_to(root) for p in root.rglob('*') if p.is_file())
            self.assertEqual(after-before,{Path('hengce/health/latest.json')})
            self.assertTrue(h.zero_valid(json.loads((root/'hengce/health/latest.json').read_text())))

    def race_fixture(self):
        from test_writer_races import WriterRaceTests
        fixture=WriterRaceTests('test_observability_has_identity_base_remote_paths_and_reason')
        fixture.setUp(); self.addCleanup(fixture.doCleanups)
        return fixture

    def test_health_publication_does_not_break_long_running_q017_capture(self):
        from test_writer_races import PRIMARY
        fixture=self.race_fixture()
        fixture.commit(fixture.a,{'hengce/health/latest.json':json.dumps(h.ZERO)+'\n'})
        rc,_,receipts=fixture.publish(fixture.a,'health-only')
        self.assertEqual(rc,0); self.assertTrue(all(h.zero_valid(x) for x in receipts))
        fixture.commit(fixture.b,{PRIMARY:'independent capture\n'})
        rc,_,_=fixture.publish(fixture.b,'q017-primary-capture')
        self.assertEqual(rc,0)
        self.assertEqual(fixture.read_remote(PRIMARY),'independent capture')

    def test_health_snapshot_cannot_overwrite_producer_or_publish_stale_inputs(self):
        from test_writer_races import LATEST
        fixture=self.race_fixture()
        fixture.commit(fixture.a,{LATEST:'new model input\n'})
        self.assertEqual(fixture.publish(fixture.a)[0],0)
        fixture.commit(fixture.b,{'hengce/health/latest.json':json.dumps(h.ZERO)+'\n'})
        rc,result,receipts=fixture.publish(fixture.b,'health-only')
        self.assertEqual(rc,2); self.assertIn('READ_DEPENDENCY',result['conflict_reason'])
        self.assertTrue(all(h.zero_valid(x) for x in receipts))
        fixture=self.race_fixture()
        fixture.commit(fixture.a,{LATEST:'forbidden health write\n'})
        rc,result,_=fixture.publish(fixture.a,'health-only')
        self.assertEqual(rc,2); self.assertIn('WRITE_SET',result['conflict_reason'])

    def test_health_workflow_separates_offline_tests_from_live_collector(self):
        import yaml
        w=yaml.load((ROOT/'.github/workflows/hengce-system-health.yml').read_text(),Loader=yaml.BaseLoader)
        self.assertEqual(w['permissions'],{'contents':'read'})
        live=w['jobs']['current-health']
        self.assertEqual(live['permissions'],{'contents':'write','actions':'read'})
        text=json.dumps(live)
        self.assertIn('--profile health-only',text); self.assertNotIn('git push',text)
        self.assertNotIn('git pull',text); self.assertNotIn('git rebase',text)
        self.assertIn("github.ref == 'refs/heads/main'",live['if'])
        self.assertNotIn('collect_runs.py',json.dumps(w['jobs']['self-test']))


if __name__=='__main__':
    unittest.main(verbosity=2)
