#!/usr/bin/env python3
"""HENGCE frozen-research monthly N0/N1/N2/N3: per-event NT$1m, NO compounding.

Rules were separately pre-registered at GitHub commit 0bbddd856a1e74e68350b294c222ac63ce5cac35.
Research only; not a capital-authorized system, PIT-certified backtest, or total-return series.
Depends on the frozen prior standalone baseline loader for the exact universe/Top100.
"""
from __future__ import annotations
import csv
import hashlib
import json
import math
import zipfile
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

from hengce_selection_baseline_20261104 import load, picks, YEARS, SOURCE

CAPITAL=1_000_000.0
SLEEVE=200_000.0
K=5
TOP=100
COSTS=(0.004,0.008)
DRAWS=10000
SEED=20261031
OUT=Path('/mnt/data/selection_fixed_1m_20261104')
PREREG_SHA='0bbddd856a1e74e68350b294c222ac63ce5cac35'


def number(x):
    if x is None:return None
    try:
        v=float(x)
    except (TypeError,ValueError):return None
    return v if math.isfinite(v) else None


def load_actions():
    frames=[]
    for year in YEARS:
        with zipfile.ZipFile(SOURCE/f'TWSE_ELECTRONICS_{year}.zip') as z:
            df=pd.read_csv(z.open(f'corporate_actions_{year}.csv'),dtype={'ticker':str})
        for c in ('rights_plus_dividend_value','previous_close','ex_reference'):
            df[c]=pd.to_numeric(df[c].astype(str).str.replace(',','',regex=False),errors='coerce')
        frames.append(df[['date','ticker','event_type','rights_plus_dividend_value','previous_close','ex_reference']])
    a=pd.concat(frames,ignore_index=True).sort_values(['ticker','date','event_type'])
    # Do not alter or dedupe source records silently.
    by={t:g.to_dict('records') for t,g in a.groupby('ticker')}
    return a,by


def events_on_trade(by,t,entry,exitd):
    return [x for x in by.get(t,()) if entry<x['date']<=exitd]


def test_periods(op,cl,median60,count60,r20,r5,taiex):
    dates=cl.index.tolist()
    complete={pd.Period(d,freq='M') for d in dates if int(d[:4])<2026}
    complete.update(pd.Period(f'2026-{m:02}',freq='M') for m in range(1,10))
    last={}
    for j,d in enumerate(dates):
        if pd.Period(d,freq='M') in complete:last[pd.Period(d,freq='M')]=j
    busy_through=-1
    for i in sorted(last.values()):
        if i<59 or i+20>=len(dates) or i<busy_through:continue
        sig=dates[i];enter=dates[i+1];exitd=dates[i+20]
        universe=median60.iloc[i].where((count60.iloc[i]>=50)&cl.iloc[i].gt(0))
        eligible=[t for t,_ in sorted(universe.dropna().items(),key=lambda x:(-x[1],x[0]))[:TOP]]
        if len(eligible)<TOP:continue
        n1=[x[0] for x in picks(r20.loc[sig,eligible],True)]
        n2=[x[0] for x in picks(r5.loc[sig,eligible],False)]
        if len(n1)!=K or len(n2)!=K:continue
        busy_through=i+20
        yield {'i':i,'signal':sig,'entry':enter,'exit':exitd,'eligible':eligible,'N1':n1,'N2':n2}


