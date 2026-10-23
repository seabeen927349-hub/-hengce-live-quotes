#!/usr/bin/env python3
from __future__ import annotations

import csv, gzip, json, math, statistics
from collections import defaultdict, deque, Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HIST = ROOT / 'research/codex_full_reset_20261023/results/stage_b/TWSE_ELECTRONICS_DAILY_2023_2025.csv.gz'
CURR = ROOT / 'hengce/q017_radar/data/twse_electronics_history_2026.csv'
OUT = ROOT / 'research/codex_full_reset_20261023/ranking_v2_2026_result.json'
EVENTS = ROOT / 'research/codex_full_reset_20261023/ranking_v2_2026_events.jsonl'

START='2026-01-01'; END='2026-10-22'; TOPN=5; H=10; TURN_MIN=50_000_000.0; JUMP=0.15
COSTS=(0.008,0.012,0.016)

class R:
    __slots__=('d','t','o','h','l','c','turn','r1','r5','r20','r60','turn20','vol20','beta60','resid5','bad','score')
    def __init__(self,d,t,o,h,l,c,turn):
        self.d=d;self.t=t;self.o=o;self.h=h;self.l=l;self.c=c;self.turn=turn
        self.r1=self.r5=self.r20=self.r60=self.turn20=self.vol20=self.beta60=self.resid5=self.score=None; self.bad=False

def f(x):
    if x in (None,'','--','---'): return None
    try:
        v=float(str(x).replace(',',''))
        return v if math.isfinite(v) else None
    except: return None

def load(path):
    op=gzip.open if path.suffix=='.gz' else open
    rows=[]
    with op(path,'rt',encoding='utf-8-sig',newline='') as fh:
        for x in csv.DictReader(fh):
            t=(x.get('ticker') or '').strip()
            if len(t)!=4 or not t.isdigit():
                continue
            d=(x.get('date') or '').strip()
            if not d: continue
            rows.append(R(d,t,f(x.get('open')),f(x.get('high')),f(x.get('low')),f(x.get('close')),f(x.get('turnover_ntd'))))
    return rows

rows=load(HIST)+load(CURR)
by=defaultdict(dict)
for r in rows:
    by[r.d][r.t]=r
dates=sorted(by)
idx={d:i for i,d in enumerate(dates)}

# 1d and jump guard
for i,d in enumerate(dates):
    if i==0: continue
    p=dates[i-1]
    for t,r in by[d].items():
        q=by[p].get(t)
        if q and q.c and r.c and q.c>0 and r.c>0:
            rr=r.c/q.c-1
            r.bad=abs(rr)>JUMP
            if not r.bad: r.r1=rr

# horizon returns / liquidity / vol and market median returns
mkt=defaultdict(dict)
for i,d in enumerate(dates):
    for t,r in by[d].items():
        for h in (5,20,60):
            if i<h: continue
            q=by[dates[i-h]].get(t)
            if not q or not q.c or not r.c or q.c<=0 or r.c<=0: continue
            ok=True
            for j in range(i-h+1,i+1):
                z=by[dates[j]].get(t)
                if z is None or z.bad: ok=False; break
            if ok: setattr(r,f'r{h}',r.c/q.c-1)
        if i>=19:
            vals=[]
            for j in range(i-19,i+1):
                z=by[dates[j]].get(t)
                if z is None or z.turn is None or z.turn<0: vals=[]; break
                vals.append(z.turn)
            if len(vals)==20:r.turn20=statistics.mean(vals)
        if i>=20:
            vals=[]
            for j in range(i-19,i+1):
                z=by[dates[j]].get(t)
                if z is None or z.r1 is None: vals=[]; break
                vals.append(z.r1)
            if len(vals)==20 and len(set(vals))>1:r.vol20=statistics.stdev(vals)
    for h in (1,5):
        vals=[]
        for r in by[d].values():
            v=r.r1 if h==1 else r.r5
            if v is not None: vals.append(v)
        if vals:mkt[d][f'r{h}']=statistics.median(vals)

# beta60 using only prior observations
hist=defaultdict(lambda:deque(maxlen=60))
for d in dates:
    mr1=mkt[d].get('r1')
    for t,r in by[d].items():
        h=hist[t]
        if len(h)>=30:
            xs=[a for a,b in h]; ys=[b for a,b in h]
            xb=statistics.mean(xs); yb=statistics.mean(ys); den=sum((x-xb)**2 for x in xs)
            if den>0:r.beta60=sum((x-xb)*(y-yb) for x,y in h)/den
        if r.beta60 is not None and r.r5 is not None and mkt[d].get('r5') is not None:
            r.resid5=r.r5-r.beta60*mkt[d]['r5']
        if mr1 is not None and r.r1 is not None:h.append((mr1,r.r1))

def ranks(vals):
    a=sorted(vals.items(), key=lambda kv:(kv[1],kv[0])); n=len(a); out={}
    if n==1:return {a[0][0]:0.5}
    i=0
    while i<n:
        j=i+1
        while j<n and a[j][1]==a[i][1]:j+=1
        pct=(((i+1)+j)/2-1)/(n-1)
        for k in range(i,j):out[a[k][0]]=pct
        i=j
    return out

