import copy
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from screen import read_daily, read_chips, screen
from validation import decision_data
from rank_whole_lot import run, read_csv_by_ticker
from freeze import make_record
from provenance import DEFAULT_DAILY, DEFAULT_CHIPS

ROOT=Path(__file__).resolve().parents[1]


class ModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.daily=read_daily(ROOT/'price_seed_through_20261106.csv.gz')
        cls.chips=read_chips(ROOT/'chip_seed_through_20261106.csv.gz')
        cls.freeze=make_record(DEFAULT_DAILY,DEFAULT_CHIPS,'2026-11-06')

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.tmp=Path(self.temp.name)

    def rank(self, frozen=None, cash=1000000, risk='PASS', asof='2026-11-06', simulate=False):
        (self.tmp/'prices.csv').write_text('ticker,reference_price,as_of\n'+''.join(f'{t},100,2026-11-06\n' for t in self.freeze['lanes']['14']['top5']))
        (self.tmp/'risk.csv').write_text('ticker,rms,s5,escape,account_eligible,tradable,as_of\n'+''.join(f'{t},{risk},PASS,PASS,PASS,PASS,{asof}\n' for t in self.freeze['lanes']['14']['top5']))
        return run(frozen or self.freeze,self.tmp/'prices.csv',dict(nav=1000000,cash=cash,held_tickers=[],as_of='2026-11-06'),self.tmp/'risk.csv',14,now=datetime(2026,11,6,15,tzinfo=ZoneInfo('Asia/Taipei')),simulate=simulate)

    def prospective(self):
        f=copy.deepcopy(self.freeze)
        f.update(kind='prospective',generated_at='2026-11-06T14:00:00+08:00')
        return f

    def test_reproduces_seed(self):
        d,c,_=decision_data(self.daily,self.chips,'2026-11-06')
        r=screen(d,c,14,pd.Timestamp('2026-11-06'))
        self.assertEqual(list(r.ticker),['2254','6782'])
        self.assertAlmostEqual(r.iloc[0].r20,next(c['r20'] for c in self.freeze['lanes']['14']['candidates'] if c['ticker']=='2254'))

    def test_future_data_and_shuffle_do_not_change_history(self):
        future=self.daily[self.daily.Date.eq(self.daily.Date.max())].copy()
        future['Date']=pd.Timestamp('2026-11-13');future['Close']=99999
        future_chip=self.chips[self.chips.Date.eq(self.chips.Date.max())].copy()
        future_chip['Date']=pd.Timestamp('2026-11-13');future_chip['delta']=-.99
        a=screen(self.daily,self.chips,14,pd.Timestamp('2026-11-06'))
        b=screen(pd.concat([self.daily,future]).sample(frac=1,random_state=7),pd.concat([self.chips,future_chip]).sample(frac=1,random_state=8),14,pd.Timestamp('2026-11-06'))
        # trade is an informational next observed session; signal columns must match.
        pd.testing.assert_frame_equal(a.drop(columns='trade'),b.drop(columns='trade'))

    def test_missing_decision_and_insufficient_history(self):
        for d in [self.daily[self.daily.Date.lt('2026-11-06')],self.daily[self.daily.Date.ge('2026-11-02')]]:
            with self.assertRaises(ValueError): decision_data(d,self.chips,'2026-11-06')

    def test_partial_market_blocked(self):
        d=self.daily[~self.daily.Date.eq('2026-11-06') | self.daily.Ticker.eq('2254')]
        with self.assertRaises(ValueError): decision_data(d,self.chips,'2026-11-06')

    def test_duplicate_keys_and_invalid_counts(self):
        p=self.tmp/'chips.csv'
        d=pd.read_csv(ROOT/'chip_seed_through_20261106.csv.gz')
        pd.concat([d,d.head(1)]).to_csv(p,index=False)
        with self.assertRaises(ValueError): read_chips(p)
        d.loc[0,'HolderLe10Lots']=-1;d.to_csv(p,index=False)
        with self.assertRaises(ValueError): read_chips(p)

    def test_weekly_gap_disables_signal(self):
        p=self.tmp/'chips.csv'
        pd.DataFrame(dict(SnapshotDate=[20261001,20261008,20261029],Ticker=['A']*3,HolderLe10Lots=[100,90,80],RetailPeopleValid=[True]*3)).to_csv(p,index=False)
        self.assertTrue(read_chips(p).delta.isna().all())

    def test_rehearsal_zero_lots(self):
        self.assertTrue(all(r['lots_for_manual_review']==0 for r in self.rank()))

    def test_hypothetical_budget_and_reserve(self):
        rows=self.rank(simulate=True)
        lots=[r['simulation_lots'] for r in rows]
        self.assertTrue(all(r['authorized_lots']==0 and r['lots_for_manual_review']==0 for r in rows))
        self.assertEqual(lots,[1]*5)
        costs=[100000*1.0025]*5
        self.assertTrue(all(c<=180000 for c in costs))
        self.assertGreaterEqual(1000000-sum(costs),100000)
        self.assertTrue(all(r['simulation_lots']==0 for r in self.rank(cash=100000,simulate=True)))

    def test_unknown_gate_and_wrong_date_block(self):
        for kw in [dict(risk='UNKNOWN'),dict(asof='2026-11-05')]:
            self.assertTrue(all(r['simulation_lots']==0 for r in self.rank(simulate=True,**kw)))

    def test_prospective_blocked_regardless_of_timestamp(self):
        for timestamp in ['2026-11-06T16:00:00+08:00','2026-11-05T14:00:00+08:00']:
            f=self.prospective();f['generated_at']=timestamp
            with self.assertRaises(ValueError): self.rank(f)
        f=self.prospective();f['decision']='2026-10-30'
        with self.assertRaises(ValueError): self.rank(f)

    def test_whitespace_duplicate_ticker(self):
        p=self.tmp/'x.csv';p.write_text('ticker,reference_price\n2254,110\n 2254,111\n')
        with self.assertRaises(ValueError): read_csv_by_ticker(p)

    def test_no_candidates_has_stable_columns(self):
        chips=self.chips.copy(); chips['delta']=0.0
        result=screen(self.daily,chips,14,pd.Timestamp('2026-11-06'))
        self.assertTrue(result.empty)
        self.assertIn('ticker',result.columns)
        self.assertTrue(result.sort_values(['liquidity','ticker']).empty)

    def test_invalid_daily_price_blocked(self):
        p=self.tmp/'daily.csv'
        pd.DataFrame(dict(Date=['2026-11-06'],Ticker=['A'],Close=[-1],Volume=[1000],Turnover=[1000])).to_csv(p,index=False)
        with self.assertRaises(ValueError): read_daily(p)

    def test_stale_chip_block(self):
        with self.assertRaises(ValueError): decision_data(self.daily,self.chips[self.chips.Date.lt('2026-10-01')],'2026-11-06')


if __name__=='__main__': unittest.main()
