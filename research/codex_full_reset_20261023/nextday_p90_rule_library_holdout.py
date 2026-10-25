#!/usr/bin/env python3
from __future__ import annotations
import json, math, statistics
from pathlib import Path
import research.codex_full_reset_20261023.ranking_v13_weak_regime_profiles as v13

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'research/codex_full_reset_20261023/nextday_p90_rule_library_holdout_result.json'
EVENTS=ROOT/'research/codex_full_reset_20261023/nextday_p90_rule_holdout_events.jsonl'
V6=(.20,.25,.30,.05,.20)
TRAIN_START='2023-01-01';TRAIN_END='2023-12-31'
TEST_START='2024-01-01';TEST_END='2026-10-22'
MIN_TRAIN=15
MIN_TEST=20
MIN_TEST_PER_YEAR=5
COST_STRESS=(0.0,0.002,0.004)
Z95=1.959963984540054

# Finite preregistered rule library. No grid and no mutation after seeing holdout outcomes.
RULES=[
 ('R00_STRONG', lambda r: r['breadth20']>=.50),
 ('R01_SCORE80', lambda r: r['breadth20']>=.50 and r['score']>=.80),
 ('R02_SCORE82', lambda r: r['breadth20']>=.50 and r['score']>=.82),
 ('R03_MARGIN02', lambda r: r['breadth20']>=.50 and r['margin']>=.02),
 ('R04_MARGIN03', lambda r: r['breadth20']>=.50 and r['margin']>=.03),
 ('R05_BREADTH60', lambda r: r['breadth20']>=.60),
 ('R06_BREADTH70', lambda r: r['breadth20']>=.70),
 ('R07_SCORE80_MARGIN02', lambda r: r['breadth20']>=.50 and r['score']>=.80 and r['margin']>=.02),
 ('R08_SCORE80_BREADTH60', lambda r: r['breadth20']>=.60 and r['score']>=.80),
 ('R09_MOM_SKIP90', lambda r: r['breadth20']>=.50 and r['mom20']>=.90 and r['skip5_60']>=.90),
 ('R10_RESID_MOM90', lambda r: r['breadth20']>=.50 and r['resid_rev']>=.90 and r['mom20']>=.90),
 ('R11_SCORE80_SKIP90', lambda r: r['breadth20']>=.50 and r['score']>=.80 and r['skip5_60']>=.90),
 ('R12_SCORE80_LOWVOL50', lambda r: r['breadth20']>=.50 and r['score']>=.80 and r['lowvol']>=.50),
 ('R13_LIQ70_LOWVOL50', lambda r: r['breadth20']>=.50 and r['liquidity']>=.70 and r['lowvol']>=.50),
 ('R14_RESID85_LOWVOL50', lambda r: r['breadth20']>=.50 and r['resid_rev']>=.85 and r['lowvol']>=.50),
 ('R15_SCORE80_MOM90_LOWVOL50', lambda r: r['breadth20']>=.50 and r['score']>=.80 and r['mom20']>=.90 and r['lowvol']>=.50),
]


def wilson_lower(w,n,z=Z95):
    if n<=0:return None
    p=w/n;z2=z*z;den=1+z2/n
    center=p+z2/(2*n)
    rad=z*math.sqrt(p*(1-p)/n+z2/(4*n*n))
    return (center-rad)/den


def top1_v6(d):
    F=v13.features.get(d,{})
    if not F:return None
    arr=[]
    for t,vals in F.items():
        score=sum(V6[i]*vals[i] for i in range(5))
        arr.append((score,t,vals))
    arr.sort(key=lambda z:(-z[0],z[1]))
    if not arr:return None
    score,t,vals=arr[0]
    second=arr[1][0] if len(arr)>1 else score
    return score,t,vals,score-second


def overnight_outcome(signal_date,t):
    i=v13.dates.index(signal_date)
    if i+2>=len(v13.dates):return None
    entry_date=v13.dates[i+1];exit_date=v13.dates[i+2]
    e=v13.by[entry_date].get(t);x=v13.by[exit_date].get(t)
    if not e or not x or e.o is None or x.c is None or e.o<=0 or x.c<=0 or e.bad or x.bad:return None
    return x.c/e.o-1,entry_date,exit_date


def summarize(rows,cost=0.0):
    rs=[r['overnight_return']-cost for r in rows]
    wins=sum(x>0 for x in rs);n=len(rs)
    nav=1.;peak=1.;mdd=0.
    for x in rs:
        nav*=1+x;peak=max(peak,nav);mdd=min(mdd,nav/peak-1)
    return {'trades':n,'wins':wins,'losses':n-wins,'win_rate':wins/n if n else None,'wilson95_lower':wilson_lower(wins,n) if n else None,'compounded_return':nav-1 if n else 0.0,'mean_return':statistics.mean(rs) if rs else None,'median_return':statistics.median(rs) if rs else None,'worst_return':min(rs) if rs else None,'max_drawdown':mdd}

