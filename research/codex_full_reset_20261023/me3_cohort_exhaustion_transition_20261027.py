from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[2]
FIXED_PATH=Path(__file__).with_name('frozen_fixed_capital_roundlot_20261026.py')
OUT=ROOT/'research/codex_full_reset_20261023/results/me3_cohort_exhaustion_transition_20261027'
OUT.mkdir(parents=True,exist_ok=True)
START=pd.Timestamp('2026-07-22'); END=pd.Timestamp('2026-10-21')
Y1=pd.Timestamp('2025-10-22'); Y2=pd.Timestamp('2026-10-21')


def load_mod(path,name):
    s=importlib.util.spec_from_file_location(name,path); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m

def run_cost(fixed,panel,start,end,label,cost):
    old=fixed.COST
    try:
        fixed.COST=cost
        return fixed.simulate(panel,start,end,label)
    finally:
        fixed.COST=old

def compact(s):
    keys=['raw_signals','selected_roundlot_trades','skipped_zero_lot','unique_signal_dates','total_pnl','win_rate','profit_factor','max_drawdown_amount','max_drawdown_pct','max_concurrent_positions','remove_best_trade_pnl','remove_top2_trades_pnl','remove_best_signal_date_pnl','remove_best_3_signal_dates_pnl','monthly_by_signal_date']
    return {k:s.get(k) for k in keys}

def monthly_quality(s):
    a=[r for r in (s.get('monthly_by_signal_date') or []) if int(r.get('count',0))>0]
    p=[r for r in a if float(r.get('sum',0))>0]
    return len(a),len(p)

def main():
    fixed=load_mod(FIXED_PATH,'fixed'); base=fixed.load_base_module()
    y26=base.load_2026(); hist,inv=base.load_history(); p=base.build_panel(hist,y26)
    # Exact baseline reproduction.
    tb,db,sb=run_cost(fixed,p,START,END,'BASE_3M',0.004)
    if not (int(sb['selected_roundlot_trades'])==39 and int(sb['unique_signal_dates'])==14 and abs(float(sb['total_pnl'])-92555.8)<10):
        raise RuntimeError('baseline mismatch')

    # Daily density of the already-frozen base cohort. No stock-level selector changes.
    d=p.groupby('Date').agg(n_market=('Ticker','size'),base_count=('base_candidate','sum')).reset_index().sort_values('Date')
    d['base_density']=d['base_count']/d['n_market']
    d['lag1_base_density']=d['base_density'].shift(1)
    # Reference for yesterday excludes yesterday itself: t-21..t-2, fully known at t close.
    d['lag1_prior20_median']=d['base_density'].shift(2).rolling(20,min_periods=10).median()
    d['density_contraction']=d['base_density'] < d['lag1_base_density']
    d['prior_day_elevated']=d['lag1_base_density'] > d['lag1_prior20_median']
    d['ME3_GATE']=d['prior_day_elevated'] & d['density_contraction']
    allowed=set(pd.to_datetime(d.loc[d['ME3_GATE'],'Date']))
    pg=p.copy(); pg['signal']=pg['signal'] & pg['Date'].isin(allowed)

    t40,e40,s40=run_cost(fixed,pg,START,END,'ME3_3M_40BP',0.004)
    t100,e100,s100=run_cost(fixed,pg,START,END,'ME3_3M_100BP',0.010)
    am,pm=monthly_quality(s40)
    checks={
      'days_ge_7': int(s40.get('unique_signal_dates',0))>=7,
      'trades_ge_15': int(s40.get('selected_roundlot_trades',0))>=15,
      'pnl40_positive': float(s40.get('total_pnl',0))>0,
      'pf40_ge_1_5': s40.get('profit_factor') is not None and float(s40['profit_factor'])>=1.5,
      'remove_top3_day_positive': float(s40.get('remove_best_3_signal_dates_pnl',-math.inf))>0,
      'mdd_not_worse': float(s40.get('max_drawdown_pct',-math.inf))>=float(sb['max_drawdown_pct'])-1e-12,
      'pnl100_positive': float(s100.get('total_pnl',0))>0,
      'pf100_gt_1': s100.get('profit_factor') is not None and float(s100['profit_factor'])>1,
      'active_months_ge_3': am>=3,
      'positive_months_ge_active_minus_1': pm>=max(0,am-1),
    }
    pass3=all(checks.values())
    res={
      'name':'ME3_COHORT_EXHAUSTION_TRANSITION',
      'rule':{
        'stock_selector':'FROZEN_UNCHANGED',
        'date_gate':['yesterday base_candidate density > median density of sessions t-21..t-2','today base_candidate density < yesterday base_candidate density'],
        'threshold_tuning':'NONE',
        'signal_time':'t close; all gate inputs known by t close'
      },
      'baseline_3m_40bp':compact(sb),
      'challenger_3m_40bp':compact(s40),
      'challenger_3m_100bp':compact(s100),
      'checks':checks,
      'three_month_decision':'SURVIVE_FREEZE' if pass3 else 'KILL',
      'one_year':None,
    }
    d.to_csv(OUT/'ME3_DAILY_COHORT_STATE.csv',index=False); t40.to_csv(OUT/'ME3_TRADES_3M.csv',index=False)
    if pass3:
        ty,ey,sy=run_cost(fixed,pg,Y1,Y2,'ME3_1Y_40BP',0.004)
        ty100,ey100,sy100=run_cost(fixed,pg,Y1,Y2,'ME3_1Y_100BP',0.010)
        pass1=(float(sy.get('total_pnl',0))>0 and sy.get('profit_factor') is not None and float(sy['profit_factor'])>1 and float(sy.get('remove_best_3_signal_dates_pnl',-math.inf))>0 and float(sy100.get('total_pnl',0))>0)
        res['one_year']={'frozen_40bp':compact(sy),'frozen_100bp':compact(sy100),'decision':'SURVIVE' if pass1 else 'KILL','rule_unchanged':True}
        ty.to_csv(OUT/'ME3_TRADES_1Y.csv',index=False)
    with open(OUT/'RESULT.json','w',encoding='utf-8') as f: json.dump(res,f,ensure_ascii=False,indent=2,allow_nan=True)
    print(json.dumps(res,ensure_ascii=False,indent=2,allow_nan=True))

if __name__=='__main__': main()