# preregistered score: 40% residual reversal, 20% 20d trend, 15% 60d trend, 10% liquidity, 15% low vol
for d in dates:
    elig={t:r for t,r in by[d].items() if r.resid5 is not None and r.r20 is not None and r.r60 is not None and r.turn20 is not None and r.vol20 is not None and r.turn20>=TURN_MIN}
    rr=ranks({t:-r.resid5 for t,r in elig.items()}); r20=ranks({t:r.r20 for t,r in elig.items()}); r60=ranks({t:r.r60 for t,r in elig.items()}); liq=ranks({t:r.turn20 for t,r in elig.items()}); lv=ranks({t:-r.vol20 for t,r in elig.items()})
    for t,r in elig.items():r.score=.40*rr[t]+.20*r20[t]+.15*r60[t]+.10*liq[t]+.15*lv[t]

def outcome(t,si):
    ei=si+1; xi=ei+H
    if xi>=len(dates): return None
    ed,xd=dates[ei],dates[xi]
    e=by[ed].get(t); x=by[xd].get(t)
    if not e or not x or e.o is None or x.c is None or e.o<=0 or x.c<=0:return None
    path=[]
    for j in range(ei,xi+1):
        z=by[dates[j]].get(t)
        if z is None or z.c is None or z.c<=0 or z.bad:return None
        path.append((dates[j],z.c/e.o-1))
    return x.c/e.o-1,ed,xd,path

events=[]; censored=0; next_free=-1
for i,d in enumerate(dates):
    if d<START or d>END or i<next_free:continue
    ranked=sorted([(r.score,t) for t,r in by[d].items() if r.score is not None], key=lambda x:(-x[0],x[1]))
    picks=[t for s,t in ranked[:TOPN]]
    if len(picks)<TOPN:continue
    xi=i+1+H
    if xi>=len(dates) or dates[xi]>END:continue
    outs=[(t,outcome(t,i)) for t in picks]
    if any(o is None for t,o in outs):
        censored+=1; next_free=xi+1; continue
    gross=statistics.mean(o[0] for t,o in outs)
    daily=[]
    for k in range(H+1):
        daily.append([outs[0][1][3][k][0], statistics.mean(o[3][k][1] for t,o in outs)])
    events.append({'signal_date':d,'entry_date':outs[0][1][1],'exit_date':outs[0][1][2],'tickers':picks,'gross_return':gross,'daily_gross_returns':daily})
    next_free=xi+1

def product(xs):
    n=1
    for x in xs:n*=1+x
    return n-1

def metrics(cost):
    nets=[e['gross_return']-cost for e in events]
    nav=1;peak=1;mdd=0
    for e in events:
        base=nav
        for j,(d,r) in enumerate(e['daily_gross_returns']):
            temp=base*(1+r-(cost if j==len(e['daily_gross_returns'])-1 else 0))
            peak=max(peak,temp);mdd=min(mdd,temp/peak-1)
        nav=base*(1+e['gross_return']-cost)
    best=max(range(len(nets)), key=lambda k:nets[k]) if nets else None
    remove=product([r for k,r in enumerate(nets) if k!=best]) if best is not None else None
    return {'cost':cost,'baskets':len(nets),'stock_positions':len(nets)*TOPN,'wins':sum(r>0 for r in nets),'win_rate':sum(r>0 for r in nets)/len(nets) if nets else None,'compounded_return':product(nets),'max_drawdown':mdd,'mean_net_return':statistics.mean(nets) if nets else None,'median_net_return':statistics.median(nets) if nets else None,'best_basket_net':max(nets) if nets else None,'worst_basket_net':min(nets) if nets else None,'remove_best_basket_return':remove}

res={'model':'HENGCE_ELECTRONICS_RANKING_V2','status':'HISTORICAL_SIMULATION_ONLY','period':[START,END],'universe':'TWSE_LISTED_ELECTRONICS_PIT_DAILY_4DIGIT','config':{'score':'0.40*rank(-resid5)+0.20*rank(r20)+0.15*rank(r60)+0.10*rank(turnover20)+0.15*rank(-vol20)','top_n':TOPN,'horizon_sessions':H,'turnover20_min':TURN_MIN,'entry':'next session open','exit':'close after 10 sessions','non_overlapping':True,'jump_guard':JUMP},'data':{'warmup':'2023-2025 frozen Stage-B mother','validation':'2026 repo electronics history','validation_rows':sum(len(by[d]) for d in dates if START<=d<=END),'validation_dates':sum(1 for d in dates if START<=d<=END)},'intended_complete_baskets':len(events),'censored_baskets':censored,'cost_cases':[metrics(c) for c in COSTS],'ticker_counts':Counter(t for e in events for t in e['tickers']).most_common(20),'events_file':str(EVENTS.relative_to(ROOT)),'new_model_evaluations':1,'authority':{'research_only':True,'capital_authority_twd':0,'broker_order_execution':False,'production_promotion':False,'merge_authorized':False}}
OUT.write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
with EVENTS.open('w',encoding='utf-8') as fh:
    for e in events:fh.write(json.dumps(e,ensure_ascii=False)+'\n')
print(json.dumps(res,ensure_ascii=False,indent=2))
