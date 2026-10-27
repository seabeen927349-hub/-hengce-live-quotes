#!/usr/bin/env python3
from __future__ import annotations
import json, math, statistics
from pathlib import Path
import research.codex_full_reset_20261023.ranking_v13_weak_regime_profiles as v13

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'research/codex_full_reset_20261023/nextday_precision_ceiling_result.json'
EVENTS=ROOT/'research/codex_full_reset_20261023/nextday_precision_ceiling_primary_events.jsonl'
V6=(.20,.25,.30,.05,.20)
TRAIN_START='2023-01-01';TRAIN_END='2023-12-31'
VALID_START='2024-01-01';VALID_END='2024-12-31'
HOLD_START='2025-01-01';HOLD_END='2026-10-22'
L2=.10;LEARNING_RATE=.05;STEPS=3000
Z95=1.959963984540054
COST_STRESS=(0.0,0.002)
COVERAGES=(.50,.35,.25,.20,.15,.10,.075,.05)
GATES=(('ALL',0.0),('B50',.50),('B60',.60),('B70',.70))
TIERS={
 '20':{'valid_min':10,'hold_min':20,'per_year':5},
 '30':{'valid_min':15,'hold_min':30,'per_year':10},
 '60':{'valid_min':30,'hold_min':60,'per_year':20},
 '120':{'valid_min':60,'hold_min':120,'per_year':40},
}


def sigmoid(z):
    if z>=0:
        e=math.exp(-z);return 1/(1+e)
    e=math.exp(z);return e/(1+e)

def wilson_lower(w,n,z=Z95):
    if n<=0:return None
    p=w/n;z2=z*z;den=1+z2/n
    center=p+z2/(2*n)
    rad=z*math.sqrt(p*(1-p)/n+z2/(4*n*n))
    return (center-rad)/den

def quantile(vals,q):
    a=sorted(vals)
    if not a:return None
    if len(a)==1:return a[0]
    x=(len(a)-1)*q;i=int(math.floor(x));j=int(math.ceil(x))
    if i==j:return a[i]
    return a[i]*(j-x)+a[j]*(x-i)

def top1_v6(d):
    F=v13.features.get(d,{})
    if not F:return None
    arr=[]
    for t,vals in F.items():
        score=sum(V6[i]*vals[i] for i in range(5))
        arr.append((score,t,vals))
    arr.sort(key=lambda z:(-z[0],z[1]))
    if not arr:return None
    score,t,vals=arr[0];second=arr[1][0] if len(arr)>1 else score
    return score,t,vals,score-second

def overnight_outcome(signal_date,t):
    i=v13.dates.index(signal_date)
    if i+2>=len(v13.dates):return None
    entry_date=v13.dates[i+1];exit_date=v13.dates[i+2]
    e=v13.by[entry_date].get(t);x=v13.by[exit_date].get(t)
    if not e or not x or e.o is None or x.c is None or e.o<=0 or x.c<=0 or e.bad or x.bad:return None
    return x.c/e.o-1,entry_date,exit_date

def features_for(d,t,score,margin,vals):
    r=v13.by[d].get(t)
    breadth=v13.breadth.get(d,0.0)
    base=[score,margin,breadth,vals[0],vals[1],vals[2],vals[3],vals[4]]
    if r is None:return base+[0.0]*7
    r1=r.r1 if r.r1 is not None and math.isfinite(r.r1) else 0.0
    r5=r.r5 if r.r5 is not None and math.isfinite(r.r5) else 0.0
    r20=r.r20 if r.r20 is not None and math.isfinite(r.r20) else 0.0
    body=(r.c/r.o-1) if r.c is not None and r.o is not None and r.o>0 else 0.0
    ta=(r.turn/r.turn20) if r.turn is not None and r.turn20 is not None and r.turn20>0 else 0.0
    ta_log=math.log1p(max(0.0,ta))
    vol20=r.vol20 if r.vol20 is not None and math.isfinite(r.vol20) else 0.0
    turn_log=math.log1p(max(0.0,r.turn if r.turn is not None else 0.0))
    return base+[r1,r5,r20,body,ta_log,vol20,turn_log]
def fit_standardizer(xs):
    mu=[];sd=[]
    for j in range(len(xs[0])):
        col=[x[j] for x in xs];m=statistics.mean(col);s=statistics.pstdev(col)
        mu.append(m);sd.append(s if s>1e-12 else 1.0)
    return mu,sd
