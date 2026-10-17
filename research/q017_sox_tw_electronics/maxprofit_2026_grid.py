#!/usr/bin/env python3
import csv,json,math
from collections import defaultdict
from pathlib import Path

ROOT=Path('research/q017_sox_tw_electronics')
ARC=ROOT/'archive_2026'
OUT=ROOT/'maxprofit_2026';OUT.mkdir(parents=True,exist_ok=True)
START=2_000_000.0
COST=.004

def f(x):
    try:return float(str(x).replace(',','').strip())
    except:return None

# SOX
sox=[]
for r in csv.DictReader((ARC/'sox_2026.csv').open(encoding='utf-8')):
    c=f(r['close'])
    if c is not None: sox.append((r['date'],c))
sox.sort(); sd=[d for d,_ in sox]
sret={sox[i][0]:sox[i][1]/sox[i-1][1]-1 for i in range(1,len(sox))}
def prevus(d):
    z=[u for u in sd if u<d]; return z[-1] if z else None

# Taiwan electronics
by_t=defaultdict(list); by_d=defaultdict(list)
for r in csv.DictReader((ARC/'twse_electronics_membership_2026.csv').open(encoding='utf-8')):
    o=f(r['open']); c=f(r['close'])
    if o is None or c is None: continue
    x={'date':r['date'],'ticker':r['ticker'],'name':r['name'],'open':o,'close':c}
    by_t[r['ticker']].append(x); by_d[r['date']].append(x)
for t in by_t: by_t[t].sort(key=lambda x:x['date'])
aligned={d:sret.get(prevus(d)) for d in by_d}

# prior-only beta, prev close, row index
beta={}; prevclose={}; idx={}
for t,rs in by_t.items():
    idx[t]={r['date']:i for i,r in enumerate(rs)}; obs=[]; pc=None
    for r in rs:
        prevclose[(r['date'],t)]=pc
        if pc and aligned.get(r['date']) is not None:
            tr=r['close']/pc-1
            if len(obs)>=30:
                z=obs[-60:]; mx=sum(x for x,y in z)/len(z); my=sum(y for x,y in z)/len(z)
                vv=sum((x-mx)**2 for x,y in z)
                beta[(r['date'],t)]=sum((x-mx)*(y-my) for x,y in z)/vv if vv else 0
            obs.append((aligned[r['date']],tr))
        pc=r['close']

# date-level SOX features
feat={}
for d in sorted(by_d):
    u=prevus(d); shock=aligned.get(d)
    if u is None or shock is None: continue
    ui=sd.index(u)
    ret5=sox[ui][1]/sox[ui-5][1]-1 if ui>=5 else None
    feat[d]={'shock':shock,'sox5':ret5}

# cache candidate data per date for speed
cand_cache={}
for d in sorted(by_d):
    ft=feat.get(d)
    if not ft: continue
    z=[]
    for r in by_d[d]:
        b=beta.get((d,r['ticker'])); pc=prevclose.get((d,r['ticker']))
        if b is None or not pc: continue
        gap=r['open']/pc-1; exp=b*ft['shock']; res=gap-exp
        z.append((b,res,r))
    cand_cache[d]=sorted(z,key=lambda x:x[0],reverse=True)

def weights(cand,scheme):
    n=len(cand)
    if n==0:return []
    if scheme=='equal':return [1/n]*n
    if scheme=='rank':
        raw=list(range(n,0,-1));s=sum(raw);return [x/s for x in raw]
    if scheme=='beta':
        raw=[max(x[0],0) for x in cand];s=sum(raw)
        return [x/s for x in raw] if s>0 else [1/n]*n
    raise ValueError(scheme)

def event_for_date(d,hold,topN,resid_max,scheme):
    ft=feat.get(d)
    if not ft:return None
    cand=cand_cache.get(d,[])
    if resid_max is not None:cand=[x for x in cand if x[1]<=resid_max]
    cand=cand[:topN]
    if not cand:return None
    rr=[]; exits=[]; used=[]
    for b,res,r in cand:
        i=idx[r['ticker']][d];j=i+hold-1
        if j>=len(by_t[r['ticker']]):continue
        er=by_t[r['ticker']][j]
        rr.append(er['close']/r['open']-1-COST);exits.append(er['date']);used.append((b,res,r))
    if not rr:return None
    w=weights(used,scheme)
    pr=sum(a*b for a,b in zip(w,rr))
    return {'entry':d,'exit':max(exits),'ret':pr,'shock':ft['shock'],'sox5':ft['sox5'],'n':len(rr),'tickers':'|'.join(x[2]['ticker'] for x in used)}

