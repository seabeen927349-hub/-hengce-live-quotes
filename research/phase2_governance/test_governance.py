"""Synthetic metadata only; no market data, holdout artifact or model is loaded."""
import copy
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from jsonschema.exceptions import ValidationError

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from research.phase1_audit import ledger as audit
from research.phase2_governance import checkpoint as custody
from research.phase2_governance import freeze
from research.phase2_governance import governance as g
from research.phase2_governance import ledger_store as store


def record(i,previous=audit.GENESIS,result='FAILED',decision='REJECT',parent=None):
    row=dict(schema_version=1,experiment_id='SYNTHETIC-'+str(i),parent_id=parent,
        hypothesis='OFFLINE INFRASTRUCTURE TEST; NO MODEL TRIAL',engine='E2',code_commit=g.BASE,
        data_cutoff='2026-10-20T00:00:00+00:00',parameters={},metrics=None,result=result,
        decision=decision,reason='Synthetic retention fixture',recorded_at='2026-10-23T00:00:00+00:00',
        previous_sha256=previous,record_sha256='',capital_authority=0,phase2_authorized=False)
    row['record_sha256']=audit.record_hash(row);return row


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        root=Path(self.temp.name);self.ledger=root/'research';self.anchor=root/'independent-custody'
        self.ledger.mkdir();self.anchor.mkdir();(self.ledger/'experiments.jsonl').write_bytes(b'')
        self.cp=custody.checkpoint(self.ledger,self.anchor,audit.GENESIS,'SYNTHETIC_CUSTODIAN',initialize=True)
        self.network=patch.object(socket.socket,'connect',side_effect=AssertionError('OFFLINE_ONLY'))
        self.network.start();self.addCleanup(self.network.stop)

    def append(self,row):return store.append(self.ledger,self.anchor,self.cp['checkpoint_sha256'],row)

    def seal(self):
        self.cp=custody.checkpoint(self.ledger,self.anchor,self.cp['checkpoint_sha256'],'SYNTHETIC_CUSTODIAN')

    def raw(self):return (self.ledger/'experiments.jsonl').read_bytes()

    def test_failed_rejected_aborted_and_proposed_all_retained(self):
        previous=audit.GENESIS;prefix=b''
        for i,(result,decision) in enumerate([('FAILED','REJECT'),('ABORTED','REJECT'),('COMPLETED','REJECT'),('PROPOSED','PENDING')]):
            row=record(i,previous,result,decision);self.append(row);self.seal()
            self.assertTrue(self.raw().startswith(prefix));prefix=self.raw();previous=row['record_sha256']
        rows=store.decode(self.raw());self.assertEqual(len(rows),4);self.assertTrue(all(x['metrics'] is None for x in rows))
        self.assertEqual(self.cp['record_count'],4)

    def test_appender_never_writes_its_own_anchor_and_requires_next_checkpoint(self):
        before={p.name:p.read_bytes() for p in self.anchor.glob('*.json')};a=record(1);self.append(a)
        self.assertEqual(before,{p.name:p.read_bytes() for p in self.anchor.glob('*.json')})
        with self.assertRaisesRegex(ValueError,'ANCHOR_MISMATCH'):self.append(record(2,a['record_sha256']))
        self.seal();self.append(record(2,a['record_sha256']))

    def test_external_anchor_detects_rehashed_rewrite(self):
        a=record(1);self.append(a);self.seal();a['reason']='rewritten';a['record_sha256']=audit.record_hash(a)
        (self.ledger/'experiments.jsonl').write_bytes(g.canonical(a)+b'\n')
        with self.assertRaisesRegex(ValueError,'ANCHOR_MISMATCH'):self.append(record(2,a['record_sha256']))
        with self.assertRaises(ValueError):self.seal()

    def test_external_anchor_detects_truncation(self):
        self.append(record(1));self.seal();(self.ledger/'experiments.jsonl').write_bytes(b'')
        with self.assertRaisesRegex(ValueError,'ANCHOR_MISMATCH'):self.append(record(2))

    def test_checkpoint_preserves_anchored_prefix_and_rejects_rewrite_plus_append(self):
        a=record(1);self.append(a);self.seal();a['reason']='rewritten';a['record_sha256']=audit.record_hash(a)
        b=record(2,a['record_sha256']);(self.ledger/'experiments.jsonl').write_bytes(g.canonical(a)+b'\n'+g.canonical(b)+b'\n')
        with self.assertRaisesRegex(ValueError,'ANCHOR_PREFIX_MISMATCH'):self.seal()

    def test_duplicate_id_rejected_without_any_append(self):
        a=record(1);self.append(a);self.seal();before=self.raw()
        with self.assertRaisesRegex(ValueError,'DUPLICATE'):self.append(record(1,a['record_sha256']))
        self.assertEqual(self.raw(),before)

    def test_chain_tampering_and_unknown_schema_fields_rejected(self):
        for row in ({**record(1),'reason':'tampered'},{**record(1),'unexpected':True}):
            with self.assertRaises((ValueError,ValidationError)):self.append(row)
        self.assertEqual(self.raw(),b'')

    def test_stale_writer_checkpoint_rejected(self):
        old=self.cp['checkpoint_sha256'];a=record(1);self.append(a);self.seal()
        with self.assertRaisesRegex(ValueError,'STALE_OR_UNTRUSTED'):
            store.append(self.ledger,self.anchor,old,record(2,a['record_sha256']))
        with self.assertRaisesRegex(ValueError,'CAS_REJECTED'):
            custody.checkpoint(self.ledger,self.anchor,old,'SYNTHETIC_CUSTODIAN')

    def test_two_appenders_with_same_checkpoint_cannot_both_publish(self):
        def attempt(i):
            try:self.append(record(i));return 'APPENDED'
            except ValueError:return 'BLOCKED'
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes=list(pool.map(attempt,(1,2)))
        self.assertEqual(sorted(outcomes),['APPENDED','BLOCKED'])
        self.assertEqual(len(store.decode(self.raw())),1)

    def test_partial_append_fails_closed_without_deleting_failed_trial_prefix(self):
        a=record(1);self.append(a);self.seal();before=self.raw();original=os.write;calls=[0]
        def torn(fd,data):
            calls[0]+=1
            if calls[0]==1:return original(fd,bytes(data[:12]))
            raise OSError('SYNTHETIC_CRASH')
        with patch.object(store.os,'write',side_effect=torn),self.assertRaises(OSError):self.append(record(2,a['record_sha256']))
        self.assertTrue(self.raw().startswith(before));self.assertGreater(len(self.raw()),len(before))
        with self.assertRaisesRegex(ValueError,'PARTIAL_LEDGER_TAIL'):self.seal()
        with self.assertRaises(ValueError):self.append(record(3,a['record_sha256']))

    def test_custody_is_external_and_cannot_be_inside_repository_or_ledger(self):
        for root in (self.ledger,g.HERE):
            with self.assertRaisesRegex(ValueError,'ANCHOR_MUST_BE_OUTSIDE'):store.external_root(root,self.ledger)

    def test_symlink_storage_rejected(self):
        link=Path(self.temp.name)/'alias';link.symlink_to(self.ledger,target_is_directory=True)
        with self.assertRaisesRegex(ValueError,'SYMLINK'):store.ledger_path(link)

    def test_append_prefix_and_git_anchor_reject_mutations_and_deletions(self):
        a=record(1);raw=g.canonical(a)+b'\n';freeze.prefix(raw,raw)
        with self.assertRaisesRegex(ValueError,'PREFIX'):freeze.prefix(raw,b'')
        a['reason']='rewritten';a['record_sha256']=audit.record_hash(a)
        with self.assertRaisesRegex(ValueError,'PREFIX'):freeze.prefix(raw,g.canonical(a)+b'\n')

    def test_independent_checkpoint_hash_and_identity_corruption_detected(self):
        p=next(self.anchor.glob('*.json'));value=g.metadata(p);value['prefix_sha256']='a'*64;p.write_bytes(g.canonical(value))
        with self.assertRaisesRegex(ValueError,'CHECKPOINT_CORRUPTED'):custody.read_anchor(self.anchor)

    def test_cannot_initialize_anchor_over_existing_trial(self):
        self.append(record(1));self.seal()
        with self.assertRaisesRegex(ValueError,'ONLY_EMPTY_GENESIS'):custody.checkpoint(self.ledger,self.anchor,audit.GENESIS,'X',initialize=True)

    def test_schema_and_authority_and_cross_engine_parent(self):
        a=record(1);self.append(a);self.seal()
        for change in ({'capital_authority':1},{'phase2_authorized':True},{'capital_authority':False},
                       {'result':'FAILED','decision':'ACCEPT'},{'engine':'M1','parent_id':a['experiment_id']}):
            b=record(2,a['record_sha256']);b.update(change);b['record_sha256']=audit.record_hash(b)
            with self.assertRaises((ValueError,ValidationError)):self.append(b)
        for k,v in g.ZERO.items():self.assertEqual(self.cp[k],v)