def standardize(x,mu,sd):return [(x[j]-mu[j])/sd[j] for j in range(len(x))]
def fit_logit(xs,ys,idxs):
    w=[0.0]*(len(idxs)+1);n=len(xs)
    for _ in range(STEPS):
        g=[0.0]*len(w)
        for x,y in zip(xs,ys):
            z=w[0]+sum(w[k+1]*x[j] for k,j in enumerate(idxs));p=sigmoid(z);e=p-y
            g[0]+=e
            for k,j in enumerate(idxs):g[k+1]+=e*x[j]
        g[0]/=n
        for k in range(1,len(w)):g[k]=g[k]/n+L2*w[k]
        for k in range(len(w)):w[k]-=LEARNING_RATE*g[k]
    return w
def pred_logit(w,x,idxs):return sigmoid(w[0]+sum(w[k+1]*x[j] for k,j in enumerate(idxs)))
def knn_prob(train_x,train_y,x,k):
    ds=[]
    p=len(x)
    for tx,y in zip(train_x,train_y):
        ds.append((sum((x[j]-tx[j])**2 for j in range(p))/p,y))
    ds.sort(key=lambda z:z[0]);near=ds[:min(k,len(ds))]
    return sum(y for _,y in near)/len(near) if near else .5

def summarize(rows,cost=0.0):
    rs=[r['overnight_return']-cost for r in rows];n=len(rs);w=sum(x>0 for x in rs)
    nav=1.;peak=1.;mdd=0.
    for x in rs:
        nav*=1+x;peak=max(peak,nav);mdd=min(mdd,nav/peak-1)
    return {'trades':n,'wins':w,'losses':n-w,'win_rate':w/n if n else None,'wilson95_lower':wilson_lower(w,n) if n else None,'compounded_return':nav-1 if n else 0.0,'mean_return':statistics.mean(rs) if rs else None,'median_return':statistics.median(rs) if rs else None,'worst_return':min(rs) if rs else None,'max_drawdown':mdd}

rows=[]
for d in v13.dates:
    if d<TRAIN_START or d>HOLD_END:continue
    top=top1_v6(d)
    if not top:continue
    score,t,vals,margin=top;out=overnight_outcome(d,t)
    if not out:continue
    ret,entry_date,exit_date=out
    rows.append({'signal_date':d,'entry_date':entry_date,'exit_date':exit_date,'ticker':t,'breadth20':v13.breadth.get(d,0.0),'overnight_return':ret,'x_raw':features_for(d,t,score,margin,vals)})
train=[r for r in rows if TRAIN_START<=r['signal_date']<=TRAIN_END]
valid=[r for r in rows if VALID_START<=r['signal_date']<=VALID_END]
hold=[r for r in rows if HOLD_START<=r['signal_date']<=HOLD_END]
if not train or not valid or not hold:raise RuntimeError('missing train/valid/hold rows')
mu,sd=fit_standardizer([r['x_raw'] for r in train])
for r in rows:r['x']=standardize(r['x_raw'],mu,sd)
train_x=[r['x'] for r in train];train_y=[1 if r['overnight_return']>0 else 0 for r in train]
BASE=list(range(8));EXP=list(range(15))
w_base=fit_logit(train_x,train_y,BASE);w_exp=fit_logit(train_x,train_y,EXP)

def score_models(r):
    x=r['x'];lb=pred_logit(w_base,x,BASE);le=pred_logit(w_exp,x,EXP)
    k15=knn_prob(train_x,train_y,x,15);k30=knn_prob(train_x,train_y,x,30);k60=knn_prob(train_x,train_y,x,60)
    return {'LOGIT_V6':lb,'LOGIT_EXP':le,'KNN15':k15,'KNN30':k30,'KNN60':k60,'BLEND':(le+k30)/2}
for r in valid+hold:r['scores']=score_models(r)

configs=[]
for model in ('LOGIT_V6','LOGIT_EXP','KNN15','KNN30','KNN60','BLEND'):
    for gate_name,gate in GATES:
        pool=[r for r in valid if r['breadth20']>=gate]
        vals=[r['scores'][model] for r in pool]
        if not vals:continue
        for cov in COVERAGES:
            thr=quantile(vals,1-cov)
            sel=[r for r in pool if r['scores'][model]>=thr]
            sm=summarize(sel,0.0)
            configs.append({'id':f'{model}_{gate_name}_TOP{cov:g}','model':model,'gate_name':gate_name,'gate':gate,'coverage':cov,'threshold':thr,'validation':sm})

def hold_for(c):return [r for r in hold if r['breadth20']>=c['gate'] and r['scores'][c['model']]>=c['threshold']]
def hold_sample_ok(sel,tier):
    rule=TIERS[tier]
    y25=sum('2025-01-01'<=r['signal_date']<='2025-12-31' for r in sel)
    y26=sum('2026-01-01'<=r['signal_date']<='2026-10-22' for r in sel)
    return len(sel)>=rule['hold_min'] and y25>=rule['per_year'] and y26>=rule['per_year'],y25,y26

