#!/usr/bin/env python3
from __future__ import annotations

import json, math, statistics
from collections import Counter, defaultdict
from pathlib import Path

# Mechanical PIT OHLCV loader/cleaner only. No O2 event family/score/pick is used.
import research.codex_full_reset_20261023.nextday_o2_reversal_analog_tailrisk as raw

ROOT = Path(__file__).resolve().parents[2]
RESET = ROOT / 'research' / 'codex_full_reset_20261023'
OUT = RESET / 'nextday_b1_consensus_basket_result.json'
EVENTS = RESET / 'nextday_b1_consensus_basket_events.jsonl'

PRIMARY_COST = 0.002
COSTS = (0.0, 0.002, 0.004, 0.008)
TRAIN = ('2023-01-01', '2023-12-31')
DEV = ('2024-01-01', '2024-12-31')
VAL = ('2025-01-01', '2025-12-31')
DIAG = ('2026-01-01', '2026-10-22')
TARGET_COUNTS = (35,45,55)
BINS = 5
SMOOTH = 40.0
BASKET_SIZE = 5
MAX_CORR = 0.85

GROUPS = {
    'MOMENTUM_RELATIVE': ('r1','r5','r20','rel20','dist_high20'),
    'CANDLE_GEOMETRY': ('gap','body','close_loc','range_pct'),
    'RISK_LIQUIDITY': ('vol_ratio','turn_ratio','vol20'),
}
ALL_FEATURES = tuple(dict.fromkeys(k for ks in GROUPS.values() for k in ks))


def outcome(d,t):
    i=raw.di[d]
    if i+2>=len(raw.dates): return None
    ed,xd=raw.dates[i+1],raw.dates[i+2]
    s=raw.by[d].get(t); e=raw.by[ed].get(t); x=raw.by[xd].get(t)
    if not s or not e or not x or e['c']<=0 or x['o']<=0: return None
    if abs(e['c']/s['c']-1)>raw.JUMP or abs(x['c']/e['c']-1)>raw.JUMP: return None
    gross=x['o']/e['c']-1
    return {'entry_date':ed,'exit_date':xd,'entry_close':e['c'],'exit_open':x['o'],'gross_return':gross,'net20':gross-PRIMARY_COST}


def pranks(pairs):
    a=sorted(pairs,key=lambda z:(z[1],z[0])); n=len(a); out={}; i=0
    while i<n:
        j=i+1
        while j<n and a[j][1]==a[i][1]: j+=1
        p=((i+j-1)/2+.5)/n
        for q in range(i,j): out[a[q][0]]=p
        i=j
    return out

# Build signal-date cross sections and future overnight labels.
panels={}
for d in raw.dates:
    if d<TRAIN[0] or d>DIAG[1] or d not in raw.market: continue
    xs=[]
    for t in raw.by[d]:
        x=raw.stock.get((d,t))
        if not x or any(k not in x for k in ALL_FEATURES): continue
        o=outcome(d,t)
        if o: xs.append((t,x,o))
    if len(xs)<20: continue
    ranks={k:pranks([(t,x[k]) for t,x,_ in xs]) for k in ALL_FEATURES}
    med=statistics.median(o['net20'] for _,_,o in xs)
    stocks=[]
    for t,x,o in xs:
        q={'signal_date':d,'ticker':t,**{f'rank_{k}':ranks[k][t] for k in ALL_FEATURES},**o}
        q['residual_net20']=o['net20']-med
        stocks.append(q)
    panels[d]={'signal_date':d,'market_median_net20':med,'stocks':stocks}

train=[s for d,p in panels.items() if TRAIN[0]<=d<=TRAIN[1] for s in p['stocks']]
if len(train)<10000: raise RuntimeError(f'INSUFFICIENT_2023_TRAIN:{len(train)}')

# Three independent sleeves estimate only market-relative residual, each from 2023.
cell=defaultdict(lambda:{'n':0,'sum':0.0})
for s in train:
    for g,ks in GROUPS.items():
        for k in ks:
            b=min(BINS-1,int(s[f'rank_{k}']*BINS))
            z=cell[(g,k,b)]; z['n']+=1; z['sum']+=s['residual_net20']


def sleeve_score(s,g,ks):
    es=[]; ns=[]
    for k in ks:
        b=min(BINS-1,int(s[f'rank_{k}']*BINS)); z=cell[(g,k,b)]
        es.append(z['sum']/(z['n']+SMOOTH)); ns.append(z['n'])
    return statistics.mean(es),min(ns)


