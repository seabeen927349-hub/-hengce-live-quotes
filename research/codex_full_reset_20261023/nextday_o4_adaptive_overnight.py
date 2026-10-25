#!/usr/bin/env python3
from __future__ import annotations

import json, math, statistics
from collections import Counter, defaultdict, deque
from pathlib import Path

import research.codex_full_reset_20261023.nextday_o3_delayed_close_overnight as o3

ROOT=Path(__file__).resolve().parents[2]
RESET=ROOT/'research/codex_full_reset_20261023'
OUT=RESET/'nextday_o4_adaptive_overnight_result.json'
EVENTS=RESET/'nextday_o4_adaptive_overnight_events.jsonl'

PRIMARY_COST=0.002
COSTS=(0.0,0.002,0.004,0.008)
DEV=o3.DEV; VAL=o3.VAL; DIAG=o3.DIAG
TARGET_COUNTS=(35,45,55)
FEATURES=o3.FEATURES
SHORT_DAYS=63
LONG_DAYS=252
PRIOR_GLOBAL_N=300.0
CELL_SMOOTH=36.0
SHORT_WEIGHT=.40
LONG_WEIGHT=.60

# Fixed 2023 bin edges from O3. O4 changes only the estimator: every current score
# uses mature historical outcomes available by that signal-date close.
edges=o3.edges

def bid(v,es):
    i=0
    while i<len(es) and v>es[i]:i+=1
    return i

def logit(p):
    p=min(max(p,1e-6),1-1e-6)
    return math.log(p/(1-p))

def logistic(x):
    if x>=0:
        e=math.exp(-x); return 1/(1+e)
    e=math.exp(x); return e/(1+e)

# Precompute compact row records. The target is unchanged: predetermined t+1 close
# entry, t+2 open exit. Maturity is exit_date <= current signal date.
records=[]
for r in o3.rows:
    if r['signal_date']<'2023-01-01':continue
    records.append({
        'signal_date':r['signal_date'],'exit_date':r['exit_date'],'ticker':r['ticker'],
        'gross_return':r['gross_return'],'net20':r['gross_return']-PRIMARY_COST,
        'bins':tuple(bid(r[k],edges[k]) for k in FEATURES),
        **{k:r[k] for k in FEATURES},
    })

by_signal=defaultdict(list); by_exit=defaultdict(list)
for r in records:
    by_signal[r['signal_date']].append(r)
    by_exit[r['exit_date']].append(r)

dates=o3.raw.dates
didx={d:i for i,d in enumerate(dates)}

class RollingStats:
    def __init__(self,window_days):
        self.window=window_days
        self.q=deque()
        self.n=0; self.w=0; self.sum=0.0
        self.cells=defaultdict(lambda:[0,0,0.0])
    def add(self,r,current_idx):
        y=int(r['net20']>0)
        item=(current_idx,r)
        self.q.append(item); self.n+=1; self.w+=y; self.sum+=r['net20']
        for fi,b in enumerate(r['bins']):
            z=self.cells[(fi,b)]; z[0]+=1; z[1]+=y; z[2]+=r['net20']
    def evict(self,current_idx):
        cutoff=current_idx-self.window
        while self.q and self.q[0][0] < cutoff:
            _,r=self.q.popleft(); y=int(r['net20']>0)
            self.n-=1; self.w-=y; self.sum-=r['net20']
            for fi,b in enumerate(r['bins']):
                z=self.cells[(fi,b)]; z[0]-=1; z[1]-=y; z[2]-=r['net20']
    def score(self,r):
        # Shrink rolling market base to the broad 2023 prior.
        gp=(self.w + PRIOR_GLOBAL_N*o3.global_p)/(self.n+PRIOR_GLOBAL_N) if self.n else o3.global_p
        gm=(self.sum + PRIOR_GLOBAL_N*o3.global_mean)/(self.n+PRIOR_GLOBAL_N) if self.n else o3.global_mean
        lod=[]; medge=[]; min_n=10**9
        for fi,b in enumerate(r['bins']):
            n,w,s=self.cells[(fi,b)]; min_n=min(min_n,n)
            p=(w + CELL_SMOOTH*gp)/(n+CELL_SMOOTH)
            m=(s + CELL_SMOOTH*gm)/(n+CELL_SMOOTH)
            lod.append(logit(p)-logit(gp)); medge.append(m-gm)
        feature_logodds=statistics.mean(lod)
        mean_edge=statistics.mean(medge)
        # Include the rolling base regime explicitly, unlike static O3.
        total_logodds=logit(gp)+feature_logodds+8.0*mean_edge
        return {'p':logistic(total_logodds),'base_p':gp,'base_mean':gm,'feature_logodds':feature_logodds,'mean_edge':mean_edge,'min_cell_n':min_n}

