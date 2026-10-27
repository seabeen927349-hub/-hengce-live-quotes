#!/usr/bin/env python3
from __future__ import annotations

import contextlib
import io
import json
import math
import statistics
from pathlib import Path

with contextlib.redirect_stdout(io.StringIO()):
    import research.codex_full_reset_20261023.ranking_v13_weak_regime_profiles as v13

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'research/codex_full_reset_20261023/HR2_HIGH_COVERAGE_RESULT_20261025.json'
EVENTS = ROOT / 'research/codex_full_reset_20261023/hr2_high_coverage_champion_events.jsonl'

DEV = ('2024-01-01','2024-12-31')
VAL = ('2025-01-01','2025-12-31')
TRAIN = ('2024-01-01','2025-12-31')
HOLDOUT = ('2026-01-01','2026-10-22')
H = 10
COST_DIAG = 0.012
V6 = (0.20,0.25,0.30,0.05,0.20)
DATES = v13.dates
DI = {d:i for i,d in enumerate(DATES)}


def wilson_lower(w,n,z=1.959963984540054):
    if n<=0:return None
    p=w/n; den=1+z*z/n
    return (p+z*z/(2*n)-z*math.sqrt(p*(1-p)/n+z*z/(4*n*n)))/den


def product(xs):
    z=1.0
    for x in xs:z*=1+x
    return z-1

# Frozen V6 top-1 signal metadata on each eligible date.
SIG={}
for d,F in v13.features.items():
    arr=[]
    for t,vals in F.items():
        s=sum(V6[k]*vals[k] for k in range(5))
        arr.append((s,t,vals))
    arr.sort(key=lambda x:(-x[0],x[1]))
    if len(arr)<2:continue
    s,t,vals=arr[0]
    SIG[d]={
        'ticker':t,'score':s,'gap':s-arr[1][0],'breadth20':v13.breadth[d],
        'resid_rev_rank':vals[0],'mom20_rank':vals[1],'skip5_60_rank':vals[2],
        'liquidity_rank':vals[3],'lowvol_rank':vals[4],
    }


def entry_gap(signal_i,ticker):
    ei=signal_i+1
    if ei>=len(DATES):return None
    s=v13.by[DATES[signal_i]].get(ticker); e=v13.by[DATES[ei]].get(ticker)
    if not s or not e or s.c is None or e.o is None or s.c<=0 or e.o<=0:return None
    return e.o/s.c-1


def path(signal_i,ticker,end):
    ei=signal_i+1; xi=ei+H
    if xi>=len(DATES) or DATES[xi]>end:return None
    er=v13.by[DATES[ei]].get(ticker)
    if not er or er.o is None or er.o<=0:return None
    entry=er.o
    for j in range(ei+1,xi+1):
        r=v13.by[DATES[j]].get(ticker)
        if not r or r.c is None or r.c<=0 or r.bad:return None
        ret=r.c/entry-1
        if ret>0:
            return {'win':True,'entry_date':DATES[ei],'exit_date':DATES[j],'entry_open':entry,'exit_close':r.c,'gross_return':ret,'hold':j-ei,'exit_i':j}
    r=v13.by[DATES[xi]].get(ticker)
    if not r or r.c is None or r.c<=0 or r.bad:return None
    ret=r.c/entry-1
    return {'win':ret>0,'entry_date':DATES[ei],'exit_date':DATES[xi],'entry_open':entry,'exit_close':r.c,'gross_return':ret,'hold':H,'exit_i':xi}

# Finite preregistered refinement library. All gates use information available by entry open.
CANDS=[{'name':'BASELINE_97'}]
for x in (.35,.40,.45,.50,.55,.60): CANDS.append({'name':f'BREADTH_MIN_{x:.2f}','breadth_min':x})
for x in (.45,.50,.55,.60,.65): CANDS.append({'name':f'BREADTH_MAX_{x:.2f}','breadth_max':x})
for x in (.78,.80,.82,.84,.86,.88): CANDS.append({'name':f'SCORE_MIN_{x:.2f}','score_min':x})
for x in (.005,.010,.015,.020,.030,.040): CANDS.append({'name':f'GAP_MIN_{x:.3f}','gap_min':x})
for field in ('resid_rev_rank','mom20_rank','skip5_60_rank','liquidity_rank','lowvol_rank'):
    for x in (.40,.50,.60,.70): CANDS.append({'name':f'{field.upper()}_MIN_{x:.2f}',field:x})
