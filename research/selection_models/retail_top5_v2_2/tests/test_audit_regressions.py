"""Adversarial regressions for independent audit A/B/C/D and fail-closed paths."""
import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from freeze import make_record
from provenance import (DEFAULT_DAILY,DEFAULT_CHIPS,DEFAULT_CONTRACT,ROOT,
                        load_contract,verify_record,load_inputs)
from select_stocks import select
from validation import decision_data
from rank_whole_lot import run


class AuditRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d=pd.read_csv(DEFAULT_DAILY,dtype={'Ticker':str})
        cls.c=pd.read_csv(DEFAULT_CHIPS,dtype={'Ticker':str,'SnapshotDate':str})
        cls.frozen=make_record(DEFAULT_DAILY,DEFAULT_CHIPS,'2026-11-06')

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.tmp=Path(self.temp.name)

    def assert_selection_rejected(self,daily=DEFAULT_DAILY,chips=DEFAULT_CHIPS,error='MISMATCH'):
        target=self.tmp/'must_not_exist'
        with self.assertRaisesRegex(ValueError,error):
            select(daily,chips,'2026-11-06',target)
        self.assertFalse(target.exists())

    def test_a_entire_daily_universe_reduced_to_four(self):
        d=self.d[self.d.Ticker.isin(['2254','6782','6689','6112'])]
        p=self.tmp/'partial.csv';d.to_csv(p,index=False)
        self.assert_selection_rejected(daily=p,error='DAILY_UNIVERSE_MISMATCH')

    def test_b_critical_chip_week_reduced_to_four(self):
        c=self.c[(self.c.SnapshotDate!='20261022') | self.c.Ticker.isin(['2254','6782','6689','6112'])]
        p=self.tmp/'partial_chip.csv';c.to_csv(p,index=False)
        self.assert_selection_rejected(chips=p,error='CHIP_UNIVERSE_MISMATCH')

    def test_a_single_ticker_replaced_same_row_count(self):
        d=self.d.copy();d.loc[d.Ticker.eq('2254'),'Ticker']='FAKE'
        p=self.tmp/'substitute.csv';d.to_csv(p,index=False)
        self.assert_selection_rejected(daily=p,error='DAILY_UNIVERSE_MISMATCH')

    def test_entire_market_date_deleted(self):
        p=self.tmp/'missing_date.csv'
        self.d[self.d.Date!='2026-10-22'].to_csv(p,index=False)
        self.assert_selection_rejected(daily=p,error='DAILY_DATE_COVERAGE_MISMATCH')

    def test_entire_chip_week_deleted(self):
        p=self.tmp/'missing_week.csv'
        self.c[self.c.SnapshotDate!='20261022'].to_csv(p,index=False)
        self.assert_selection_rejected(chips=p,error='CHIP_DATE_COVERAGE_MISMATCH')

    def test_changed_price_with_unchanged_universe(self):
        d=self.d.copy();d.loc[d.Date.eq('2026-11-06') & d.Ticker.eq('2254'),'Close']='111'
        p=self.tmp/'price_edit.csv';d.to_csv(p,index=False)
        self.assert_selection_rejected(daily=p,error='SOURCE_SHA256_MISMATCH')

    def test_custom_reduced_reference_is_not_trusted(self):
        c=load_contract();c['daily_universe']={day:['2254'] for day in c['daily_universe']}
        p=self.tmp/'forged_contract.json';p.write_text(json.dumps(c))
        with self.assertRaisesRegex(ValueError,'REFERENCE_CONTRACT_MISMATCH'):
            select(DEFAULT_DAILY,DEFAULT_CHIPS,'2026-11-06',self.tmp/'out',contract_path=p)
        self.assertFalse((self.tmp/'out').exists())

    def test_c_forged_hashes_rejected(self):
        for field in ['price_sha256','chip_sha256','contract_sha256','code_sha256']:
            with self.subTest(field=field):
                f=copy.deepcopy(self.frozen)
                f[field]='0'*64 if field!='code_sha256' else {k:'0'*64 for k in f[field]}
                with self.assertRaisesRegex(ValueError,'HASH_MISMATCH'):
                    verify_record(f)

    def test_c_forged_prospective_rejected(self):
        f=copy.deepcopy(self.frozen);f.update(kind='prospective',generated_at='2026-11-06T14:00:00+08:00')
        with self.assertRaisesRegex(ValueError,'OFFICIAL_EVIDENCE_UNAVAILABLE'):
            verify_record(f)

    def test_candidate_content_recomputed_not_just_hash_checked(self):
        f=copy.deepcopy(self.frozen);f['lanes']['14']['candidates'][0]['r20']=.99
        with self.assertRaisesRegex(ValueError,'FREEZE_REPLAY_MISMATCH'):
            verify_record(f)

    def test_candidate_removal_recomputed(self):
        f=copy.deepcopy(self.frozen);f['lanes']['14']['candidates']=[]
        with self.assertRaisesRegex(ValueError,'FREEZE_REPLAY_MISMATCH'):
            verify_record(f)

    def test_false_authority_labels_rejected(self):
        for field,value in [('authority','APPROVED'),('official_publication_verified',True),('integrity','SIGNED')]:
            f=copy.deepcopy(self.frozen);f[field]=value
            with self.assertRaises(ValueError): verify_record(f)

    def test_d_legacy_preserved_and_rejected(self):
        f=json.loads((ROOT/'legacy'/'rehearsal_20261106.json').read_text())
        self.assertNotEqual(f['price_sha256'],hashlib.sha256(DEFAULT_DAILY.read_bytes()).hexdigest())
        self.assertNotEqual(f['chip_sha256'],hashlib.sha256(DEFAULT_CHIPS.read_bytes()).hexdigest())
        with self.assertRaisesRegex(ValueError,'LEGACY_OR_UNKNOWN_FREEZE'): verify_record(f)

    def test_new_freeze_matches_actual_sources(self):
        self.assertEqual(self.frozen['price_sha256'],hashlib.sha256(DEFAULT_DAILY.read_bytes()).hexdigest())
        self.assertEqual(self.frozen['chip_sha256'],hashlib.sha256(DEFAULT_CHIPS.read_bytes()).hexdigest())
        self.assertEqual(verify_record(self.frozen),self.frozen['lanes'])

    def scenario(self, *, simulate=False, acct=None):
        p=self.tmp/'prices.csv';r=self.tmp/'risk.csv'
        p.write_text('ticker,reference_price,as_of\n'+''.join(f'{t},100,2026-11-06\n' for t in self.frozen['lanes']['14']['top5']))
        r.write_text('ticker,rms,s5,escape,account_eligible,tradable,as_of\n'+''.join(f'{t},PASS,PASS,PASS,PASS,PASS,2026-11-06\n' for t in self.frozen['lanes']['14']['top5']))
        return run(self.frozen,p,acct or dict(nav=1000000,cash=1000000,held_tickers=[],as_of='2026-11-06'),r,simulate=simulate)

    def test_c_all_pass_does_not_authorize_any_lots(self):
        for simulate in [False,True]:
            out=self.scenario(simulate=simulate)
            self.assertTrue(all(r['input_gate_all_pass'] for r in out))
            self.assertTrue(all(r['lots_for_manual_review']==r['authorized_lots']==0 and not r['gate_all_pass'] for r in out))
            self.assertEqual([r['simulation_lots'] for r in out],[1]*5 if simulate else [0]*5)

    def test_existing_holdings_missing_valuations_stop_simulation(self):
        out=self.scenario(simulate=True,acct=dict(nav=1000000,cash=900000,held_tickers=['1101'],as_of='2026-11-06'))
        self.assertTrue(all(r['simulation_lots']==0 for r in out))
        self.assertIn('持倉市值',out[0]['simulation_status'])

    def test_existing_concentration_stops_new_simulation(self):
        out=self.scenario(simulate=True,acct=dict(nav=1000000,cash=600000,held_tickers=['1101'],position_market_values={'1101':400000},as_of='2026-11-06'))
        self.assertTrue(all(r['simulation_lots']==0 for r in out))
        self.assertIn('集中度',out[0]['simulation_status'])

    def test_nav_reconciliation_stops_simulation(self):
        out=self.scenario(simulate=True,acct=dict(nav=1000000,cash=900000,held_tickers=['1101'],position_market_values={'1101':50000},as_of='2026-11-06'))
        self.assertTrue(all(r['simulation_lots']==0 for r in out))
        self.assertIn('NAV',out[0]['simulation_status'])

    def test_official_selection_refused_before_output(self):
        with self.assertRaisesRegex(ValueError,'OFFICIAL_EVIDENCE_UNAVAILABLE'):
            select(DEFAULT_DAILY,DEFAULT_CHIPS,'2026-11-06',self.tmp/'out',mode='official')
        self.assertFalse((self.tmp/'out').exists())

    def test_official_freeze_cli_refused_before_output(self):
        output=self.tmp/'forbidden.json'
        result=subprocess.run([sys.executable,str(ROOT/'freeze.py'),str(DEFAULT_DAILY),str(DEFAULT_CHIPS),'2026-11-06',str(output)],capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('OFFICIAL_EVIDENCE_UNAVAILABLE',result.stderr)
        self.assertFalse(output.exists())

    def test_screen_cli_cannot_bypass_coverage(self):
        p=self.tmp/'small.csv';self.d[self.d.Ticker.eq('2254')].to_csv(p,index=False)
        output=self.tmp/'forbidden.csv'
        result=subprocess.run([sys.executable,str(ROOT/'screen.py'),str(p),str(DEFAULT_CHIPS),str(output)],capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('DAILY_UNIVERSE_MISMATCH',result.stderr)
        self.assertFalse(output.exists())

    def test_output_is_not_overwritten(self):
        p=self.tmp/'existing';p.mkdir();(p/'keep').write_text('preserve')
        with self.assertRaises(FileExistsError): select(DEFAULT_DAILY,DEFAULT_CHIPS,'2026-11-06',p)
        self.assertEqual((p/'keep').read_text(),'preserve')


if __name__=='__main__': unittest.main()
