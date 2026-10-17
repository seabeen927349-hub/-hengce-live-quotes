#!/usr/bin/env python3
import csv,json
from collections import defaultdict
from pathlib import Path
ROOT=Path('research/q017_sox_tw_electronics');ARC=ROOT/'archive_2026';OUT=ROOT/'gate_extension_2026';OUT.mkdir(parents=True,exist_ok=True)
START=2_000_000.;COST=.004

def f(x):
    try:return float(str(x).replace(',','').strip())
    except:return None
sox=[]
for r in csv.DictReader((ARC/'sox_2026.csv').open(encoding='utf-8')):
    c=f(r['close']);
    if c is not None:sox.append((r['date'],c))
sox.sort();sd=[d for d,_ in sox];sret={sox[i][0]:sox[i][1]/sox[i-1][1]-1 for i in range(1,len(sox))}
def prevus(d):
    z=[u for u in sd if u<d];return z[-1] if z else None
by_t=defaultdict(list);by_d=defaultdict(list)
for r in csv.DictReader((ARC/'twse_electronics_membership_2026.csv').open(encoding='utf-8')):
    o=f(r['open']);c=f(r['close'])
    if o is None or c is None:continue
    x={'date':r['date'],'ticker':r['ticker'],'open':o,'close':c};by_t[r['ticker']].append(x);by_d[r['date']].append(x)
for t in by_t:by_t[t].sort(key=lambda x:x['date'])
idx={t:{r['date']:i for i,r in enumerate(rs)} for t,rs in by_t.items()};aligned={d:sret.get(prevus(d)) for d in by_d}
beta={};prevc={}
for t,rs in by_t.items():
    obs=[];pc=None
    for r in rs:
        prevc[(r['date'],t)]=pc
        if pc and aligned.get(r['date']) is not None:
            tr=r['close']/pc-1
            if len(obs)>=30:
                z=obs[-60:];mx=sum(a for a,b in z)/len(z);my=sum(b for a,b in z)/len(z);vv=sum((a-mx)**2 for a,b in z)
                beta[(r['date'],t)]=sum((a-mx)*(b-my) for a,b in z)/vv if vv else 0
            obs.append((aligned[r['date']],tr))
        pc=r['close']
feat={}
for d in sorted(by_d):
    u=prevus(d);sh=aligned.get(d)
    if not u or sh is None:continue
    ui=sd.index(u);r5=sox[ui][1]/sox[ui-5][1]-1 if ui>=5 else None
    feat[d]={'shock':sh,'sox5':r5}

def run(sh,s5,resmax,hold,k):
    cap=START;busy='';ev=[]
    for d in sorted(by_d):
        if busy and d<=busy:continue
        ft=feat.get(d)
        if not ft or ft['shock']>sh or ft['sox5'] is None or ft['sox5']>s5:continue
        cs=[]
        for r in by_d[d]:
            b=beta.get((d,r['ticker']));pc=prevc.get((d,r['ticker']))
            if b is None or not pc:continue
            res=r['open']/pc-1-b*ft['shock']
            if res<=resmax:
                sc=b*(1+k*max(-res,0));cs.append((sc,b,res,r))
        if not cs:continue
        sc,b,res,r=max(cs,key=lambda x:x[0]);i=idx[r['ticker']][d];j=i+hold-1
        if j>=len(by_t[r['ticker']]):continue
        ex=by_t[r['ticker']][j];ret=ex['close']/r['open']-1-COST;cap*=1+ret;busy=ex['date']
        ev.append({'entry':d,'exit':ex['date'],'ticker':r['ticker'],'ret':ret,'capital':cap,'score':sc,'beta':b,'resid':res,'shock':ft['shock'],'sox5':ft['sox5']})
    return cap,ev
rows=[];details={}
for sh in (0,-.005,-.0075,-.01,-.0125,-.015,-.02):
 for s5 in (.01,0,-.01,-.015,-.02,-.025,-.03):
  for res in (.035,.04,.045,.05):
   for hold in (9,10,11):
    for k in (15,20,25,30,35):
      cap,ev=run(sh,s5,res,hold,k);key=(sh,s5,res,hold,k);details[key]=ev
      rows.append({'shock_max':sh,'sox5_max':s5,'resid_max':res,'hold':hold,'overshoot_k':k,'final':cap,'ret':cap/START-1,'n':len(ev),'wins':sum(e['ret']>0 for e in ev)})
rows.sort(key=lambda x:x['final'],reverse=True);best=rows[0];key=(best['shock_max'],best['sox5_max'],best['resid_max'],best['hold'],best['overshoot_k']);bf=best['final']
summary={'objective':'extend SOX shock and 5D gate until profit peak is not a loose-boundary artifact','tested':len(rows),'best':best,'top30':rows[:30],'surface_stats':{'within_95pct_best':sum(r['final']>=.95*bf for r in rows),'within_90pct_best':sum(r['final']>=.9*bf for r in rows),'positive':sum(r['final']>START for r in rows)},'best_events':details[key]}
(OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
with (OUT/'grid.csv').open('w',newline='',encoding='utf-8') as f0:
 w=csv.DictWriter(f0,fieldnames=list(rows[0].keys()));w.writeheader();w.writerows(rows)
print(json.dumps(summary,ensure_ascii=False,indent=2))