for thr in (.50,.60):
    for k in (2,3,4): CANDS.append({'name':f'CONSENSUS_{thr:.2f}_ATLEAST_{k}','consensus_thr':thr,'consensus_k':k})
for x in (.10,.20,.30): CANDS.append({'name':f'WEAKEST_FACTOR_MIN_{x:.2f}','weakest_min':x})
for x in (.00,.01,.02,.03,.05): CANDS.append({'name':f'ENTRY_GAP_MAX_{x:.2f}','entry_gap_max':x})
for x in (.02,.03,.05): CANDS.append({'name':f'ENTRY_ABS_GAP_MAX_{x:.2f}','entry_abs_gap_max':x})
# A small set of explicit two-gate hypotheses, declared before seeing 2026 outcomes.
CANDS += [
 {'name':'B45_LV50','breadth_min':.45,'lowvol_rank':.50},
 {'name':'B50_LV50','breadth_min':.50,'lowvol_rank':.50},
 {'name':'B45_MOM50','breadth_min':.45,'mom20_rank':.50},
 {'name':'LV50_MOM50','lowvol_rank':.50,'mom20_rank':.50},
 {'name':'LV60_SKIP50','lowvol_rank':.60,'skip5_60_rank':.50},
 {'name':'RES50_LV50','resid_rev_rank':.50,'lowvol_rank':.50},
 {'name':'MOM50_SKIP50','mom20_rank':.50,'skip5_60_rank':.50},
 {'name':'B45_CONS3','breadth_min':.45,'consensus_thr':.50,'consensus_k':3},
 {'name':'B50_CONS3','breadth_min':.50,'consensus_thr':.50,'consensus_k':3},
 {'name':'SCORE82_LV50','score_min':.82,'lowvol_rank':.50},
]


def passes(c,s,eg):
    if s['score'] < c.get('score_min',.75): return False
    if s['gap'] < c.get('gap_min',0.0): return False
    if 'breadth_min' in c and s['breadth20'] < c['breadth_min']: return False
    if 'breadth_max' in c and s['breadth20'] >= c['breadth_max']: return False
    for f in ('resid_rev_rank','mom20_rank','skip5_60_rank','liquidity_rank','lowvol_rank'):
        if f in c and s[f] < c[f]: return False
    if 'weakest_min' in c:
        if min(s[f] for f in ('resid_rev_rank','mom20_rank','skip5_60_rank','liquidity_rank','lowvol_rank')) < c['weakest_min']: return False
    if 'consensus_thr' in c:
        cnt=sum(s[f]>=c['consensus_thr'] for f in ('resid_rev_rank','mom20_rank','skip5_60_rank','liquidity_rank','lowvol_rank'))
        if cnt<c['consensus_k']: return False
    if eg is None:return False
    if 'entry_gap_max' in c and eg>c['entry_gap_max']:return False
    if 'entry_abs_gap_max' in c and abs(eg)>c['entry_abs_gap_max']:return False
    return True


def simulate(c,start,end,include=False):
    ev=[]; next_free=-1; invalid=0; seen=0
    for i,d in enumerate(DATES):
        if d<start or d>end or i<next_free:continue
        s=SIG.get(d)
        if not s:continue
        eg=entry_gap(i,s['ticker'])
        if not passes(c,s,eg):continue
        seen+=1
        o=path(i,s['ticker'],end)
        if o is None:
            invalid+=1;continue
        e={'signal_date':d,**s,'entry_gap':eg,**o}
        ev.append(e);next_free=o['exit_i']
    n=len(ev);w=sum(e['win'] for e in ev);rets=[e['gross_return'] for e in ev];holds=[e['hold'] for e in ev]
    m={'trades':n,'wins':w,'losses':n-w,'win_rate':w/n if n else None,'wilson95_lower':wilson_lower(w,n),'eligible_signals':seen,'invalid_paths':invalid,
       'mean_gross_return':statistics.mean(rets) if rets else None,'median_gross_return':statistics.median(rets) if rets else None,'worst_gross_return':min(rets) if rets else None,
       'compounded_gross_return':product(rets) if rets else None,'after_1p2pct_cost_positive_rate':sum(r>COST_DIAG for r in rets)/n if n else None,
       'mean_hold':statistics.mean(holds) if holds else None,'median_hold':statistics.median(holds) if holds else None}
    if include:m['events']=ev
    return m