def one_position(t,rank,opn,cls,actions,signal,entry,exitd,strategy):
    opened=number(opn)
    closed=number(cls)
    lots=math.floor(SLEEVE/(opened*1000)) if opened is not None and opened>0 else 0
    shares=1000*lots
    invested=shares*opened if lots else 0.
    if opened is None or opened<=0:status='ENTRY_OPEN_MISSING'
    elif lots==0:status='UNAFFORDABLE_BOARD_LOT_200K_SLEEVE'
    elif closed is None or closed<=0:status='EXIT_CLOSE_MISSING_BLOCKED'
    else:status='PRICE_ONLY_PRICED'
    a=[{'date':ev['date'],'type':ev['event_type'],'value':number(ev['rights_plus_dividend_value'])} for ev in actions]
    # Only cash-only ex-dividend events are eligible for a NONAUTHORITATIVE receivable approximation.
    cash=float(sum(float(ev['value']) for ev in a if ev['type']=='息' and ev['value'] is not None))*shares if lots else 0.
    rights=bool(lots and any(ev['type']!='息' for ev in a))
    if lots and any(ev['type']=='息' and ev['value'] is None for ev in a):rights=True
    pnl40=(shares*(closed-opened)-.004*invested) if status=='PRICE_ONLY_PRICED' else None
    pnl80=(shares*(closed-opened)-.008*invested) if status=='PRICE_ONLY_PRICED' else None
    return {'strategy':strategy,'signal':signal,'entry':entry,'exit':exitd,'ticker':t,'rank':rank,'entry_open':opened,
            'exit_close':closed,'lots':lots,'shares':shares,'invested':invested,'status':status,
            'pnl_40bp':pnl40,'pnl_80bp':pnl80,'cash_only_dividend_scenario':cash,
            'rights_unresolved':rights,'corporate_action_count':len(a),'corporate_action_types':';'.join(ev['type'] for ev in a),
            'corporate_action_details':json.dumps(a,ensure_ascii=False,sort_keys=True)}


def random_without_replacement(rng,N):
    ids=np.empty((DRAWS,K),dtype=np.int16)
    for k in range(K):
        x=rng.integers(N,size=DRAWS)
        if k:
            duplicate=(ids[:,:k]==x[:,None]).any(axis=1)
            while duplicate.any():
                x[duplicate]=rng.integers(N,size=int(duplicate.sum()))
                duplicate=(ids[:,:k]==x[:,None]).any(axis=1)
        ids[:,k]=x
    assert np.all(np.array([len(set(row))==K for row in ids]))
    return ids


