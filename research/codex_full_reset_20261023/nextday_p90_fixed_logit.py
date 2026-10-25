#!/usr/bin/env python3
from __future__ import annotations
import json, math, statistics
from pathlib import Path
import research.codex_full_reset_20261023.ranking_v13_weak_regime_profiles as v13

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'research/codex_full_reset_20261023/nextday_p90_fixed_logit_result.json'
EVENTS=ROOT/'research/codex_full_reset_20261023/nextday_p90_events.jsonl'
V6=(.20,.25,.30,.05,.20)
TRAIN_START='2023-01-01'
TRAIN_END='2023-12-31'
EVAL_START='2024-01-01'
EVAL_END='2026-10-22'
PROB_THRESHOLD=.90
MIN_SAMPLE=30
MIN_PER_YEAR=5
L2=.10
LEARNING_RATE=.05
STEPS=4000
COST_STRESS=(0.0,0.002,0.004)


def sigmoid(z):
    if z>=0:
        e=math.exp(-z);return 1/(1+e)
    e=math.exp(z);return e/(1+e)


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


def raw_features(d,score,margin,vals):
    return [score,margin,v13.breadth.get(d,0.0),vals[0],vals[1],vals[2],vals[3],vals[4]]


def fit_standardizer(xs):
    mu=[];sd=[]
    for j in range(len(xs[0])):
        col=[x[j] for x in xs]
        m=statistics.mean(col)
        s=statistics.pstdev(col)
        mu.append(m);sd.append(s if s>1e-12 else 1.0)
    return mu,sd


def standardize(x,mu,sd):
    return [(x[j]-mu[j])/sd[j] for j in range(len(x))]


def fit_logit(xs,ys):
    # fixed full-batch gradient descent, intercept not regularized; no hyperparameter search
    p=len(xs[0]);w=[0.0]*(p+1);n=len(xs)
    for _ in range(STEPS):
        g=[0.0]*(p+1)
        for x,y in zip(xs,ys):
            z=w[0]+sum(w[j+1]*x[j] for j in range(p))
            pr=sigmoid(z);err=pr-y
            g[0]+=err
            for j in range(p):g[j+1]+=err*x[j]
        g[0]/=n
        for j in range(1,p+1):g[j]=g[j]/n+L2*w[j]
        for j in range(p+1):w[j]-=LEARNING_RATE*g[j]
    return w


def predict(w,x):
    return sigmoid(w[0]+sum(w[j+1]*x[j] for j in range(len(x))))


def summarize(events,cost):
    rs=[e['overnight_return']-cost for e in events]
    nav=1.;peak=1.;mdd=0.
    for r in rs:
        nav*=1+r;peak=max(peak,nav);mdd=min(mdd,nav/peak-1)
    wins=sum(r>0 for r in rs)
    return {'trades':len(rs),'wins':wins,'losses':len(rs)-wins,'win_rate':wins/len(rs) if rs else None,'compounded_return':nav-1 if rs else 0.0,'mean_return':statistics.mean(rs) if rs else None,'median_return':statistics.median(rs) if rs else None,'worst_return':min(rs) if rs else None,'max_drawdown':mdd}

rows=[]
for d in v13.dates:
    if d<TRAIN_START or d>EVAL_END:continue
    top=top1_v6(d)
    if top is None:continue
    score,t,vals,margin=top
    out=overnight_outcome(d,t)
    if out is None:continue
    ret,entry_date,exit_date=out
    rows.append({'signal_date':d,'entry_date':entry_date,'exit_date':exit_date,'ticker':t,'score':score,'margin_top1_top2':margin,'breadth20':v13.breadth.get(d,0.0),'regime':'STRONG' if v13.breadth.get(d,0)>=v13.BREADTH_CUTOFF else 'WEAK','factor_ranks':{'resid_rev':vals[0],'mom20':vals[1],'skip5_60':vals[2],'liquidity':vals[3],'lowvol':vals[4]},'x_raw':raw_features(d,score,margin,vals),'overnight_return':ret,'label':1 if ret>0 else 0})

train=[r for r in rows if TRAIN_START<=r['signal_date']<=TRAIN_END]
if not train:raise RuntimeError('no training rows')
mu,sd=fit_standardizer([r['x_raw'] for r in train])
train_x=[standardize(r['x_raw'],mu,sd) for r in train]
train_y=[r['label'] for r in train]
w=fit_logit(train_x,train_y)

