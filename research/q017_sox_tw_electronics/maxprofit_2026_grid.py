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
    if c is not None:sox.append((r['date'],c))
sox.sort(); sd=[d for d,_ in sox]
sret={sox[i][0]:sox[i][1]/sox[i-1][1]-1 for i in range(1,len(sox))}
def prevus(d):
    z=[u for u in sd if u<d];return z[-1] if z else None
# stocks
by_t=defaultdict(list);by_d=defaultdict(list)
for r in csv.DictReader((ARC/'twse_electronics_membership_2026.csv').open(encoding='utf-8')):
    o=f(r['open']);c=f(r['close'])
    if o is None or c is None:continue
    x={'date':r['date'],'ticker':r['ticker'],'name':r['name'],'open':o,'close':c};by_t[r['ticker']].append(x);by_d[r['date']].append(x)
for t in by_t:by_t[t].sort(key=lambda x:x['date'])
aligned={d:sret.get(prevus(d)) for d in by_d}
# prior beta and prev close
beta={};prevclose={};idx={}
for t,rs in by_t.items():
    idx[t]={r['date']:i for i,r in enumerate(rs)};obs=[];pc=None
    for r in rs:
        prevclose[(r['date'],t)]=pc
        if pc and aligned.get(r['date']) is not None:
            tr=r['close']/pc-1
            if len(obs)>=30:
                z=obs[-60:];mx=sum(x for x,y in z)/len(z);my=sum(y for x,y in z)/len(z);vv=sum((x-mx)**2 for x,y in z)
                beta[(r['date'],t)]=sum((x-mx)*(y-my) for x,y in z)/vv if vv else 0
            obs.append((aligned[r['date']],tr))
        pc=r['close']
# features per date
feat={}
for d in sorted(by_d):
    u=prevus(d);shock=aligned.get(d)
    if u is None or shock is None:continue
    ui=sd.index(u)
    ret5=sox[ui][1]/sox[ui-5][1]-1 if ui>=5 else None
    feat[d]={'shock':shock,'sox5':ret5}

def run(shock_max,sox5_max,hold,topN,resid_max):
    cap=START;pk=cap;dd=0;events=[];busy=''
    for d in sorted(by_d):
        if busy and d<=busy:continue
        ft=feat.get(d)
        if not ft or ft['shock']>shock_max or ft['sox5'] is None or ft['sox5']>sox5_max:continue
        cand=[]
        for r in by_d[d]:
            b=beta.get((d,r['ticker']));pc=prevclose.get((d,r['ticker']))
            if b is None or not pc:continue
            gap=r['open']/pc-1;exp=b*ft['shock'];res=gap-exp
            cand.append((b,res,r))
        cand=sorted(cand,key=lambda x:x[0],reverse=True)
        if resid_max is not None:
            cand=[x for x in cand if x[1]<=resid_max]
        cand=cand[:topN]
        rr=[];ex=[]
        for b,res,r in cand:
            i=idx[r['ticker']][d];j=i+hold-1
            if j>=len(by_t[r['ticker']]):continue
            er=by_t[r['ticker']][j];rr.append(er['close']/r['open']-1-COST);ex.append(er['date'])
        if not rr:continue
        pr=sum(rr)/len(rr);cap*=1+pr;pk=max(pk,cap);dd=min(dd,cap/pk-1);busy=max(ex)
        events.append((d,pr,cap,ft['shock'],ft['sox5'],len(rr)))
    return {'final':cap,'ret':cap/START-1,'mdd':dd,'n':len(events),'wins':sum(r[1]>0 for r in events),'events':events}

shock_grid=[-.02,-.025,-.03,-.035,-.04,-.045]
sox5_grid=[.01,0,-.01,-.02,-.03,-.04,-.05]
hold_grid=[2,3,4,5]
top_grid=[3,5,7,10]
resid_grid=[None,.04,.03,.025,.02]
rows=[]
for sh in shock_grid:
 for s5 in sox5_grid:
  for h in hold_grid:
   for n in top_grid:
    for rg in resid_grid:
      r=run(sh,s5,h,n,rg)
      rows.append({'shock_max':sh,'sox5_max':s5,'hold':h,'topN':n,'resid_max':'NONE' if rg is None else rg,'final':r['final'],'ret':r['ret'],'mdd':r['mdd'],'events':r['n'],'wins':r['wins'],'win_rate':r['wins']/r['n'] if r['n'] else 0})
rows.sort(key=lambda x:x['final'],reverse=True)
# neighborhood around global best: same residual mode, +/- adjacent values where available
best=rows[0]
def neigh_vals(grid,v):
    i=grid.index(v);return grid[max(0,i-1):min(len(grid),i+2)]
rg_best=None if best['resid_max']=='NONE' else float(best['resid_max'])
zone=[]
for sh in neigh_vals(shock_grid,best['shock_max']):
 for s5 in neigh_vals(sox5_grid,best['sox5_max']):
  for h in neigh_vals(hold_grid,best['hold']):
   for n in neigh_vals(top_grid,best['topN']):
    r=run(sh,s5,h,n,rg_best)
    zone.append({'shock_max':sh,'sox5_max':s5,'hold':h,'topN':n,'resid_max':best['resid_max'],'final':r['final'],'ret':r['ret'],'mdd':r['mdd'],'events':r['n'],'wins':r['wins'],'win_rate':r['wins']/r['n'] if r['n'] else 0})
zone.sort(key=lambda x:x['final'],reverse=True)
# detailed best event path + contribution concentration
rb=run(best['shock_max'],best['sox5_max'],best['hold'],best['topN'],rg_best)
rets=[e[1] for e in rb['events']]
prod=lambda xs: math.prod(1+x for x in xs)-1 if xs else 0
contrib={'base_return':rb['ret'],'remove_best1':prod(sorted(rets,reverse=True)[1:]) if len(rets)>1 else None,'remove_best3':prod(sorted(rets,reverse=True)[3:]) if len(rets)>3 else None}
summary={'objective':'maximize 2026 final capital only; MDD/win rate diagnostics','tested':len(rows),'best20':rows[:20],'best':best,'best_event_path':[{'entry':e[0],'ret':e[1],'capital':e[2],'sox_shock':e[3],'sox5':e[4],'n_stocks':e[5]} for e in rb['events']],'best_concentration_stress':contrib,'best_neighborhood_top20':zone[:20],'best_neighborhood_stats':{'count':len(zone),'positive':sum(z['ret']>0 for z in zone),'above50pct':sum(z['ret']>.5 for z in zone),'median_final':sorted(z['final'] for z in zone)[len(zone)//2] if zone else None,'min_final':min(z['final'] for z in zone) if zone else None,'max_final':max(z['final'] for z in zone) if zone else None}}
(OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
with (OUT/'grid.csv').open('w',newline='',encoding='utf-8') as f0:
    w=csv.DictWriter(f0,fieldnames=list(rows[0].keys()));w.writeheader();w.writerows(rows)
print(json.dumps(summary,ensure_ascii=False,indent=2))