base_dev=simulate(CANDS[0],*DEV);base_val=simulate(CANDS[0],*VAL);base_train=simulate(CANDS[0],*TRAIN);base_hold=simulate(CANDS[0],*HOLDOUT)

rows=[]
for c in CANDS:
    dev=simulate(c,*DEV); val=simulate(c,*VAL); train=simulate(c,*TRAIN)
    if not dev['trades'] or not val['trades']:continue
    row={'rule':c,'dev_2024':dev,'validation_2025':val,'train_2024_2025':train,
         'dev_coverage_vs_baseline':dev['trades']/base_dev['trades'],
         'val_coverage_vs_baseline':val['trades']/base_val['trades'],
         'train_coverage_vs_baseline':train['trades']/base_train['trades']}
    rows.append(row)


def key(r):
    a=r['dev_2024'];b=r['validation_2025'];p=r['train_2024_2025']
    return (min(a['win_rate'],b['win_rate']), b['win_rate'], p['win_rate'], p['wilson95_lower'], p['trades'])

pool85=[r for r in rows if r['dev_coverage_vs_baseline']>=.85 and r['val_coverage_vs_baseline']>=.85]
pool70=[r for r in rows if r['dev_coverage_vs_baseline']>=.70 and r['val_coverage_vs_baseline']>=.70]
pool85.sort(key=key,reverse=True);pool70.sort(key=key,reverse=True)
champ85=pool85[0] if pool85 else None
champ70=pool70[0] if pool70 else None
for ch in (champ85,champ70):
    if ch is not None:ch['holdout_2026']=simulate(ch['rule'],*HOLDOUT)

# Event ledger for the 85%-coverage champion; this is the primary continuation of the original 97-trade line.
if champ85 is not None:
    with EVENTS.open('w',encoding='utf-8') as fh:
        for label,(s,e) in [('DEV_2024',DEV),('VALIDATION_2025',VAL),('HOLDOUT_2026',HOLDOUT)]:
            mm=simulate(champ85['rule'],s,e,include=True)
            for x in mm['events']:
                x['split']=label;fh.write(json.dumps(x,ensure_ascii=False)+'\n')

res={
 'status':'HR2_HIGH_COVERAGE_REFINEMENT_COMPLETE',
 'objective':'improve gross directional hit rate of HR1 97-trade V6 top1 / H10 line without collapsing coverage',
 'protocol':{
   'development':'2024','validation':'2025','locked_holdout':'2026-01-01..2026-10-22',
   'selection_key':'maximize min(2024 win rate, 2025 win rate), then 2025 win rate, pooled win rate, Wilson lower, trade count',
   'primary_min_coverage_each_preholdout_year':.85,'secondary_min_coverage_each_preholdout_year':.70,
   'max_hold':H,'entry':'next trading-day open','exit':'first later close > entry open else H10 close',
   'candidate_count':len(CANDS),'candidate_library':'finite signal-day/entry-open gates only; no 2026-informed patching'
 },
 'baseline_97_reference':{'dev_2024':base_dev,'validation_2025':base_val,'train_2024_2025':base_train,'holdout_2026':base_hold},
 'primary_85pct_coverage_champion':champ85,
 'secondary_70pct_coverage_champion':champ70,
 'top10_primary_pool':pool85[:10],
 'top10_secondary_pool':pool70[:10],
 'authority':{'research_only':True,'capital_authority_twd':0,'broker_order_execution':False,'production_promotion':False,'merge_authorized':False},
 'caveat':'2026 is locked for HR2 selection but has been exposed elsewhere in the broader project, so it is a historical diagnostic rather than untouched future OOS.'
}
OUT.write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('HR2_RESULT='+json.dumps(res,ensure_ascii=False,separators=(',',':')))