short=RollingStats(SHORT_DAYS); long=RollingStats(LONG_DAYS)
scored=[]; matured_seen=set()
for d in dates:
    i=didx[d]
    # Add all outcomes that are known by today's close. Assign their rolling age by
    # exit-date index, so no future result enters an earlier score.
    for r in by_exit.get(d,[]):
        key=(r['signal_date'],r['ticker'])
        if key in matured_seen:continue
        matured_seen.add(key)
        short.add(r,i); long.add(r,i)
    short.evict(i); long.evict(i)
    if d<'2024-01-01':continue
    cur=[]
    for r in by_signal.get(d,[]):
        a=short.score(r); b=long.score(r)
        adaptive_p=SHORT_WEIGHT*a['p']+LONG_WEIGHT*b['p']
        base_p=SHORT_WEIGHT*a['base_p']+LONG_WEIGHT*b['base_p']
        # Require relative feature quality and regime base in one continuous score.
        adaptive_score=adaptive_p + .35*(base_p-o3.global_p)
        q=dict(r)
        q.update({
            'short_p':a['p'],'long_p':b['p'],'adaptive_p':adaptive_p,'adaptive_base_p':base_p,
            'adaptive_score':adaptive_score,'short_base_mean':a['base_mean'],'long_base_mean':b['base_mean'],
            'short_min_cell_n':a['min_cell_n'],'long_min_cell_n':b['min_cell_n'],
        })
        cur.append(q)
    if cur:
        cur.sort(key=lambda z:(-z['adaptive_score'],-z['adaptive_p'],-z['turn_ratio'],z['ticker']))
        scored.append(cur[0])


def wilson(w,n,z=1.959963984540054):
    if not n:return None
    p=w/n; z2=z*z; den=1+z2/n
    return (p+z2/(2*n)-z*math.sqrt(p*(1-p)/n+z2/(4*n*n)))/den

def metrics(rs,cost):
    xs=[r['gross_return']-cost for r in rs]; n=len(xs); w=sum(x>0 for x in xs)
    nav=1.; peak=1.; mdd=0.; cur=mx=0
    for x in xs:
        nav*=1+x; peak=max(peak,nav); mdd=min(mdd,nav/peak-1)
        if x<=0:cur+=1;mx=max(mx,cur)
        else:cur=0
    c=Counter(r['ticker'] for r in rs)
    return {'trades':n,'wins':w,'losses':n-w,'win_rate':w/n if n else None,'wilson95_lower':wilson(w,n),
            'mean_return':statistics.mean(xs) if xs else None,'median_return':statistics.median(xs) if xs else None,
            'worst_return':min(xs) if xs else None,'best_return':max(xs) if xs else None,'compounded_return':nav-1 if n else 0.0,
            'max_drawdown':mdd,'max_consecutive_losses':mx,'top_ticker_share':max(c.values())/n if n and c else None}
def split(rs,p):return [r for r in rs if p[0]<=r['signal_date']<=p[1]]
def stress(rs):return {str(c):metrics(rs,c) for c in COSTS}

dev_all=split(scored,DEV)
if len(dev_all)<max(TARGET_COUNTS):raise RuntimeError(f'INSUFFICIENT_2024_DAILY:{len(dev_all)}')
configs=[]
for target in TARGET_COUNTS:
    ranked=sorted(dev_all,key=lambda r:(-r['adaptive_score'],r['signal_date']))
    th=ranked[target-1]['adaptive_score']
    sel=[r for r in dev_all if r['adaptive_score']>=th]
    configs.append({'target_count':target,'threshold':th,'actual_dev_count':len(sel),'dev_net20':metrics(sel,PRIMARY_COST)})