def recent_returns(d,t,n=20):
    i=raw.di[d]; out=[]
    for j in range(max(1,i-n+1),i+1):
        a=raw.by[raw.dates[j-1]].get(t); b=raw.by[raw.dates[j]].get(t)
        if not a or not b or a['c']<=0 or b['c']<=0: return None
        q=b['c']/a['c']-1
        if abs(q)>raw.JUMP: return None
        out.append(q)
    return out if len(out)>=15 else None


def corr(a,b):
    if not a or not b or len(a)!=len(b) or len(a)<3: return 1.0
    ma=statistics.mean(a); mb=statistics.mean(b)
    xa=[x-ma for x in a]; xb=[x-mb for x in b]
    da=math.sqrt(sum(x*x for x in xa)); db=math.sqrt(sum(x*x for x in xb))
    if da<=1e-12 or db<=1e-12: return 1.0
    return sum(x*y for x,y in zip(xa,xb))/(da*db)

# One five-stock basket per signal day. Candidate score requires agreement across
# independently modelled sleeves; diversification is enforced using only past returns.
daily=[]
for d,p in sorted(panels.items()):
    if d<DEV[0]: continue
    arr=[]
    for s in p['stocks']:
        scores={}; supports=[]
        for g,ks in GROUPS.items():
            sc,n=sleeve_score(s,g,ks); scores[g]=sc; supports.append(n)
        vals=list(scores.values())
        positive=sum(v>0 for v in vals)
        # Median consensus plus a conservative minimum-sleeve term. One hot sleeve cannot dominate.
        consensus=statistics.median(vals)+.35*min(vals)
        q=dict(s); q.update({f'sleeve_{g}':v for g,v in scores.items()})
        q.update({'positive_sleeves':positive,'consensus_score':consensus,'min_cell_n':min(supports)})
        q['recent20']=recent_returns(d,s['ticker'])
        if q['recent20'] is not None: arr.append(q)
    arr.sort(key=lambda z:(-z['positive_sleeves'],-z['consensus_score'],z['ticker']))
    if len(arr)<BASKET_SIZE: continue
    chosen=[]
    for q in arr:
        if len(chosen)>=BASKET_SIZE: break
        if all(corr(q['recent20'],z['recent20'])<=MAX_CORR for z in chosen): chosen.append(q)
    if len(chosen)<BASKET_SIZE:
        # Fill only if correlation guard prevents completion; keep ranking fixed and record it.
        used={z['ticker'] for z in chosen}
        for q in arr:
            if q['ticker'] not in used:
                chosen.append(q); used.add(q['ticker'])
                if len(chosen)>=BASKET_SIZE: break
    if len(chosen)<BASKET_SIZE: continue
    gross=statistics.mean(q['gross_return'] for q in chosen)
    opportunity=statistics.mean(q['consensus_score'] for q in chosen)
    agree=statistics.mean(q['positive_sleeves'] for q in chosen)
    daily.append({
        'signal_date':d,'entry_date':chosen[0]['entry_date'],'exit_date':chosen[0]['exit_date'],
        'tickers':[q['ticker'] for q in chosen],'legs':BASKET_SIZE,
        'gross_return':gross,'net20':gross-PRIMARY_COST,'opportunity_score':opportunity,
        'mean_positive_sleeves':agree,'market_median_net20':p['market_median_net20'],
        'leg_returns':[q['gross_return'] for q in chosen],
        'leg_consensus_scores':[q['consensus_score'] for q in chosen],
    })


def wilson(w,n,z=1.959963984540054):
    if not n:return None
    p=w/n; z2=z*z; den=1+z2/n
    return (p+z2/(2*n)-z*math.sqrt(p*(1-p)/n+z2/(4*n*n)))/den

def metrics(rs,cost):
    xs=[r['gross_return']-cost for r in rs]; n=len(xs); w=sum(x>0 for x in xs)
    nav=1.;peak=1.;mdd=0.;cur=mx=0
    for x in xs:
        nav*=1+x;peak=max(peak,nav);mdd=min(mdd,nav/peak-1)
        if x<=0:cur+=1;mx=max(mx,cur)
        else:cur=0
    tick=Counter(t for r in rs for t in r['tickers'])
    return {'basket_nights':n,'underlying_legs':n*BASKET_SIZE,'wins':w,'losses':n-w,'win_rate':w/n if n else None,
            'wilson95_lower':wilson(w,n),'mean_return':statistics.mean(xs) if xs else None,'median_return':statistics.median(xs) if xs else None,
            'worst_return':min(xs) if xs else None,'best_return':max(xs) if xs else None,'compounded_return':nav-1 if n else 0.0,
            'max_drawdown':mdd,'max_consecutive_losses':mx,'top_ticker_leg_share':max(tick.values())/(n*BASKET_SIZE) if n and tick else None}