def summarize(strategy,events,positions):
    sub=[e for e in events if e['strategy']==strategy]
    pos=[p for p in positions if p['strategy']==strategy]
    good=[e for e in sub if e['status']=='PRICE_ONLY_COMPLETE']
    closed=[p for p in pos if p['status']=='PRICE_ONLY_PRICED']
    blocked=[e for e in sub if e['status']=='EXIT_PRICE_BLOCKED']
    pnl=[float(e['pnl_40bp']) for e in good]
    pnls=sorted((float(p['pnl_40bp']) for p in closed),reverse=True)
    winners=sorted(pnl,reverse=True)
    years={}
    for year in sorted({e['signal'][:4] for e in sub}):
        a=[e for e in sub if e['signal'].startswith(year)]
        x=[e for e in a if e['status']=='PRICE_ONLY_COMPLETE']
        years[year]={ 'events':len(a),'priced_events':len(x),'blocked_events':len(a)-len(x),
                      'pnl_40bp':round(sum(float(e['pnl_40bp']) for e in x),2),
                      'avg_pnl_per_1m_priced_event':round(sum(float(e['pnl_40bp']) for e in x)/len(x),2) if x else None,
                      'positive_events':sum(float(e['pnl_40bp'])>0 for e in x),
                      'cash_dividend_scenario':round(sum(float(e['cash_dividend_scenario']) for e in x),2),
                      'events_with_rights':sum(bool(e['unresolved_rights']) for e in a)}
    return {'events':len(sub),'fully_priced_events':len(good),'blocked_events':len(blocked),
            'bought_positions':sum(p['lots']>0 for p in pos),
            'priced_positions':len(closed),'unfilled_positions':sum(p['lots']==0 for p in pos),
            'positions_with_corporate_actions':sum(p['lots']>0 and p['corporate_action_count']>0 for p in pos),
            'positions_with_rights_unresolved':sum(p['lots']>0 and p['rights_unresolved'] for p in pos),
            'positions_with_pretax_cash_dividend_approx':sum(p['lots']>0 and p['cash_only_dividend_scenario']>0 for p in pos),
            'fixed_notional_per_event':CAPITAL,
            'aggregate_price_only_pnl_40bp_on_priced_events':round(sum(pnl),2),
            'aggregate_price_only_pnl_80bp_on_priced_events':round(sum(float(e['pnl_80bp']) for e in good),2),
            'average_price_only_pnl_per_priced_1m_event':round(sum(pnl)/len(pnl),2) if pnl else None,
            'average_return_on_fixed_1m_per_priced_event':sum(pnl)/(len(pnl)*CAPITAL) if pnl else None,
            'all_84_windows_certified_price_only':len(good)==len(sub),
            'positive_event_count':sum(x>0 for x in pnl),'negative_event_count':sum(x<0 for x in pnl),'zero_event_count':sum(x==0 for x in pnl),
            'median_priced_event_pnl':round(float(np.median(pnl)),2) if pnl else None,
            'total_cash_dividend_only_scenario_on_priced_events':round(sum(float(e['cash_dividend_scenario']) for e in good),2),
            'scenario_cash_only_augmented_pnl_40bp_if_rights_still_unresolved':round(sum(float(e['pnl_40bp'])+float(e['cash_dividend_scenario']) for e in good),2),
            'remove_best_positions_pnl_40bp':{str(k):round(sum(pnl)-sum(pnls[:k]),2) for k in (1,3,5)},
            'remove_best_events_pnl_40bp':{str(k):round(sum(pnl)-sum(winners[:k]),2) for k in (1,3,5)},
            'mean_capital_fraction_invested_per_event':float(np.mean([e['invested']/CAPITAL for e in sub])),
            'min_event_pnl':min(pnl) if pnl else None,'max_event_pnl':max(pnl) if pnl else None,
            'by_year':years,
            'recent_3m':{ 'first_exit_cutoff':'2026-07-27','events':sum(e['exit']>='2026-07-27' for e in sub),
                         'priced_events':sum(e['exit']>='2026-07-27' and e['status']=='PRICE_ONLY_COMPLETE' for e in sub),
                         'pnl_40bp':round(sum(float(e['pnl_40bp']) for e in good if e['exit']>='2026-07-27'),2)},
            'blocking_events':[{ 'signal':e['signal'],'entry':e['entry'],'exit':e['exit'], 'unpriced_tickers':e['unpriced_tickers']} for e in blocked]}


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    op,cl,m60,n60,r20,r5,cp,taiex,src=load()
    allactions,byaction=load_actions()
    allwindows=list(test_periods(op,cl,m60,n60,r20,r5,taiex))
    old=pd.read_csv('/mnt/data/selection_baseline_audit_20261104/baseline_event_summary.csv')
    assert len(allwindows)==len(old)==84
    for w,(_,v) in zip(allwindows,old.iterrows()):
        assert w['signal']==v['signal'] and w['entry']==v['entry'] and w['exit']==v['exit']
        assert str(w['N1'])==v['N1_tickers'] and str(w['N2'])==v['N2_tickers']
    pos=[]; evs=[]; N0=[]; ndraw40=np.zeros(DRAWS);ndraw80=np.zeros(DRAWS);blocked_path=np.zeros(DRAWS,dtype=bool)
    n3_ca_path=np.zeros(DRAWS,dtype=bool);n3_rights_path=np.zeros(DRAWS,dtype=bool)
    yearly_random=defaultdict(lambda:{'pnl40':np.zeros(DRAWS),'blocked':np.zeros(DRAWS,dtype=bool)})
    rng=np.random.Generator(np.random.PCG64(SEED))
    for w in allwindows:
        sig,enter,exitd=w['signal'],w['entry'],w['exit'];elig=w['eligible']
        ov=op.loc[enter,elig].to_numpy(dtype=float);cv=cl.loc[exitd,elig].to_numpy(dtype=float)
        flags=(cp.loc[exitd,elig]-cp.loc[enter,elig]).to_numpy(dtype=float)>0
        # theoretical N0 only when ALL 100 names have complete prices; no future-data filtering.
        valid=(np.isfinite(ov)&(ov>0)&np.isfinite(cv)&(cv>0))
        n0ret=float((cv/ov-1).mean()-0.004) if valid.all() else None
        taiex_old=float(taiex.loc[sig]);taiex_exit=float(taiex.loc[exitd]);taiex_enter_close=float(taiex.loc[enter]);
        txp=CAPITAL*(taiex_exit/taiex_old-1) if taiex_old>0 else None
        txe=CAPITAL*(taiex_exit/taiex_enter_close-1) if taiex_enter_close>0 else None
        N0.append({'signal':sig,'entry':enter,'exit':exitd,'complete_name_count':int(valid.sum()),
                   'n0_price_only_equalweight_pct':n0ret,'n0_full_100_complete':bool(valid.all()),
                   'taiex_signal_close_to_exit_close_1m_pnl':txp,
                   'taiex_entry_session_close_to_exit_close_1m_pnl':txe,
                   'n0_any_actions':int(flags.sum())})
        for strat in ('N1','N2'):
            rec=[]
            for k,t in enumerate(w[strat]):
                r=one_position(t,k+1,op.loc[enter,t],cl.loc[exitd,t],events_on_trade(byaction,t,enter,exitd),sig,enter,exitd,strat)
                i=w['i']; start=i-(20 if strat=='N1' else 5)
                r['signal_lookback_corporate_action_count']=int(cp.loc[sig,t]-cp.iloc[start][t])
                rec.append(r)
            pos.extend(rec)
            bad=[r['ticker'] for r in rec if r['status']=='EXIT_CLOSE_MISSING_BLOCKED']
            if bad:
                state='EXIT_PRICE_BLOCKED';pnl40=None;pnl80=None
            else:
                state='PRICE_ONLY_COMPLETE';pnl40=round(sum(r['pnl_40bp'] for r in rec if r['pnl_40bp'] is not None),2)
                pnl80=round(sum(r['pnl_80bp'] for r in rec if r['pnl_80bp'] is not None),2)
            evs.append({'signal':sig,'entry':enter,'exit':exitd,'strategy':strat,
                        'status':state,'selected_tickers':','.join(w[strat]),
                        'pnl_40bp':pnl40,'pnl_80bp':pnl80,
                        'return_on_fixed_1m':pnl40/CAPITAL if pnl40 is not None else None,
                        'invested':round(sum(r['invested'] for r in rec),2),
                        'cash_unused':round(CAPITAL-sum(r['invested'] for r in rec),2),
                        'bought_positions':sum(r['lots']>0 for r in rec),
                        'missing_entry_count':sum(r['status']=='ENTRY_OPEN_MISSING' for r in rec),
                        'unaffordable_count':sum(r['status']=='UNAFFORDABLE_BOARD_LOT_200K_SLEEVE' for r in rec),
                        'unpriced_tickers':','.join(bad),
                        'cash_dividend_scenario':round(sum(r['cash_only_dividend_scenario'] for r in rec),2),
                        'unresolved_rights':any(r['rights_unresolved'] for r in rec),
                        'corporate_action_positions':sum(r['lots']>0 and r['corporate_action_count']>0 for r in rec),
                        'lookback_action_selected_names':sum(r['signal_lookback_corporate_action_count']>0 for r in rec)})
        ids=random_without_replacement(rng,len(elig));pickopen=ov[ids];pickclose=cv[ids]
        okopen=np.isfinite(pickopen)&(pickopen>0)
        l=np.floor(SLEEVE/(np.where(okopen,pickopen,np.inf)*1000)).astype(np.int32)
        openval=np.where(okopen,pickopen,0)
        invested=l*1000*openval
        needclose=l>0
        missing=(needclose&(~np.isfinite(pickclose)|(pickclose<=0))).any(axis=1)
        blocked_path|=missing;yearly_random[sig[:4]]['blocked']|=missing
        n3_ca_path|=(needclose&flags[ids]).any(axis=1)
        # Corporate action types: any flagged cash or rights, no cash amount used in random formal comparator.
        vv=l*1000*(np.where(np.isfinite(pickclose),pickclose,0)-openval)
        vv[~needclose]=0
        part40=(vv-.004*invested).sum(axis=1)
        part80=(vv-.008*invested).sum(axis=1)
        # All paths with any missing purchased exit are excluded ONLY from descriptive complete-path distribution.
        ndraw40+=np.where(missing,0,part40)
        ndraw80+=np.where(missing,0,part80)
        yearly_random[sig[:4]]['pnl40']+=np.where(missing,0,part40)
        assert (invested.sum(axis=1)<=CAPITAL+1e-6).all()
    pd.DataFrame(pos).to_csv(OUT/'positions_fixed_1m.csv',index=False)
    pd.DataFrame(evs).to_csv(OUT/'events_fixed_1m.csv',index=False)
    pd.DataFrame(N0).to_csv(OUT/'n0_taiex_window_comparison_fixed_1m.csv',index=False)
    summary={'authority':'RESEARCH_PRICE_ONLY_FIXED_1M_NO_COMPOUND','trading_authority':'NONE','alpha_verdict':'INCONCLUSIVE',
             'preregistration_commit':PREREG_SHA,'source_shas':{k:v['sha256'] for k,v in src.items()},
             'fixed_capital_each_event':CAPITAL,'sleeve_per_selected_ticker':SLEEVE,'events':len(allwindows),
             'first_signal':allwindows[0]['signal'],'last_exit':allwindows[-1]['exit'],
             'strategies':{name:summarize(name,evs,pos) for name in ('N1','N2')},
             'matched_n0_taiex':{},'random_N3':{},'warnings':[]}
    n0=[x['n0_price_only_equalweight_pct'] for x in N0 if x['n0_price_only_equalweight_pct'] is not None]
    x=[z['taiex_signal_close_to_exit_close_1m_pnl'] for z in N0 if z['taiex_signal_close_to_exit_close_1m_pnl'] is not None]
    xc=[z['taiex_entry_session_close_to_exit_close_1m_pnl'] for z in N0 if z['taiex_entry_session_close_to_exit_close_1m_pnl'] is not None]
    summary['matched_n0_taiex']={'N0_full_price_100_name_events':len(n0),'N0_theoretical_equalweight_mean_net_event_return_full_cases':float(np.mean(n0)),
         'N0_sum_theoretical_fixed_1m_pnl_over_full_cases':round(sum(n0)*CAPITAL,2),
         'TAIEX_84_price_index_signal_close_to_exit_sum_fixed_1m_pnl':round(sum(x),2),
         'TAIEX_84_entry_session_close_to_exit_sum_fixed_1m_pnl':round(sum(xc),2),
         'TAIEX_84_mean_return_signal_close':float(np.mean(x)/CAPITAL),
         'benchmarks_not_entry_open_execution_equivalent':True,
         'N0_unpriced_100_name_windows':len(N0)-len(n0)}
    good=~blocked_path
    if good.any():
        sorted40=np.sort(ndraw40[good]);q=np.quantile(sorted40,[.05,.5,.95]);
        summary['random_N3']={'draws':DRAWS,'complete_price_paths':int(good.sum()),'blocked_price_paths':int(blocked_path.sum()),
                               'complete_price_path_pnl40_p05_p50_p95':[round(float(z),2) for z in q],
                               'complete_price_path_median_pnl80':round(float(np.median(ndraw80[good])),2),
                               'paths_with_any_corporate_action':int(n3_ca_path.sum()),
                               'conditional_on_future_price_completeness':True,
                               'N2_vs_conditioned_random_percentile_EXPLORATORY_ONLY':float(np.mean(ndraw40[good]<summary['strategies']['N2']['aggregate_price_only_pnl_40bp_on_priced_events']))}
    summary['random_N3']['by_year_price_complete_path_diagnostics']={y:{'complete_paths':int((~z['blocked']).sum()),
        'conditional_median_fixed_capital_pnl':round(float(np.median(z['pnl40'][~z['blocked']])),2) if (~z['blocked']).any() else None} for y,z in yearly_random.items()}
    # Conditional paired N1 and N2 comparison on the EXACT matched dates; not survivor-free formal comparison.
    pn1={e['signal']:e for e in evs if e['strategy']=='N1'};pn2={e['signal']:e for e in evs if e['strategy']=='N2'}
    shared=[d for d in pn1 if pn1[d]['pnl_40bp'] is not None and pn2[d]['pnl_40bp'] is not None]
    deltas=np.array([pn2[d]['pnl_40bp']-pn1[d]['pnl_40bp'] for d in shared],float)
    # Paired no-retuning bootstrap of yearly blocks, including same-date correlation; descriptive given 9 vintages.
    years=sorted(set(x[:4] for x in shared));blocks=[deltas[[d[:4]==y for d in shared]] for y in years]
    rngb=np.random.Generator(np.random.PCG64(20261104))
    draws=[]
    for _ in range(5000):
        order=rngb.integers(len(years),size=len(years))
        sampled=np.concatenate([blocks[int(i)] for i in order]);draws.append(float(np.mean(sampled)))
    lo,hi=np.percentile(draws,[2.5,97.5]);
    summary['paired_n2_minus_n1_price_only']={'matched_priced_events':len(shared),'N2_sum_pnl_matched':round(sum(pn2[d]['pnl_40bp'] for d in shared),2),
        'N1_sum_pnl_matched':round(sum(pn1[d]['pnl_40bp'] for d in shared),2),
        'N2_minus_N1_mean_per_1m_event':float(np.mean(deltas)),
        'year_block_resampled_5000_mean_difference_CI95': [float(lo),float(hi)],
        'bootstrap_is_descriptive_not_prospective':True}
    summary['warnings']=[
        'Noncompounded sum of fixed-1m event PnL is not a live terminal equity curve: 84 independent funded windows cannot be collapsed into a 1m continuously invested portfolio.',
        'Price-only research PnL is not investor total return: dividends are unverified scenarios, rights/stock dividends are unresolved, and potential adjustments/survivorship/PIT require independent work.',
        'N1 has missing purchased exit price on one event; no formal complete 84-event aggregate. All subsequent fixed-capital events remain interpretable independent of this blocked earlier event.',
        'N3 conditional complete-path distribution excludes paths based on future exit availability, so not a certified random-null p-value.',
        'TAIEX lacks index open and is only same-window close-index reference. N0 equalweight 100 is not board-lot executable with NT$1m.',
        'This is a historical price-only 2018–2026 study with 2025-26 already exposed: NOT genuinely prospective OOS.',
        'Monthly end-of-month signals through 2026-08 only; source 2026-10 is incomplete.',
        'PIT electronic membership is sourced from historical archived daily TWSE files, not yet externally certified as-of legal common-stock registry.',
        'One lot/one-fifth sleeve may produce significant unused cash; no optimizing to improve deployment.'
    ]
    (OUT/'summary_fixed_1m.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'events':len(evs)//2,'N1':summary['strategies']['N1'],'N2':summary['strategies']['N2'],
        'N3':summary['random_N3'],'N0_TAIEX':summary['matched_n0_taiex'],'paired':summary['paired_n2_minus_n1_price_only']},ensure_ascii=False,indent=2))
    return summary

if __name__=='__main__':main()