tier_results={}
for tier,rule in TIERS.items():
    elig=[c for c in configs if c['validation']['trades']>=rule['valid_min']]
    elig.sort(key=lambda c:(-(c['validation']['wilson95_lower'] if c['validation']['wilson95_lower'] is not None else -1),-(c['validation']['win_rate'] or -1),-c['validation']['trades'],c['id']))
    c=elig[0];sel=hold_for(c);ok,y25,y26=hold_sample_ok(sel,tier)
    tier_results[tier]={'selected_config':{k:c[k] for k in ('id','model','gate_name','gate','coverage','threshold')},'selection_basis':'2024 validation Wilson95 lower bound only','validation':c['validation'],'holdout':{str(cost):summarize(sel,cost) for cost in COST_STRESS},'holdout_2025_trades':y25,'holdout_2026_trades':y26,'sample_ok':ok}

# Descriptive oracle envelope: explicitly non-deployable, because it selects after seeing holdout.
oracle={}
for tier in TIERS:
    candidates=[]
    for c in configs:
        sel=hold_for(c);ok,y25,y26=hold_sample_ok(sel,tier)
        if not ok:continue
        sm=summarize(sel,0.0)
        candidates.append((sm['win_rate'],sm['wilson95_lower'],sm['trades'],c,sel,y25,y26))
    if candidates:
        candidates.sort(key=lambda z:(-z[0],-z[1],-z[2],z[3]['id']))
        wr,lcb,n,c,sel,y25,y26=candidates[0]
        oracle[tier]={'config':{k:c[k] for k in ('id','model','gate_name','gate','coverage','threshold')},'holdout':summarize(sel,0.0),'holdout_2025_trades':y25,'holdout_2026_trades':y26,'warning':'post-hoc holdout-selected descriptive upper envelope; not a valid deployable OOS estimate'}

primary=tier_results['30'];pc=primary['selected_config'];primary_sel=[r for r in hold if r['breadth20']>=pc['gate'] and r['scores'][pc['model']]>=pc['threshold']]
with EVENTS.open('w',encoding='utf-8') as fh:
    for r in primary_sel:
        fh.write(json.dumps({'signal_date':r['signal_date'],'entry_date':r['entry_date'],'exit_date':r['exit_date'],'ticker':r['ticker'],'breadth20':r['breadth20'],'model_score':r['scores'][pc['model']],'overnight_return':r['overnight_return']},ensure_ascii=False)+'\n')

top_valid=sorted(configs,key=lambda c:(-(c['validation']['wilson95_lower'] if c['validation']['wilson95_lower'] is not None else -1),-(c['validation']['win_rate'] or -1),-c['validation']['trades'],c['id']))[:10]
res={
 'status':'PRECISION_CEILING_COMPLETE',
 'objective':'bounded estimate of maximum next-day realized win rate versus coverage, without choosing on 2025-2026 holdout',
 'timing':'signal after t close; enter t+1 open; exit t+2 close',
 'train_period':'2023 only','validation_period':'2024 only','holdout_period':'2025-01-01 through 2026-10-22',
 'candidate_library':'6 frozen score models x 4 breadth gates x 8 top-score coverage levels = up to 192 configs; model weights fit on 2023 only, config selection on 2024 only, 2025-2026 untouched for honest evaluation in this run',
 'models':['LOGIT_V6','LOGIT_EXP','KNN15','KNN30','KNN60','BLEND'],'gates':dict(GATES),'coverages':COVERAGES,'candidate_count':len(configs),
 'tier_rules':TIERS,'tiers':tier_results,'primary_tier':'30','primary':primary,'primary_events_file':str(EVENTS.relative_to(ROOT)),
 'top10_validation_configs':[{**{k:c[k] for k in ('id','model','gate_name','coverage','threshold')},'validation':c['validation']} for c in top_valid],
 'oracle_descriptive_upper_envelope':oracle,
 'train_rows':len(train),'validation_rows':len(valid),'holdout_rows':len(hold),
 'model_details':{'base_feature_count':8,'expanded_feature_count':15,'expanded_additions':['r1','r5','r20','close/open body','turnover acceleration log','vol20','turnover log'],'l2':L2,'learning_rate':LEARNING_RATE,'steps':STEPS,'standardizer_mean':mu,'standardizer_sd':sd},
 'authority':{'research_only':True,'capital_authority_twd':0,'broker_order_execution':False,'production_promotion':False,'merge_authorized':False},
 'caveat':'Historical holdout inside an already-exposed research archive is not a guarantee of future performance. The honest tier configs are selected without using 2025-2026 outcomes in this run; the oracle envelope is deliberately labeled post-hoc and non-deployable.'
}
OUT.write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(res,ensure_ascii=False,indent=2))