def split(rs,p):return[r for r in rs if p[0]<=r['signal_date']<=p[1]]
def stress(rs):return{str(c):metrics(rs,c) for c in COSTS}

dev_all=split(daily,DEV);val_all=split(daily,VAL);diag_all=split(daily,DIAG)
if len(dev_all)<max(TARGET_COUNTS):raise RuntimeError(f'INSUFFICIENT_2024_BASKETS:{len(dev_all)}')
configs=[]
for target in TARGET_COUNTS:
    ranked=sorted(dev_all,key=lambda r:(-r['opportunity_score'],r['signal_date']))
    th=ranked[target-1]['opportunity_score'];sel=[r for r in dev_all if r['opportunity_score']>=th]
    m=metrics(sel,PRIMARY_COST)
    configs.append({'target_count':target,'opportunity_threshold':th,'actual_dev_count':len(sel),'dev_net20':m})
configs.sort(key=lambda c:((c['dev_net20']['wilson95_lower'] or -1),c['dev_net20']['mean_return'] or -9,-abs(c['actual_dev_count']-45)),reverse=True)
champ=configs[0];th=champ['opportunity_threshold']
selected=[r for r in daily if r['opportunity_score']>=th]
dev=split(selected,DEV);val=split(selected,VAL);diag=split(selected,DIAG);pre=dev+val
v=metrics(val,PRIMARY_COST)
coverage=30<=v['basket_nights']<=70
positive=(v['mean_return'] is not None and v['mean_return']>0 and v['median_return'] is not None and v['median_return']>0)
beats_o3=(v['win_rate'] is not None and v['win_rate']>30/46)
if coverage and positive and beats_o3:status='B1_BASKET_BEATS_O3_2025_REUSED_VALIDATION'
elif coverage and v['win_rate'] is not None and v['win_rate']>=.60 and v['mean_return'] is not None and v['mean_return']>0:status='B1_BASKET_PROMISING_REUSED_VALIDATION'
else:status='B1_BASKET_REJECTED'

with EVENTS.open('w',encoding='utf-8') as fh:
    for label,rs in [('DEV_2024',dev),('REUSED_2025',val),('DIAGNOSTIC_2026',diag)]:
        for r in rs:fh.write(json.dumps({'split':label,**r},ensure_ascii=False)+'\n')
res={
 'status':status,'model':'B1 diversified five-stock consensus residual overnight basket',
 'timing':'signal after t close; equal-weight five-stock basket entered t+1 close; exited t+2 open',
 'new_mode':'Treat one diversified basket-night as the decision unit instead of guessing a single top1 stock. Three independent 2023-fitted sleeves must agree; recent-return correlation limits idiosyncratic concentration.',
 'independence':'Raw TWSE electronics OHLC/turnover only; no HENGCE/V/X/HR, O3/G1 score, T86, or prior selected-trade identity.',
 'groups':GROUPS,'protocol':{'fit':'2023 only','threshold_selection':'2024 only','2025':'reused frozen validation','2026':'diagnostic only','target_counts_2024':TARGET_COUNTS,'basket_size':BASKET_SIZE,'max_pair_corr':MAX_CORR,'bins':BINS,'smoothing':SMOOTH,'primary_cost':PRIMARY_COST,'cost_stress':COSTS},
 'train_rows_2023':len(train),'development_configs':configs,'selected_threshold':th,'selected_target_count':champ['target_count'],
 'all_nights_baseline':{'development_2024':stress(dev_all),'reused_validation_2025':stress(val_all),'diagnostic_2026':stress(diag_all)},
 'selected_development_2024':stress(dev),'selected_reused_validation_2025':stress(val),'selected_pre2026':stress(pre),'selected_diagnostic_2026':stress(diag),
 'acceptance_checks':{'validation_coverage_30_to_70_basket_nights':coverage,'validation_positive_mean_and_median_net20':positive,'validation_win_rate_beats_o3_single_stock_reference':beats_o3,'o3_2025_reference':30/46},
 'events_file':str(EVENTS.relative_to(ROOT)),
 'research_boundary':'Architecture fixed before reading G1 result. 2025/2026 remain reused historical diagnostics globally, not pristine OOS.',
 'authority':{'research_only':True,'capital_authority_twd':0,'broker_order_execution':False,'production_promotion':False,'merge_authorized':False},
 'caveat':'Historical research only. Basket execution, close auction fills, slippage and capacity need separate prospective validation; no historical hit rate guarantees future gains.'}
OUT.write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('B1_RESULT='+json.dumps(res,ensure_ascii=False,separators=(',',':')))
