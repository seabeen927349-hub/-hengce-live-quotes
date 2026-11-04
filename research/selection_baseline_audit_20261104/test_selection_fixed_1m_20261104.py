#!/usr/bin/env python3
"""Independent output and accounting tests, fixed-NT$1m no compounding, research only."""
import unittest
import json
from pathlib import Path
import numpy as np
import pandas as pd

D=Path('/mnt/data/selection_fixed_1m_20261104')
E=pd.read_csv(D/'events_fixed_1m.csv',keep_default_na=False)
P=pd.read_csv(D/'positions_fixed_1m.csv',keep_default_na=False)
R=pd.read_csv(D/'n0_taiex_window_comparison_fixed_1m.csv',keep_default_na=False)
S=json.loads((D/'summary_fixed_1m.json').read_text())
B=json.loads((D/'paired_descriptive_comparisons.json').read_text())


def fl(x):return float(x)

class FixedOneMillionAuditTest(unittest.TestCase):
    def test_01_event_count(self): self.assertEqual(S['events'],84)
    def test_02_events_each_strategy(self): self.assertEqual(E.strategy.value_counts().to_dict(),{'N1':84,'N2':84})
    def test_03_five_selections(self): self.assertTrue(all(E.selected_tickers.str.count(',')==4))
    def test_04_positions_count(self): self.assertEqual(P.shape[0],840)
    def test_05_no_compounding(self): self.assertTrue(np.allclose(P[P.lots>0].invested.div(P[P.lots>0].lots).values,1000.*P[P.lots>0].entry_open.values))
    def test_06_lot_board(self): self.assertTrue((P.shares==P.lots*1000).all())
    def test_07_per_ticker_sleeve(self): self.assertTrue((P.invested<=200000.000001).all())
    def test_08_per_event_max_capital(self): self.assertTrue((E.invested<=1000000.000001).all())
    def test_09_per_event_cash_reconciles(self): self.assertTrue(np.allclose(E.invested+E.cash_unused,1000000))
    def test_10_duplicate_events(self): self.assertFalse(E.duplicated(['signal','strategy']).any())
    def test_11_rank_no_dupes(self): self.assertTrue(all(len(set(x.split(',')))==5 for x in E.selected_tickers))
    def test_12_no_duplicate_ticker_per_event(self): self.assertFalse(P.duplicated(['signal','strategy','ticker']).any())
    def test_13_price_only_formula(self):
        v=P[P.status=='PRICE_ONLY_PRICED']
        expected=v.shares*(v.exit_close.astype(float)-v.entry_open.astype(float))-.004*v.invested
        self.assertTrue(np.allclose(v.pnl_40bp.astype(float),expected))
    def test_14_80bp_adjustment(self):
        v=P[P.status=='PRICE_ONLY_PRICED']
        self.assertTrue(np.allclose(v.pnl_80bp.astype(float),v.pnl_40bp.astype(float)-.004*v.invested.astype(float)))
    def test_15_event_40bp_reconciliation(self):
        for _,e in E.iterrows():
            v=P[(P.signal==e.signal)&(P.strategy==e.strategy)]
            if e.status=='PRICE_ONLY_COMPLETE': self.assertAlmostEqual(fl(e.pnl_40bp),v.loc[v.status=='PRICE_ONLY_PRICED','pnl_40bp'].astype(float).sum(),places=4)
    def test_16_event_80bp_reconciliation(self):
        for _,e in E.iterrows():
            v=P[(P.signal==e.signal)&(P.strategy==e.strategy)]
            if e.status=='PRICE_ONLY_COMPLETE': self.assertAlmostEqual(fl(e.pnl_80bp),v.loc[v.status=='PRICE_ONLY_PRICED','pnl_80bp'].astype(float).sum(),places=4)
    def test_17_N1_missing_block(self): self.assertEqual(S['strategies']['N1']['blocked_events'],1)
    def test_18_N2_no_missing_block(self): self.assertEqual(S['strategies']['N2']['blocked_events'],0)
    def test_19_missing_price_never_pnl(self): self.assertTrue((P[P.status=='EXIT_CLOSE_MISSING_BLOCKED'].pnl_40bp=='').all())
    def test_20_event_block_no_partial_capital(self): self.assertTrue((E[E.status=='EXIT_PRICE_BLOCKED'].pnl_40bp=='').all())
    def test_21_missing_exit_identity(self):
        v=P[P.status=='EXIT_CLOSE_MISSING_BLOCKED']
        self.assertEqual(v.ticker.tolist(),[2316]);self.assertEqual(v['exit'].iloc[0],'2019-10-01')
    def test_22_rights_flag_not_cash(self):
        v=P[P.rights_unresolved==True]
        self.assertTrue(all(('權' in str(t)) for t in v.corporate_action_types))
    def test_23_N2_equal_event_count(self): self.assertEqual(S['strategies']['N2']['fully_priced_events'],84)
    def test_24_annual_sums(self):
        for s in ('N1','N2'):
            k=S['strategies'][s];self.assertAlmostEqual(k['aggregate_price_only_pnl_40bp_on_priced_events'],sum(x['pnl_40bp'] for x in k['by_year'].values()),places=2)
    def test_25_annual_counts(self):
        for s in ('N1','N2'):
            k=S['strategies'][s];self.assertEqual(sum(v['events'] for v in k['by_year'].values()),84)
    def test_26_noncompound_average(self):
        for s in ('N1','N2'):
            k=S['strategies'][s];self.assertAlmostEqual(k['average_return_on_fixed_1m_per_priced_event'],k['aggregate_price_only_pnl_40bp_on_priced_events']/(k['fully_priced_events']*1000000))
    def test_27_no_final_capital_promotion(self): self.assertTrue(all('capital_final' not in k for k in S['strategies'].values()))
    def test_28_random_draw_count(self): self.assertEqual(S['random_N3']['draws'],10000)
    def test_29_random_missing_counts(self): self.assertEqual(S['random_N3']['blocked_price_paths']+S['random_N3']['complete_price_paths'],10000)
    def test_30_random_not_formal(self): self.assertTrue(S['random_N3']['conditional_on_future_price_completeness'])
    def test_31_no_stock_selection_authority(self): self.assertEqual(S['trading_authority'],'NONE')
    def test_32_N0_incomplete_not_priced(self): self.assertEqual(int((R.n0_price_only_equalweight_pct!='').sum()),78)
    def test_33_2026_oct_not_fake_month_end(self): self.assertEqual(S['last_exit'],'2026-09-30')
    def test_34_3m_sample_count(self): self.assertEqual(S['strategies']['N2']['recent_3m']['events'],3)
    def test_35_same_windows_benchmarks(self): self.assertEqual(len(R),84)
    def test_36_paired_N2_N1_83(self): self.assertEqual(B['n2_vs_n1']['pairs'],83)
    def test_37_paired_N2_N0_78(self): self.assertEqual(B['n2_vs_n0']['pairs'],78)
    def test_38_paired_N2_TAIEX_84(self): self.assertEqual(B['n2_vs_taiex_close_signal']['pairs'],84)
    def test_39_all_events_month_end_from_old_frozen_study(self):
        old=pd.read_csv('/mnt/data/selection_baseline_audit_20261104/baseline_event_summary.csv')
        n2=E[E.strategy=='N2']
        self.assertEqual(n2.signal.tolist(),old.signal.tolist())
        self.assertEqual(n2.entry.tolist(),old.entry.tolist())
        self.assertEqual(n2['exit'].tolist(),old['exit'].tolist())
    def test_40_no_enter_after_exit(self): self.assertTrue((pd.to_datetime(E.entry)<pd.to_datetime(E['exit'])).all())
    def test_41_no_overlapping_events(self):
        n2=E[E.strategy=='N2'].reset_index(drop=True)
        self.assertTrue((pd.to_datetime(n2['exit'].iloc[:-1].to_numpy())<pd.to_datetime(n2.entry.iloc[1:].to_numpy())).all())
    def test_42_rights_not_declared_validated(self): self.assertEqual(S['alpha_verdict'],'INCONCLUSIVE')
    def test_43_n2_cash_scenario_nonzero(self): self.assertGreater(S['strategies']['N2']['total_cash_dividend_only_scenario_on_priced_events'],0)
    def test_44_no_negative_cash(self): self.assertTrue((E.cash_unused>=-1e-7).all())
    def test_45_no_transaction_fee_in_invalid_positions(self): self.assertTrue(all((r['pnl_40bp']=='' or r['status']=='PRICE_ONLY_PRICED') for _,r in P.iterrows()))

if __name__=='__main__':unittest.main(verbosity=2)