class GovernanceTests(unittest.TestCase):
    def setUp(self):
        network=patch.object(socket.socket,'connect',side_effect=AssertionError('OFFLINE_ONLY'))
        network.start();self.addCleanup(network.stop)

    def test_production_bytes_and_model_runtime_scope_unchanged(self):
        self.assertEqual(freeze.verify(os.environ.get('HENGCE_GOVERNANCE_BASE',g.BASE))['ledger_record_count'],0)
        for path in ('scripts/hengce_e2_live.py','.github/workflows/hengce-daily-command-center.yml',
                     'hengce/live_universe.json','research/e2_profit_max/results.json'):
            with self.assertRaisesRegex(ValueError,'OUT_OF_SCOPE'):freeze.check_paths([path])

    def test_unrelated_main_advancement_is_not_mistaken_for_branch_mutation(self):
        advanced='f'*40;calls=[];actual=freeze.git;run=subprocess.run
        def fake(*args):
            calls.append(args)
            if args==('merge-base',advanced,'HEAD'):return (g.BASE+'\n').encode()
            if args==('diff','--name-only',advanced):return b'hengce/q017_radar/selfverify/infrastructure_latest.json\n'
            return actual(*args)
        def remote(args,*a,**kw):
            if args[-3:]==['cat-file','-e',advanced+':'+freeze.LEDGER]:return subprocess.CompletedProcess(args,1)
            if args[-4:]==['merge-base','--is-ancestor',g.BASE,advanced]:return subprocess.CompletedProcess(args,0)
            return run(args,*a,**kw)
        with patch.object(freeze,'git',side_effect=fake),patch.object(freeze.subprocess,'run',side_effect=remote):
            self.assertEqual(freeze.verify(advanced)['status'],'PASS')
        self.assertIn(('diff','--name-only',g.BASE),calls)
        self.assertNotIn(('diff','--name-only',advanced),calls)

    def test_research_environment_and_all_transitive_hash_pins_match(self):
        lock=g.verify_environment();self.assertEqual(len(lock['dependencies']),14)
        text=(g.HERE/'requirements.lock').read_text()
        for dep in lock['dependencies']:self.assertIn(dep['name']+'=='+dep['version']+' --hash=sha256:'+dep['sha256'],text)

    def test_every_human_approval_is_pending_and_no_run_can_be_authorized_by_toggle(self):
        p=g.metadata(g.HERE/'phase2-policy.json');g.validate_policy(p)
        with self.assertRaisesRegex(ValueError,'B10_BLOCKED'):g.require_phase2_run(p)
        for key,change in [('phase2_authorized',True),('authorization_event','self-approved')]:
            q=copy.deepcopy(p);q[key]=change
            with self.assertRaises(ValueError):g.require_phase2_run(q)
        q=copy.deepcopy(p);q['human_approvals']['trial_budget_multiple_testing']['approved_value']=24
        with self.assertRaises(ValueError):g.validate_policy(q)

    def test_exposed_history_scope_and_aggregate_cost_cannot_be_relabeled(self):
        p=g.metadata(g.HERE/'phase2-policy.json')
        for field,value in [('pristine_holdout',True),('years',[2026])]:
            q=copy.deepcopy(p);q['historical_exposure'][field]=value
            with self.assertRaises(ValueError):g.validate_policy(q)
        for changed in ({'roundtrip_cost':.016},{'component_costs':{'fees':.001}}):
            q=copy.deepcopy(p);q['existing_e2_baseline'].update(changed)
            with self.assertRaises(ValueError):g.validate_policy(q)

    def test_holdout_pure_metadata_irreversibility_without_opening_artifact(self):
        empty=g.metadata(g.HERE/'holdout-state.json');before=copy.deepcopy(empty)
        sealed={**empty,'state':'SEALED','custodian':'SYNTHETIC','artifact_commitment_sha256':'a'*64,
          'policy_authorization_id':'SYNTHETIC_METADATA_ONLY','access_policy_sha256':'b'*64,'sealed_at':'2099-01-01T00:00:00Z'}
        opened={**sealed,'state':'OPENED','opened_at':'2099-01-02T00:00:00Z','open_count':1,'exposed':True}
        consumed={**opened,'state':'CONSUMED','consumed_at':'2099-01-03T00:00:00Z'}
        for a,b in ((empty,sealed),(sealed,opened),(opened,consumed)):self.assertTrue(g.validate_holdout_transition(a,b))
        for a,b in ((opened,sealed),(consumed,opened),(opened,{**opened,'open_count':0}),
                    (opened,{**opened,'opened_at':'2099-01-04T00:00:00Z'})):
            with self.assertRaises((ValueError,ValidationError)):g.validate_holdout_transition(a,b)
        self.assertEqual(empty,before);self.assertEqual(g.metadata(g.HERE/'holdout-state.json'),before)
        with self.assertRaisesRegex(ValueError,'ACCESS_FORBIDDEN'):g.require_holdout_access(g.metadata(g.HERE/'phase2-policy.json'))

    def test_unauthorized_run_cli_is_rejected_without_creating_records(self):
        before=(g.HERE/'ledger/experiments.jsonl').read_bytes()
        out=subprocess.run([sys.executable,'-B',str(g.HERE/'ledger_store.py'),'check-run'],capture_output=True,text=True)
        self.assertEqual(out.returncode,2);self.assertIn('B10_BLOCKED',out.stdout)
        self.assertEqual((g.HERE/'ledger/experiments.jsonl').read_bytes(),before)


if __name__=='__main__':unittest.main(verbosity=2)
