#!/usr/bin/env python3
import csv,json,math
from collections import defaultdict
from pathlib import Path

ROOT=Path('research/q017_sox_tw_electronics')
ARC=ROOT/'archive_2026'; OUT=ROOT/'hold_horizon_2026'; OUT.mkdir(parents=True,exist_ok=True)
START=2_000_000.0; COST=.004

def f(x):
    try:return float(str(x).replace(',','').strip())
    except:return None

# data
sox=[]
for r in csv.DictReader((ARC/'sox_2026.csv').open(encoding='utf-8')):
    c=f(r['close'])
    if c is not None:sox.append((r['date'],c))
sox.sort(); sd=[d for d,_ in sox]
sret={sox[i][0]:sox[i][1]/sox[i-1][1]-1 for i in range(1,len(sox))}
def prevus(d):
    z=[u for u in sd if u<d]; return z[-1] if z else None

by_t=defaultdict(list); by_d=defaultdict(list)
for r in csv.DictReader((ARC/'twse_electronics_membership_2026.csv').open(encoding='utf-8')):
    o=f(r['open']); c=f(r['close'])
    if o is None or c is None:continue
    x={'date':r['date'],'ticker':r['ticker'],'open':o,'close':c}
    by_t[r['ticker']].append(x);by_d[r['date']].append(x)
for t in by_t:by_t[t].sort(key=lambda x:x['date'])
aligned={d:sret.get(prevus(d)) for d in by_d}

beta={}; prevc={}; idx={}
for t,rs in by_t.items():
    idx[t]={r['date']:i for i,r in enumerate(rs)};obs=[];pc=None
    for r in rs:
        prevc[(r['date'],t)]=pc
        if pc and aligned.get(r['date']) is not None:
            tr=r['close']/pc-1
            if len(obs)>=30:
                z=obs[-60:];mx=sum(x for x,y in z)/len(z);my=sum(y for x,y in z)/len(z);vv=sum((x-mx)**2 for x,y in z)
                beta[(r['date'],t)]=sum((x-mx)*(y-my) for x,y in z)/vv if vv else 0
            obs.append((aligned[r['date']],tr))
        pc=r['close']

feat={}
for d in sorted(by_d):
    u=prevus(d);sh=aligned.get(d)
    if not u or sh is None:continue
    ui=sd.index(u);r5=sox[ui][1]/sox[ui-5][1]-1 if ui>=5 else None
    feat[d]={'shock':sh,'sox5':r5}

def pick(d,shock_max=-.02,sox5_max=-.04,resid_max=.04):
    ft=feat.get(d)
    if not ft or ft['shock']>shock_max or ft['sox5'] is None or ft['sox5']>sox5_max:return None
    cs=[]
    for r in by_d[d]:
        b=beta.get((d,r['ticker']));pc=prevc.get((d,r['ticker']))
        if b is None or not pc:continue
        gap=r['open']/pc-1;res=gap-b*ft['shock']
        if res<=resid_max:cs.append((b,res,r))
    if not cs:return None
    return max(cs,key=lambda x:x[0])

def run(hold):
    cap=START;busy='';events=[]
    for d in sorted(by_d):
        if busy and d<=busy:continue
        p=pick(d)
        if not p:continue
        b,res,r=p;i=idx[r['ticker']][d];j=i+hold-1
        if j>=len(by_t[r['ticker']]):continue
        ex=by_t[r['ticker']][j];ret=ex['close']/r['open']-1-COST;cap*=1+ret;busy=ex['date']
        events.append({'entry':d,'exit':busy,'ticker':r['ticker'],'ret':ret,'capital':cap,'shock':feat[d]['shock'],'sox5':feat[d]['sox5'],'beta':b,'resid':res})
    return {'hold':hold,'final':cap,'ret':cap/START-1,'n':len(events),'wins':sum(e['ret']>0 for e in events),'events':events}

# scan every feasible hold day up to 60 first; enough to see a peak/trend without arbitrary 10-day cap
rows=[]
for h in range(1,61):
    r=run(h);rows.append({k:v for k,v in r.items() if k!='events'})
rows.sort(key=lambda x:x['final'],reverse=True)
best=rows[0]; rb=run(best['hold'])
# local curve around optimum
curve=sorted(rows,key=lambda x:x['hold'])
summary={'objective':'2026 final capital maximum; fixed best SOX gate/top1/residual, scan hold 1..60 trading days','best':best,'top15':rows[:15],'best_events':rb['events'],'curve':curve}
(OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
with (OUT/'curve.csv').open('w',newline='',encoding='utf-8') as f0:
    w=csv.DictWriter(f0,fieldnames=['hold','final','ret','n','wins']);w.writeheader();w.writerows(curve)
print(json.dumps(summary,ensure_ascii=False,indent=2))
