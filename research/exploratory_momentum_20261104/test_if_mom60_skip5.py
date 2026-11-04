from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from if_mom60_skip5 import BASE, trade, choose

OUT=Path(__file__).resolve().parent

def test_trade_deducts_full_budget_fee_reserve():
    t=trade(102.5,115,.004)
    assert t['lots']*1000*102.5*1.004<=BASE

def test_no_pseudo_five_sequential_trades():
    a=pd.read_csv(OUT/'all84_three_strategies_40_80bp.csv',dtype={'ticker':str})
    assert set(a.strategy)=={'MOM60_SKIP5','MOM20_SIMPLE','N2_FROZEN'}
    assert len(a)==84*3*2
    assert len(a.signal.unique())==84
    assert all(a.groupby(['signal','strategy','cost']).size().eq(1))

def test_flat_no_lot_is_idle():
    x=trade(7_000,7_200,.004)
    assert x['lots']==0 and x['pnl']==0 and x['status']=='UNAFFORDABLE_NO_TRADE'

def test_exit_unpriced_blocks_entire_event():
    x=trade(100,np.nan,.004)
    assert x['status']=='EXIT_DATA_BLOCKED' and x['pnl'] is None

def test_entry_unpriced_blocks():
    x=trade(np.nan,150,.004)
    assert x['status']=='ENTRY_DATA_BLOCKED' and x['pnl'] is None

def test_tie_breaker_deterministic():
    assert choose(['2301','2302'],pd.Series({'2302':1.,'2301':1.}),True)=='2301'

def test_84_orig_selections_match_frozen_ledger():
    out=pd.read_csv(OUT/'all84_three_strategies_40_80bp.csv',dtype={'ticker':str})
    prior=pd.read_csv('/mnt/data/n2_top1_fixed5m_20261104/all84_trades_fixed5m.csv',dtype={'ticker':str})
    n=out[(out.cost==.004)&out.strategy.eq('N2_FROZEN')].sort_values('signal')
    prior=prior.sort_values('signal')
    assert n.ticker.tolist()==prior.ticker.tolist()
    assert n.signal.tolist()==prior.signal.tolist()
    assert n.entry.tolist()==prior.entry.tolist()
    assert n.exit.tolist()==prior.exit.tolist()

def test_no_unpriced_candidate_silently_dropped():
    data=pd.read_csv(OUT/'all84_three_strategies_40_80bp.csv')
    assert len(data.query('strategy=="MOM60_SKIP5" and cost==0.004'))==84
    assert data.query('strategy=="MOM60_SKIP5" and cost==0.004').pnl.notna().all()

def test_80bp_not_better_due_to_costs():
    df=pd.read_csv(OUT/'all84_three_strategies_40_80bp.csv')
    a=df[df.cost.eq(.004)].set_index(['signal','strategy'])
    b=df[df.cost.eq(.008)].set_index(['signal','strategy'])
    # varying budget reserves may change lots, so compare group aggregates, not all individual pnls.
    sm=pd.read_csv(OUT/'strategy_summary.csv')
    for s in sm.strategy.unique():
        x=sm[sm.strategy.eq(s)].set_index('cost').total_pnl_if_complete
        assert x.loc[.004]>=x.loc[.008]

def test_candidate_failed_both_simple_benchmarks():
    sm=pd.read_csv(OUT/'strategy_summary.csv').query('cost==0.004').set_index('strategy')
    assert sm.loc['MOM60_SKIP5','total_pnl_if_complete']<sm.loc['MOM20_SIMPLE','total_pnl_if_complete']
    assert sm.loc['MOM60_SKIP5','total_pnl_if_complete']<sm.loc['N2_FROZEN','total_pnl_if_complete']

def test_random_pool_missing_candidates_not_filled_with_zero():
    d=pd.read_csv(OUT/'random_null_pool_coverage.csv')
    assert len(d)==168
    incomplete=d.query('unpriced_pool>0')
    assert len(incomplete)>0
    assert incomplete.random_expected_pnl_if_complete.isna().all()

def test_data_limitations_never_claim_production():
    j=json.loads((OUT/'summary.json').read_text())
    assert j['frozen_events']==84
    assert j['future_oos']=='NOT_AVAILABLE'
    assert j['opening_fills']=='DATA_BLOCKED_ALL'
    assert j['corporate_actions']=='NOT_TOTAL_RETURN_CERTIFIED'
    assert j['status']!='TRADING_GO'