all_eval=[];events=[]
for r in rows:
    if not (EVAL_START<=r['signal_date']<=EVAL_END):continue
    x=standardize(r['x_raw'],mu,sd)
    pr=predict(w,x)
    rec={k:v for k,v in r.items() if k!='x_raw'}
    rec['pred_up_probability']=pr
    rec['take_trade']=bool(r['regime']=='STRONG' and pr>=PROB_THRESHOLD)
    all_eval.append(rec)
    if rec['take_trade']:events.append(rec)

with EVENTS.open('w',encoding='utf-8') as fh:
    for e in events:fh.write(json.dumps(e,ensure_ascii=False)+'\n')

years={}
for y,(s,e) in v13.PERIODS.items():
    ys=[x for x in events if s<=x['signal_date']<=e]
    years[y]={str(c):summarize(ys,c) for c in COST_STRESS}
combined={str(c):summarize(events,c) for c in COST_STRESS}
per_year_ok=all(years.get(y,{}).get('0.0',{}).get('trades',0)>=MIN_PER_YEAR for y in ('2024','2025','2026'))
sample_ok=combined['0.0']['trades']>=MIN_SAMPLE and per_year_ok
p90_ok=sample_ok and combined['0.0']['win_rate'] is not None and combined['0.0']['win_rate']>=.90
p90_20bp_ok=sample_ok and combined['0.002']['win_rate'] is not None and combined['0.002']['win_rate']>=.90
if p90_ok:status='P90_OOS_QUALIFIED'
elif events and not sample_ok:status='P90_TOO_SPARSE'
elif events:status='P90_REJECTED_BELOW_90'
else:status='P90_NO_SIGNALS'
probs=[r['pred_up_probability'] for r in all_eval]
strong_probs=[r['pred_up_probability'] for r in all_eval if r['regime']=='STRONG']
# Fixed diagnostics only; not alternate decision thresholds.
top_conf=sorted(all_eval,key=lambda r:(-r['pred_up_probability'],r['signal_date']))[:20]
res={
 'status':status,
 'objective':'fixed 90% probability gate with nonzero minimum sample; no post-hoc threshold tuning',
 'timing':'signal after t close; enter t+1 open; exit t+2 close',
 'training':'2023 only',
 'evaluation':'2024-01-01 through 2026-10-22 OOS only',
 'method':'frozen V6 Top1 plus one fixed regularized logistic model on existing score, Top1 margin, breadth and five factor ranks. Model fit only on 2023 fully realized outcomes. In OOS, trade only in canonical STRONG regime when predicted up probability >= 0.90. No threshold/grid search.',
 'probability_threshold':PROB_THRESHOLD,
 'sample_rule':{'min_total_trades':MIN_SAMPLE,'min_trades_each_year_2024_2025_2026':MIN_PER_YEAR},
 'v6_weights':V6,'breadth_cutoff':v13.BREADTH_CUTOFF,
 'model':{'feature_order':['v6_score','top1_margin','breadth20','resid_rev_rank','mom20_rank','skip5_60_rank','liquidity_rank','lowvol_rank'],'standardizer_mean':mu,'standardizer_sd':sd,'weights_intercept_first':w,'l2':L2,'learning_rate':LEARNING_RATE,'steps':STEPS,'train_rows':len(train),'train_win_rate':sum(train_y)/len(train_y)},
 'diagnostics':{'eval_rows':len(all_eval),'strong_eval_rows':sum(r['regime']=='STRONG' for r in all_eval),'signals_at_90':len(events),'max_pred_probability_all_eval':max(probs) if probs else None,'max_pred_probability_strong_eval':max(strong_probs) if strong_probs else None,'top20_confidence_realized_win_rate':sum(r['label'] for r in top_conf)/len(top_conf) if top_conf else None},
 'years':years,'combined':combined,'sample_ok':sample_ok,'p90_gross_qualified':p90_ok,'p90_after_20bp_stress_qualified':p90_20bp_ok,
 'events_file':str(EVENTS.relative_to(ROOT)),
 'new_model_evaluations':1,
 'research_boundary':'single fixed P90 test; do not change 0.90 gate, regularization, features, or minimum sample on this exposed OOS period',
 'authority':{'research_only':True,'capital_authority_twd':0,'broker_order_execution':False,'production_promotion':False,'merge_authorized':False},
 'caveat':'Historical OOS simulation on an already-exposed research archive is not a guarantee of future gains; predicted probabilities are model scores, not certified probabilities.'
}
OUT.write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(res,ensure_ascii=False,indent=2))