configs.sort(key=lambda c:((c['dev_net20']['wilson95_lower'] or -1),c['dev_net20']['mean_return'] or -9,-abs(c['actual_dev_count']-45)),reverse=True)
champ=configs[0]; threshold=champ['threshold']
selected=[r for r in scored if r['adaptive_score']>=threshold]
dev=split(selected,DEV); val=split(selected,VAL); diag=split(selected,DIAG); pre=dev+val
val20=metrics(val,PRIMARY_COST); diag20=metrics(diag,PRIMARY_COST)
coverage_ok=30<=val20['trades']<=75
positive_econ=val20['mean_return'] is not None and val20['mean_return']>0 and val20['median_return'] is not None and val20['median_return']>0
if coverage_ok and positive_econ and val20['win_rate'] is not None and val20['win_rate']>=.75 and diag20['win_rate'] is not None and diag20['win_rate']>=.60:
    status='O4_ADAPTIVE_OVERNIGHT_RESEARCH_FRONTIER'
elif coverage_ok and positive_econ and val20['win_rate'] is not None and val20['win_rate']>=.60:
    status='O4_ADAPTIVE_OVERNIGHT_PROMISING_REUSED_VALIDATION'
else:
    status='O4_ADAPTIVE_OVERNIGHT_REJECTED'

with EVENTS.open('w',encoding='utf-8') as fh:
    for label,rs in [('DEV_2024',dev),('REUSED_2025',val),('DIAGNOSTIC_2026',diag)]:
        for r in rs:fh.write(json.dumps({'split':label,**r},ensure_ascii=False)+'\n')

res={
 'status':status,
 'model':'O4 mature-only rolling adaptive quantile likelihood for delayed-close overnight',
 'timing':'signal t close; predetermined entry t+1 close; exit t+2 open',
 'target':'gross overnight return minus 20bp > 0',
 'protocol':{
   'bin_edges':'frozen from 2023 O3 training distribution','rolling_update':'only outcomes with exit_date <= current signal date',
   'short_window_trading_days':SHORT_DAYS,'long_window_trading_days':LONG_DAYS,'short_weight':SHORT_WEIGHT,'long_weight':LONG_WEIGHT,
   'global_prior_strength':PRIOR_GLOBAL_N,'cell_smoothing':CELL_SMOOTH,'threshold_selection':'2024 only',
   '2025':'reused validation, not globally pristine','2026':'diagnostic only; not used in formula/threshold selection',
   'target_counts_2024':TARGET_COUNTS,'primary_cost':PRIMARY_COST,'cost_stress':COSTS,
 },
 'hypothesis_lock':'O4 formula/constants were committed before O3 robustness-audit output was inspected. O4 is intended to test whether mature-only rolling adaptation reduces static O3 regime decay without any 2026-specific rule.',
 'development_configs':configs,'selected_threshold':threshold,'selected_target_count':champ['target_count'],
 'development_2024':stress(dev),'reused_validation_2025':stress(val),'pre2026':stress(pre),'historical_diagnostic_2026':stress(diag),
 'counts':{'daily_top1':len(scored),'selected':len(selected)},
 'acceptance_checks':{'validation_coverage_30_to_75':coverage_ok,'validation_positive_mean_and_median_net20':positive_econ,'research_frontier_requires_val_win_gte_75_and_2026_diag_win_gte_60':True},
 'events_file':str(EVENTS.relative_to(ROOT)),
 'research_boundary':'Historical research only. 2025/2026 have been exposed elsewhere in the project, so this cannot restore pristine OOS status. The sequential estimator itself is point-in-time and mature-only.',
 'authority':{'research_only':True,'capital_authority_twd':0,'broker_order_execution':False,'production_promotion':False,'merge_authorized':False},
 'caveat':'No historical win rate guarantees future gains; market-at-close execution/slippage still requires separate validation.'
}
OUT.write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('O4_RESULT='+json.dumps(res,ensure_ascii=False,separators=(',',':')))