rows=[]
for d in v13.dates:
    if d<TRAIN_START or d>TEST_END:continue
    top=top1_v6(d)
    if not top:continue
    score,t,vals,margin=top
    out=overnight_outcome(d,t)
    if not out:continue
    ret,entry_date,exit_date=out
    rows.append({'signal_date':d,'entry_date':entry_date,'exit_date':exit_date,'ticker':t,'score':score,'margin':margin,'breadth20':v13.breadth.get(d,0.0),'resid_rev':vals[0],'mom20':vals[1],'skip5_60':vals[2],'liquidity':vals[3],'lowvol':vals[4],'overnight_return':ret})

train=[r for r in rows if TRAIN_START<=r['signal_date']<=TRAIN_END]
test=[r for r in rows if TEST_START<=r['signal_date']<=TEST_END]
train_results=[]
for name,fn in RULES:
    sel=[r for r in train if fn(r)]
    sm=summarize(sel,0.0)
    sm['rule']=name
    sm['eligible_train']=len(sel)>=MIN_TRAIN
    train_results.append(sm)
elig=[x for x in train_results if x['eligible_train']]
if not elig:raise RuntimeError('no eligible train rules')
# Predeclared selection criterion: maximize 95% Wilson lower bound; ties by more trades, then rule name.
elig.sort(key=lambda x:(-(x['wilson95_lower'] if x['wilson95_lower'] is not None else -1),-x['trades'],x['rule']))
champ=elig[0]
champ_name=champ['rule'];champ_fn=dict(RULES)[champ_name]
held=[r for r in test if champ_fn(r)]

with EVENTS.open('w',encoding='utf-8') as fh:
    for r in held:fh.write(json.dumps(r,ensure_ascii=False)+'\n')

years={}
for y,(s,e) in v13.PERIODS.items():
    ys=[r for r in held if s<=r['signal_date']<=e]
    years[y]={str(c):summarize(ys,c) for c in COST_STRESS}
combined={str(c):summarize(held,c) for c in COST_STRESS}
per_year_ok=all(years[y]['0.0']['trades']>=MIN_TEST_PER_YEAR for y in ('2024','2025','2026'))
sample_ok=combined['0.0']['trades']>=MIN_TEST and per_year_ok
p90=sample_ok and combined['0.0']['win_rate'] is not None and combined['0.0']['win_rate']>=.90
p90_20=sample_ok and combined['0.002']['win_rate'] is not None and combined['0.002']['win_rate']>=.90
if p90:status='RULE_P90_HOLDOUT_QUALIFIED'
elif held and not sample_ok:status='RULE_P90_HOLDOUT_TOO_SPARSE'
elif held:status='RULE_P90_HOLDOUT_REJECTED_BELOW_90'
else:status='RULE_P90_HOLDOUT_NO_TRADES'
res={
 'status':status,
 'objective':'finite rule-library test for >=90% realized next-day win rate with nonzero coverage',
 'timing':'signal after t close; enter t+1 open; exit t+2 close',
 'selection_period':'2023 only',
 'holdout_period':'2024-01-01 through 2026-10-22',
 'method':'Evaluate exactly 16 preregistered STRONG-regime rule profiles on 2023 only; among rules with >=15 train trades choose the one with highest 95% Wilson lower bound, tie by more trades then rule name; freeze it and evaluate 2024-2026. No holdout-driven retuning.',
 'rule_library_size':len(RULES),
 'selected_rule':champ_name,
 'selected_rule_train':champ,
 'all_train_rules':train_results,
 'sample_rule':{'min_holdout_total':MIN_TEST,'min_holdout_each_year_2024_2025_2026':MIN_TEST_PER_YEAR},
 'years':years,'combined':combined,'sample_ok':sample_ok,'p90_gross_qualified':p90,'p90_after_20bp_stress_qualified':p90_20,
 'events_file':str(EVENTS.relative_to(ROOT)),
 'new_model_evaluations':1,
 'research_boundary':'single 16-rule library selected on 2023 and frozen on 2024-2026; do not add rules or change thresholds after holdout review',
 'authority':{'research_only':True,'capital_authority_twd':0,'broker_order_execution':False,'production_promotion':False,'merge_authorized':False},
 'caveat':'This is a historical holdout inside an already-exposed archive, not a guarantee of future performance. The rule library was fixed before this run, but the broader research history has been seen.'
}
OUT.write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(res,ensure_ascii=False,indent=2))