def run(shock_max,sox5_max,hold,topN,resid_max,scheme,sleeves):
    # sleeves=1 reproduces full-capital non-overlap. sleeves>1 allows overlapping signals with equal capital sleeves.
    caps=[START/sleeves]*sleeves; busy=['']*sleeves; events=[]
    for d in sorted(by_d):
        ft=feat.get(d)
        if not ft or ft['shock']>shock_max or ft['sox5'] is None or ft['sox5']>sox5_max:continue
        free=[i for i,b in enumerate(busy) if not b or d>b]
        if not free:continue
        e=event_for_date(d,hold,topN,resid_max,scheme)
        if not e:continue
        # allocate new event to the currently smallest free sleeve to avoid favoring a lucky sleeve by ordering
        i=min(free,key=lambda k:caps[k])
        caps[i]*=1+e['ret'];busy[i]=e['exit'];events.append({**e,'sleeve':i,'sleeve_cap_after':caps[i]})
    final=sum(caps)
    return {'final':final,'ret':final/START-1,'n':len(events),'wins':sum(e['ret']>0 for e in events),'events':events,'sleeve_caps':caps}

# Search only around already-proven 2026 region; objective = final capital.
shock_grid=[-.02,-.025,-.03]
sox5_grid=[-.04,-.05,-.06]
hold_grid=list(range(3,11))
top_grid=[1,2,3,4,5]
resid_grid=[None,.04,.03,.025,.02]
scheme_grid=['equal','rank','beta']
sleeve_grid=[1,2,3]
rows=[]
for sh in shock_grid:
 for s5 in sox5_grid:
  for h in hold_grid:
   for n in top_grid:
    for rg in resid_grid:
     for scheme in scheme_grid:
      for sleeves in sleeve_grid:
       r=run(sh,s5,h,n,rg,scheme,sleeves)
       rows.append({'shock_max':sh,'sox5_max':s5,'hold':h,'topN':n,'resid_max':'NONE' if rg is None else rg,'scheme':scheme,'sleeves':sleeves,'final':r['final'],'ret':r['ret'],'events':r['n'],'wins':r['wins'],'win_rate':r['wins']/r['n'] if r['n'] else 0})
rows.sort(key=lambda x:x['final'],reverse=True)
best=rows[0]
rg=None if best['resid_max']=='NONE' else float(best['resid_max'])
rb=run(best['shock_max'],best['sox5_max'],best['hold'],best['topN'],rg,best['scheme'],best['sleeves'])

# nearby robustness: one-step neighbors in every dimension except scheme/sleeves are exact + adjacent discrete values

def near(grid,v):
    i=grid.index(v);return grid[max(0,i-1):min(len(grid),i+2)]
zone=[]
for sh in near(shock_grid,best['shock_max']):
 for s5 in near(sox5_grid,best['sox5_max']):
  for h in near(hold_grid,best['hold']):
   for n in near(top_grid,best['topN']):
    for scheme in scheme_grid:
     for sleeves in sleeve_grid:
      r=run(sh,s5,h,n,rg,scheme,sleeves)
      zone.append({'shock_max':sh,'sox5_max':s5,'hold':h,'topN':n,'resid_max':best['resid_max'],'scheme':scheme,'sleeves':sleeves,'final':r['final'],'ret':r['ret'],'events':r['n'],'wins':r['wins'],'win_rate':r['wins']/r['n'] if r['n'] else 0})
zone.sort(key=lambda x:x['final'],reverse=True)

summary={
 'objective':'maximize 2026 final capital; 2M start; 0.4% per-stock round-trip cost; prior-only beta',
 'tested':len(rows),
 'best':best,
 'best20':rows[:20],
 'best_event_path':rb['events'],
 'best_sleeve_caps':rb['sleeve_caps'],
 'neighborhood':{
   'count':len(zone),
   'positive':sum(z['ret']>0 for z in zone),
   'above50pct':sum(z['ret']>.5 for z in zone),
   'median_final':sorted(z['final'] for z in zone)[len(zone)//2],
   'min_final':min(z['final'] for z in zone),
   'top20':zone[:20]
 }
}
(OUT/'operational_opt_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
with (OUT/'operational_opt_grid.csv').open('w',newline='',encoding='utf-8') as f0:
    w=csv.DictWriter(f0,fieldnames=list(rows[0].keys()));w.writeheader();w.writerows(rows)
print(json.dumps(summary,ensure_ascii=False,indent=2))
