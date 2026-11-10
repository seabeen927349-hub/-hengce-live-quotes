"""Top5 strategy and malformed batch error regressions from the V2.1 audit."""
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd
from freeze import make_record
from provenance import (ROOT,DEFAULT_DAILY,DEFAULT_CHIPS,load_inputs,verify_record,compute_lanes)
from screen import eligible_stocks,screen
from select_stocks import select
from rank_whole_lot import run,account_state
from strategy import PARAMETERS

EXPECTED=['6446','2412','1476','2610','2254','4720','6782']


class Top5Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.daily,cls.chips,cls.contract=load_inputs()
        cls.frozen=make_record(DEFAULT_DAILY,DEFAULT_CHIPS,'2026-11-06')

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.tmp=Path(self.temp.name)

    def test_all_seven_and_top_five_independently_expected(self):
        result=select(DEFAULT_DAILY,DEFAULT_CHIPS,'2026-11-06',self.tmp/'out')
        self.assertEqual([r['ticker'] for r in result['all_qualified']],EXPECTED)
        self.assertEqual([r['ticker'] for r in result['candidates']],EXPECTED[:5])
        self.assertEqual(result['qualified_count'],7)
        self.assertEqual(result['selected_count'],5)
        self.assertEqual(result['matched_research_count'],2)
        self.assertEqual(list(pd.read_csv(self.tmp/'out'/'all_qualified.csv',dtype={'ticker':str}).ticker),EXPECTED)
        self.assertEqual(list(pd.read_csv(self.tmp/'out'/'candidates.csv',dtype={'ticker':str}).ticker),EXPECTED[:5])

    def test_pairing_kept_separate_not_required(self):
        lane=self.frozen['lanes']['14']
        self.assertEqual([c['ticker'] for c in lane['research_pairs']],['2254','6782'])
        self.assertIn('6446',lane['top5'])
        self.assertNotIn('6782',lane['top5'])
        self.assertEqual(len(lane['candidates']),7)

    def test_freeze_replays_strategy_and_both_pools(self):
        self.assertEqual(self.frozen['strategy'],PARAMETERS)
        self.assertEqual(verify_record(self.frozen),self.frozen['lanes'])
        for field in ['top5','research_pairs']:
            altered=copy.deepcopy(self.frozen);altered['lanes']['14'][field]=[]
            with self.assertRaisesRegex(ValueError,'FREEZE_REPLAY_MISMATCH'):verify_record(altered)
        altered=copy.deepcopy(self.frozen);altered['strategy']['position_cap']=.3
        with self.assertRaisesRegex(ValueError,'FREEZE_STRATEGY_MISMATCH'):verify_record(altered)

    def test_unchanged_all_qualified_after_future_and_shuffle(self):
        future=self.daily[self.daily.Date.eq(self.daily.Date.max())].copy()
        future['Date']=pd.Timestamp('2026-11-13');future['Close']=99999
        a=eligible_stocks(self.daily,self.chips,14,pd.Timestamp('2026-11-06'))
        b=eligible_stocks(pd.concat([self.daily,future]).sample(frac=1,random_state=3),self.chips.sample(frac=1,random_state=4),14,pd.Timestamp('2026-11-06'))
        pd.testing.assert_frame_equal(a.drop(columns='trade'),b.drop(columns='trade'))

    def scenario(self,price=100,acct=None):
        top=self.frozen['lanes']['14']['top5']
        p=self.tmp/'prices.csv';r=self.tmp/'risk.csv'
        p.write_text('ticker,reference_price,as_of\n'+''.join(f'{t},{price},2026-11-06\n' for t in top))
        r.write_text('ticker,rms,s5,escape,account_eligible,tradable,as_of\n'+''.join(f'{t},PASS,PASS,PASS,PASS,PASS,2026-11-06\n' for t in top))
        return run(self.frozen,p,acct or dict(nav=1000000,cash=1000000,held_tickers=[],as_of='2026-11-06'),r,simulate=True)

    def test_five_equal_caps_and_cash_reserve(self):
        out=self.scenario(price=10)
        self.assertEqual([r['simulation_lots'] for r in out],[17]*5)
        costs=[r['simulation_lots']*10000*1.0025 for r in out]
        self.assertTrue(all(c<=180000 for c in costs))
        self.assertGreaterEqual(1000000-sum(costs),100000)
        self.assertTrue(all(r['authorized_lots']==r['lots_for_manual_review']==0 for r in out))

    def test_unaffordable_top_five_stays_zero_no_sixth_replacement(self):
        out=self.scenario(price=1000)
        self.assertEqual([r['ticker'] for r in out],EXPECTED[:5])
        self.assertTrue(all(r['simulation_lots']==0 for r in out))

    def test_held_top_five_no_chase_no_replacement(self):
        out=self.scenario(acct=dict(nav=1000000,cash=850000,held_tickers=[' 6446 '],position_market_values={'6446':150000},as_of='2026-11-06'))
        self.assertEqual(out[0]['simulation_lots'],0)
        self.assertIn('已持有',out[0]['simulation_status'])
        self.assertEqual([r['ticker'] for r in out],EXPECTED[:5])

    def test_existing_five_positions_no_sixth_buy(self):
        acct=dict(nav=1000000,cash=250000,held_tickers=['A','B','C','D','E'],position_market_values={t:150000 for t in 'ABCDE'},as_of='2026-11-06')
        out=self.scenario(acct=acct)
        self.assertTrue(all(r['simulation_lots']==0 for r in out))
        self.assertTrue(all('最多5檔' in r['simulation_status'] for r in out))

    def test_six_existing_positions_rejected(self):
        with self.assertRaises(ValueError):account_state(dict(nav=1000000,cash=400000,held_tickers=list('ABCDEF')))

    def test_v21_freeze_rejected(self):
        old=json.loads((ROOT/'legacy'/'v2_1'/'rehearsal_verified_20261106.json').read_text())
        with self.assertRaisesRegex(ValueError,'LEGACY_OR_UNKNOWN_FREEZE'):verify_record(old)

    def assert_cli_input_error(self,path,*,chips=False):
        target=self.tmp/'no_output'
        result=subprocess.run([sys.executable,str(ROOT/'select_stocks.py'),'--weekly' if chips else '--daily',str(path),'--decision','2026-11-06','--output',str(target)],capture_output=True,text=True)
        self.assertEqual(result.returncode,2,result.stderr)
        self.assertIn('選股失敗：DATA_INPUT_ERROR',result.stderr)
        self.assertIn('batch=original_seed_through_20261106',result.stderr)
        self.assertIn('sha256=',result.stderr)
        self.assertNotIn('Traceback',result.stderr)
        self.assertFalse(target.exists())

    def test_truncated_gzip_consistent_error(self):
        p=self.tmp/'truncated.csv.gz';p.write_bytes(DEFAULT_DAILY.read_bytes()[:-15])
        self.assert_cli_input_error(p)

    def test_corrupt_gzip_footer_consistent_error(self):
        p=self.tmp/'bad.csv.gz';p.write_bytes(DEFAULT_DAILY.read_bytes()[:-15]+b'\x00'*15)
        self.assert_cli_input_error(p)

    def test_unterminated_csv_quote_consistent_error(self):
        p=self.tmp/'bad.csv';p.write_text('Date,Ticker,Close,Volume,Turnover\n"unterminated')
        self.assert_cli_input_error(p)

    def test_empty_csv_consistent_error(self):
        p=self.tmp/'empty.csv';p.write_bytes(b'')
        self.assert_cli_input_error(p)

    def test_invalid_encoding_consistent_error(self):
        p=self.tmp/'encoding.csv';p.write_bytes(b'\xff\xfe\x81')
        self.assert_cli_input_error(p)

    def test_chip_gzip_corruption_consistent_error(self):
        p=self.tmp/'chip.csv.gz';p.write_bytes(DEFAULT_CHIPS.read_bytes()[:-10])
        self.assert_cli_input_error(p,chips=True)

    def test_other_entrypoints_use_same_data_error(self):
        p=self.tmp/'broken.gz';p.write_bytes(DEFAULT_DAILY.read_bytes()[:-15])
        for script,args in [('screen.py',[str(p),str(DEFAULT_CHIPS),str(self.tmp/'no.csv')]),('freeze.py',[str(p),str(DEFAULT_CHIPS),'2026-11-06',str(self.tmp/'no.json'),'--rehearsal'])]:
            res=subprocess.run([sys.executable,str(ROOT/script),*args],capture_output=True,text=True)
            self.assertEqual(res.returncode,2,res.stderr)
            self.assertIn('DATA_INPUT_ERROR',res.stderr)
            self.assertNotIn('Traceback',res.stderr)
        self.assertFalse((self.tmp/'no.csv').exists());self.assertFalse((self.tmp/'no.json').exists())


if __name__=='__main__':unittest.main()
